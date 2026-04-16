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
        self.nrzi_state = 0     # Current NRZI state (0 or 1)
    
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
        self.nrzi_state = 0
        
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
        
        logger.debug(f"[HDLC] Encoded frame: {len(ax25_data)} data bytes + CRC → {len(bits)} bits")
        return bits
    
    def _send_control_byte(self, byte: int) -> List[int]:
        """
        Send control byte (FLAG) with NRZI but NO bit stuffing
        Bits sent LSB first
        """
        bits = []
        for i in range(8):
            bit = (byte >> i) & 1
            bits.append(self._nrzi_encode_bit(bit))
        
        # Reset stuff counter after flags
        self.stuff_counter = 0
        return bits
    
    def _send_data_byte(self, byte: int) -> List[int]:
        """
        Send data byte with NRZI and bit stuffing
        Bits sent LSB first
        
        Bit stuffing: If 5 consecutive 1 bits are sent, insert a 0 bit
        """
        bits = []
        for i in range(8):
            bit = (byte >> i) & 1
            
            # Send the bit
            bits.append(self._nrzi_encode_bit(bit))
            
            # Count consecutive 1 bits for stuffing
            if bit == 1:
                self.stuff_counter += 1
                if self.stuff_counter == 5:
                    # Insert stuff bit (0)
                    bits.append(self._nrzi_encode_bit(0))
                    self.stuff_counter = 0
            else:
                self.stuff_counter = 0
        
        return bits
    
    def _nrzi_encode_bit(self, bit: int) -> int:
        """
        NRZI encoding:
        - 1 bit: no state change
        - 0 bit: state change (invert)
        
        Returns: NRZI-encoded bit (output state)
        """
        if bit == 0:
            # Invert state
            self.nrzi_state = 1 - self.nrzi_state
        
        return self.nrzi_state


