#!/usr/bin/env python3
"""
TX Pipeline: KISS -> HDLC -> AFSK -> Audio
Converts incoming KISS frames to audio output
"""

import threading
import logging
from queue import Queue, Empty
from typing import Callable, Optional
import numpy as np
import wave
import os
from datetime import datetime

try:
    from .hdlc_codec import HDLCEncoder
except ImportError:  # pragma: no cover - fallback for direct script execution
    from hdlc_codec import HDLCEncoder

try:
    from .audio_manager import AudioManager
except ImportError:  # pragma: no cover - fallback for direct script execution
    from audio_manager import AudioManager

try:
    from .afsk_modem import AFSKModulator
    from .modem_factory import ModemFactory, ModemProfile
except ImportError:  # pragma: no cover - fallback for direct script execution
    from afsk_modem import AFSKModulator
    from modem_factory import ModemFactory, ModemProfile

logger = logging.getLogger(__name__)


class TXPipeline:
    """
    TX Pipeline: Processes KISS frames and outputs audio
    
    Flow: KISS frame -> HDLC encode -> AFSK modulate -> Audio output
    """
    
    def __init__(self, audio_manager: AudioManager, modem_profile: Optional[ModemProfile] = None, modem_id: Optional[str] = None):
        self.audio_manager = audio_manager
        self.input_queue = Queue()  # Receives KISS frames
        self.running = False
        self.thread = None
        self.modem_profile = modem_profile or ModemFactory.get_profile(modem_id)
        
        # Components
        self.hdlc_encoder = HDLCEncoder()
        self.afsk_modulator = None  # Initialized in start() with actual sample rate
        
        # Callbacks
        self.on_tx_start: Optional[Callable] = None
        self.on_tx_complete: Optional[Callable] = None
        self.on_tx_error: Optional[Callable] = None
    
    def start(self):
        """Start TX pipeline thread
        
        CRITICAL: Must be called AFTER audio_manager.start_output_stream() is called!
        This ensures we use the ACTUAL audio device sample rate, not a hardcoded value.
        """
        if self.running:
            logger.warning("[TX] Pipeline already running")
            return
        
        # Get actual output sample rate from audio manager
        # This is CRITICAL - must match the actual device sample rate!
        actual_sample_rate = self.audio_manager.get_output_sample_rate()
        logger.info(f"[TX] Using actual audio device sample rate: {actual_sample_rate} Hz")
        
        # Initialize AFSK modulator with actual sample rate
        # IMPORTANT: This ensures the selected modem profile uses CORRECT phase increments
        self.afsk_modulator = AFSKModulator(sample_rate=actual_sample_rate, profile=self.modem_profile)
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="TXPipeline")
        self.thread.start()
        logger.info("[TX] Pipeline started")
    
    def stop(self):
        """Stop TX pipeline"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("[TX] Pipeline stopped")
    
    def send_kiss_frame(self, kiss_data: bytes):
        """Queue KISS frame for transmission"""
        self.input_queue.put(kiss_data)

    def set_modem_profile(self, modem_profile: ModemProfile) -> None:
        """Update modem profile used for future transmissions."""
        self.modem_profile = modem_profile
        if self.afsk_modulator is not None:
            self.afsk_modulator.set_profile(modem_profile)
    
    def _run(self):
        """Main TX pipeline loop"""
        while self.running:
            try:
                # Get KISS frame from queue (timeout to allow stopping)
                try:
                    kiss_data = self.input_queue.get(timeout=0.5)
                except Empty:
                    continue
                
                # Process frame
                self._process_kiss_frame(kiss_data)
                
            except Exception as e:
                logger.error(f"[TX] Pipeline error: {e}")
                if self.on_tx_error:
                    self.on_tx_error(str(e))
    
    def _process_kiss_frame(self, kiss_data: bytes):
        """
        Process KISS frame through entire TX pipeline
        
        KISS format:
        - 0xC0 = START
        - 0xC0 = END
        - 0xDB 0xDC = escaped 0xC0
        - 0xDB 0xDD = escaped 0xDB
        
        After unescaping:
        - First byte = command (0x00 = data, 0x01 = TX delay, etc)
        - Rest = AX.25 frame
        """
        
        try:
            logger.debug(f"[TX] Received KISS frame: {len(kiss_data)} bytes")
            
            # Parse KISS frame
            ax25_data = self._parse_kiss_frame(kiss_data)
            
            if not ax25_data:
                logger.error("[TX] Invalid KISS frame")
                return
            
            if self.on_tx_start:
                self.on_tx_start(f"TX: {len(ax25_data)} bytes")
            
            # Step 1: HDLC encode
            logger.debug(f"[TX] HDLC encoding {len(ax25_data)} bytes...")
            hdlc_bits = self.hdlc_encoder.encode_frame(ax25_data)
            logger.debug(f"[TX] HDLC encoded to {len(hdlc_bits)} bits")
            
            # Step 2: AFSK modulate (use continuous phase for profile accuracy)
            logger.debug(f"[TX] AFSK modulating {len(hdlc_bits)} bits...")
            audio = self.afsk_modulator.modulate_continuous(hdlc_bits, amplitude=0.9)
            logger.debug(
                f"[TX] AFSK modulated to {len(audio)} audio samples "
                f"({len(audio)/max(1, self.afsk_modulator.sample_rate):.2f}s)"
            )
            
            # Step 3: Output to audio device
            logger.debug(f"[TX] Sending to audio output...")
            self.audio_manager.write_audio(audio)
            
            # Save to WAV for debugging
            self._save_audio_debug(audio, len(ax25_data))
            
            logger.info(f"[TX] Frame transmitted: {len(ax25_data)} bytes -> {len(audio)} samples")
            
            if self.on_tx_complete:
                self.on_tx_complete(f"TX OK: {len(ax25_data)} bytes")
        
        except Exception as e:
            logger.error(f"[TX] Frame processing error: {e}")
            if self.on_tx_error:
                self.on_tx_error(str(e))
    
    @staticmethod
    def _parse_kiss_frame(data: bytes) -> Optional[bytes]:
        """
        Parse KISS frame and extract AX.25 data
        
        Returns: Unescaped AX.25 frame or None if invalid
        """
        if len(data) < 2:
            return None
        
        # Unescape KISS data
        unescaped = bytearray()
        i = 0
        while i < len(data):
            if data[i] == 0xDB and i + 1 < len(data):
                # Escaped byte
                next_byte = data[i + 1]
                if next_byte == 0xDC:
                    unescaped.append(0xC0)  # Escaped flag
                elif next_byte == 0xDD:
                    unescaped.append(0xDB)  # Escaped escape
                else:
                    logger.warning(f"[TX] Invalid KISS escape sequence: 0xDB 0x{next_byte:02X}")
                    unescaped.append(next_byte)
                i += 2
            else:
                unescaped.append(data[i])
                i += 1
        
        # First byte is command type (0x00 = data frame)
        if len(unescaped) < 2:
            return None
        
        command = unescaped[0] & 0x0F  # Lower 4 bits = command
        port = (unescaped[0] >> 4) & 0x0F  # Upper 4 bits = port
        
        if command != 0x00:
            logger.debug(f"[TX] Ignoring non-data command: 0x{command:02X}")
            return None
        
        # Return AX.25 frame (everything after command byte)
        return bytes(unescaped[1:])
    
    def _save_audio_debug(self, audio_data: np.ndarray, data_len: int):
        """Save audio to WAV file for debugging"""
        try:
            # Create debug directory if needed
            debug_dir = "tx_debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = os.path.join(debug_dir, f"tx_{timestamp}_{data_len}bytes.wav")
            
            # Convert numpy array to 16-bit PCM
            if audio_data.dtype == np.float32:
                # Scale from [-1, 1] to [-32768, 32767]
                audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            else:
                audio_int16 = audio_data.astype(np.int16)
            
            # Write WAV file
            with wave.open(filename, 'w') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(int(self.afsk_modulator.sample_rate) if self.afsk_modulator else 44100)
                wav_file.writeframes(audio_int16.tobytes())
            
            logger.info(f"[TX] Audio saved to {filename}")
        except Exception as e:
            logger.error(f"[TX] Failed to save audio: {e}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Test
    from audio_manager import AudioManager
    
    audio_mgr = AudioManager()
    tx = TXPipeline(audio_mgr)
    tx.on_tx_start = lambda msg: print(f"[EVENT] {msg}")
    tx.on_tx_complete = lambda msg: print(f"[EVENT] {msg}")
    tx.on_tx_error = lambda msg: print(f"[ERROR] {msg}")
    
    # Create test KISS frame with AX.25 data
    # KISS format: [0xC0][CMD][DATA][0xC0]
    # where CMD = 0x00 for data frame
    
    test_ax25 = b'\x82\xa0\xa4\x60\x9c\x84\x62\x81\x03\xf0Test'
    test_kiss = bytes([0xC0, 0x00]) + test_ax25 + bytes([0xC0])
    
    print(f"Test KISS frame: {test_kiss.hex()}")
    
    tx.start()
    tx.send_kiss_frame(test_kiss)
    
    import time
    time.sleep(5)
    
    tx.stop()
