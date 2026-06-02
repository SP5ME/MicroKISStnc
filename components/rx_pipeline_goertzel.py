#!/usr/bin/env python3
"""
RX Pipeline v2 - Goertzel + Phase Search (wzorowane na aprs_audio_bits.py)
Decodes AFSK audio -> bits -> HDLC frames with AX.25 validation
"""

import numpy as np
import logging
import math
from typing import Optional, Callable, Tuple, List
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)

# Configuration
BAUD = 1200
MARK_HZ = 1200
SPACE_HZ = 2200
TARGET_FS = 48000
FLAG_BITS = "01111110"


# =============================================================================
# TONE POWER MEASUREMENT (GOERTZEL)
# =============================================================================

def tone_power_goertzel(samples, fs, freq):
    """Goertzel algorithm to measure tone power at specific frequency"""
    n = len(samples)
    if n == 0:
        return 0.0
    
    k = int(0.5 + (n * freq / fs))
    omega = (2.0 * math.pi * k) / n
    coeff = 2.0 * math.cos(omega)
    
    s_prev = 0.0
    s_prev2 = 0.0
    
    for x in samples:
        s = x + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s
    
    power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
    return power


# =============================================================================
# DEMODULATION
# =============================================================================

def demodulate_symbols(data, fs, phase):
    """
    Demodulate AFSK symbols at specific phase offset.
    Returns: (symbols, confidences)
    - symbols: 1 = MARK 1200Hz, 0 = SPACE 2200Hz
    - confidences: power ratio confidence per symbol
    """
    samples_per_bit = fs // BAUD
    
    symbols = []
    confidences = []
    
    pos = phase
    while pos + samples_per_bit <= len(data):
        window = data[pos:pos + samples_per_bit]
        
        p_mark = tone_power_goertzel(window, fs, MARK_HZ)
        p_space = tone_power_goertzel(window, fs, SPACE_HZ)
        
        if p_mark >= p_space:
            symbols.append(1)
        else:
            symbols.append(0)
        
        denom = p_mark + p_space
        if denom > 0:
            confidences.append(abs(p_mark - p_space) / denom)
        else:
            confidences.append(0.0)
        
        pos += samples_per_bit
    
    return symbols, confidences


# =============================================================================
# NRZI DECODE (STANDARD LOGIC)
# =============================================================================

def nrzi_decode(symbols):
    """
    NRZI decoding - AX.25/APRS standard:
    - Transition (tone change) = 0
    - No transition (same tone) = 1
    """
    bits = []
    
    for i in range(1, len(symbols)):
        if symbols[i] == symbols[i - 1]:
            bits.append(1)  # NO CHANGE = 1
        else:
            bits.append(0)  # CHANGE = 0
    
    return bits


# =============================================================================
# HDLC FLAG AND BIT DESTUFFING
# =============================================================================

def bits_to_string(bits):
    return "".join("1" if b else "0" for b in bits)

