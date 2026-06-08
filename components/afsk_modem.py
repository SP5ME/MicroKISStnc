"""
AFSK (Audio Frequency Shift Keying) Modulator/Demodulator.

Uses selectable modem profiles so the same implementation can cover Bell 202
and HF APRS 300 baud AFSK variants.
"""

import math
import numpy as np
import logging
from typing import List, Optional, Tuple

try:
    from .modem_factory import ModemFactory, ModemProfile
except ImportError:  # pragma: no cover - fallback for direct script execution
    from modem_factory import ModemFactory, ModemProfile

logger = logging.getLogger(__name__)


class AFSKModulator:
    """
    Converts HDLC bitstream to audio samples (AFSK)
    
    Configuration is supplied by a modem profile.
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        profile: Optional[ModemProfile] = None,
        modem_id: Optional[str] = None,
    ):
        self.profile = profile or ModemFactory.get_profile(modem_id)
        self.sample_rate = sample_rate
        self.bit_rate = int(self.profile.bit_rate)
        self.mark_freq = float(self.profile.tx_mark_hz)
        self.space_freq = float(self.profile.tx_space_hz)
        self.samples_per_bit_int = sample_rate // self.bit_rate
        self.samples_per_bit_float = sample_rate / self.bit_rate  # EXACT (not rounded down)
        
        # Calculate phase increments per sample for each frequency
        # CRITICAL: These must be recalculated for EACH sample rate!
        self.phase_inc_mark = 2.0 * math.pi * self.mark_freq / self.sample_rate
        self.phase_inc_space = 2.0 * math.pi * self.space_freq / self.sample_rate
        
        logger.info(f"[AFSK] Initialized @ {sample_rate} Hz using {self.profile.summary()}")
        logger.info(f"[AFSK]   - Exact samples_per_bit: {self.samples_per_bit_float:.3f}")
        logger.info(f"[AFSK]   - Integer samples_per_bit: {self.samples_per_bit_int}")
        logger.info(f"[AFSK]   - Mark freq: {self.mark_freq} Hz")
        logger.info(f"[AFSK]   - Space freq: {self.space_freq} Hz")
        logger.info(f"[AFSK]   - Mark phase_inc: {self.phase_inc_mark:.8f} rad/sample")
        logger.info(f"[AFSK]   - Space phase_inc: {self.phase_inc_space:.8f} rad/sample")
        
        # VERIFICATION: Calculate what frequencies these phase increments produce
        # freq = phase_inc * sample_rate / (2*pi)
        mark_check = self.phase_inc_mark * self.sample_rate / (2.0 * math.pi)
        space_check = self.phase_inc_space * self.sample_rate / (2.0 * math.pi)
        logger.info(f"[AFSK] VERIFICATION: Mark phase_inc produces {mark_check:.1f} Hz (expected {self.mark_freq})")
        logger.info(f"[AFSK] VERIFICATION: Space phase_inc produces {space_check:.1f} Hz (expected {self.space_freq})")
    
    def _precalc_sine_waves(self):
        """DEPRECATED: Do not use pre-calculated sine waves - generate dynamically instead!"""
        pass

    def set_profile(self, profile: ModemProfile) -> None:
        self.profile = profile
        self.bit_rate = int(profile.bit_rate)
        self.mark_freq = float(profile.tx_mark_hz)
        self.space_freq = float(profile.tx_space_hz)
        self.samples_per_bit_int = self.sample_rate // self.bit_rate
        self.samples_per_bit_float = self.sample_rate / self.bit_rate
        self.phase_inc_mark = 2.0 * math.pi * self.mark_freq / self.sample_rate
        self.phase_inc_space = 2.0 * math.pi * self.space_freq / self.sample_rate
    
    def modulate(self, bits: List[int], amplitude: float = 0.5) -> np.ndarray:
        """
        Modulate bit stream to audio samples - DYNAMICALLY GENERATES SINE FOR EACH BIT
        
        CRITICAL FIXES:
        1. Generate sine dynamically instead of pre-calculated table
        2. Accumulate fractional samples (36.75) instead of rounding
        This ensures EXACT frequency accuracy regardless of sample rate
        
        Args:
            bits: List of bits (0 or 1)
            amplitude: Output amplitude (0.0 to 1.0)
            
        Returns:
            PCM audio samples (float32) normalized to [-1, 1]
        """
        audio = []
        sample_accumulator = 0.0  # Accumulate fractional samples for exact baud rate
        
        for bit in bits:
            # Select frequency based on bit (restarts phase each bit - discontinuous)
            if bit == 1:
                freq = self.mark_freq
            else:
                freq = self.space_freq
            
            phase_inc = 2.0 * math.pi * freq / self.sample_rate
            
            # Accumulate samples for this bit (36.75 on average)
            sample_accumulator += self.samples_per_bit_float
            num_samples = int(sample_accumulator)  # Take integer part
            sample_accumulator -= num_samples      # Keep fractional part for next bit
            
            # Generate one bit period of samples (starting from phase 0 - discontinuous)
            for i in range(num_samples):
                phase = i * phase_inc
                sample = amplitude * math.sin(phase)
                audio.append(sample)
        
        return np.array(audio, dtype=np.float32)
    
    def modulate_continuous(self, bits: List[int], amplitude: float = 0.5) -> np.ndarray:
        """
        Modulate with phase continuity and NRZI encoding (smoother transitions)
        
        CRITICAL: Implements NRZI encoding:
        - Input bit 1: no state change
        - Input bit 0: state change (invert)
        - Output state (0 or 1) determines frequency: 0=SPACE, 1=MARK
        
        CRITICAL: Accumulates fractional samples (36.75) for exact baud rate
        
        Args:
            bits: List of input bits (0 or 1) - raw AX.25 bits
            amplitude: Output amplitude (0.0 to 1.0)
            
        Returns:
            PCM audio samples (float32)
        """
        audio = []
        phase = 0.0  # Track phase across all bits for continuity
        sample_accumulator = 0.0  # Accumulate fractional samples for exact baud rate
        
        # NRZI state machine
        nrzi_state = 1  # Start at MARK (idle state)
        
        for bit in bits:
            # NRZI encoding: determine output state based on input bit
            if bit == 0:
                # 0 bit: change state
                nrzi_state = 1 - nrzi_state
            # else: 1 bit keeps nrzi_state unchanged
            
            # Select frequency based on NRZI output state
            freq = self.mark_freq if nrzi_state == 1 else self.space_freq
            phase_inc = 2.0 * math.pi * freq / self.sample_rate
            
            # Accumulate samples for this bit (36.75 on average)
            sample_accumulator += self.samples_per_bit_float
            num_samples = int(sample_accumulator)  # Take integer part
            sample_accumulator -= num_samples      # Keep fractional part for next bit
            
            # Generate one bit period of samples with continuous phase
            for _ in range(num_samples):
                sample = amplitude * math.sin(phase)
                audio.append(sample)
                phase += phase_inc
        
        return np.array(audio, dtype=np.float32)
    
    def get_audio_params(self) -> dict:
        """Get audio parameters for file writing"""
        return {
            'sample_rate': self.sample_rate,
            'channels': 1,
            'bit_depth': 16,
            'format': 'PCM'  # Signed 16-bit PCM
        }


class AFSKDemodulator:
    """
    Converts audio samples (AFSK) back to bit stream
    
    Uses Goertzel algorithm for tone detection with adaptive thresholding
    to handle varying signal levels and tone imbalance
    
    Enhanced features:
    - Carrier detection (signal presence verification)
    - AGC (Automatic Gain Control) preprocessing
    - Bit synchronization verification
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        use_nrzi: bool = False,
        profile: Optional[ModemProfile] = None,
        modem_id: Optional[str] = None,
    ):
        self.profile = profile or ModemFactory.get_profile(modem_id)
        self.sample_rate = sample_rate
        self.bit_rate = int(self.profile.bit_rate)
        self.mark_freq = float(self.profile.rx_mark_hz)
        self.space_freq = float(self.profile.rx_space_hz)
        self.samples_per_bit = sample_rate // self.bit_rate  # Integer for indexing
        self.samples_per_bit_exact = sample_rate / self.bit_rate  # Float for precision
        self.use_nrzi = use_nrzi  # NRZI: transitions=0, no-transitions=1
        self._calc_goertzel_coeff()
        
        # State tracking for adaptive thresholding
        self.last_bit = 0
        self.hysteresis = 0.05  # ±5% hysteresis band
        
        # Carrier detection thresholds
        # Threshold is in RMS units (after sqrt), not power!
        # Normal background noise: RMS ~0.001
        # Weak signal: RMS ~0.002-0.005
        # Strong signal: RMS >0.01
        self.carrier_threshold = 0.0005  # Carrier detection threshold (in RMS units)
        self.carrier_hysteresis = 0.0001  # Hysteresis for carrier state
        self.on_carrier = False
        
        # AGC state
        self.agc_window = 256  # Running window for gain calculation
        self.current_gain = 1.0
        self.min_level = 0.001
        self.max_level = 0.8  # Target maximum level
        
        logger.info(f"[AFSK-DEMOD] Initialized: {self.samples_per_bit} samples/bit @ {sample_rate} Hz using {self.profile.summary()}")
        logger.info(f"[AFSK-DEMOD] Hysteresis: ±{self.hysteresis*100:.1f}%")
        logger.info(f"[AFSK-DEMOD] Carrier threshold: {self.carrier_threshold:.4f}")
        logger.info(f"[AFSK-DEMOD] AGC enabled (window={self.agc_window})")
    
    def _calc_goertzel_coeff(self):
        """Calculate Goertzel coefficients for mark and space frequencies"""
        # Goertzel coefficient: k = N * f / sample_rate
        # where N = samples_per_bit
        
        k_mark = self.samples_per_bit * self.mark_freq / self.sample_rate
        k_space = self.samples_per_bit * self.space_freq / self.sample_rate
        
        # w = 2 * pi * k / N
        w_mark = 2.0 * math.pi * k_mark / self.samples_per_bit
        w_space = 2.0 * math.pi * k_space / self.samples_per_bit
        
        # Goertzel coefficient: 2 * cos(w)
        self.coeff_mark = 2.0 * math.cos(w_mark)
        self.coeff_space = 2.0 * math.cos(w_space)

    def set_profile(self, profile: ModemProfile) -> None:
        self.profile = profile
        self.bit_rate = int(profile.bit_rate)
        self.mark_freq = float(profile.rx_mark_hz)
        self.space_freq = float(profile.rx_space_hz)
        self.samples_per_bit = self.sample_rate // self.bit_rate
        self.samples_per_bit_exact = self.sample_rate / self.bit_rate
        self._calc_goertzel_coeff()
    
    def preprocess_agc(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply AGC (Automatic Gain Control) to normalize signal level
        
        Args:
            audio: Input audio samples
            
        Returns:
            AGC-normalized audio samples
        """
        if len(audio) == 0:
            return audio
        
        # Calculate RMS level over agc_window
        rms_levels = []
        for i in range(0, len(audio) - self.agc_window, self.agc_window // 2):
            window = audio[i:i + self.agc_window]
            rms = np.sqrt(np.mean(window ** 2))
            rms_levels.append(rms)
        
        if not rms_levels:
            return audio
        
        # Average RMS level
        avg_rms = np.mean(rms_levels)
        
        # Calculate gain to bring level to max_level
        if avg_rms > self.min_level:
            self.current_gain = self.max_level / avg_rms
        else:
            self.current_gain = 1.0
        
        # Limit gain to prevent artifacts
        self.current_gain = np.clip(self.current_gain, 0.5, 4.0)
        
        # Apply gain
        processed = audio * self.current_gain
        
        # Clip to prevent overflow
        processed = np.clip(processed, -0.95, 0.95)
        
        return processed
    
    def detect_carrier(self, audio: np.ndarray) -> Tuple[bool, float]:
        """
        Detect presence of carrier signal (is there any signal?)
        
        Args:
            audio: Audio samples
            
        Returns:
            Tuple of (carrier_detected: bool, signal_strength: float)
        """
        if len(audio) < self.samples_per_bit:
            return False, 0.0
        
        # Measure RMS level (root mean square - easier to interpret than power)
        rms_level = np.sqrt(np.mean(audio ** 2))
        
        # Check against threshold with hysteresis
        # Threshold should be in RMS units, not power!
        if self.on_carrier:
            # Already on carrier - need to drop below (threshold - hysteresis) to turn off
            carrier_on = rms_level > (self.carrier_threshold - self.carrier_hysteresis)
        else:
            # Not on carrier - need to rise above (threshold + hysteresis) to turn on
            carrier_on = rms_level > (self.carrier_threshold + self.carrier_hysteresis)
        
        self.on_carrier = carrier_on
        
        return carrier_on, float(rms_level)
    
    def verify_bit_sync(self, bits: List[int], window: int = 8) -> Tuple[bool, float]:
        """
        Verify that bits are properly synchronized
        
        Checks if decoded bits match expected HDLC frame structure:
        - Should have reasonable 1/0 distribution (not all 1s or all 0s)
        - Optionally checks for flag pattern [0,1,1,1,1,1,1,0]
        
        Args:
            bits: Decoded bit stream
            window: Window size for checking bit distribution
            
        Returns:
            Tuple of (sync_verified: bool, confidence: float 0-1.0)
        """
        if len(bits) < 16:
            return False, 0.0
        
        # Check for HDLC flag pattern at start (not mandatory, just informational)
        flag_pattern = [0, 1, 1, 1, 1, 1, 1, 0]
        has_flag = bits[:8] == flag_pattern or bits[0:8] == [1, 0, 0, 0, 0, 0, 0, 1]  # Inverted
        
        # Check bit distribution (should be roughly 50% 1s and 50% 0s for random data)
        sample_size = min(len(bits), 256)
        sample = bits[:sample_size]
        ones_ratio = sum(sample) / len(sample)
        
        # Good distribution: between 20% and 80% (relaxed from 30-70)
        good_distribution = 0.2 < ones_ratio < 0.8
        confidence = 1.0 - abs(ones_ratio - 0.5) * 2  # Max confidence when exactly 50/50
        
        # Bit sync is OK if distribution is good (flag pattern is just informational)
        sync_ok = good_distribution
        
        return sync_ok, float(confidence)
    
    def _nrzi_decode(self, raw_bits: List[int]) -> List[int]:
        """
        NRZI Decoding (Non-Return-to-Zero Inverted)
        
        In AX.25/HDLC:
        - Transition (state change) → decoded bit = 0
        - No transition (state same) → decoded bit = 1
        
        Args:
            raw_bits: Raw bit stream from frequency detection
            
        Returns:
            NRZI decoded bits (first bit preserved, then transitions)
        """
        if len(raw_bits) < 2:
            return raw_bits
        
        decoded = [raw_bits[0]]  # Keep first bit as-is
        
        for i in range(1, len(raw_bits)):
            # If bit changed (transition), append 0; else append 1
            decoded.append(0 if raw_bits[i] != raw_bits[i-1] else 1)
        
        logger.debug(f"[AFSK-DEMOD] NRZI decoded {len(raw_bits)} raw bits → {len(decoded)} bits")
        
        return decoded
    
    def demodulate(self, audio: np.ndarray) -> List[int]:
        """
        Demodulate audio samples to bit stream
        
        Includes AGC preprocessing, carrier detection, and bit sync verification
        
        Args:
            audio: PCM audio samples (float32)
            
        Returns:
            List of bits (0 or 1)
        """
        # Step 1: Apply AGC
        processed_audio = self.preprocess_agc(audio)
        
        # Step 2: Detect carrier
        carrier_detected, signal_strength = self.detect_carrier(processed_audio)
        
        if not carrier_detected:
            logger.debug(f"[AFSK-DEMOD] No carrier detected (strength={signal_strength:.6f})")
            return []
        
        logger.debug(f"[AFSK-DEMOD] Carrier detected (strength={signal_strength:.6f})")
        
        bits = []
        
        # Process audio in bit-sized chunks
        num_bits = len(processed_audio) // self.samples_per_bit
        
        for bit_idx in range(num_bits):
            start = bit_idx * self.samples_per_bit
            end = start + self.samples_per_bit
            
            bit_samples = processed_audio[start:end]
            
            # Detect which tone (using energy method)
            mark_energy = self._detect_tone(bit_samples, self.mark_freq)
            space_energy = self._detect_tone(bit_samples, self.space_freq)
            
            # Normalize by total energy to account for signal level variations
            total_energy = mark_energy + space_energy
            
            if total_energy > 0:
                # Use ratio with hysteresis for stability
                mark_ratio = mark_energy / total_energy
                
                # Hysteresis: use different thresholds depending on last bit
                # This prevents bit-flipping noise
                if self.last_bit == 1:
                    # Coming from Mark - need to drop below (0.5 - hysteresis) to switch
                    threshold = 0.5 - self.hysteresis
                else:
                    # Coming from Space - need to rise above (0.5 + hysteresis) to switch
                    threshold = 0.5 + self.hysteresis
                
                bit = 1 if mark_ratio > threshold else 0
            else:
                # No signal detected, maintain last bit
                bit = self.last_bit
            
            bits.append(bit)
            self.last_bit = bit
        
        # Step 3: Verify bit synchronization
        if len(bits) > 8:
            sync_ok, confidence = self.verify_bit_sync(bits)
            logger.debug(f"[AFSK-DEMOD] Bit sync: {'✓' if sync_ok else '✗'} (confidence={confidence:.2f})")
        
        # Step 4: Apply NRZI decoding if needed
        if self.use_nrzi:
            bits = self._nrzi_decode(bits)
        
        return bits
    
    def demodulate_verbose(self, audio: np.ndarray) -> Tuple[List[int], dict]:
        """
        Demodulate with detailed diagnostics
        
        Returns:
            Tuple of (bits, diagnostics_dict)
        """
        diagnostics = {}
        
        # AGC stats
        processed_audio = self.preprocess_agc(audio)
        diagnostics['agc_gain'] = float(self.current_gain)
        diagnostics['input_rms'] = float(np.sqrt(np.mean(audio ** 2)))
        diagnostics['output_rms'] = float(np.sqrt(np.mean(processed_audio ** 2)))
        
        # Carrier detection
        carrier_detected, signal_strength = self.detect_carrier(processed_audio)
        diagnostics['carrier_detected'] = carrier_detected
        diagnostics['signal_strength'] = float(signal_strength)
        
        # Bit sync
        bits = self.demodulate(audio)
        if len(bits) > 8:
            sync_ok, confidence = self.verify_bit_sync(bits)
            diagnostics['bit_sync_ok'] = sync_ok
            diagnostics['bit_sync_confidence'] = float(confidence)
        
        diagnostics['bits_decoded'] = len(bits)
        diagnostics['nrzi_enabled'] = self.use_nrzi
        
        return bits, diagnostics
    
    def _detect_tone(self, samples: np.ndarray, freq: float) -> float:
        """
        Detect tone energy using Goertzel algorithm (CRITICAL: must account for window size)
        
        Args:
            samples: Audio samples for one bit period
            freq: Frequency to detect
            
        Returns:
            Energy level at target frequency
        """
        # CRITICAL FIX: Goertzel must use ACTUAL window size, not pre-calculated coefficient
        # Normalized frequency: k = N * f / sample_rate where N = len(samples)
        N = len(samples)
        k = N * freq / self.sample_rate
        
        # Angular frequency: w = 2*pi*k/N
        w = 2.0 * math.pi * k / N
        
        # Goertzel coefficient: 2*cos(w)
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
    
    # Test bits (default Bell 202 profile)
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