class HDLCDecoder:
    """
    Decodes HDLC bitstream (NRZI) back to AX.25 frames
    
    Process:
    1. NRZI decode bits
    2. Find START FLAG (0x7E)
    3. Collect data with bit destuffing
    4. Find END FLAG
    5. Verify CRC
    """
    
    def __init__(self):
        self.bit_buffer = []
        self.nrzi_state = 0
    
    def decode_bits(self, nrzi_bits: List[int]) -> Tuple[bytes, bool]:
        """
        Decode NRZI bitstream to AX.25 frame
        
        Args:
            nrzi_bits: NRZI-encoded bits (0 and 1)
            
        Returns:
            Tuple of (AX.25 bytes, is_valid_crc)
        """
        # NRZI decode
        raw_bits = []
        for nrzi_bit in nrzi_bits:
            raw_bits.append(self._nrzi_decode_bit(nrzi_bit))
        
        # Find and extract frame between flags
        frame_bits = self._find_frame(raw_bits)
        
        if not frame_bits:
            logger.warning("[HDLC] No valid frame found")
            return b'', False
        
        # Convert bits to bytes (LSB first)
        frame_bytes = self._bits_to_bytes(frame_bits)
        
        if len(frame_bytes) < 2:
            logger.warning("[HDLC] Frame too short")
            return b'', False
        
        # Extract CRC (last 2 bytes) and data
        data = frame_bytes[:-2]
        received_crc = frame_bytes[-2] | (frame_bytes[-1] << 8)
        
        # Calculate expected CRC
        expected_crc = CRC16CCITT.calculate(data)
        
        # Verify CRC
        is_valid = received_crc == expected_crc
        
        if not is_valid:
            logger.error(f"[HDLC] CRC mismatch: received {received_crc:04x}, expected {expected_crc:04x}")
        else:
            logger.debug(f"[HDLC] Frame decoded: {len(data)} bytes, CRC valid")
        
        return data, is_valid
    
    def _nrzi_decode_bit(self, nrzi_bit: int) -> int:
        """
        NRZI decode:
        Encoding was:
        - 1 bit → no state change
        - 0 bit → state change (invert)
        
        So decoding is reverse:
        - If state changed (nrzi_bit != nrzi_state): sent 0
        - If state same (nrzi_bit == nrzi_state): sent 1
        """
        bit = 1 if nrzi_bit == self.nrzi_state else 0
        self.nrzi_state = nrzi_bit
        return bit
    
    def _find_frame(self, raw_bits: List[int]) -> List[int]:
        """
        Find frame between START and END flags (0x7E = 01111110)
        
        Challenge: FLAGS contain 6 consecutive 1 bits (unique signature), but
        bit stuffing is inserted before END FLAG if data ends with 5 consecutive 1s.
        
        Strategy: Look for flag signature (6 consecutive 1 bits surrounded by 0s)
        while accounting for bit stuffing.
        """
        # Find START FLAG: look for pattern with 6 consecutive 1s
        start_idx = self._find_flag_start(raw_bits)
        
        if start_idx == -1:
            logger.warning(f"[HDLC] START FLAG not found in {len(raw_bits)} bits")
            return []
        
        logger.debug(f"[HDLC] Found START FLAG at bit {start_idx}")
        
        # Extract frame and find END FLAG while destuffing
        frame_bits = []
        i = start_idx + 8  # Start after START FLAG
        
        while i < len(raw_bits):
            # Check if we're at END FLAG location
            # END FLAG can be preceded by stuff bit if data ends with 5 ones
            if self._is_flag_at_position(raw_bits, i):
                logger.debug(f"[HDLC] Found END FLAG at bit {i}, extracted {len(frame_bits)} frame bits")
                return frame_bits
            
            # Destuff: if we see 5 consecutive 1s, skip the 0 that follows (stuff bit)
            if len(frame_bits) >= 5 and all(frame_bits[-5 + j] == 1 for j in range(5)):
                # This is a stuff bit, skip it
                logger.debug(f"[HDLC] Destuffing: skipping stuff bit at raw position {i}")
                i += 1
            else:
                frame_bits.append(raw_bits[i])
                i += 1
        
        logger.warning(f"[HDLC] END FLAG not found after START FLAG")
        return []
    
    def _find_flag_start(self, raw_bits: List[int]) -> int:
        """Find START FLAG by looking for 6 consecutive 1 bits (unique to flags)"""
        # Look for pattern: something, then 6 consecutive 1s, then 0
        # FLAG = [0, 1, 1, 1, 1, 1, 1, 0] has pattern of 6 consecutive 1s
        for i in range(len(raw_bits) - 7):
            # Check for 6 consecutive 1 bits (bits 1-6 of the flag)
            if all(raw_bits[i + j] == 1 for j in range(1, 7)):
                # Check if preceded by 0 and followed by 0
                if (i == 0 or raw_bits[i - 1] == 0) and (i + 7 < len(raw_bits) and raw_bits[i + 7] == 0):
                    logger.debug(f"[HDLC] Flag pattern found at {i}: {raw_bits[max(0,i-1):min(len(raw_bits),i+8)]}")
                    return i - 1 if i > 0 else 0
        
        return -1
    
    def _is_flag_at_position(self, raw_bits: List[int], i: int) -> bool:
        """Check if position i contains a FLAG (possibly with stuff bit before it)"""
        # Check for normal flag pattern: [0, 1, 1, 1, 1, 1, 1, 0]
        if i + 7 < len(raw_bits):
            if (raw_bits[i:i+1] == [0] and 
                all(raw_bits[i+1+j] == 1 for j in range(6)) and 
                raw_bits[i+7] == 0):
                return True
        
        # Check for flag with preceding stuff bit: [0(stuff), 0, 1, 1, 1, 1, 1, 1, 0]
        # This happens when data before flag ends with 5 consecutive 1s
        if i > 0 and i + 7 < len(raw_bits):
            # If we see [0, 0, 1, 1, 1, 1, 1, 0] and position i-1 had 5 ones before it
            if (raw_bits[i:i+2] == [0, 0] and 
                all(raw_bits[i+2+j] == 1 for j in range(5)) and 
                raw_bits[i+7] == 0):
                # Verify that previous was stuff bit (after 5 ones)
                # This is harder to verify here, but we can return true and let caller handle it
                logger.debug(f"[HDLC] Found FLAG with potential stuff bit at position {i}")
                return True  # This is a flag preceded by stuff bit
        
        return False
    
    @staticmethod
    def _bits_to_bytes(bits: List[int]) -> bytes:
        """Convert bit list (LSB first) to bytes"""
        result = []
        for i in range(0, len(bits) - 7, 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits):
                    byte |= (bits[i + j] << j)
            result.append(byte)
        return bytes(result)


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
