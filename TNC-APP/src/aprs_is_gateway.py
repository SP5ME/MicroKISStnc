"""
APRS-IS Gateway - odbiera pakiety z internetu i wstrzykuje je do lokalnego KISS serwera
Cel: debugowanie aplikacji bez fizycznego radia
"""

import socket
import threading
import logging
import time
from typing import Callable, Optional

from .kiss_builder import KISSBuilder

logger = logging.getLogger(__name__)


class APRSISGateway:
    """Gateway łączący APRS-IS z lokalnym KISS serwerem"""
    
    def __init__(self, local_kiss_host: str = "127.0.0.1", local_kiss_port: int = 8001):
        self.local_kiss_host = local_kiss_host
        self.local_kiss_port = local_kiss_port
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.aprs_is_socket: Optional[socket.socket] = None
        self.kiss_client_socket: Optional[socket.socket] = None  # Dla przyszłych TX
        self.on_packet_injected: Optional[Callable] = None
        self.on_frame_to_broadcast: Optional[Callable] = None  # Callback do KISS broadcast
        
    def start(self, server: str = "poland.aprs2.net", port: int = 14580, 
              callsign: str = "GUEST", passcode: str = "-1",
              filter_cmd: str = "filter r/52.23/21.01/50") -> bool:
        """Uruchom gateway"""
        if self.running:
            logger.warning("APRS-IS Gateway already running")
            return False
        
        self.running = True
        self.aprs_is_server = server
        self.aprs_is_port = port
        self.callsign = callsign
        self.passcode = passcode
        self.filter_cmd = filter_cmd
        
        self.thread = threading.Thread(target=self._run, daemon=True, name="APRS-IS-Gateway")
        self.thread.start()
        return True
    
    def stop(self):
        """Zatrzymaj gateway"""
        self.running = False
        if self.aprs_is_socket:
            try:
                self.aprs_is_socket.close()
            except:
                pass
        if self.kiss_client_socket:
            try:
                self.kiss_client_socket.close()
            except:
                pass
    
    def _run(self):
        """Główna pętla gatewaya"""
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                retry_count = 0  # Reset on successful connection
                self._connect_and_listen()
            except Exception as e:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = min(5 * (2 ** (retry_count - 1)), 60)  # Exponential backoff
                    logger.error(f"APRS-IS error (attempt {retry_count}): {e}")
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"APRS-IS: Max retries ({max_retries}) exceeded, giving up")
                    break
    
    def _connect_and_listen(self):
        """Połącz się z APRS-IS i nasłuchuj"""
        logger.info(f"Connecting to APRS-IS: {self.aprs_is_server}:{self.aprs_is_port}")
        
        # Połącz się z APRS-IS
        self.aprs_is_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.aprs_is_socket.settimeout(10)  # 10 sekundowy timeout
        
        try:
            self.aprs_is_socket.connect((self.aprs_is_server, self.aprs_is_port))
            logger.info(f"[OK] APRS-IS: Connected to {self.aprs_is_server}:{self.aprs_is_port}")
            
            # Enable TCP keep-alive
            self.aprs_is_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except socket.timeout:
            logger.error(f"[ERROR] APRS-IS: Connection TIMEOUT ({self.aprs_is_server}:{self.aprs_is_port})")
            logger.error("   -> Firewall/ISP blocking port 14580? Try VPN or proxy")
            raise
        except ConnectionRefusedError:
            logger.error(f"[ERROR] APRS-IS: Connection REFUSED - server down?")
            raise
        except socket.gaierror as e:
            logger.error(f"[ERROR] APRS-IS: DNS resolution failed for {self.aprs_is_server}: {e}")
            raise
        except OSError as e:
            logger.error(f"[ERROR] APRS-IS: Network error: {e}")
            raise
        except Exception as e:
            logger.error(f"[ERROR] APRS-IS: Connection failed: {type(e).__name__}: {e}")
            raise
        
        # Login
        login_str = f"user {self.callsign} pass {self.passcode} vers TNC-APP 0.1.0 {self.filter_cmd}\r\n"
        try:
            self.aprs_is_socket.sendall(login_str.encode('ascii'))
            logger.info(f"[OK] APRS-IS: Sent login with filter: {self.filter_cmd}")
        except Exception as e:
            logger.error(f"❌ APRS-IS: Failed to send login: {e}")
            raise
        
        # Nasłuchuj pakietów
        buffer = ""
        packet_count = 0
        while self.running:
            try:
                data = self.aprs_is_socket.recv(1024).decode('ascii', errors='ignore')
                if not data:
                    logger.warning("APRS-IS connection closed by server")
                    break
                
                buffer += data
                lines = buffer.split('\n')
                
                # Przetwórz wszystkie pełne linie (ostatnia może być niekompletna)
                for line in lines[:-1]:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Pomiń komentarze i puste linie
                        if not line.startswith('user'):  # Pomiń login echo
                            packet_count += 1
                            self._process_tnc2_line(line)
                
                # Zachowaj ostatnią niekompletną linię
                buffer = lines[-1]
                
                if packet_count % 10 == 0 and packet_count > 0:
                    logger.debug(f"APRS-IS: Received {packet_count} packets so far")
                
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error receiving from APRS-IS: {e}")
                break
    
    def _process_tnc2_line(self, tnc2_line: str):
        """Przetwórz linię w formacie TNC2 z APRS-IS"""
        try:
            # TNC2 format: SENDER>RECEIVER,PATH:DATA
            # Przykład: SP5ME-1>APWW11,WIDE1-1,qAS,SP5XA:/150732h5225.50NE02101.21E^270/012/A=001234
            
            # Pomiń komentarze i puste linie
            if not tnc2_line or tnc2_line.startswith('#'):
                return
            
            logger.info(f"[OK] APRS-IS RX: {tnc2_line[:80]}")
            
            # Konwertuj TNC2 na KISS ramkę
            kiss_frame = KISSBuilder.tnc2_to_kiss(tnc2_line)
            if not kiss_frame:
                logger.warning(f"Failed to convert TNC2 to KISS: {tnc2_line[:80]}")
                return
            
            # Wyślij do GUI jako info
            if self.on_packet_injected:
                msg = f"[INET] {tnc2_line[:80]}"
                self.on_packet_injected(msg)
            
            # Wyślij KISS ramkę do broadcast do wszystkich klientów
            if self.on_frame_to_broadcast:
                self.on_frame_to_broadcast(kiss_frame)
        
        except Exception as e:
            logger.error(f"Error processing TNC2 line '{tnc2_line[:80]}': {e}", exc_info=True)
