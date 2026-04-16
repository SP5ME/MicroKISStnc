"""
AFSK (Audio Frequency Shift Keying) Modulator/Demodulator
- 1200 bps APRS standard (VHF/UHF)
- Mark (1): 1200 Hz
- Space (0): 2200 Hz
- Sample rate: 44100 Hz

Based on Direwolf's demod_afsk.c
"""

import math
import numpy as np
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class AFSKModulator:
    """
    Converts HDLC bitstream to audio samples (AFSK)
    
    Configuration:
    - Bit rate: 1200 bps
    - Mark frequency (1): 1200 Hz
    - Space frequency (0): 2200 Hz
    - Sample rate: 44100 Hz
    """
    
    # Configuration constants
    BIT_RATE = 1200          # bits per second
    MARK_FREQ = 1200         # Hz (bit = 1)
    SPACE_FREQ = 2200        # Hz (bit = 0)
    SAMPLE_RATE = 44100      # Hz
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.samples_per_bit = sample_rate // self.BIT_RATE
        
        # Pre-calculated sine wave samples for each frequency
        self._precalc_sine_waves()
        
        # Phase tracking for continuous tone generation
        self.phase_mark = 0.0
        self.phase_space = 0.0
        
        logger.info(f"[AFSK] Initialized: {self.samples_per_bit} samples/bit @ {sample_rate} Hz")
    
    def _precalc_sine_waves(self):
        """Pre-calculate sine wave samples for mark and space frequencies"""
        # Phase increment per sample
        self.phase_inc_mark = 2.0 * math.pi * self.MARK_FREQ / self.sample_rate
        self.phase_inc_space = 2.0 * math.pi * self.SPACE_FREQ / self.sample_rate
        
        # Pre-calculated sine tables for one bit period (1200 samples for 44.1kHz)
        self.sine_mark = np.sin(
            np.arange(self.samples_per_bit) * self.phase_inc_mark
        ).astype(np.float32)
        
        self.sine_space = np.sin(
            np.arange(self.samples_per_bit) * self.phase_inc_space
        ).astype(np.float32)
    
    def modulate(self, bits: List[int], amplitude: float = 0.5) -> np.ndarray:
        """
        Modulate bit stream to audio samples
        
        Args:
            bits: List of bits (0 or 1)
            amplitude: Output amplitude (0.0 to 1.0)
            
        Returns:
            PCM audio samples (float32) normalized to [-1, 1]
        """
        audio = []
        
        for bit in bits:
            if bit == 1:
                # Mark frequency (1200 Hz)
                samples = self.sine_mark * amplitude
            else:
                # Space frequency (2200 Hz)
                samples = self.sine_space * amplitude
            
            audio.extend(samples)
        
        return np.array(audio, dtype=np.float32)
    
    def modulate_continuous(self, bits: List[int], amplitude: float = 0.5) -> np.ndarray:
        """
        Modulate with phase continuity (smoother transitions)
        
        Args:
            bits: List of bits (0 or 1)
            amplitude: Output amplitude (0.0 to 1.0)
            
        Returns:
            PCM audio samples (float32)
        """
        audio = []
        
        for bit in bits:
            # Select frequency based on bit
            freq = self.MARK_FREQ if bit == 1 else self.SPACE_FREQ
            phase_inc = 2.0 * math.pi * freq / self.sample_rate
            
            # Generate one bit period of samples with continuous phase
            bit_samples = []
            for _ in range(self.samples_per_bit):
                sample = amplitude * math.sin(self.phase_mark)
                bit_samples.append(sample)
                self.phase_mark += phase_inc
            
            audio.extend(bit_samples)
        
        return np.array(audio, dtype=np.float32)
    
    def get_audio_params(self) -> dict:
        """Get audio parameters for file writing"""
        return {
            'sample_rate': self.sample_rate,
            'channels': 1,
            'bit_depth': 16,
            'format': 'PCF'  # Signed 16-bit PCM
        }


