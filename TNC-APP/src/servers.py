"""
Serwery KISS i AGWPE
"""

import socket
import threading
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class KISSServer:
    """Serwer KISS do odbierania pakietów"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.on_data_received: Optional[Callable[[bytes], None]] = None
        self.on_connected: Optional[Callable[[str], None]] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None
        
        # Przechowuj aktywne połączenia klientów
        self.client_sockets = []
        self.client_lock = threading.Lock()

    def start(self) -> bool:
        """Uruchom serwer KISS"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 1)  # Graceful close
            self.socket.settimeout(1.0)  # 1 second timeout na accept
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            
            self.thread = threading.Thread(target=self._accept_connections, daemon=True, name="KISS-Accept")
            self.thread.start()
            
            logger.info(f"[OK] KISS Server started on {self.host}:{self.port}")
            return True
        except OSError as e:
            if "Address already in use" in str(e) or "48" in str(e):
                logger.error(f"[ERROR] KISS: Port {self.port} already in use! Another instance is running?")
                logger.error(f"   Kill all python.exe or TNC instances and restart")
            else:
                logger.error(f"Failed to start KISS server: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start KISS server: {e}")
            return False

    def _accept_connections(self):
        """Akceptuj połączenia od klientów"""
        logger.info("[KISS] Accepting connections...")
        while self.running:
            try:
                client_socket, client_addr = self.socket.accept()
                logger.info(f"[KISS] Client connected from {client_addr[0]}:{client_addr[1]}")
                
                # Zarejestruj klienta
                with self.client_lock:
                    self.client_sockets.append(client_socket)
                
                if self.on_connected:
                    self.on_connected(f"KISS client connected: {client_addr[0]}:{client_addr[1]}")
                
                # Obsługuj klienta w osobnym wątku
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True,
                    name=f"KISS-Client-{client_addr[0]}:{client_addr[1]}"
                )
                client_thread.start()
            except socket.timeout:
                # Timeout na accept - to normalne, pozwala na graceful shutdown
                continue
            except OSError as e:
                if self.running:
                    logger.error(f"[ERROR] Error accepting connection: {e}")
                break
            except Exception as e:
                if self.running:
                    logger.error(f"[ERROR] Unexpected error accepting connection: {e}")
                break
        
        logger.info("[KISS] Accept thread exiting...")

    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Obsługuj klienta KISS"""
        buffer = b""
        packet_count = 0
        recv_count = 0
        
        try:
            # Ustaw timeout na recv
            client_socket.settimeout(2.0)
            logger.info(f"[KISS] Waiting for data from {client_addr[0]}:{client_addr[1]}...")
            
            while self.running:
                try:
                    data = client_socket.recv(1024)
                    recv_count += 1
                except socket.timeout:
                    # Timeout - sprawdź czy serwer jeszcze działa
                    continue
                
                if not data:
                    logger.info(f"[KISS] Client {client_addr[0]}:{client_addr[1]} closed connection")
                    break
                
                logger.debug(f"[KISS] RX #{recv_count}: {len(data)} bytes from {client_addr[0]}:{client_addr[1]}, hex={data[:50].hex()}")
                
                buffer += data
                
                # Szukaj kompletnych ramek KISS (FEND...FEND)
                while b'\xC0' in buffer:
                    start = buffer.find(b'\xC0')
                    end = buffer.find(b'\xC0', start + 1)
                    
                    if end != -1:
                        frame = buffer[start:end+1]
                        buffer = buffer[end+1:]
                        packet_count += 1
                        
                        logger.info(f"[OK] KISS RX: Frame {packet_count} from {client_addr[0]}:{client_addr[1]}, {len(frame)} bytes")
                        
                        if self.on_data_received:
                            self.on_data_received(frame)
                    else:
                        break
                        
        except Exception as e:
            logger.error(f"[ERROR] Error handling KISS client {client_addr}: {e}")
        finally:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                client_socket.close()
            except:
                pass
            
            if packet_count > 0:
                logger.info(f"[OK] KISS: Client {client_addr[0]}:{client_addr[1]} disconnected - {packet_count} packets received")
            else:
                logger.warning(f"[WARN] KISS: Client {client_addr[0]}:{client_addr[1]} disconnected (no KISS frames, {recv_count} recv calls)")
            
            if self.on_disconnected:
                self.on_disconnected(f"KISS client disconnected: {client_addr[0]}:{client_addr[1]}")
            
            # Usuń z listy klientów
            with self.client_lock:
                try:
                    self.client_sockets.remove(client_socket)
                except ValueError:
                    pass

    def broadcast_to_clients(self, kiss_frame: bytes) -> int:
        """Wyślij KISS ramkę do wszystkich połączonych klientów"""
        if not isinstance(kiss_frame, bytes):
            logger.error(f"broadcast_to_clients: not bytes: {type(kiss_frame)}")
            return 0
        
        count = 0
        with self.client_lock:
            to_remove = []
            for sock in self.client_sockets:
                try:
                    sock.sendall(kiss_frame)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error sending to KISS client: {e}")
                    to_remove.append(sock)
            
            # Usuń zerwane połączenia
            for sock in to_remove:
                try:
                    self.client_sockets.remove(sock)
                except ValueError:
                    pass
        
        if count > 0:
            logger.debug(f"[KISS] Broadcast: sent frame to {count} clients, {len(kiss_frame)} bytes")
        return count

    def stop(self):
        """Zatrzymaj serwer KISS - graceful shutdown"""
        logger.info("[KISS] Stopping KISS Server...")
        self.running = False
        
        # Zamknij wszystkich klientów
        logger.info("[KISS] Closing all client connections...")
        with self.client_lock:
            for sock in list(self.client_sockets):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
            self.client_sockets.clear()
        
        # Zamknij server socket
        if self.socket:
            try:
                logger.info("[KISS] Closing server socket...")
                self.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.socket.close()
            except:
                pass
        
        logger.info("[OK] KISS Server stopped")


class AGWPEServer:
    """Serwer AGWPE do odbierania pakietów"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.on_data_received: Optional[Callable[[bytes], None]] = None
        self.on_connected: Optional[Callable[[str], None]] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None

    def start(self) -> bool:
        """Uruchom serwer AGWPE"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            
            self.thread = threading.Thread(target=self._accept_connections, daemon=True)
            self.thread.start()
            
            logger.info(f"AGWPE Server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start AGWPE server: {e}")
            return False

    def _accept_connections(self):
        """Akceptuj połączenia od klientów"""
        while self.running:
            try:
                client_socket, client_addr = self.socket.accept()
                if self.on_connected:
                    self.on_connected(f"AGWPE client connected: {client_addr[0]}:{client_addr[1]}")
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True
                )
                client_thread.start()
            except OSError:
                if self.running:
                    logger.error("Error accepting connection")
                break

    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Obsługuj klienta AGWPE"""
        buffer = b""
        client_info = {"port": 0, "monitoring_raw": False}
        
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                buffer += data
                
                # AGWPE frame: 36-byte header + variable length data
                while len(buffer) >= 36:
                    # Extract data_len from header (bytes 28-31, little-endian)
                    try:
                        import struct
                        data_len = struct.unpack('<I', buffer[28:32])[0]
                        total_frame_len = 36 + data_len
                        
                        if len(buffer) >= total_frame_len:
                            frame = buffer[:total_frame_len]
                            buffer = buffer[total_frame_len:]
                            
                            # Obsłuż ramkę
                            self._process_agwpe_command(frame, client_socket, client_info)
                        else:
                            # Nie mamy jeszcze całej ramki
                            break
                    except struct.error:
                        # Błąd parsowania, pomiń jeden bajt i spróbuj ponownie
                        buffer = buffer[1:]
                        
        except Exception as e:
            logger.error(f"Error handling AGWPE client {client_addr}: {e}")
        finally:
            client_socket.close()
            if self.on_disconnected:
                self.on_disconnected(f"AGWPE client disconnected: {client_addr[0]}:{client_addr[1]}")

    def _process_agwpe_command(self, frame: bytes, client_socket: socket.socket, client_info: dict):
        """Przetwórz komendę AGWPE i wyślij odpowiedź"""
        try:
            from .parser import AGWPEFrame, create_agwpe_frame
            
            parsed = AGWPEFrame.parse(frame)
            if not parsed:
                return
            
            # Loguj komendę
            logger.debug(f"AGWPE command: '{parsed.datakind}' from {parsed.call_from} (port={parsed.port})")
            
            # Obsługuj poszczególne komendy
            if parsed.datakind == 'R':  # Version request
                self._cmd_version_request(client_socket, client_info)
                
            elif parsed.datakind == 'G':  # Port information
                self._cmd_port_info(client_socket, client_info)
                
            elif parsed.datakind == 'k':  # Start receiving raw frames
                client_info["monitoring_raw"] = True
                logger.info("AGWPE: Monitoring raw frames enabled")
                
            elif parsed.datakind == 'K':  # Transmit raw frame / pass-through
                # Jeśli klient wysyła dane w 'K', dekoduj je
                if parsed.data:
                    logger.debug(f"AGWPE: Raw data received (len={len(parsed.data)})")
                    if self.on_data_received:
                        self.on_data_received(parsed.data)
                        
            elif parsed.datakind == 'H':  # Heard stations - ignore for now
                logger.debug("AGWPE: Heard stations request (not implemented)")
                
            else:
                logger.debug(f"AGWPE: Unhandled command '{parsed.datakind}'")
                
        except Exception as e:
            logger.error(f"Error processing AGWPE command: {e}")

    def _cmd_version_request(self, client_socket: socket.socket, client_info: dict):
        """Odpowiedź na komendę 'R' - Version request"""
        try:
            from .parser import create_agwpe_frame
            
            # Wersja: "TNC-APP v0.1.0"
            version_str = "TNC-APP v0.1.0"
            response = create_agwpe_frame(
                port=0,
                datakind='R',
                call_from='TNC-APP',
                call_to='',
                data=version_str.encode('ascii')
            )
            client_socket.sendall(response)
            logger.info(f"AGWPE: Sent version response ({len(response)} bytes)")
        except Exception as e:
            logger.error(f"Error sending version response: {e}")

    def _cmd_port_info(self, client_socket: socket.socket, client_info: dict):
        """Odpowiedź na komendę 'G' - Port information"""
        try:
            from .parser import create_agwpe_frame
            
            # Zwróć informacje o porcie
            port_info = "1;Port1 TNC-APP\r"  # Format: number of ports; port descriptions
            response = create_agwpe_frame(
                port=0,
                datakind='G',
                call_from='TNC-APP',
                call_to='',
                data=port_info.encode('ascii')
            )
            client_socket.sendall(response)
            logger.info(f"AGWPE: Sent port info ({len(response)} bytes)")
        except Exception as e:
            logger.error(f"Error sending port info: {e}")



    def stop(self):
        """Zatrzymaj serwer AGWPE"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        logger.info("AGWPE Server stopped")

