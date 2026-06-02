"""
System Volume Monitor - Reads Windows system volume and applies to TX/RX
Uses pycaw (Python Core Audio Windows) to get Master Volume level
"""

import logging
import threading
from typing import Callable, Optional

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    AudioUtilities = None
    ISimpleAudioVolume = None

logger = logging.getLogger(__name__)


class SystemVolumeMonitor:
    """Monitor system volume and notify on changes"""
    
    def __init__(self, callback: Optional[Callable[[float], None]] = None, poll_interval: float = 0.5):
        """
        Args:
            callback: Function to call when volume changes: callback(volume: 0.0-1.0)
            poll_interval: How often to check volume (seconds)
        """
        self.callback = callback
        self.poll_interval = poll_interval
        self.current_volume = 0.8  # Default
        self.last_reported_volume = -1  # Force first update
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        if PYCAW_AVAILABLE:
            logger.info("[VOLUME] pycaw available - system volume monitoring enabled")
            self._read_system_volume()
        else:
            logger.warning("[VOLUME] pycaw not available - using default 0.8")
    
    def _read_system_volume(self) -> float:
        """Read current system master volume (0.0 to 1.0)"""
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                volume = session.SimpleAudioVolume
                if volume:
                    current_vol = volume.GetMasterVolume()
                    return min(max(current_vol, 0.0), 1.0)  # Clamp to [0, 1]
        except Exception as e:
            logger.debug(f"[VOLUME] Could not read system volume: {e}")
        
        return self.current_volume
    
    def get_volume(self) -> float:
        """Get current volume level (0.0 to 1.0)"""
        if PYCAW_AVAILABLE:
            self.current_volume = self._read_system_volume()
        return self.current_volume
    
    def start_monitoring(self):
        """Start background thread to monitor volume changes"""
        if not PYCAW_AVAILABLE:
            logger.debug("[VOLUME] Monitoring skipped - pycaw not available")
            return
        
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("[VOLUME] Monitoring started")
    
    def stop_monitoring(self):
        """Stop volume monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        logger.debug("[VOLUME] Monitoring stopped")
    
    def _monitor_loop(self):
        """Background thread loop - checks volume periodically"""
        while self.running:
            try:
                current = self.get_volume()
                
                # Only trigger callback if volume changed significantly (>2% change)
                if abs(current - self.last_reported_volume) > 0.02:
                    self.last_reported_volume = current
                    if self.callback:
                        self.callback(current)
                    logger.debug(f"[VOLUME] System volume changed: {current:.2%}")
                
                threading.Event().wait(self.poll_interval)
            except Exception as e:
                logger.debug(f"[VOLUME] Monitor error: {e}")
                threading.Event().wait(self.poll_interval)
