"""
Zarządzanie konfiguracją aplikacji
"""

import json
import os
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Konfiguracja serwera"""
    enabled: bool
    host: str
    port: int


@dataclass
class DebugConfig:
    """Konfiguracja debugowania (APRS-IS Gateway)"""
    enabled: bool
    server: str
    port: int
    callsign: str
    passcode: str
    filter: str


@dataclass
class AppConfig:
    """Główna konfiguracja aplikacji"""
    kiss_server: ServerConfig
    window_title: str
    window_width: int
    window_height: int

    @classmethod
    def load(cls, config_path: str = "config.json") -> "AppConfig":
        """Załaduj konfigurację z pliku JSON"""
        # Jeśli relative path, szukaj w katalogu main.py
        if not os.path.isabs(config_path):
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Parent of src/
            config_path = os.path.join(script_dir, config_path)
        
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls.default()

        with open(config_path, 'r') as f:
            data = json.load(f)

        kiss_cfg = data.get('servers', {}).get('kiss', {})
        gui_cfg = data.get('gui', {})

        return cls(
            kiss_server=ServerConfig(
                enabled=kiss_cfg.get('enabled', True),
                host=kiss_cfg.get('host', '0.0.0.0'),
                port=kiss_cfg.get('port', 8001)
            ),
            window_title=gui_cfg.get('window_title', 'MicroKISStnc - Development'),
            window_width=gui_cfg.get('window_width', 900),
            window_height=gui_cfg.get('window_height', 600)
        )

    @classmethod
    def default(cls) -> "AppConfig":
        """Zwróć domyślną konfigurację"""
        return cls(
            kiss_server=ServerConfig(enabled=True, host='0.0.0.0', port=8001),
            window_title='MicroKISStnc - Development',
            window_width=900,
            window_height=600
        )
