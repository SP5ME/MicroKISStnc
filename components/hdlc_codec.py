"""
HDLC (High-Level Data Link Control) Codec
- Encoder: AX.25 bytes → HDLC frame (with flags, bit stuffing, CRC, NRZI)
- Decoder: HDLC bitstream → AX.25 bytes (reverse process)

Based on Direwolf's hdlc_send.c implementation
"""

import struct
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class CRC16CCITT:
    """CRC-16-CCITT calculator for AX.25 frames"""
    
    # CRC lookup table from RFC 1549
    CCITT_TABLE = [
        0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
        0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
        0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
        0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
        0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
        0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
        0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
        0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
        0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
        0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
        0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
        0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
        0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
        0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
        0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
        0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
        0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
        0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
        0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
        0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
        0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
        0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
        0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
        0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
        0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
        0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
        0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
        0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
        0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
        0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
        0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
        0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
    ]
    
    @staticmethod
    def calculate(data: bytes) -> int:
        """
        Calculate CRC-16-CCITT for AX.25 frame
        
        Args:
            data: Bytes to calculate CRC for (excluding flags)
            
        Returns:
            16-bit CRC value
        """
        crc = 0xffff
        
        for byte in data:
            crc = ((crc >> 8) ^ CRC16CCITT.CCITT_TABLE[(crc ^ byte) & 0xff])
        
        return crc ^ 0xffff


class HDLCEncoder:
    """
    Encodes AX.25 frames to HDLC bitstream with NRZI encoding
    
    Process:
    1. Add START FLAG (0x7E)
    2. Send data bytes with bit stuffing
    3. Calculate and append CRC-16-CCITT
    4. Add END FLAG (0x7E)
    5. NRZI encode all bits
    
    NRZI encoding:
    - 1 bit → no state change
    - 0 bit → state change (invert)
    """
    
    def __init__(self):
        self.stuff_counter = 0  # Count consecutive 1 bits
        # NOTE: NRZI encoding is now done in AFSK modulator, not here!
    
    def encode_frame(self, ax25_data: bytes) -> List[int]:
        """
        Encode AX.25 frame to HDLC bitstream with NRZI
        
        Args:
            ax25_data: AX.25 frame bytes (without flags)
            
        Returns:
            List of bits (0 and 1) NRZI-encoded
        """
        bits = []
        
        # START FLAG - no bit stuffing on flags
        bits.extend(self._send_control_byte(0x7E))
        self.stuff_counter = 0
        # NOTE: Do NOT reset nrzi_state here - it carries over from the flag!
        
        # DATA BYTES - with bit stuffing
        for byte in ax25_data:
            bits.extend(self._send_data_byte(byte))
        
        # CALCULATE CRC
        crc = CRC16CCITT.calculate(ax25_data)
        
        # Send CRC low byte first, then high byte (LSB first per AX.25)
        crc_low = crc & 0xFF
        crc_high = (crc >> 8) & 0xFF
        
        bits.extend(self._send_data_byte(crc_low))
        bits.extend(self._send_data_byte(crc_high))
        
        # END FLAG - no bit stuffing
        bits.extend(self._send_control_byte(0x7E))
        self.stuff_counter = 0
        # NOTE: nrzi_state carries over (but frame is done so doesn't matter)
        
        logger.debug(f"[HDLC] Encoded frame: {len(ax25_data)} data bytes + CRC → {len(bits)} bits")
        return bits
    
    def generate_preamble(self, num_flags: int = 15) -> List[int]:
        """
        Generate preamble as series of FLAG bytes (0x7E)
        
        Following Direwolf's layer2_preamble_postamble():
        - Preamble is FLAG bytes (0x7E)
        - NO bit stuffing on FLAG bytes
        - Returns RAW bits (0 and 1) - NRZI encoding done in AFSK modulator!
        
        Args:
            num_flags: Number of 0x7E flag bytes (default 15 = ~100ms @ 1200 baud)
                      15 flags * 8 bits = 120 bits
            
        Returns:
            List of raw bits (0 and 1 values)
        """
        bits = []
        
        for _ in range(num_flags):
            # Each FLAG byte (0x7E = 01111110 in binary, LSB first)
            bits.extend(self._send_control_byte(0x7E))
            # Reset bit stuffing counter (no bit stuffing on flags)
            self.stuff_counter = 0
        
        logger.debug(f"[HDLC] Generated preamble: {num_flags} FLAG bytes (0x7E) → {len(bits)} raw bits")
        return bits
    
    def _send_control_byte(self, byte: int) -> List[int]:
        """
        Send control byte (FLAG) with NO bit stuffing
        Returns RAW bits (0 and 1 values) - NRZI encoding done in AFSK modulator!
        Bits sent LSB first
        """
        bits = []
        for i in range(8):
            bit = (byte >> i) & 1
            bits.append(bit)  # Return raw bit, not NRZI-encoded
        
        # Reset stuff counter after flags
        self.stuff_counter = 0
        return bits
    
    def _send_data_byte(self, byte: int) -> List[int]:
        """
        Send data byte with bit stuffing
        Returns RAW bits (0 and 1 values) - NRZI encoding done in AFSK modulator!
        Bits sent LSB first
        
        Bit stuffing: If 5 consecutive 1 bits are sent, insert a 0 bit
        """
        bits = []
        for i in range(8):
            bit = (byte >> i) & 1
            
            # Send the raw bit
            bits.append(bit)
            
            # Count consecutive 1 bits for stuffing
            if bit == 1:
                self.stuff_counter += 1
                if self.stuff_counter == 5:
                    # Insert stuff bit (0)
                    bits.append(0)  # Raw 0, not NRZI-encoded
                    self.stuff_counter = 0
            else:
                self.stuff_counter = 0
        
        return bits
    
    # NOTE: NRZI encoding removed from HDLC encoder
    # It is now done in AFSK modulator (modulate_nrzi method)


