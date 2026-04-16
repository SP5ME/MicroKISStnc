"""
Parser pakietów APRS i AX.25
"""

import struct
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AX25Frame:
    """Reprezentacja ramki AX.25"""
    def __init__(self):
        self.destination = ""
        self.source = ""
        self.digipeaters: List[str] = []
        self.control = 0
        self.pid = 0
        self.info = b""
        self.fcs = 0
        self.raw_data = b""

    def __repr__(self) -> str:
        return f"AX25Frame(src={self.source}, dst={self.destination}, info_len={len(self.info)})"


class KISSFrame:
    """Reprezentacja ramki KISS"""
    def __init__(self):
        self.command = 0
        self.data = b""
        self.raw_data = b""

    @staticmethod
    def parse(data: bytes) -> Optional["KISSFrame"]:
        """Parsuj ramkę KISS"""
        if len(data) < 2:
            return None

        frame = KISSFrame()
        frame.raw_data = data

        # KISS frame format: FEND CMD DATA FEND
        # FEND = 0xC0
        if data[0] != 0xC0:
            return None

        # Szukamy drugiego FEND
        end_idx = data.find(0xC0, 1)
        if end_idx == -1:
            return None

        frame.command = data[1] & 0x0F
        frame.data = unescape_kiss(data[2:end_idx])
        
        return frame

    def __repr__(self) -> str:
        cmd_names = {0: "DATA", 1: "TXDELAY", 2: "PERSISTENCE", 3: "SLOT_TIME", 4: "TX_TAIL"}
        cmd_name = cmd_names.get(self.command, f"CMD_{self.command}")
        return f"KISSFrame(cmd={cmd_name}, data_len={len(self.data)})"


class AGWPEFrame:
    """Reprezentacja ramki AGWPE - oparta na direwolf agwlib.c"""
    def __init__(self):
        self.port = 0
        self.datakind = ""  # Command letter (R, m, etc.) - 1 bajt
        self.pid = 0        # Protocol ID
        self.call_from = ""
        self.call_to = ""
        self.data = b""
        self.raw_data = b""

    @staticmethod
    def parse(data: bytes) -> Optional["AGWPEFrame"]:
        """
        Parsuj ramkę AGWPE (36-byte header + payload)
        Struktura nagłówka (jak w direwolf agwlib.c):
        - Offset 0: Port (1 byte)
        - Offset 1-3: Reserved (3 bytes)
        - Offset 4: DataKind (1 byte)
        - Offset 5: Reserved (1 byte)
        - Offset 6: PID (1 byte)
        - Offset 7: Reserved (1 byte)
        - Offset 8: CallFrom (10 bytes, string)
        - Offset 18: CallTo (10 bytes, string)
        - Offset 28: DataLength (4 bytes, int, little-endian)
        - Offset 32: UserReserved (4 bytes, int, little-endian)
        """
        if len(data) < 36:
            return None

        try:
            frame = AGWPEFrame()
            frame.raw_data = data
            
            # Parse header (direwolf-compatible)
            frame.port = data[0]  # 1 byte
            frame.datakind = chr(data[4])  # 1 byte
            frame.pid = data[6]  # 1 byte
            
            # Extract callsigns (10 bytes each, null-terminated strings)
            call_from = data[8:18].rstrip(b'\x00').decode('ascii', errors='ignore').strip()
            call_to = data[18:28].rstrip(b'\x00').decode('ascii', errors='ignore').strip()
            
            frame.call_from = call_from
            frame.call_to = call_to
            
            # Extract data length (4 bytes, little-endian)
            data_len = struct.unpack('<I', data[28:32])[0]
            # data[32:36] = user_reserved (4 bytes, little-endian int)
            
            # Extract payload data
            if len(data) >= 36 + data_len:
                frame.data = data[36:36 + data_len]
            
            return frame
        except Exception as e:
            logger.error(f"Error parsing AGWPE frame: {e}")
            return None

    def __repr__(self) -> str:
        return f"AGWPEFrame(cmd='{self.datakind}', port={self.port}, from={self.call_from}, to={self.call_to}, data_len={len(self.data)})"


