#!/usr/bin/env python3
"""
TX Pipeline: Converts KISS frames to Bell 202 AFSK audio
Flow: KISS frame → Parse → HDLC encode → AFSK modulate → Audio output
"""

import threading
import queue
import logging
import time
from audio_manager import AudioManager
from hdlc_codec import HDLCCodec
from afsk_modem import AFSKModem

logger = logging.getLogger(__name__)


class TXPipeline(threading.Thread):
    """TX Processing Pipeline - Daemon thread"""
    
    def __init__(self, audio_manager):
        super().__init__(daemon=True, name="TXPipeline")
        self.audio_manager = audio_manager
        self.running = False
        self.frame_queue = queue.Queue()
        
        # Codecs
        self.hdlc = HDLCCodec()
        self.afsk = AFSKModem()
        
        # Callbacks
        self.on_tx_start = None
        self.on_tx_complete = None
        self.on_tx_error = None
        
    def run(self):
        """Main TX loop"""
        self.running = True
        logger.info("[TX] Pipeline started")
        
        while self.running:
            try:
                # Wait for frame (timeout to allow checking running flag)
                try:
                    kiss_frame = self.frame_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Process frame
                self._process_kiss_frame(kiss_frame)
                
            except Exception as e:
                logger.error(f"[TX] Pipeline error: {e}")
                if self.on_tx_error:
                    self.on_tx_error(str(e))
    
    def queue_frame(self, kiss_frame):
        """Add frame to TX queue"""
        self.frame_queue.put(kiss_frame)
    
    def _process_kiss_frame(self, kiss_frame):
        """Process single KISS frame: Parse → HDLC → AFSK → Audio"""
        try:
            # Parse KISS frame
            data = self._parse_kiss_frame(kiss_frame)
            if data is None:
                logger.warning("[TX] Invalid KISS frame")
                return
            
            logger.debug(f"[TX] Parsed KISS frame: {len(data)} data bytes")
            
            # Signal TX start
            if self.on_tx_start:
                self.on_tx_start()
            
            # Encode with HDLC
            hdlc_frame = self.hdlc.encode(data)
            logger.debug(f"[TX] HDLC encoded: {len(hdlc_frame)} bytes")
            
            # Modulate to AFSK
            audio_data = self.afsk.modulate(hdlc_frame)
            logger.debug(f"[TX] AFSK modulated: {len(audio_data)} samples")
            
            # Write to audio device
            self.audio_manager.write_audio(audio_data)
            logger.info(f"[TX] Frame transmitted: {len(data)} bytes")
            
            # Signal TX complete
            if self.on_tx_complete:
                self.on_tx_complete()
                
        except Exception as e:
            logger.error(f"[TX] Frame processing error: {e}")
            if self.on_tx_error:
                self.on_tx_error(str(e))
    
    def _parse_kiss_frame(self, frame):
        """
        Parse KISS frame format:
        - Start: 0xC0 (FEND)
        - Type: 1 byte (lower 4 bits = port, bit 4 = flag)
        - Data: N bytes (escaped)
        - End: 0xC0 (FEND)
        
        KISS escaping:
        - 0xC0 → 0xDB 0xDC (FEND)
        - 0xDB → 0xDB 0xDD (FESC)
        """
        if not frame or len(frame) < 2:
            return None
        
        if frame[0] != 0xc0 or frame[-1] != 0xc0:
            logger.warning("[TX] Invalid KISS frame: missing FEND markers")
            return None
        
        # Get command byte (0x00 = data frame, lower 4 bits = port)
        cmd = frame[1]
        if cmd & 0x0f != 0:
            logger.debug(f"[TX] Ignoring command frame (port {cmd & 0x0f})")
            return None
        
        # Unescape data
        escaped_data = frame[2:-1]
        unescaped = bytearray()
        i = 0
        while i < len(escaped_data):
            if escaped_data[i] == 0xdb:
                if i + 1 >= len(escaped_data):
                    logger.warning("[TX] Invalid KISS escaping: truncated")
                    return None
                if escaped_data[i + 1] == 0xdc:
                    unescaped.append(0xc0)  # FEND
                    i += 2
                elif escaped_data[i + 1] == 0xdd:
                    unescaped.append(0xdb)  # FESC
                    i += 2
                else:
                    logger.warning(f"[TX] Invalid KISS escape: 0xDB 0x{escaped_data[i+1]:02x}")
                    return None
            else:
                unescaped.append(escaped_data[i])
                i += 1
        
        return bytes(unescaped)
    
    def stop(self):
        """Stop TX pipeline"""
        self.running = False
        logger.info("[TX] Pipeline stopped")