class HDLCDecoder:
    """
    Decodes HDLC bitstream back to AX.25 frames
    
    Implementation based on Direwolf's hdlc_rec.c
    
    Process:
    1. NRZI decode: dbit = (raw == prev_raw)
    2. Shift pat_det (8-bit pattern detector), accumulate bits
    3. When pat_det == 0x7E: frame boundary (flag)
    4. Handle bit stuffing: when 5 ones followed by 0
    5. Accumulate bits into bytes (LSB first)
    6. Verify CRC when frame complete
    """
    
    def __init__(self, skip_nrzi=False, skip_crc_check=False):
        self.prev_raw = 1  # AFSK idles at mark (1200 Hz) = raw 1
        self.skip_nrzi = skip_nrzi  # If True, skip NRZI decoding (bits already decoded)
        self.skip_crc_check = skip_crc_check  # If True, accept frames without CRC validation (for testing)
        self.pat_det = 0
        self.oacc = 0
        self.olen = 0
        self.frame_buf = []
        self.in_frame = False  # Have we seen START flag?
        self.frames_found = []  # Accumulated completed frames from streaming decoding
    
    def decode_bits(self, raw_bits: List[int]) -> Tuple[bytes, bool]:
        """
        Decode raw bits to AX.25 frame (following Direwolf algorithm)
        
        Streaming state machine:
        1. IDLE: looking for START FLAG (0x7E)
        2. IN_FRAME: collecting data after START FLAG, with destuffing
        3. When END FLAG (0x7E) found: validate frame and reset
        
        Args:
            raw_bits: Raw bits from demodulator (0 or 1)
            
        Returns:
            Tuple of (frame_data, is_valid_crc)
        """
        # NOTE: State is maintained between calls for streaming decoding
        # Reset only happens when frame completes or on abort pattern
        
        # Process each bit
        for bit_idx, raw in enumerate(raw_bits):
            # NRZI decode: if same as previous → bit=1, if different → bit=0
            # UNLESS skip_nrzi is True (bits already decoded)
            if self.skip_nrzi:
                dbit = raw  # Use raw bit directly
            else:
                dbit = (raw == self.prev_raw)
                self.prev_raw = raw
            
            # Shift pattern detector right and insert new bit at MSB
            self.pat_det >>= 1
            if dbit:
                self.pat_det |= 0x80
            
            # Check for abort pattern: 7 ones in a row (0xFE = 11111110)
            if self.pat_det == 0xfe:
                logger.debug(f"[HDLC] Abort pattern detected at bit {bit_idx}")
                self._reset()
                continue
            
            # Check for frame boundary: flag pattern 0x7E (01111110)
            if self.pat_det == 0x7e:
                if self.in_frame:
                    # END FLAG - we have a complete frame
                    logger.info(f"[HDLC] END FLAG detected at bit {bit_idx}, frame_len={len(self.frame_buf)}, olen={self.olen}")
                    frame_with_partial = self.frame_buf + ([self.oacc] if self.olen > 0 else [])
                    logger.info(f"[HDLC]   Full frame: {bytes(frame_with_partial).hex()}")
                    logger.info(f"[HDLC]   NRZI raw bits in pat_det: {self.pat_det:08b}")
                    
                    # Validate frame (discard any partial byte olen bits - those are part of END FLAG)
                    if len(self.frame_buf) >= 2:
                        result = self._validate_frame()
                        self._reset()
                        return result
                    
                    # Otherwise, malformed frame - reset and look for next START
                    logger.debug(f"[HDLC] Incomplete frame (len={len(self.frame_buf)})")
                    self._reset()
                else:
                    # START FLAG - enter frame collection mode
                    logger.debug(f"[HDLC] START FLAG detected at bit {bit_idx}")
                    self.in_frame = True
                    self.frame_buf = []  # Reset frame buffer for new frame
                    self.oacc = 0
                    self.olen = 0
                
                continue
            
            # Only collect data if we're in a frame (after START FLAG)
            if not self.in_frame:
                continue
            
            # Check for bit stuffing: 5 ones followed by 0
            # (pat_det >> 2) == 0x1F means bits [7:2] are 011111 (5 ones before current 0)
            if not dbit and (self.pat_det >> 2) == 0x1f:
                logger.debug(f"[HDLC] Bit stuff detected at bit {bit_idx}, skipping (pat_det={self.pat_det:08b})")
                continue
            
            # Accumulate bits into bytes
            self.oacc >>= 1
            if dbit:
                self.oacc |= 0x80
            
            self.olen += 1
            
            if self.olen == 1 or self.olen == 8:
                logger.debug(f"[HDLC] Bit {bit_idx}: dbit={dbit}, olen={self.olen}, pat_det={self.pat_det:08b}, oacc={self.oacc:08b}")
            
            # When we have 8 bits, store byte in frame
            if self.olen == 8:
                self.olen = 0
                if len(self.frame_buf) < 1000:  # Prevent buffer overflow
                    self.frame_buf.append(self.oacc)
        
        # End of bit stream - no complete frame found
        return b'', False
    
    def _reset(self):
        """Reset decoder state for next frame"""
        self.prev_raw = 1  # AFSK idles at mark (1200 Hz) = raw 1
        self.pat_det = 0
        self.oacc = 0
        self.olen = 0
        self.frame_buf = []
        self.in_frame = False
    
    def _validate_frame(self) -> Tuple[bytes, bool]:
        """Validate frame CRC and return result"""
        if len(self.frame_buf) < 2:
            return b'', False
        
        frame_bytes = bytes(self.frame_buf)
        
        # Extract CRC (last 2 bytes) - Low byte first (AX.25 format)
        received_crc = frame_bytes[-2] | (frame_bytes[-1] << 8)
        
        # Data is everything except CRC
        data = frame_bytes[:-2]
        
        # Calculate expected CRC
        expected_crc = CRC16CCITT.calculate(data)
        
        # Verify (or skip if testing)
        is_valid = self.skip_crc_check or (received_crc == expected_crc)
        
        if is_valid:
            logger.info(f"[HDLC] ✓ FRAME DECODED: {len(data)} bytes, CRC valid")
            logger.info(f"  Data: {data.hex()}")
        else:
            logger.debug(f"[HDLC] CRC mismatch: received {received_crc:04x}, expected {expected_crc:04x}, data_len={len(data)}")
            logger.debug(f"  Frame hex: {frame_bytes.hex()}")
            logger.debug(f"  Data hex: {data.hex()}")
        
        return data, is_valid


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test data
    test_frame = b'\x82\xa0\xa4\x60\x9c\x84\x62\x81\x03\xf0Test Data'
    
    # Encode
    encoder = HDLCEncoder()
    bits = encoder.encode_frame(test_frame)
    print(f"Encoded {len(test_frame)} bytes to {len(bits)} bits")
    print(f"First 32 bits: {bits[:32]}")
    
    # Decode
    decoder = HDLCDecoder()
    decoded, crc_valid = decoder.decode_bits(bits)
    
    print(f"Decoded: {len(decoded)} bytes")
    print(f"CRC valid: {crc_valid}")
    print(f"Data matches: {decoded == test_frame}")
