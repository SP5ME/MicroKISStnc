#!/usr/bin/env python3
"""
Audio Signal Monitor
Real-time monitoring of input/output signal levels
"""

import numpy as np
import logging
from collections import deque
from typing import Optional, Callable
from threading import Lock

logger = logging.getLogger(__name__)


class AudioMonitor:
    """Monitors and analyzes audio signal levels"""
    
    def __init__(self, buffer_size: int = 4410):  # ~100ms @ 44100 Hz
        """
        Initialize audio monitor
        
        Args:
            buffer_size: Number of samples to keep in RMS buffer
        """
        self.buffer_size = buffer_size
        self.sample_buffer = deque(maxlen=buffer_size)
        self.lock = Lock()
        
        # Statistics
        self.peak_level = 0.0  # -inf dBFS initially
        self.rms_level = 0.0   # dBFS
        self.peak_percentage = 0.0  # 0-100%
        self.rms_percentage = 0.0   # 0-100%
        
    def update(self, audio_samples: np.ndarray):
        """
        Update monitor with new audio samples
        
        Args:
            audio_samples: numpy array of audio samples (float32, range [-1.0, 1.0])
        """
        with self.lock:
            # Add samples to buffer
            for sample in audio_samples:
                self.sample_buffer.append(float(sample))
            
            # Calculate levels
            if len(self.sample_buffer) > 0:
                data = np.array(list(self.sample_buffer))
                
                # Peak level (absolute maximum)
                peak_linear = np.max(np.abs(data))
                self.peak_level = self._linear_to_dbfs(peak_linear)
                self.peak_percentage = min(100.0, peak_linear * 100.0)
                
                # RMS level
                rms_linear = np.sqrt(np.mean(data ** 2))
                self.rms_level = self._linear_to_dbfs(rms_linear)
                self.rms_percentage = min(100.0, rms_linear * 100.0)
    
    def get_peak_dbfs(self) -> float:
        """Get peak level in dBFS"""
        with self.lock:
            return self.peak_level
    
    def get_rms_dbfs(self) -> float:
        """Get RMS level in dBFS"""
        with self.lock:
            return self.rms_level
    
    def get_peak_percentage(self) -> float:
        """Get peak level as percentage (0-100)"""
        with self.lock:
            return self.peak_percentage
    
    def get_rms_percentage(self) -> float:
        """Get RMS level as percentage (0-100)"""
        with self.lock:
            return self.rms_percentage
    
    def get_all_levels(self) -> dict:
        """Get all level measurements"""
        with self.lock:
            return {
                "peak_dbfs": self.peak_level,
                "peak_pct": self.peak_percentage,
                "rms_dbfs": self.rms_level,
                "rms_pct": self.rms_percentage,
            }
    
    def reset(self):
        """Reset monitor to initial state"""
        with self.lock:
            self.sample_buffer.clear()
            self.peak_level = -96.0  # Quiet
            self.rms_level = -96.0
            self.peak_percentage = 0.0
            self.rms_percentage = 0.0
    
    @staticmethod
    def _linear_to_dbfs(linear_value: float) -> float:
        """
        Convert linear amplitude to dBFS (decibels relative to full scale)
        
        dBFS = 20 * log10(linear_value)
        """
        if linear_value <= 0:
            return -96.0  # Effectively silent
        
        dbfs = 20.0 * np.log10(max(linear_value, 1e-6))
        return max(-96.0, min(0.0, dbfs))  # Clamp to [-96, 0]


class AudioMeterDisplay:
    """Helper for displaying audio meter values"""
    
    @staticmethod
    def format_display(monitor: AudioMonitor) -> str:
        """Format audio levels for display"""
        levels = monitor.get_all_levels()
        
        peak_pct = levels["peak_pct"]
        rms_pct = levels["rms_pct"]
        peak_db = levels["peak_dbfs"]
        rms_db = levels["rms_dbfs"]
        
        # Create bar representation
        bar_peak = AudioMeterDisplay._make_bar(peak_pct)
        bar_rms = AudioMeterDisplay._make_bar(rms_pct)
        
        return (
            f"Peak: {bar_peak} {peak_pct:5.1f}% ({peak_db:6.1f} dBFS)\n"
            f"RMS:  {bar_rms} {rms_pct:5.1f}% ({rms_db:6.1f} dBFS)"
        )
    
    @staticmethod
    def _make_bar(percentage: float, width: int = 30) -> str:
        """Create visual bar for percentage value"""
        filled = int((percentage / 100.0) * width)
        empty = width - filled
        
        # Color coding (simple version)
        if percentage > 90:
            color = "🔴"  # Red - clipping risk
        elif percentage > 70:
            color = "🟡"  # Yellow - high
        else:
            color = "🟢"  # Green - normal
        
        bar = "█" * filled + "░" * empty
        return f"{color} [{bar}]"


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    monitor = AudioMonitor()
    
    # Simulate audio data
    print("=== Testing Audio Monitor ===\n")
    
    # Test 1: Quiet signal
    print("Test 1: Quiet signal (-60 dBFS)")
    quiet_signal = np.random.randn(4410) * 0.001
    monitor.update(quiet_signal)
    print(AudioMeterDisplay.format_display(monitor))
    
    # Test 2: Medium signal
    print("\nTest 2: Medium signal (-20 dBFS)")
    monitor.reset()
    medium_signal = np.random.randn(4410) * 0.1
    monitor.update(medium_signal)
    print(AudioMeterDisplay.format_display(monitor))
    
    # Test 3: Loud signal
    print("\nTest 3: Loud signal (-3 dBFS)")
    monitor.reset()
    loud_signal = np.random.randn(4410) * 0.7
    monitor.update(loud_signal)
    print(AudioMeterDisplay.format_display(monitor))
    
    # Test 4: Clipping
    print("\nTest 4: Clipping (0 dBFS)")
    monitor.reset()
    clip_signal = np.random.randn(4410) * 1.5
    clip_signal = np.clip(clip_signal, -1.0, 1.0)
    monitor.update(clip_signal)
    print(AudioMeterDisplay.format_display(monitor))
