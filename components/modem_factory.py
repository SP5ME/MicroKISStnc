#!/usr/bin/env python3
"""
Modem profile registry and factory helpers.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModemProfile:
    modem_id: str
    label: str
    modulation: str
    bit_rate: int
    tx_mark_hz: float
    tx_space_hz: float
    rx_mark_hz: float
    rx_space_hz: float
    description: str = ""

    @property
    def shift_hz(self) -> float:
        return abs(float(self.tx_space_hz) - float(self.tx_mark_hz))

    def summary(self) -> str:
        return (
            f"{self.label} ({self.bit_rate} baud, "
            f"mark {int(self.tx_mark_hz)} Hz / space {int(self.tx_space_hz)} Hz)"
        )


class ModemFactory:
    DEFAULT_MODEM_ID = "bell202_1200"

    _PROFILES: Dict[str, ModemProfile] = {
        "bell202_1200": ModemProfile(
            modem_id="bell202_1200",
            label="AFSK1200bd (VHF/UHF)",
            modulation="afsk",
            bit_rate=1200,
            tx_mark_hz=1200,
            tx_space_hz=2200,
            rx_mark_hz=1200,
            rx_space_hz=2200,
            description="AFSK1200bd modem profile for APRS VHF/UHF.",
        ),
        "hf_aprs_300_soundmodem": ModemProfile(
            modem_id="hf_aprs_300_soundmodem",
            label="AFSK 300bd (HF)",
            modulation="afsk",
            bit_rate=300,
            tx_mark_hz=1800,
            tx_space_hz=1600,
            rx_mark_hz=1800,
            rx_space_hz=1600,
            description="AFSK 300bd HF profile compatible with Soundmodem.",
        ),
    }

    @classmethod
    def get_profile(cls, modem_id: Optional[str]) -> ModemProfile:
        normalized = str(modem_id or cls.DEFAULT_MODEM_ID).strip().lower()
        return cls._PROFILES.get(normalized, cls._PROFILES[cls.DEFAULT_MODEM_ID])

    @classmethod
    def list_profiles(cls) -> List[ModemProfile]:
        return list(cls._PROFILES.values())

    @classmethod
    def is_known(cls, modem_id: Optional[str]) -> bool:
        return str(modem_id or "").strip().lower() in cls._PROFILES