class AFSKDemodulator:
    """
    Converts audio samples (AFSK) back to bit stream
    
    Uses Goertzel algorithm for tone detection
    """
    
    BIT_RATE = 1200
    MARK_FREQ = 1200
    SPACE_FREQ = 2200
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.samples_per_bit = sample_rate // self.BIT_RATE
        
        # Goertzel coefficients for tone detection
        self._calc_goertzel_coeff()
        
        logger.info(f"[AFSK-DEMOD] Initialized: {self.samples_per_bit} samples/bit")
    
    def _calc_goertzel_coeff(self):
        """Calculate Goertzel coefficients for mark and space frequencies"""
        # Goertzel coefficient: k = N * f / sample_rate
        # where N = samples_per_bit
        
        k_mark = self.samples_per_bit * self.MARK_FREQ / self.sample_rate
        k_space = self.samples_per_bit * self.SPACE_FREQ / self.sample_rate
        
        # w = 2 * pi * k / N
        w_mark = 2.0 * math.pi * k_mark / self.samples_per_bit
        w_space = 2.0 * math.pi * k_space / self.samples_per_bit
        
        # Goertzel coefficient: 2 * cos(w)
        self.coeff_mark = 2.0 * math.cos(w_mark)
        self.coeff_space = 2.0 * math.cos(w_space)
    
    def demodulate(self, audio: np.ndarray) -> List[int]:
        """
        Demodulate audio samples to bit stream
        
        Args:
            audio: PCM audio samples (float32)
            
        Returns:
            List of bits (0 or 1)
        """
        bits = []
        
        # Process audio in bit-sized chunks
        num_bits = len(audio) // self.samples_per_bit
        
        for bit_idx in range(num_bits):
            start = bit_idx * self.samples_per_bit
            end = start + self.samples_per_bit
            
            bit_samples = audio[start:end]
            
            # Detect which tone (using energy method for simplicity)
            mark_energy = self._detect_tone(bit_samples, self.MARK_FREQ)
            space_energy = self._detect_tone(bit_samples, self.SPACE_FREQ)
            
            # Decide based on which has more energy
            if mark_energy > space_energy:
                bits.append(1)
            else:
                bits.append(0)
        
        return bits
    
    def _detect_tone(self, samples: np.ndarray, freq: float) -> float:
        """
        Detect tone energy using Goertzel algorithm
        
        Args:
            samples: Audio samples for one bit period
            freq: Frequency to detect
            
        Returns:
            Energy level at target frequency
        """
        # Goertzel algorithm
        w = 2.0 * math.pi * freq / self.sample_rate
        coeff = 2.0 * math.cos(w)
        
        s0 = 0.0
        s1 = 0.0
        s2 = 0.0
        
        for sample in samples:
            s0 = sample + coeff * s1 - s2
            s2 = s1
            s1 = s0
        
        # Calculate power (simplified)
        real = s1 - s2 * math.cos(w)
        imag = s2 * math.sin(w)
        power = real * real + imag * imag
        
        return power


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Create modulator
    modulator = AFSKModulator()
    
    # Test bits (1200 bps, so 1200 samples/bit)
    test_bits = [1, 0, 1, 1, 0, 0, 1, 0] * 10  # Repeat pattern
    
    # Modulate
    audio = modulator.modulate(test_bits, amplitude=0.3)
    print(f"Modulated {len(test_bits)} bits to {len(audio)} audio samples")
    
    # Create demodulator
    demodulator = AFSKDemodulator()
    
    # Demodulate
    recovered_bits = demodulator.demodulate(audio)
    print(f"Demodulated back to {len(recovered_bits)} bits")
    
    # Check accuracy
    errors = sum(1 for a, b in zip(test_bits, recovered_bits) if a != b)
    print(f"Bit errors: {errors}/{len(test_bits)}")
