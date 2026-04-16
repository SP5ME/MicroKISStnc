#!/usr/bin/env python3
"""
TNC-APP Headless Mode: KISS Server + TX Pipeline (no GUI)
For testing audio transmission
"""

import threading
import logging
import socket
import time
import signal
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

from audio_manager import AudioManager
from tx_pipeline import TXPipeline

class KISSServer:
    """Simple KISS server for testing"""
    
    def __init__(self, host="127.0.0.1", port=8001, tx_pipeline=None):
        self.host = host
        self.port = port
        self.tx_pipeline = tx_pipeline
        self.running = False
        self.server_socket = None
        self.thread = None
        
    def start(self):
        """Start server"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="KISSServer")
        self.thread.start()
    
    def _run(self):
        """Server loop"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"KISS server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, client_addr = self.server_socket.accept()
                    logger.info(f"Client connected: {client_addr}")
                    
                    # Handle client
                    try:
                        while self.running:
                            data = client_socket.recv(1024)
                            if not data:
                                break
                            logger.info(f"RX: {len(data)} bytes from {client_addr}")
                            if self.tx_pipeline:
                                self.tx_pipeline.send_kiss_frame(data)
                    finally:
                        client_socket.close()
                        logger.info(f"Client disconnected: {client_addr}")
                        
                except socket.timeout:
                    pass
                except Exception as e:
                    if self.running:
                        logger.error(f"Error: {e}")
                    
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("KISS server stopped")

def main():
    logger.info("=== TNC-APP Headless Mode ===")
    
    try:
        # Initialize audio
        logger.info("Initializing audio manager...")
        audio_mgr = AudioManager()
        
        logger.info("Starting output stream...")
        if not audio_mgr.start_output_stream():
            logger.error("Failed to start output stream")
            return
        
        # Initialize TX pipeline
        logger.info("Initializing TX pipeline...")
        tx_pipeline = TXPipeline(audio_mgr)
        tx_pipeline.start()
        
        # Start KISS server (listen on all interfaces)
        logger.info("Starting KISS server...")
        kiss_server = KISSServer(host="0.0.0.0", port=8001, tx_pipeline=tx_pipeline)
        kiss_server.start()
        
        logger.info("=== All systems ready ===")
        logger.info("Ready to receive KISS frames on 127.0.0.1:8001")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if 'audio_mgr' in locals():
            audio_mgr.stop_all()
        logger.info("Shutdown complete")

if __name__ == "__main__":
    main()
