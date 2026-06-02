#!/usr/bin/env python3
"""
Test Tone Generator
Generates AFSK test tones (1200 Hz, 2200 Hz, or Both)
"""

import numpy as np
import logging
from typing import Optional, Literal
from threading import Thread, Event

logger = logging.getLogger(__name__)


class TestToneGenerator:
    """Generate test tones for audio level adjustment"""
    
    # AFSK standard frequencies
    MARK_FREQ = 1200    # Hz (binary 1)
    SPACE_FREQ = 2200   # Hz (binary 0)
    DEFAULT_SAMPLE_RATE = 44100  # Hz - default fallback
    
    def __init__(self, sample_rate: int = 44100):
        """
        Initialize test tone generator
        
        Args:
            sample_rate: Audio sample rate in Hz (must match output device rate!)
        """
        self.sample_rate = sample_rate  # Store as instance variable (can be changed)
        self.is_generating = False
        self.generation_thread: Optional[Thread] = None
        self.stop_event = Event()
        self.on_audio_ready = None  # Callback: function(audio_samples)
        logger.info(f"[TONE] Initialized @ {self.sample_rate} Hz")
    
    def generate_tone(self, frequency: float, duration_seconds: float) -> np.ndarray:
        """
        Generate a sine wave tone at current sample rate
        
        Args:
            frequency: Frequency in Hz
            duration_seconds: Duration in seconds
        
        Returns:
            numpy array of audio samples (float32, range [-1.0, 1.0])
        """
        num_samples = int(self.sample_rate * duration_seconds)
        t = np.arange(num_samples) / self.sample_rate
        
        # Generate clean sine wave (no fade in chunks - causes artifacts)
        wave = np.sin(2.0 * np.pi * frequency * t).astype(np.float32)
        
        # Normalize to ensure consistent amplitude across all tones
        max_val = np.max(np.abs(wave))
        if max_val > 0:
            wave = wave / max_val * 0.8  # Scale to 0.8 to leave headroom
        
        return wave
    
    def generate_mark(self, duration_seconds: float = 0.1) -> np.ndarray:
        """Generate 1200 Hz (MARK) test tone"""
        return self.generate_tone(self.MARK_FREQ, duration_seconds)
    
    def generate_space(self, duration_seconds: float = 0.1) -> np.ndarray:
        """Generate 2200 Hz (SPACE) test tone"""
        return self.generate_tone(self.SPACE_FREQ, duration_seconds)
    
    def generate_both(self, duration_seconds: float = 0.1) -> np.ndarray:
        """Generate mixed 1200 Hz + 2200 Hz test tone"""
        mark = self.generate_tone(self.MARK_FREQ, duration_seconds)
        space = self.generate_tone(self.SPACE_FREQ, duration_seconds)
        
        # Mix both tones (sum and normalize to avoid clipping)
        mixed = (mark + space) / 2.0
        return np.clip(mixed, -1.0, 1.0).astype(np.float32)
    
    def set_sample_rate(self, sample_rate: int):
        """
        Update sample rate for tone generation
        
        CRITICAL: Call this before start_continuous() if output device uses different rate!
        
        Args:
            sample_rate: Audio sample rate in Hz (must match output device rate)
        """
        if sample_rate > 0:
            self.sample_rate = sample_rate
            logger.info(f"[TONE] Sample rate updated to {self.sample_rate} Hz")
        else:
            logger.warning(f"[TONE] Invalid sample rate: {sample_rate}")
    
    def start_continuous(self, tone_type: Literal["1200", "2200", "both"], 
                         callback=None, chunk_duration: float = 0.1, sample_rate: Optional[int] = None):
        """
        Start generating continuous tone until stopped
        
        Args:
            tone_type: "1200", "2200", or "both"
            callback: Function to call with each audio chunk
            chunk_duration: Duration of each chunk (seconds)
            sample_rate: Optional - override generator's sample rate for this tone
        """
        if self.is_generating:
            logger.warning("[TONE] Already generating tone")
            return
        
        # Update sample rate if provided
        if sample_rate is not None and sample_rate > 0:
            old_rate = self.sample_rate
            self.set_sample_rate(sample_rate)
            logger.info(f"[TONE] Switched sample rate: {old_rate} Hz → {self.sample_rate} Hz")
        
        self.is_generating = True
        self.stop_event.clear()
        self.on_audio_ready = callback
        
        self.generation_thread = Thread(
            target=self._generation_loop,
            args=(tone_type, chunk_duration),
            daemon=True,
            name="ToneGenerator"
        )
        self.generation_thread.start()
        logger.info(f"[TONE] Started {tone_type} Hz tone")
    
    def stop_continuous(self):
        """Stop generating continuous tone"""
        if not self.is_generating:
            logger.warning("[TONE] Not currently generating")
            return
        
        self.stop_event.set()
        if self.generation_thread:
            self.generation_thread.join(timeout=1.0)
        
        self.is_generating = False
        logger.info("[TONE] Stopped tone generation")
    
    def _generation_loop(self, tone_type: str, chunk_duration: float):
        """Internal loop for continuous tone generation"""
        
        # Select generator function
        if tone_type == "1200":
            generator = self.generate_mark
        elif tone_type == "2200":
            generator = self.generate_space
        elif tone_type == "both":
            generator = self.generate_both
        else:
            logger.error(f"[TONE] Unknown tone type: {tone_type}")
            return
        
        try:
            while not self.stop_event.is_set():
                # Generate chunk
                audio_chunk = generator(chunk_duration)
                
                # Send to callback
                if self.on_audio_ready:
                    self.on_audio_ready(audio_chunk)
                
                # Check stop event (very responsive - 1ms timeout)
                if self.stop_event.wait(timeout=0.001):
                    break
        
        except Exception as e:
            logger.error(f"[TONE] Generation error: {e}")
        
        finally:
            self.is_generating = False
    
    def is_running(self) -> bool:
        """Check if tone generation is active"""
        return self.is_generating


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    gen = TestToneGenerator()
    
    print("=== Test Tone Generator ===\n")
    
    # Test 1: Generate single tones
    print("Test 1: Generate 1200 Hz tone (1 second)")
    tone_1200 = gen.generate_mark(1.0)
    print(f"Generated {len(tone_1200)} samples, peak: {np.max(np.abs(tone_1200)):.3f}")
    
    print("\nTest 2: Generate 2200 Hz tone (1 second)")
    tone_2200 = gen.generate_space(1.0)
    print(f"Generated {len(tone_2200)} samples, peak: {np.max(np.abs(tone_2200)):.3f}")
    
    print("\nTest 3: Generate Both tones (1 second)")
    tone_both = gen.generate_both(1.0)
    print(f"Generated {len(tone_both)} samples, peak: {np.max(np.abs(tone_both)):.3f}")
    
    # Test 4: Continuous generation (simulate)
    print("\nTest 4: Continuous tone generation (5 seconds simulation)")
    
    chunks_received = []
    
    def chunk_callback(chunk):
        chunks_received.append(chunk)
        if len(chunks_received) % 10 == 0:
            print(f"  Received {len(chunks_received)} chunks ({len(chunks_received) * 0.1:.1f}s)")
    
    gen.start_continuous("both", callback=chunk_callback, chunk_duration=0.1)
    
    # Simulate 5 seconds
    import time
    time.sleep(5.0)
    
    gen.stop_continuous()
    
    print(f"\nTotal chunks received: {len(chunks_received)}")
    print(f"Total duration: {len(chunks_received) * 0.1:.1f} seconds")