class APRSPacket:
    """Reprezentacja zdekodowanego pakietu APRS"""
    def __init__(self):
        self.source = ""
        self.destination = ""
        self.digipeaters: List[str] = []
        self.timestamp = datetime.now()
        self.data_type = ""
        self.payload = ""
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.raw_ax25 = ""

    def __repr__(self) -> str:
        return f"APRSPacket(src={self.source}, type={self.data_type}, pos={self.latitude},{self.longitude})"

    def to_readable(self) -> str:
        """Zwróć czytelny format pakietu"""
        lines = [
            f"═══════════════════════════════════════",
            f"TIMESTAMP: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}",
            f"SOURCE:    {self.source}",
            f"DEST:      {self.destination}",
            f"DIGIPEATERS: {' -> '.join(self.digipeaters) if self.digipeaters else '(none)'}",
            f"TYPE:      {self.data_type}",
            f"PAYLOAD:   {self.payload[:100]}{'...' if len(self.payload) > 100 else ''}",
        ]
        if self.latitude is not None and self.longitude is not None:
            lines.append(f"POSITION:  {self.latitude:.6f}, {self.longitude:.6f}")
        lines.append(f"═══════════════════════════════════════")
        return "\n".join(lines)


def unescape_kiss(data: bytes) -> bytes:
    """Unescape KISS escaped bytes"""
    result = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xDB:  # FESC
            if i + 1 < len(data):
                if data[i + 1] == 0xDC:  # TFEND
                    result.append(0xC0)
                    i += 2
                elif data[i + 1] == 0xDD:  # TFESC
                    result.append(0xDB)
                    i += 2
                else:
                    result.append(data[i])
                    i += 1
            else:
                result.append(data[i])
                i += 1
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


def escape_kiss(data: bytes) -> bytes:
    """Escape bytes for KISS transmission"""
    result = bytearray()
    for byte in data:
        if byte == 0xC0:  # FEND
            result.extend([0xDB, 0xDC])
        elif byte == 0xDB:  # FESC
            result.extend([0xDB, 0xDD])
        else:
            result.append(byte)
    return bytes(result)


def parse_ax25_callsign(data: bytes, offset: int) -> tuple[str, int]:
    """Parsuj callsign z ramki AX.25"""
    if offset + 7 > len(data):
        return "", 7

    call_bytes = data[offset:offset+6]
    ssid_byte = data[offset+6]

    # Decode callsign (każdy bajt zawiera dwa ASCII znaki przesunięte o 1)
    callsign = ""
    for byte in call_bytes:
        char = chr(byte >> 1)
        if char != ' ':
            callsign += char

    # Parse SSID
    ssid = (ssid_byte >> 1) & 0x0F
    if ssid > 0:
        callsign += f"-{ssid}"

    return callsign, 7


def parse_ax25_frame(data: bytes) -> Optional[AX25Frame]:
    """Parsuj ramkę AX.25 z KISS payloadu"""
    if len(data) < 15:
        return None

    frame = AX25Frame()
    frame.raw_data = data
    offset = 0

    try:
        # Destination
        dest, _ = parse_ax25_callsign(data, offset)
        frame.destination = dest
        offset += 7

        # Source
        src, _ = parse_ax25_callsign(data, offset)
        frame.source = src
        offset += 7

        # Digipeaters
        while offset + 7 <= len(data):
            digi_byte = data[offset + 6]
            digi, _ = parse_ax25_callsign(data, offset)
            frame.digipeaters.append(digi)
            offset += 7

            # Check if this is the last digipeater (bit 0 of SSID byte set)
            if digi_byte & 0x01:
                break

        # Control and PID
        if offset < len(data):
            frame.control = data[offset]
            offset += 1

        if offset < len(data):
            frame.pid = data[offset]
            offset += 1

        # Info field
        if offset < len(data):
            frame.info = data[offset:]

        return frame

    except (IndexError, struct.error):
        return None