def find_flags(bit_string):
    """Find all HDLC flag positions"""
    positions = []
    start = 0
    
    while True:
        pos = bit_string.find(FLAG_BITS, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    
    return positions

def destuff_bits(bits):
    """Remove HDLC bit stuffing - after 5 ones, remove the next 0"""
    out = []
    ones = 0
    
    for b in bits:
        if b == 1:
            out.append(b)
            ones += 1
        else:
            if ones == 5:
                # This zero was stuffed - skip it
                ones = 0
                continue
            out.append(b)
            ones = 0
    
    return out

def bits_lsb_to_bytes(bits):
    """Convert bits to bytes using LSB-first (AX.25) byte ordering"""
    result = []
    
    for i in range(0, len(bits) - 7, 8):
        value = 0
        for bit_index in range(8):
            value |= bits[i + bit_index] << bit_index
        result.append(value)
    
    return bytes(result)


# =============================================================================
# AX.25 PARSING & VALIDATION
# =============================================================================

def ax25_fcs_ok(frame_bytes):
    """
    CRC-16/X-25 validation for AX.25 frame.
    Valid frame (with FCS) calculates to 0xF0B8.
    """
    crc = 0xFFFF
    
    for byte in frame_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
            crc &= 0xFFFF
    
    return crc == 0xF0B8, crc


def decode_ax25_callsign(addr_bytes):
    """Decode AX.25 7-byte address field"""
    if len(addr_bytes) != 7:
        return None
    
    callsign = ""
    
    for b in addr_bytes[:6]:
        c = chr((b >> 1) & 0x7F)
        if c != " ":
            callsign += c
    
    ssid_byte = addr_bytes[6]
    ssid = (ssid_byte >> 1) & 0x0F
    
    if ssid:
        full = f"{callsign}-{ssid}"
    else:
        full = callsign
    
    return {"callsign": callsign, "full": full}


def address_chars_are_plausible(addr):
    """Basic check if 6-byte address looks like AX.25"""
    for b in addr[:6]:
        c = (b >> 1) & 0x7F
        if c == 0x20:  # space
            continue
        if 0x30 <= c <= 0x39:  # 0-9
            continue
        if 0x41 <= c <= 0x5A:  # A-Z
            continue
        return False
    
    return True

def parse_ax25_structure(frame_bytes):
    """Parse AX.25 frame structure if recognizable"""
    if len(frame_bytes) < 16:
        return None
    
    body = frame_bytes[:-2] if len(frame_bytes) >= 2 else frame_bytes
    
    offset = 0
    addresses = []
    
    while offset + 7 <= len(body):
        addr = body[offset:offset + 7]
        
        if not address_chars_are_plausible(addr):
            return None
        
        decoded = decode_ax25_callsign(addr)
        if decoded is None:
            return None
        
        addresses.append(decoded)
        offset += 7
        
        if len(addresses) > 10:
            return None
    
    if len(addresses) < 2:
        return None
    
    if offset + 2 > len(body):
        return None
    
    control = body[offset]
    pid = body[offset + 1]
    payload = body[offset + 2:]
    
    return {
        "addresses": addresses,
        "control": control,
        "pid": pid,
        "payload": payload,
    }


def score_ax25_candidate(frame_bytes):
    """Score frame candidate based on AX.25 structure quality"""
    score = 0
    reasons = []
    
    length = len(frame_bytes)
    
    if length == 0:
        return -1000, ["empty"]
    
    if length < 16:
        return -500 + length, ["too_short"]
    
    if 20 <= length <= 330:
        score += 20
        reasons.append("reasonable_length")
    
    parsed = parse_ax25_structure(frame_bytes)
    if parsed is None:
        return score - 50, reasons + ["not_ax25"]
    
    score += 200
    reasons.append("ax25_ok")
    
    if parsed["control"] == 0x03:
        score += 200
        reasons.append("UI_frame")
    
    if parsed["pid"] == 0xF0:
        score += 200
        reasons.append("PID_F0")
    
    payload = parsed["payload"]
    if payload and 32 <= payload[0] <= 126:
        score += 50
        reasons.append("ascii_payload")
    
    fcs_ok, fcs_value = ax25_fcs_ok(frame_bytes)
    if fcs_ok:
        score += 1000
        reasons.append("FCS_OK")
    else:
        score -= 20
        reasons.append(f"FCS_bad")
    
    return score, reasons, parsed


# =============================================================================
# FRAME EXTRACTION & CANDIDATE SELECTION
# =============================================================================

def extract_all_frame_candidates(bit_string):
    """Extract all frame candidates between flags and score them"""
    flag_positions = find_flags(bit_string)
    candidates = []
    
    for i in range(len(flag_positions) - 1):
        flag_a = flag_positions[i]
        flag_b = flag_positions[i + 1]
        
        start = flag_a + len(FLAG_BITS)
        end = flag_b
        
        if end < start:
            continue
        
        frame_bits_str = bit_string[start:end]
        
        if not frame_bits_str:
            continue
        
        frame_bits = [1 if c == "1" else 0 for c in frame_bits_str]
        destuffed = destuff_bits(frame_bits)
        frame_bytes = bits_lsb_to_bytes(destuffed)
        
        score, reasons, parsed = score_ax25_candidate(frame_bytes)
        
        candidates.append({
            "score": score,
            "reasons": reasons,
            "bytes": frame_bytes,
            "parsed": parsed,
        })
    
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return flag_positions, candidates


def choose_best_phase(data, fs):
    """Try all bit phases and return the best one based on frame quality"""
    samples_per_bit = fs // BAUD
    
    best = None
    
    for phase in range(samples_per_bit):
        symbols, confidences = demodulate_symbols(data, fs, phase)
        bits = nrzi_decode(symbols)
        bit_string = bits_to_string(bits)
        
        flag_positions, candidates = extract_all_frame_candidates(bit_string)
        
        best_candidate_score = candidates[0]["score"] if candidates else -9999
        flags = len(flag_positions)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        
        score = best_candidate_score + flags * 2 + avg_conf
        
        if best is None or score > best["score"]:
            best = {
                "phase": phase,
                "symbols": symbols,
                "bits": bits,
                "candidates": candidates,
                "best_candidate_score": best_candidate_score,
                "flags": flags,
                "score": score,
            }
    
    return best


# =============================================================================
# RX PIPELINE
# =============================================================================

class RXPipelineGoertzel:
    """RX pipeline using Goertzel tone detection and phase search"""
    
    def __init__(self, sample_rate: int = 48000, on_frame_decoded: Optional[Callable] = None):
        """
        Initialize RX pipeline
        
        Args:
            sample_rate: Audio sample rate (Hz) - will be resampled to TARGET_FS internally
            on_frame_decoded: Callback function(frame_data, parsed) when valid frame decoded
        """
        self.input_sample_rate = sample_rate
        self.sample_rate = sample_rate  # Alias for compatibility
        self.target_sample_rate = TARGET_FS
        self.on_frame_decoded = on_frame_decoded
        
        self.frame_buffer = np.array([], dtype=np.float64)
        self.frame_count = 0
        self.chunk_processed = 0
        
        logger.info(f"[RX-GOERTZEL] Initialized @ {sample_rate}Hz (target {TARGET_FS}Hz)")
    
    def process_audio(self, audio_samples: np.ndarray):
        """
        Process audio samples through RX pipeline
        
        Args:
            audio_samples: PCM audio (float32 or float64)
        """
        if len(audio_samples) == 0:
            return
        
        # Convert to float64 if needed
        audio_64 = audio_samples.astype(np.float64)
        
        # Resample if needed
        if self.input_sample_rate != self.target_sample_rate:
            g = math.gcd(self.input_sample_rate, self.target_sample_rate)
            up = self.target_sample_rate // g
            down = self.input_sample_rate // g
            audio_64 = resample_poly(audio_64, up, down)
        
        # Accumulate into buffer
        self.frame_buffer = np.concatenate([self.frame_buffer, audio_64])
        
        # Process when buffer is large enough (2 seconds @ TARGET_FS)
        chunk_size = self.target_sample_rate * 2
        while len(self.frame_buffer) >= chunk_size:
            chunk = self.frame_buffer[:chunk_size]
            self.frame_buffer = self.frame_buffer[chunk_size:]
            
            self._process_chunk(chunk)
    
    def _process_chunk(self, chunk):
        """Process 2-second audio chunk"""
        try:
            self.chunk_processed += 1
            
            best = choose_best_phase(chunk, self.target_sample_rate)
            
            if not best["candidates"]:
                return
            
            frame = best["candidates"][0]
            
            # Only process good frames
            if frame["score"] < 300:
                return
            
            if not frame["parsed"]:
                return
            
            self.frame_count += 1
            
            # Call callback with frame data and parsed info
            if self.on_frame_decoded:
                self.on_frame_decoded(frame["bytes"], frame["parsed"])
            
            logger.info(
                f"[RX-FRAME #{self.frame_count}] Score: {frame['score']:.1f} "
                f"bytes: {len(frame['bytes'])} "
                f"from: {frame['parsed']['addresses'][1]['full']} "
                f"to: {frame['parsed']['addresses'][0]['full']}"
            )
        
        except Exception as e:
            logger.error(f"[RX-CHUNK] Error processing chunk: {e}", exc_info=True)
    
    def flush(self):
        """Flush remaining buffered data"""
        if len(self.frame_buffer) > 0:
            chunk = self.frame_buffer
            self.frame_buffer = np.array([], dtype=np.float64)
            
            # Pad to minimum chunk size or process as-is if close
            if len(chunk) > self.target_sample_rate:
                self._process_chunk(chunk)
