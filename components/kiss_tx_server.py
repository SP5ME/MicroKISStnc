#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KISS TX Server - Standalone script (FIXED VERSION)
Listens on KISS port (8001), receives frames, encodes HDLC, modulates AFSK, plays audio
Multi-sample-rate support: 44.1kHz, 48kHz, 32kHz, 16kHz (auto-detect)

Usage:
    python kiss_tx_server.py
"""

import sys
import io

# Napraw encode dla Windows console - UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import logging
import socket
import threading
import time
from pathlib import Path
from datetime import datetime

# Add TNC-APP to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hdlc_codec import HDLCEncoder, CRC16CCITT
from afsk_modem import AFSKModulator
from audio_manager import AudioManager

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(filename='kiss_tx_server.log'):
    """Configure detailed logging"""
    log_format = '%(asctime)s.%(msecs)03d [%(levelname)-7s] %(name)-20s | %(message)s'
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(filename),
            logging.StreamHandler()
        ]
    )
    
    # Set specific loggers
    logging.getLogger('kiss_tx_server').setLevel(logging.DEBUG)
    
    return logging.getLogger('kiss_tx_server')


logger = setup_logging()


# ============================================================================
# KISS PROTOCOL FUNCTIONS
# ============================================================================

def unescape_kiss(data: bytes) -> bytes:
    """
    Unescape KISS frame data
    0xDB 0xDC -> 0xC0 (FEND)
    0xDB 0xDD -> 0xDB (FESC)
    """
    result = b''
    i = 0
    while i < len(data):
        if data[i:i+1] == b'\xdb':
            if i + 1 < len(data):
                if data[i+1:i+2] == b'\xdc':
                    result += b'\xc0'
                    i += 2
                elif data[i+1:i+2] == b'\xdd':
                    result += b'\xdb'
                    i += 2
                else:
                    logger.warning(f"[KISS] Invalid escape sequence at offset {i}")
                    result += data[i:i+1]
                    i += 1
            else:
                result += data[i:i+1]
                i += 1
        else:
            result += data[i:i+1]
            i += 1
    return result


def parse_kiss_frame(data: bytes) -> tuple:
    """
    Parse KISS frame
    Format: FEND [CMD] [ESCAPED_DATA] FEND
    
    Returns: (command, unescaped_data, port)
    """
    if len(data) < 2:
        logger.error(f"[KISS] Frame too short: {len(data)} bytes")
        return None, None, None
    
    # Check for frame boundaries
    if data[0] != 0xC0:
        logger.error(f"[KISS] Missing start FEND, got {data[0]:02X}")
        return None, None, None
    
    if data[-1] != 0xC0:
        logger.error(f"[KISS] Missing end FEND, got {data[-1]:02X}")
        return None, None, None
    
    # Extract command and data
    cmd = data[1] & 0x0F
    port = (data[1] >> 4) & 0x0F
    
    # Data is between cmd byte and last FEND
    raw_data = data[2:-1]
    
    # Unescape
    unescaped = unescape_kiss(raw_data)
    
    return cmd, unescaped, port


# ============================================================================
# KISS TX SERVER
# ============================================================================

class KISSTransmitServer:
    """KISS server that receives frames and transmits via audio"""
    
    def __init__(self, host='0.0.0.0', port=8001, audio_device=None):
        self.host = host
        self.port = port
        self.audio_device = audio_device
        
        self.server_socket = None
        self.running = False
        self.accept_thread = None
        
        # Audio components
        self.audio_manager = None
        self.afsk_modem = None
        self.hdlc_encoder = None
        
        # KISS Parameters (RFC 1549 defaults)
        self.tx_delay = 50        # 0x01: units of 10ms (500ms default - PTT warm-up)
        self.tx_tail = 30         # 0x04: units of 10ms (300ms default - transmitter tail)
        self.persistence = 63     # 0x02: 0-255 (0.25 default - transmit probability)
        self.slot_time = 10       # 0x03: units of 10ms (100ms default - slot interval)
        self.full_duplex = 0      # 0x05: 0=half-duplex, 1=full-duplex
        
        # Statistics
        self.frames_received = 0
        self.frames_transmitted = 0
        self.errors = 0
        
        logger.info("[INIT] KISS TX Server initialized")
        logger.info(f"[INIT]   Host: {host}:{port}")
        logger.info(f"[INIT]   Audio device: {audio_device if audio_device else 'auto-detect'}")
    
    def initialize_audio(self) -> bool:
        """Initialize audio components"""
        try:
            logger.info("\n[INIT] Initializing audio system...")
            
            # Initialize audio manager
            self.audio_manager = AudioManager()
            logger.info(f"[OK] Audio manager initialized")
            
            # Try to select Virtual Cable for TX
            self._select_virtual_cable_output()
            
            # Initialize AFSK modulator
            self.afsk_modem = AFSKModulator(sample_rate=AudioManager.SAMPLE_RATE)
            logger.info(f"[OK] AFSK modulator initialized (1200 Hz mark, 2200 Hz space)")
            
            # Initialize HDLC encoder
            self.hdlc_encoder = HDLCEncoder()
            logger.info(f"[OK] HDLC encoder initialized")
            
            return True
        except Exception as e:
            logger.error(f"[ERROR] Audio initialization failed: {e}", exc_info=True)
            return False
    
    def _select_virtual_cable_output(self) -> bool:
        """Try to select VB-Audio Virtual Cable as output device for TX"""
        try:
            devices = self.audio_manager.list_output_devices()
            logger.info(f"[AUDIO] Searching for Virtual Cable device among {len(devices)} output devices...")
            
            # First priority: "CABLE In" (direct input to Virtual Cable)
            for device in devices:
                name_lower = device.name.lower()
                if "cable in" in name_lower and "vb-audio" in name_lower:
                    logger.info(f"[AUDIO] Found CABLE In: Device #{device.index} - {device.name}")
                    if self.audio_manager.set_output_device(device.index):
                        logger.info(f"[AUDIO] TX audio will use: {device.name} (Device #{device.index})")
                        return True
            
            # Fallback: Any Virtual Cable
            for device in devices:
                name_lower = device.name.lower()
                if "virtual cable" in name_lower and "vb-audio" in name_lower:
                    logger.info(f"[AUDIO] Found Virtual Cable: Device #{device.index} - {device.name}")
                    if self.audio_manager.set_output_device(device.index):
                        logger.info(f"[AUDIO] TX audio will use: {device.name} (Device #{device.index})")
                        return True
            
            logger.warning(f"[AUDIO] Virtual Cable not found, using default output device")
            return False
        except Exception as e:
            logger.error(f"[AUDIO] Failed to select Virtual Cable: {e}", exc_info=True)
            return False
    
    def start(self) -> bool:
        """Start KISS server"""
        if not self.initialize_audio():
            return False
        
        try:
            logger.info("\n[INIT] Starting KISS server...")
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)
            
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            logger.info(f"[OK] Server listening on {self.host}:{self.port}")
            
            self.accept_thread = threading.Thread(
                target=self._accept_connections,
                daemon=True,
                name="KISS-Accept"
            )
            self.accept_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to start server: {e}", exc_info=True)
            return False
    
    def _accept_connections(self):
        """Accept incoming KISS connections"""
        logger.info("[KISS] Accepting connections...\n")
        
        while self.running:
            try:
                client_socket, client_addr = self.server_socket.accept()
                logger.info(f"[KISS-ACCEPT] Client connected: {client_addr[0]}:{client_addr[1]}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True,
                    name=f"KISS-Client-{client_addr[0]}"
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"[ERROR] Accept error: {e}")
                break
    
    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Handle individual KISS client"""
        buffer = b''
        client_frames = 0
        
        try:
            client_socket.settimeout(2.0)
            
            while self.running:
                try:
                    data = client_socket.recv(1024)
                except socket.timeout:
                    continue
                
                if not data:
                    logger.info(f"[KISS-CLIENT] {client_addr[0]} closed connection")
                    break
                
                logger.debug(f"[KISS-RX] {len(data)} bytes from {client_addr[0]}")
                buffer += data
                
                # Process complete KISS frames
                while b'\xC0' in buffer:
                    start = buffer.find(b'\xC0')
                    end = buffer.find(b'\xC0', start + 1)
                    
                    if end != -1:
                        frame = buffer[start:end+1]
                        buffer = buffer[end+1:]
                        
                        client_frames += 1
                        self.frames_received += 1
                        
                        logger.info(f"[KISS-FRAME-RX] Frame #{self.frames_received} from {client_addr[0]}")
                        logger.info(f"[KISS-SIZE] {len(frame)} bytes")
                        logger.info(f"[KISS-HEX] {frame[:50].hex()}")
                        
                        # Process frame
                        self._process_kiss_frame(frame)
                    else:
                        break
        
        except Exception as e:
            logger.error(f"[ERROR] Client handler error: {e}")
            self.errors += 1
        finally:
            try:
                client_socket.close()
            except:
                pass
            
            logger.info(f"[KISS-CLIENT] {client_addr[0]} disconnected ({client_frames} frames)")
    
    def _process_kiss_frame(self, frame: bytes):
        """Process received KISS frame"""
        try:
            # Parse KISS frame
            cmd, data, port = parse_kiss_frame(frame)
            
            if cmd is None:
                logger.warning("[KISS-PARSE] Failed to parse KISS frame")
                self.errors += 1
                return
            
            logger.info(f"[KISS-CMD] Command: {cmd} (PORT: {port})")
            logger.info(f"[KISS-DATA] Unescaped data: {len(data)} bytes")
            
            if cmd == 0x00:  # Data frame
                self._transmit_ax25_frame(data)
            elif cmd == 0x01:  # TX Delay
                self.tx_delay = data[0] if len(data) > 0 else 50
                logger.info(f"[KISS-CONFIG] TX Delay: {self.tx_delay * 10}ms")
            elif cmd == 0x02:  # Persistence (p)
                self.persistence = data[0] if len(data) > 0 else 63
                logger.info(f"[KISS-CONFIG] Persistence P: {self.persistence} ({self.persistence/256:.3f})")
            elif cmd == 0x03:  # Slot time
                self.slot_time = data[0] if len(data) > 0 else 10
                logger.info(f"[KISS-CONFIG] Slot time: {self.slot_time * 10}ms")
            elif cmd == 0x04:  # TX Tail
                self.tx_tail = data[0] if len(data) > 0 else 30
                logger.info(f"[KISS-CONFIG] TX Tail: {self.tx_tail * 10}ms")
            elif cmd == 0x05:  # Full duplex
                self.full_duplex = data[0] if len(data) > 0 else 0
                logger.info(f"[KISS-CONFIG] Full duplex: {'YES' if self.full_duplex else 'NO'}")
            else:
                logger.warning(f"[KISS] Unknown command: {cmd}")
        
        except Exception as e:
            logger.error(f"[ERROR] Processing KISS frame: {e}", exc_info=True)
            self.errors += 1
    
    def _transmit_ax25_frame(self, ax25_data: bytes):
        """Transmit AX.25 frame via audio"""
        try:
            logger.info(f"\n[TX-START] ============================================")
            logger.info(f"[TX-AX25] Received AX.25 frame: {len(ax25_data)} bytes")
            logger.info(f"[TX-HEX] {ax25_data[:60].hex()}")
            
            # Validate AX.25 frame (basic)
            if len(ax25_data) < 7:
                logger.error(f"[TX-ERROR] Frame too short: {len(ax25_data)} bytes")
                self.errors += 1
                return
            
            # ===== STEP 0: TX DELAY (PTT warm-up) =====
            tx_delay_sec = self.tx_delay * 0.01  # Convert 10ms units to seconds
            logger.info(f"[TX-DELAY] Waiting {tx_delay_sec*1000:.0f}ms before transmission...")
            time.sleep(tx_delay_sec)
            
            # ===== STEP 0.5: START AUDIO STREAM FIRST =====
            # CRITICAL: Must start stream BEFORE modulation to get actual sample rate!
            logger.info(f"[TX-AUDIO-INIT] Starting output stream...")
            if not self.audio_manager.start_output_stream():
                logger.error(f"[TX-ERROR] Failed to start output stream")
                self.errors += 1
                return
            
            # Get ACTUAL sample rate from audio device (may differ from 44100!)
            actual_sr = self.audio_manager.get_output_sample_rate()
            logger.info(f"[TX-AUDIO-SR] Actual device sample rate: {actual_sr} Hz")
            logger.info(f"[TX-AUDIO-SR] AFSK modulator current SR: {self.afsk_modem.sample_rate} Hz")
            
            # Calculate offset if any
            sr_diff = actual_sr - self.afsk_modem.sample_rate
            if sr_diff != 0:
                logger.warning(f"[TX-SR-OFFSET] ⚠️  Sample rate offset detected: {sr_diff:+d} Hz")
            
            # Re-initialize AFSK modulator with CORRECT sample rate BEFORE modulation
            if actual_sr != self.afsk_modem.sample_rate:
                logger.warning(f"[TX-SR-MISMATCH] Device SR={actual_sr} Hz, AFSK SR={self.afsk_modem.sample_rate} Hz - RE-INITIALIZING")
                self.afsk_modem = AFSKModulator(sample_rate=actual_sr)
                logger.info(f"[TX-SR-CORRECTED] AFSK re-initialized to {actual_sr} Hz")
                logger.info(f"[TX-AFSK-DEBUG] Mark phase_inc: {self.afsk_modem.phase_inc_mark:.8f} rad/sample")
                logger.info(f"[TX-AFSK-DEBUG] Space phase_inc: {self.afsk_modem.phase_inc_space:.8f} rad/sample")
            
            # ===== STEP 1: HDLC Encoding =====
            logger.info(f"[TX-HDLC] Encoding to HDLC bitstream...")
            
            bits = self.hdlc_encoder.encode_frame(ax25_data)
            logger.info(f"[TX-HDLC-OK] Generated {len(bits)} raw bits (NRZI encoding in AFSK)")
            logger.info(f"[TX-HDLC-INFO] Bits layout: [FLAG] [DATA] [CRC] [FLAG] - raw AX.25 bits with bit stuffing")
            
            # ===== STEP 1.5: Add Preamble (rozbiegówka) - FLAG bytes as raw bits =====
            # Preamble is series of FLAG bytes (0x7E) sent as raw bits
            # NRZI encoding happens in AFSK modulator
            # Standard: ~100ms at 1200 baud = ~120 bits = 15 FLAG bytes * 8 bits
            preamble_bits = self.hdlc_encoder.generate_preamble(num_flags=15)
            logger.info(f"[TX-PREAMBLE] Generated {len(preamble_bits)} raw preamble bits from 15 FLAG bytes (NRZI in AFSK)")
            full_bits = preamble_bits + bits
            logger.info(f"[TX-TOTAL-BITS] Preamble + Frame = {len(preamble_bits)} + {len(bits)} = {len(full_bits)} bits")
            
            # ===== STEP 2: AFSK Modulation WITH CORRECT SAMPLE RATE =====
            logger.info(f"[TX-AFSK] Modulating to AFSK with SR={self.afsk_modem.sample_rate}Hz...")
            
            samples = self.afsk_modem.modulate_continuous(full_bits)
            logger.info(f"[TX-AFSK-OK] Generated {len(samples)} audio samples")
            logger.info(f"[TX-AFSK-INFO] Duration: {len(samples) / self.afsk_modem.sample_rate * 1000:.1f} ms")
            logger.info(f"[TX-AFSK-FREQ] Mark: 1200 Hz, Space: 2200 Hz, Baud: 1200 @ {self.afsk_modem.sample_rate} Hz")
            
            # ===== STEP 3: Audio Output =====
            logger.info(f"[TX-AUDIO] Playing audio...")
            
            try:
                # Convert float32 samples [-1, 1] to int16 bytes
                import numpy as np
                int16_samples = (samples * 32767).astype(np.int16)
                audio_bytes = int16_samples.tobytes()
                
                # Write audio to stream
                self.audio_manager.write_audio(audio_bytes)
                logger.info(f"[TX-AUDIO-OK] Audio playback started")
                
                # Wait for audio to finish (use actual SR for duration calculation)
                duration_ms = len(samples) / actual_sr * 1000
                time.sleep(duration_ms / 1000 + 0.05)  # +50ms buffer
                
                logger.info(f"[TX-AUDIO] Audio transmission complete")
                
                # ===== STEP 4: TX TAIL (transmitter tail - after transmission) =====
                tx_tail_sec = self.tx_tail * 0.01  # Convert 10ms units to seconds
                logger.info(f"[TX-TAIL] Holding TX open for {tx_tail_sec*1000:.0f}ms (tx tail)...")
                time.sleep(tx_tail_sec)
                
                self.frames_transmitted += 1
                logger.info(f"[TX-COMPLETE] Frame transmitted successfully")
                logger.info(f"[TX-STATS] Total transmitted: {self.frames_transmitted}")
                logger.info(f"[TX-PARAMS] TX Delay: {self.tx_delay*10}ms | TX Tail: {self.tx_tail*10}ms | P: {self.persistence} | Slot: {self.slot_time*10}ms")
                logger.info(f"[TX-END] ============================================\n")
            
            except Exception as e:
                logger.error(f"[ERROR] Audio output failed: {e}", exc_info=True)
                self.errors += 1
            finally:
                # Stop output stream
                self.audio_manager.stop_output_stream()
        
        except Exception as e:
            logger.error(f"[ERROR] TX failed: {e}", exc_info=True)
            self.errors += 1
    
    def print_stats(self):
        """Print server statistics"""
        logger.info(f"\n[STATS] KISS TX SERVER STATISTICS")
        logger.info(f"[STATS]   Frames received: {self.frames_received}")
        logger.info(f"[STATS]   Frames transmitted: {self.frames_transmitted}")
        logger.info(f"[STATS]   Errors: {self.errors}")
        logger.info(f"[STATS]   Success rate: {self.frames_transmitted}/{self.frames_received} "
                   f"({100*self.frames_transmitted/max(1,self.frames_received):.1f}%)")
        logger.info(f"")
    
    def stop(self):
        """Stop server gracefully"""
        logger.info("\n[SHUTDOWN] Stopping KISS TX Server...")
        self.running = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Stop audio
        if self.audio_manager:
            try:
                self.audio_manager.stop()
            except:
                pass
        
        self.print_stats()
        logger.info("[OK] KISS TX Server stopped")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    logger.info("\n")
    logger.info("==========================================")
    logger.info("KISS TX SERVER - KISS to AFSK Audio")
    logger.info("")
    logger.info("  Listens on KISS port (8001)")
    logger.info("  Receives AX.25 frames")
    logger.info("  Encodes to HDLC")
    logger.info("  Modulates to AFSK (Bell 202)")
    logger.info("  Plays on speaker")
    logger.info("==========================================\n")
    
    server = KISSTransmitServer(host='0.0.0.0', port=8001, audio_device=None)
    
    if not server.start():
        logger.error("[ERROR] Failed to start server")
        sys.exit(1)
    
    try:
        logger.info("[INFO] Server running. Press Ctrl+C to stop.\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n[INFO] Keyboard interrupt detected")
    finally:
        server.stop()
        logger.info("[EXIT] Goodbye!")


if __name__ == "__main__":
    main()