def parse_aprs_from_ax25(frame: AX25Frame) -> Optional[APRSPacket]:
    """Parsuj APRS packet z ramki AX.25"""
    if not frame.info:
        return None

    packet = APRSPacket()
    packet.source = frame.source
    packet.destination = frame.destination
    packet.digipeaters = frame.digipeaters
    packet.raw_ax25 = f"{frame.source}>{frame.destination}"
    if frame.digipeaters:
        packet.raw_ax25 += "," + ",".join(frame.digipeaters)

    try:
        info_str = frame.info.decode('utf-8', errors='replace')
        packet.payload = info_str

        # Ustal typ pakietu
        if len(info_str) > 0:
            first_char = info_str[0]
            packet.data_type = {
                '!': 'Position without timestamp',
                '/': 'Position with timestamp',
                '@': 'Position with timestamp (APRS)',
                '=': 'Status',
                '>': 'Status with timestamp',
                ':': 'Message',
                ';': 'Object',
                '\\': 'Item',
                '_': 'Weather',
                "'": 'Old Mic-E',
                '`': 'Mic-E current',
                '{': 'User-defined',
                '}': 'Third-party',
            }.get(first_char, f'Unknown ({first_char})')

        return packet

    except Exception as e:
        return None


def parse_aprs_from_agwpe_data(agwpe_data: bytes) -> Optional[APRSPacket]:
    """Parsuj APRS packet z surowych danych AGWPE"""
    # AGWPE dostarcza surowe dane AX.25, parsujemy je jak zwykły AX.25 frame
    ax25_frame = parse_ax25_frame(agwpe_data)
    if ax25_frame:
        return parse_aprs_from_ax25(ax25_frame)
    return None


def create_agwpe_frame(port: int = 0, datakind: str = '', call_from: str = '', 
                       call_to: str = '', data: bytes = b'', pid: int = 0) -> bytes:
    """
    Utwórz ramkę AGWPE do wysłania do klienta
    Struktura (direwolf-compatible, 36 bytes header):
    - Offset 0: Port (1 byte)
    - Offset 1-3: Reserved (3 bytes)
    - Offset 4: DataKind (1 byte)
    - Offset 5: Reserved (1 byte)
    - Offset 6: PID (1 byte)
    - Offset 7: Reserved (1 byte)
    - Offset 8-17: CallFrom (10 bytes)
    - Offset 18-27: CallTo (10 bytes)
    - Offset 28-31: DataLength (4 bytes, little-endian)
    - Offset 32-35: UserReserved (4 bytes, little-endian)
    """
    try:
        frame = bytearray(36)
        
        # Offset 0: Port (1 byte)
        frame[0] = port & 0xFF
        # Offset 1-3: Reserved (3 bytes) - leave as 0
        
        # Offset 4: DataKind (1 byte)
        frame[4] = ord(datakind[0]) if datakind else 0
        # Offset 5: Reserved
        # Offset 6: PID (1 byte)
        frame[6] = pid & 0xFF
        # Offset 7: Reserved
        
        # Offset 8-17: CallFrom (10 bytes, null-padded)
        call_from_bytes = call_from.encode('ascii')[:9]
        frame[8:8+len(call_from_bytes)] = call_from_bytes
        # Null padding from offset 8+len to 18
        
        # Offset 18-27: CallTo (10 bytes, null-padded)
        call_to_bytes = call_to.encode('ascii')[:9]
        frame[18:18+len(call_to_bytes)] = call_to_bytes
        # Null padding from offset 18+len to 28
        
        # Offset 28-31: DataLength (4 bytes, little-endian)
        struct.pack_into('<I', frame, 28, len(data))
        
        # Offset 32-35: UserReserved (4 bytes, little-endian) - default 0
        struct.pack_into('<I', frame, 32, 0)
        
        # Return header + data
        return bytes(frame) + data
    except Exception as e:
        logger.error(f"Error creating AGWPE frame: {e}")
        return b''
