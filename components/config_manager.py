#!/usr/bin/env python3
"""
Configuration Manager for MicroKISStnc Desktop App
Handles loading/saving settings to JSON config file
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration (JSON file-based)"""
    
    # Default config file location
    CONFIG_DIR = Path.home() / ".microkisstnc"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    
    # Default configuration values
    DEFAULT_CONFIG = {
        "audio": {
            "input_device": None,  # Will auto-detect
            "output_device": None,  # Will auto-detect
            "sample_rate": 44100,
            "channels": 1,
        },
        "ptt": {
            "mode": "disabled",  # disabled, vox, COM1, COM2, etc.
            "use_rts": False,
            "use_dts": False,
            "vox_delay_ms": 500,
            "vox_threshold": -40,  # dBFS
        },
        "kiss": {
            "port": 8001,
            "host": "0.0.0.0",
        },
        "ui": {
            "geometry": [100, 100, 1000, 800],  # x, y, width, height
            "monitor_buffer_size": 200,
        },
        "application": {
            "auto_start_rx": True,
            "auto_start_kiss": True,
            "config_ui_mode": "basic",
        }
    }
    
    def __init__(self):
        """Initialize config manager and load existing config"""
        self.config = self.DEFAULT_CONFIG.copy()
        self._ensure_config_dir()
        self._load_config()
    
    @staticmethod
    def _ensure_config_dir():
        """Create config directory if it doesn't exist"""
        try:
            ConfigManager.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[CONFIG] Could not create config dir: {e}")
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            if self.CONFIG_FILE.exists():
                with open(self.CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults (in case new keys were added)
                    self.config = self._deep_merge(self.DEFAULT_CONFIG, loaded_config)
                logger.info(f"[CONFIG] Loaded from {self.CONFIG_FILE}")
            else:
                logger.info(f"[CONFIG] No config file found, using defaults")
                self.config = self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"[CONFIG] Error loading config: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
    
    def save(self):
        """Save configuration to JSON file"""
        try:
            self._ensure_config_dir()
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"[CONFIG] Saved to {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"[CONFIG] Error saving config: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value using dot-notation path
        Example: get("audio.input_device") -> value
        """
        keys = key_path.split(".")
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """
        Set config value using dot-notation path
        Example: set("audio.input_device", "default")
        """
        keys = key_path.split(".")
        config = self.config
        
        try:
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            config[keys[-1]] = value
            logger.debug(f"[CONFIG] Set {key_path} = {value}")
        except Exception as e:
            logger.error(f"[CONFIG] Error setting {key_path}: {e}")
    
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """Deep merge override dict into base dict"""
        result = base.copy()
        
        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def to_dict(self) -> Dict:
        """Get entire config as dictionary"""
        return self.config.copy()
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
        logger.info("[CONFIG] Reset to defaults")


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.DEBUG)
    
    cfg = ConfigManager()
    print("\n=== Current Configuration ===")
    print(json.dumps(cfg.to_dict(), indent=2))
    
    print("\n=== Test get/set ===")
    print(f"KISS port: {cfg.get('kiss.port')}")
    cfg.set("kiss.port", 9001)
    print(f"After change: {cfg.get('kiss.port')}")
    
    print("\n=== Test save ===")
    cfg.save()
    print(f"Config saved to: {ConfigManager.CONFIG_FILE}")
