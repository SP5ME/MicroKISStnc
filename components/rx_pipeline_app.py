#!/usr/bin/env python3
"""
RX Pipeline for MicroKISStnc
Decodes AFSK audio -> bits -> HDLC frames -> display
"""

import numpy as np
import logging
from typing import Optional, Callable
from components.afsk_modem import AFSKDemodulator
from components.hdlc_codec import HDLCDecoder, CRC16CCITT

logger = logging.getLogger(__name__)


class RXPipeline:
    """RX audio decoding pipeline"""
    
    def __init__(self, sample_rate: int = 44100, on_frame_decoded: Optional[Callable] = None):
        """
        Initialize RX pipeline
        
        Args:
            sample_rate: Audio sample rate (Hz)
            on_frame_decoded: Callback function(frame_data) when HDLC frame decoded
        """
        self.sample_rate = sample_rate
        self.on_frame_decoded = on_frame_decoded
        
        # Components
        self.afsk_demod = AFSKDemodulator(sample_rate=sample_rate)
        self.hdlc_decoder = HDLCDecoder()
        self.crc = CRC16CCITT()
        
        # Bit buffer for HDLC decoding
        self.bit_buffer = bytearray()
        self.frame_count = 0
        
        logger.info(f"[RX-PIPELINE] Initialized @ {sample_rate}Hz")
    
    def process_audio(self, audio_samples: np.ndarray):
        """
        Process audio samples through RX pipeline
        
        Args:
            audio_samples: PCM audio (float32)
        """
        if len(audio_samples) == 0:
            return
        
        try:
            import time as time_module
            
            # Stage 1: AFSK Demodulation (audio -> bits)
            demod_start = time_module.time()
            logger.info(f"[RX-PIPELINE] >> process_audio({len(audio_samples)} samples)")
            bits = self.afsk_demod.demodulate(audio_samples)
            demod_elapsed = time_module.time() - demod_start
            
            if demod_elapsed > 0.01:
                logger.warning(f"[RX-PIPELINE] DEMOD took {demod_elapsed*1000:.1f}ms for {len(audio_samples)} samples!")
                
            logger.info(f"[RX-PIPELINE] << demodulated {len(bits)} bits")
            
            if len(bits) == 0:
                logger.info(f"[RX-PIPELINE] No bits demodulated, returning")
                return
            
            # Add bits to buffer
            for bit in bits:
                self.bit_buffer.append(bit)
            
            logger.info(f"[RX-PIPELINE] Bit buffer now has {len(self.bit_buffer)} bits")
            
            # Stage 2: HDLC Decoding (bits -> frames)
            self._try_decode_hdlc()
        
        except Exception as e:
            logger.error(f"[RX-PIPELINE] EXCEPTION: {e}", exc_info=True)
    
    def _try_decode_hdlc(self):
        """Try to decode HDLC frames from bit buffer"""
        # Need at least one HDLC frame (minimal ~10 bytes = 80 bits + flags)
        if len(self.bit_buffer) < 80:
            return
        
        try:
            # Try to decode frames
            frames = self.hdlc_decoder.decode_bits(self.bit_buffer)
            
            if frames:
                self.bit_buffer.clear()  # Clear processed bits
                
                for frame_data in frames:
                    if len(frame_data) >= 2:
                        # Validate CRC
                        frame_payload = frame_data[:-2]
                        frame_crc = frame_data[-2:]
                        
                        calculated_crc = self.crc.compute(frame_payload)
                        calculated_bytes = bytes([
                            (calculated_crc >> 8) & 0xFF,
                            calculated_crc & 0xFF
                        ])
                        
                        if frame_crc == calculated_bytes:
                            self.frame_count += 1
                            logger.info(f"[RX-PIPELINE] Frame #{self.frame_count} decoded ({len(frame_payload)} bytes, CRC OK)")
                            
                            # Callback
                            if self.on_frame_decoded:
                                try:
                                    self.on_frame_decoded(frame_payload)
                                except Exception as e:
                                    logger.warning(f"[RX-PIPELINE] Callback error: {e}")
                        else:
                            logger.warning(f"[RX-PIPELINE] CRC mismatch - expected {calculated_bytes.hex()}, got {frame_crc.hex()}")
        
        except Exception as e:
            logger.debug(f"[RX-PIPELINE] Decode attempt: {e}")
