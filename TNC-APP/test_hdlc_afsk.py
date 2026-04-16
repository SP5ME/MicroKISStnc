#!/usr/bin/env python3
"""
Integration test: KISS -> HDLC -> AFSK -> Audio -> AFSK -> HDLC -> KISS
Tests the complete TX/RX chain
"""

import sys
import io
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Fix stdout encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from hdlc_codec import HDLCEncoder, HDLCDecoder, CRC16CCITT
from afsk_modem import AFSKModulator, AFSKDemodulator
import numpy as np

def test_hdlc_codec():
    """Test HDLC encoding/decoding with CRC"""
    print("\n" + "="*60)
    print("TEST 1: HDLC Codec (CRC, Bit Stuffing, NRZI)")
    print("="*60)
    
    # Test AX.25 frame
    test_frame = b'\x82\xa0\xa4\x60\x9c\x84\x62\x81\x03\xf0SP5ME-1>APWW11,WIDE1-1:/150732h5225.50NE02101.21E^270/012/A=001234'
    
    print(f"Original frame: {len(test_frame)} bytes")
    print(f"  Data: {test_frame}")
    
    # Encode
    encoder = HDLCEncoder()
    bits = encoder.encode_frame(test_frame)
    
    print(f"Encoded to: {len(bits)} bits (NRZI + bit stuffing + CRC)")
    print(f"  First 32 bits: {bits[:32]}")
    print(f"  Last 32 bits: {bits[-32:]}")
    
    # Decode
    decoder = HDLCDecoder()
    decoded, crc_valid = decoder.decode_bits(bits)
    
    print(f"Decoded: {len(decoded)} bytes, CRC: {'OK' if crc_valid else 'FAIL'}")
    print(f"  Data matches: {'YES' if decoded == test_frame else 'NO'}")
    
    if decoded == test_frame:
        print("[OK] HDLC Codec Test: PASSED")
        return True
    else:
        print("[FAIL] HDLC Codec Test: FAILED")
        print(f"  Expected: {test_frame}")
        print(f"  Got:      {decoded}")
        return False


def test_afsk_modem():
    """Test AFSK modulation/demodulation"""
    print("\n" + "="*60)
    print("TEST 2: AFSK Modem (1200/2200 Hz, 1200 bps)")
    print("="*60)
    
    # Test bit pattern
    test_bits = [1, 0, 1, 1, 0, 0, 1, 0] * 10  # Repeat pattern (80 bits)
    
    print(f"Test bits: {test_bits[:16]}... (80 bits total)")
    
    # Modulate
    modulator = AFSKModulator(sample_rate=44100)
    audio = modulator.modulate(test_bits, amplitude=0.3)
    
    print(f"Modulated to: {len(audio)} audio samples @ 44100 Hz")
    print(f"  Amplitude range: [{audio.min():.3f}, {audio.max():.3f}]")
    print(f"  Duration: {len(audio)/44100:.3f} seconds")
    
    # Demodulate
    demodulator = AFSKDemodulator(sample_rate=44100)
    recovered_bits = demodulator.demodulate(audio)
    
    print(f"Demodulated to: {len(recovered_bits)} bits")
    print(f"  First 16 bits: {recovered_bits[:16]}")
    
    # Check accuracy
    errors = sum(1 for a, b in zip(test_bits, recovered_bits) if a != b)
    error_rate = errors / len(test_bits) * 100
    
    print(f"  Bit errors: {errors}/{len(test_bits)} ({error_rate:.1f}%)")
    
    if error_rate == 0:
        print("[OK] AFSK Modem Test: PASSED (100% accuracy)")
        return True
    elif error_rate < 5:
        print(f"[WARN] AFSK Modem Test: MARGINAL ({error_rate:.1f}% errors)")
        return True
    else:
        print(f"[FAIL] AFSK Modem Test: FAILED ({error_rate:.1f}% errors)")
        return False


def test_full_chain():
    """Test full TX/RX chain: KISS -> HDLC -> AFSK -> AFSK -> HDLC -> KISS"""
    print("\n" + "="*60)
    print("TEST 3: Full TX/RX Chain (HDLC -> AFSK -> Demod -> HDLC)")
    print("="*60)
    
    # Original AX.25 frame (simulated KISS data)
    original_frame = b'\x82\xa0\xa4\x60\x9c\x84\x62\x81\x03\xf0Test APRS Data'
    
    print(f"1. Original frame (from KISS): {len(original_frame)} bytes")
    
    # STEP 1: HDLC Encode (TX side)
    print("\n2. HDLC Encoding (TX)...")
    encoder = HDLCEncoder()
    hdlc_bits = encoder.encode_frame(original_frame)
    print(f"   → {len(hdlc_bits)} bits (with NRZI + bit stuffing + CRC)")
    
    # STEP 2: AFSK Modulate (TX side)
    print("\n3. AFSK Modulation (TX)...")
    modulator = AFSKModulator(sample_rate=44100)
    audio = modulator.modulate(hdlc_bits, amplitude=0.3)
    print(f"   → {len(audio)} audio samples")
    
    # Add some noise simulation (optional)
    noise_level = 0.01
    noise = np.random.normal(0, noise_level, len(audio))
    audio_with_noise = audio + noise
    print(f"   → Added noise (σ={noise_level}) for realistic test")
    
    # STEP 3: AFSK Demodulate (RX side)
    print("\n4. AFSK Demodulation (RX)...")
    demodulator = AFSKDemodulator(sample_rate=44100)
    recovered_bits = demodulator.demodulate(audio_with_noise)
    print(f"   → Recovered {len(recovered_bits)} bits")
    
    # STEP 4: HDLC Decode (RX side)
    print("\n5. HDLC Decoding (RX)...")
    decoder = HDLCDecoder()
    recovered_frame, crc_valid = decoder.decode_bits(recovered_bits)
    print(f"   → {len(recovered_frame)} bytes")
    print(f"   → CRC: {'✓ VALID' if crc_valid else '✗ INVALID'}")
    
    # Check result
    print("\n6. Verification:")
    print(f"   Original length: {len(original_frame)} bytes")
    print(f"   Recovered length: {len(recovered_frame)} bytes")
    print(f"   Data match: {'✓ YES' if recovered_frame == original_frame else '✗ NO'}")
    print(f"   CRC valid: {'✓ YES' if crc_valid else '✗ NO'}")
    
    if recovered_frame == original_frame and crc_valid:
        print("\n[OK] Full Chain Test: PASSED")
        return True
    else:
        print("\n[FAIL] Full Chain Test: FAILED")
        if recovered_frame != original_frame:
            print(f"   Data mismatch:")
            print(f"     Expected: {original_frame[:50]}")
            print(f"     Got:      {recovered_frame[:50]}")
        return False


def main():
    print("\n" + "="*70)
    print("TNC-APP: Integration Test - HDLC + AFSK Modem")
    print("="*70)
    
    results = []
    
    try:
        # Test 1: HDLC Codec
        results.append(("HDLC Codec", test_hdlc_codec()))
        
        # Test 2: AFSK Modem
        results.append(("AFSK Modem", test_afsk_modem()))
        
        # Test 3: Full Chain
        results.append(("Full Chain", test_full_chain()))
        
    except Exception as e:
        print(f"\n[ERROR] Test Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {name:.<40} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests PASSED! TNC modem is ready.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Need to fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
