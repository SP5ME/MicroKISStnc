"""
Builder do tworzenia prawidłowych ramek KISS na podstawie TNC2
"""

import logging

logger = logging.getLogger(__name__)


class KISSBuilder:
    """Buduj prawidłowe ramki KISS z TNC2"""
    
    FEND = 0xC0
    FESC = 0xDB
    TFEND = 0xDC
    TFESC = 0xDD
    
    KISS_CMD_DATA_FRAME = 0
    
    @staticmethod
    def encode_callsign(callsign: str) -> bytes:
        """Koduj callsign w formacie AX.25 (7 bajtów)"""
        # Jeśli nie ma SSID, użyj -0
        if '-' not in callsign:
            callsign = callsign + '-0'
        
        call, ssid = callsign.split('-')
        
        # Pad callsign do 6 bajtów
        call = call.ljust(6, ' ')
        
        # Shift left o 1 bit (standard AX.25)
        encoded = bytearray()
        for c in call[:6]:
            encoded.append(ord(c) << 1)
        
        # SSID byte: ssid<<1 | 0x60 (address field bit) | has_more_bit
        ssid_byte = (int(ssid) << 1) | 0x60
        encoded.append(ssid_byte)
        
        return bytes(encoded)
    
    @staticmethod
    def build_ax25_from_tnc2(from_call: str, to_call: str, info: str) -> bytes:
        """Zbuduj AX.25 ramkę z TNC2 danych
        
        Uproszczona wersja - bierze jedno-hop format
        Format: [7 bytes destination] [7 bytes source] [1 byte control] [1 byte PID] [payload]
        """
        try:
            # Destination
            dest_bytes = KISSBuilder.encode_callsign(to_call)
            
            # Source (ostatni element w path - ma set EndOfAddress bit)
            src_bytes = bytearray(KISSBuilder.encode_callsign(from_call))
            src_bytes[6] |= 0x01  # Set End of Address bit
            
            # Control field: 0x03 (UNNUM INFORMATION)
            control = 0x03
            
            # PID: 0xF0 (no layer 3)
            pid = 0xF0
            
            # Payload
            payload = info.encode('latin-1', errors='replace')
            
            # Złóż całą ramkę
            frame = dest_bytes + bytes(src_bytes) + bytes([control, pid]) + payload
            
            logger.debug(f"AX.25 frame built: {len(frame)} bytes")
            return frame
        
        except Exception as e:
            logger.error(f"Error building AX.25 frame: {e}")
            return None
    
    @staticmethod
    def encapsulate_kiss(frame_data: bytes, channel: int = 0, cmd: int = 0) -> bytes:
        """Enkapsuluj ramkę AX.25 w KISS format"""
        try:
            # Command byte: (channel<<4) | cmd
            cmd_byte = (channel << 4) | cmd
            
            # Początkowe dane: [cmd_byte] + [frame_data]
            data = bytes([cmd_byte]) + frame_data
            
            # Escape i dodaj FEND
            result = bytearray([KISSBuilder.FEND])
            
            for byte in data:
                if byte == KISSBuilder.FEND:
                    result.append(KISSBuilder.FESC)
                    result.append(KISSBuilder.TFEND)
                elif byte == KISSBuilder.FESC:
                    result.append(KISSBuilder.FESC)
                    result.append(KISSBuilder.TFESC)
                else:
                    result.append(byte)
            
            result.append(KISSBuilder.FEND)
            
            logger.debug(f"KISS encapsulation: {len(data)} bytes -> {len(result)} bytes")
            return bytes(result)
        
        except Exception as e:
            logger.error(f"Error encapsulating KISS frame: {e}")
            return None
    
    @staticmethod
    def tnc2_to_kiss(tnc2_line: str) -> bytes:
        """Konwertuj TNC2 linię do KISS ramki"""
        try:
            # Parsuj TNC2: SOURCE>DEST,PATH:DATA
            if ':' not in tnc2_line:
                return None
            
            header_part, info_part = tnc2_line.split(':', 1)
            
            if '>' not in header_part:
                return None
            
            from_call, dest_and_path = header_part.split('>', 1)
            path_parts = dest_and_path.split(',')
            to_call = path_parts[0] if path_parts else ''
            
            # Zbuduj AX.25
            ax25_frame = KISSBuilder.build_ax25_from_tnc2(from_call, to_call, info_part)
            if not ax25_frame:
                return None
            
            # Enkapsuluj w KISS
            kiss_frame = KISSBuilder.encapsulate_kiss(ax25_frame)
            
            logger.info(f"TNC2->KISS: {from_call} > {to_call}, AX.25={len(ax25_frame)} bytes, KISS={len(kiss_frame)} bytes")
            return kiss_frame
        
        except Exception as e:
            logger.error(f"Error converting TNC2 to KISS: {e}", exc_info=True)
            return None
