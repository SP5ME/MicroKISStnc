#!/usr/bin/env python3
"""
KISS Server for MicroKISStnc Application
Listens on port 8001 for KISS protocol frames
Integrates with app callbacks for TX/RX
"""

import socket
import threading
import logging
import ipaddress
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class KISSServerApp:
    """KISS protocol server for app integration"""
    
    KISS_FEND = 0xC0
    KISS_FESC = 0xDB
    KISS_TFEND = 0xDC
    KISS_TFESC = 0xDD
    ALLOW_ALL_TOKEN = "0.0.0.0"
    LOCAL_ALWAYS_ALLOWED = {"127.0.0.1", "::1"}
    
    def __init__(
        self,
        port: int = 8001,
        on_frame_received: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        allowed_ips: Optional[set] = None,
        max_clients: int = 4,
        max_buffer_bytes: int = 65536,
        max_payload_bytes: int = 330,
    ):
        """
        Initialize KISS server
        
        Args:
            port: Listen port (default 8001)
            on_frame_received: Callback function(frame_data, src_addr) when frame received
            on_error: Callback function(error_message) on initialization error
        """
        self.port = port
        self.on_frame_received = on_frame_received
        self.on_error = on_error
        self.server_socket = None
        self.is_running = False
        self.thread = None
        self.clients = []
        self.clients_lock = threading.Lock()
        self.allowed_ips = set(allowed_ips or [])
        self.max_clients = max(1, int(max_clients))
        self.max_buffer_bytes = max(1024, int(max_buffer_bytes))
        self.max_payload_bytes = max(32, int(max_payload_bytes))
        
        logger.info(f"[KISS-SERVER] Initialized on port {port}")
    
    def start(self):
        """Start KISS server in background thread"""
        if self.is_running:
            logger.warning("[KISS-SERVER] Already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()
        logger.info("[KISS-SERVER] Started")
    
    def stop(self):
        """Stop KISS server"""
        self.is_running = False
        
        # Close all client connections
        with self.clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        logger.info("[KISS-SERVER] Stopped")
    
    def _server_loop(self):
        """Main server loop"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Do NOT set SO_REUSEADDR - we want to prevent port reuse
            # This ensures only one instance can use port 8001
            
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            logger.info(f"[KISS-SERVER] Listening on 0.0.0.0:{self.port}")
            
            while self.is_running:
                try:
                    client, addr = self.server_socket.accept()
                    client_ip = addr[0]
                    if self.allowed_ips and not self._is_ip_allowed(client_ip):
                        logger.warning(f"[KISS-SERVER] Rejected client from {client_ip} (not in allowlist)")
                        client.close()
                        continue

                    with self.clients_lock:
                        if len(self.clients) >= self.max_clients:
                            logger.warning(f"[KISS-SERVER] Rejected client from {client_ip} (max_clients={self.max_clients})")
                            client.close()
                            continue
                        self.clients.append(client)

                    logger.info(f"[KISS-SERVER] Client connected from {addr}")
                    
                    # Handle client in thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        logger.warning(f"[KISS-SERVER] Accept error: {e}")
        
        except OSError as e:
            error_msg = f"KISS Server Error on port {self.port}: {str(e)}"
            if "Address already in use" in str(e) or "Only one usage" in str(e):
                error_msg = f"⚠️ PORT {self.port} ALREADY IN USE!\n\nAnother application is using port {self.port}.\nPlease close it and restart MicroKISStnc."
            
            logger.error(f"[KISS-SERVER] {error_msg}")
            if self.on_error:
                try:
                    self.on_error(error_msg)
                except Exception as callback_err:
                    logger.warning(f"[KISS-SERVER] Error callback failed: {callback_err}")
        except Exception as e:
            error_msg = f"KISS Server Error: {str(e)}"
            logger.error(f"[KISS-SERVER] {error_msg}")
            if self.on_error:
                try:
                    self.on_error(error_msg)
                except Exception as callback_err:
                    logger.warning(f"[KISS-SERVER] Error callback failed: {callback_err}")
        finally:
            self.is_running = False

    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if remote IP is allowed by current allowlist."""
        if ip in self.LOCAL_ALWAYS_ALLOWED:
            return True
        if not self.allowed_ips:
            return True
        if self.ALLOW_ALL_TOKEN in self.allowed_ips:
            return True
        if ip in self.allowed_ips:
            return True

        # Support CIDR networks (e.g. 192.168.1.0/24) in allowlist.
        try:
            remote_ip = ipaddress.ip_address(ip)
        except ValueError:
            return False

        for entry in self.allowed_ips:
            if "/" not in entry:
                continue
            try:
                net = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                continue
            if remote_ip in net:
                return True
        return False
    
    def _handle_client(self, client: socket.socket, addr):
        """Handle individual client connection"""
        buffer = bytearray()
        
        try:
            while self.is_running:
                data = client.recv(1024)
                if not data:
                    break
                
                buffer.extend(data)
                if len(buffer) > self.max_buffer_bytes:
                    logger.warning(f"[KISS-SERVER] Buffer overflow from {addr}, dropping client")
                    break
                
                # Parse KISS frames
                while self.KISS_FEND in buffer:
                    idx = buffer.find(self.KISS_FEND)
                    
                    # Find end frame marker
                    next_idx = buffer.find(self.KISS_FEND, idx + 1)
                    if next_idx == -1:
                        break
                    
                    # Extract frame between markers
                    frame_data = buffer[idx+1:next_idx]
                    buffer = buffer[next_idx:]
                    
                    # Unescape KISS frame
                    unescaped = self._unescape_kiss(frame_data)
                    
                    if len(unescaped) > 0:
                        # First byte is command, rest is payload
                        cmd = unescaped[0]
                        payload = unescaped[1:]
                        
                        # Command 0x00 = data frame
                        if cmd == 0x00:
                            if len(payload) > self.max_payload_bytes:
                                logger.warning(
                                    f"[KISS-SERVER] Payload too large from {addr}: {len(payload)} > {self.max_payload_bytes}"
                                )
                                continue
                            logger.info(f"[KISS-SERVER] RX frame from {addr}: {len(payload)} bytes")
                            
                            # Callback
                            if self.on_frame_received:
                                try:
                                    self.on_frame_received(payload, addr[0])
                                except Exception as e:
                                    logger.warning(f"[KISS-SERVER] Callback error: {e}")
        
        except Exception as e:
            logger.warning(f"[KISS-SERVER] Client error ({addr}): {e}")
        finally:
            try:
                client.close()
                with self.clients_lock:
                    if client in self.clients:
                        self.clients.remove(client)
                logger.info(f"[KISS-SERVER] Client disconnected: {addr}")
            except:
                pass
    
    def send_frame(self, frame_data: bytes):
        """Send frame to all connected clients"""
        escaped = self._escape_kiss(frame_data)
        kiss_frame = bytes([self.KISS_FEND]) + escaped + bytes([self.KISS_FEND])
        
        with self.clients_lock:
            for client in self.clients[:]:
                try:
                    client.send(kiss_frame)
                except Exception as e:
                    logger.warning(f"[KISS-SERVER] Send error: {e}")
                    self.clients.remove(client)
    
    def _escape_kiss(self, data: bytes) -> bytes:
        """Escape KISS special bytes"""
        result = bytearray([0x00])  # Command byte (data frame)
        
        for byte in data:
            if byte == self.KISS_FEND:
                result.extend([self.KISS_FESC, self.KISS_TFEND])
            elif byte == self.KISS_FESC:
                result.extend([self.KISS_FESC, self.KISS_TFESC])
            else:
                result.append(byte)
        
        return bytes(result)
    
    def _unescape_kiss(self, data: bytes) -> bytes:
        """Unescape KISS special bytes"""
        result = bytearray()
        i = 0
        
        while i < len(data):
            if data[i] == self.KISS_FESC and i + 1 < len(data):
                next_byte = data[i + 1]
                if next_byte == self.KISS_TFEND:
                    result.append(self.KISS_FEND)
                    i += 2
                elif next_byte == self.KISS_TFESC:
                    result.append(self.KISS_FESC)
                    i += 2
                else:
                    result.append(data[i])
                    i += 1
            else:
                result.append(data[i])
                i += 1
        
        return bytes(result)
