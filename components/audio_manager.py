"""
Audio Device Manager
- Automatic detection of audio devices
- Recording/Playback device configuration
"""

import pyaudio
import logging
import threading
import queue
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AudioDevice:
    """Represents an audio device"""
    
    def __init__(self, index: int, info: dict):
        self.index = index
        self.name = info['name']
        self.max_input_channels = info['maxInputChannels']
        self.max_output_channels = info['maxOutputChannels']
        self.sample_rate = int(info['defaultSampleRate'])
        self.is_input = info['maxInputChannels'] > 0
        self.is_output = info['maxOutputChannels'] > 0
        
    def __str__(self):
        """String representation like Windows Device Manager"""
        device_type = ""
        if self.is_input and self.is_output:
            device_type = "I/O Device"
        elif self.is_input:
            device_type = "Microphone"
        elif self.is_output:
            device_type = "Speaker"
            
        channels = f"{self.max_input_channels}ch in" if self.is_input else ""
        if self.is_input and self.is_output:
            channels = f"{self.max_input_channels}in/{self.max_output_channels}out"
        elif self.is_output:
            channels = f"{self.max_output_channels}ch out"
            
        return f"[{self.index:2d}] {self.name:40s} | {device_type:12s} | {channels:15s} @ {self.sample_rate} Hz"
    
    def __repr__(self):
        return self.__str__()


class AudioManager:
    """
    Manages audio device enumeration and selection
    """
    
    SAMPLE_RATE = 44100
    CHANNELS = 1
    CHUNK_SIZE = 1024
    
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.input_device = None
        self.output_device = None
        self.input_stream = None
        self.output_stream = None
        self.actual_input_sample_rate = self.SAMPLE_RATE   # Will be updated after stream start
        self.actual_output_sample_rate = self.SAMPLE_RATE  # Will be updated after stream start
        
        logger.info("[AUDIO] Initialized PyAudio")
        
        # Auto-select best devices
        default_output = self._get_default_output_device()
        if default_output:
            self.set_output_device(default_output.index)
        
        default_input = self._get_default_input_device()
        if default_input:
            self.set_input_device(default_input.index)
    
    def list_input_devices(self) -> List[AudioDevice]:
        """Get list of input devices (microphones)"""
        devices = []
        
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                device = AudioDevice(i, info)
                devices.append(device)
                logger.debug(f"[AUDIO] Input device: {device}")
        
        return devices
    
    def list_output_devices(self) -> List[AudioDevice]:
        """Get list of output devices (speakers)"""
        devices = []
        
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                device = AudioDevice(i, info)
                devices.append(device)
                logger.debug(f"[AUDIO] Output device: {device}")
        
        return devices
    
    def list_all_devices(self) -> List[AudioDevice]:
        """Get list of all devices"""
        devices = []
        
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            device = AudioDevice(i, info)
            devices.append(device)
        
        return devices
    
    def print_devices(self):
        """Print all audio devices in Windows-like format"""
        print("\n" + "="*110)
        print("AUDIO DEVICES (Windows-style listing)")
        print("="*110)
        
        devices = self.list_all_devices()
        
        if not devices:
            print("No audio devices found!")
            return
        
        # Print header
        print(f"{'IDX':<4} {'DEVICE NAME':<42} {'TYPE':<14} {'CHANNELS':<17} {'SAMPLE RATE':<10}")
        print("-"*110)
        
        # Print each device
        for device in devices:
            device_type = ""
            if device.is_input and device.is_output:
                device_type = "I/O Device"
            elif device.is_input:
                device_type = "Microphone"
            elif device.is_output:
                device_type = "Speaker"
            
            channels = ""
            if device.is_input and device.is_output:
                channels = f"{device.max_input_channels}in/{device.max_output_channels}out"
            elif device.is_input:
                channels = f"{device.max_input_channels}ch in"
            elif device.is_output:
                channels = f"{device.max_output_channels}ch out"
                
            print(f"[{device.index:<2}] {device.name[:40]:<42} {device_type:<14} {channels:<17} {device.sample_rate}")
        
        print("="*110 + "\n")
    
    def _get_default_output_device(self) -> Optional[AudioDevice]:
        """Find best output device - prefer CABLE for testing, else real speakers"""
        devices = self.list_output_devices()
        
        # First, check for CABLE/Virtual devices (for loopback testing)
        for device in devices:
            name_lower = device.name.lower()
            if "cable" in name_lower and "input" in name_lower:  # CABLE Input = sends to CABLE Output
                logger.info(f"[AUDIO] Selected output device (CABLE loopback): {device.name}")
                return device
        
        # Preferred keywords for real devices
        preferences = [
            "speaker",  # Polskie: głośniki
            "headphone",
            "audio",
            "output",
        ]
        
        # Exclude keywords (for real devices)
        excludes = [
            "spdif",
            "s/pdif",
            "steam",
        ]
        
        # Filter preferred devices
        for pref in preferences:
            for device in devices:
                name_lower = device.name.lower()
                if pref in name_lower and not any(excl in name_lower for excl in excludes):
                    logger.info(f"[AUDIO] Selected output device: {device.name}")
                    return device
        
        # Return first real device if nothing matched
        if devices:
            logger.info(f"[AUDIO] Using first output device: {devices[0].name}")
            return devices[0]
        
        return None
    
    def _get_default_input_device(self) -> Optional[AudioDevice]:
        """Find best input device (prefer real microphone over virtual)"""
        devices = self.list_input_devices()
        
        # Preferred keywords
        preferences = [
            "microphone",  # Polskie: mikrofon
            "mic",
            "input",
            "recording",
        ]
        
        # Exclude keywords
        excludes = [
            "cable",
            "virtual",
            "steam",
            "mapper",  # Mapowanie dźwięku
        ]
        
        # Filter preferred devices
        for pref in preferences:
            for device in devices:
                name_lower = device.name.lower()
                if pref in name_lower and not any(excl in name_lower for excl in excludes):
                    logger.info(f"[AUDIO] Selected input device: {device.name}")
                    return device
        
        # Return first real device if nothing matched
        if devices:
            logger.info(f"[AUDIO] Using first input device: {devices[0].name}")
            return devices[0]
        
        return None
    
    def set_input_device(self, device_index: int) -> bool:
        """Set recording device"""
        try:
            info = self.pa.get_device_info_by_index(device_index)
            if info['maxInputChannels'] == 0:
                logger.error(f"[AUDIO] Device {device_index} is not an input device")
                return False
            
            self.input_device = device_index
            logger.info(f"[AUDIO] Input device set to: {info['name']}")
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Failed to set input device: {e}")
            return False
    
    def set_output_device(self, device_index: int) -> bool:
        """Set playback device"""
        try:
            info = self.pa.get_device_info_by_index(device_index)
            if info['maxOutputChannels'] == 0:
                logger.error(f"[AUDIO] Device {device_index} is not an output device")
                return False
            
            self.output_device = device_index
            logger.info(f"[AUDIO] Output device set to: {info['name']}")
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Failed to set output device: {e}")
            return False
    
    def start_input_stream(self, strict_device: bool = False) -> bool:
        """Start recording stream
        
        Args:
            strict_device: If True, only try requested device (no fallback - fail if device unavailable).
                          If False, try requested device first, then fallback to others if needed.
        """
        if self.input_device is None:
            logger.error("[AUDIO] Input device not set")
            return False
        
        # Determine which devices to try
        devices_to_try = [self.input_device]
        
        # Add fallback devices unless strict mode is enabled
        if not strict_device:
            for device in self.list_input_devices():
                if device.index != self.input_device:
                    devices_to_try.append(device.index)
        
        for device_index in devices_to_try:
            try:
                logger.debug(f"[AUDIO] Trying input device {device_index}...")
                
                # Try Int16 format first
                try:
                    self.input_stream = self.pa.open(
                        format=pyaudio.paInt16,
                        channels=self.CHANNELS,
                        rate=self.SAMPLE_RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=self.CHUNK_SIZE,
                        start=False
                    )
                    self.input_stream.start_stream()
                except Exception as e:
                    logger.debug(f"[AUDIO] paInt16 failed: {e}, trying paFloat32...")
                    self.input_stream = self.pa.open(
                        format=pyaudio.paFloat32,
                        channels=self.CHANNELS,
                        rate=self.SAMPLE_RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=self.CHUNK_SIZE,
                        start=False
                    )
                    self.input_stream.start_stream()
                
                info = self.pa.get_device_info_by_index(device_index)
                
                # CRITICAL: Get actual sample rate from STREAM
                # Try to read stream's sample rate property
                try:
                    # PyAudio stream.sample_rate property
                    stream_sr = self.input_stream.sample_rate
                    self.actual_input_sample_rate = int(stream_sr)
                except (AttributeError, TypeError):
                    # If property doesn't exist, assume what was requested was accepted
                    logger.warning(f"[AUDIO] ⚠️  Stream.sample_rate property not available, assuming device accepted requested 44100 Hz")
                    self.actual_input_sample_rate = self.SAMPLE_RATE
                
                logger.info(f"[AUDIO] Input stream started: device {device_index} ({info['name']})")
                logger.info(f"[AUDIO]   - Device defaultSampleRate: {int(info['defaultSampleRate'])} Hz")
                logger.info(f"[AUDIO]   - Stream actual sample_rate: {self.actual_input_sample_rate} Hz")
                
                if self.actual_input_sample_rate != int(info['defaultSampleRate']):
                    logger.warning(f"[AUDIO] ⚠️  MISMATCH: Requested {int(info['defaultSampleRate'])} Hz but got {self.actual_input_sample_rate} Hz!")
                if self.actual_input_sample_rate != self.SAMPLE_RATE:
                    logger.error(f"[AUDIO] ❌ CRITICAL: Stream negotiated {self.actual_input_sample_rate} Hz but app expects {self.SAMPLE_RATE} Hz!")
                    logger.error(f"[AUDIO] ❌ CRITICAL: This will cause frequency offset!")
                
                self.input_device = device_index
                return True
                
            except Exception as e:
                logger.debug(f"[AUDIO] Device {device_index} failed: {e}")
                self.input_stream = None
                continue
        
        logger.error("[AUDIO] Failed to start input stream on any device")
        return False
    
    def start_output_stream(self) -> bool:
        """Start playback stream - try multiple devices if needed"""
        if self.output_device is None:
            logger.error("[AUDIO] Output device not set")
            return False
        
        # Try current device first
        devices_to_try = [self.output_device]
        
        # Add other output devices as fallback
        for device in self.list_output_devices():
            if device.index != self.output_device:
                devices_to_try.append(device.index)
        
        for device_index in devices_to_try:
            try:
                # Get device info for this index
                info = self.pa.get_device_info_by_index(device_index)
                logger.info(f"[AUDIO] Trying output device {device_index}: {info['name']}")
                
                # Try Int16 format first (more universal)
                try:
                    self.output_stream = self.pa.open(
                        format=pyaudio.paInt16,
                        channels=self.CHANNELS,
                        rate=self.SAMPLE_RATE,
                        output=True,
                        output_device_index=device_index,
                        frames_per_buffer=self.CHUNK_SIZE,
                        start=False
                    )
                    self.output_stream.start_stream()
                except Exception as e:
                    logger.debug(f"[AUDIO] paInt16 failed: {e}, trying paFloat32...")
                    self.output_stream = self.pa.open(
                        format=pyaudio.paFloat32,
                        channels=self.CHANNELS,
                        rate=self.SAMPLE_RATE,
                        output=True,
                        output_device_index=device_index,
                        frames_per_buffer=self.CHUNK_SIZE,
                        start=False
                    )
                    self.output_stream.start_stream()
                
                # CRITICAL: Get actual sample rate from STREAM
                # Try to read stream's sample rate property
                try:
                    # PyAudio stream.sample_rate property
                    stream_sr = self.output_stream.sample_rate
                    self.actual_output_sample_rate = int(stream_sr)
                except (AttributeError, TypeError):
                    # If property doesn't exist, assume what was requested was accepted
                    logger.warning(f"[AUDIO] WARNING: Stream.sample_rate property not available, assuming device accepted requested 44100 Hz")
                    self.actual_output_sample_rate = self.SAMPLE_RATE
                
                logger.info(f"[AUDIO] Output stream started: device {device_index} ({info['name']})")
                logger.info(f"[AUDIO]   - Device defaultSampleRate: {int(info['defaultSampleRate'])} Hz")
                logger.info(f"[AUDIO]   - Stream actual sample_rate: {self.actual_output_sample_rate} Hz")
                
                if self.actual_output_sample_rate != int(info['defaultSampleRate']):
                    logger.warning(f"[AUDIO] MISMATCH: Requested {int(info['defaultSampleRate'])} Hz but got {self.actual_output_sample_rate} Hz!")
                if self.actual_output_sample_rate != self.SAMPLE_RATE:
                    logger.error(f"[AUDIO] CRITICAL: Stream negotiated {self.actual_output_sample_rate} Hz but app expects {self.SAMPLE_RATE} Hz!")
                    logger.error(f"[AUDIO] CRITICAL: This will cause frequency offset!")
                
                self.output_device = device_index
                return True
                
            except Exception as e:
                logger.debug(f"[AUDIO] Device {device_index} failed: {e}")
                self.output_stream = None
                continue
        
        logger.error("[AUDIO] Failed to start output stream on any device")
        return False
    
    def read_audio(self, num_frames: int = None, timeout: float = 2.0) -> bytes:
        """Read audio from input stream with timeout
        
        Args:
            num_frames: Number of frames to read (default: CHUNK_SIZE)
            timeout: Maximum time to wait for data in seconds (default: 2.0s)
        
        Returns:
            Audio data as bytes, empty if timeout exceeded
        """
        if not self.input_stream:
            logger.warning("[AUDIO] Input stream not started")
            return b''
        
        try:
            if num_frames is None:
                num_frames = self.CHUNK_SIZE
            
            # Use threading to implement timeout on blocking read()
            result_queue = queue.Queue()
            
            def do_read():
                try:
                    data = self.input_stream.read(num_frames, exception_on_overflow=False)
                    result_queue.put(('success', data))
                except Exception as e:
                    result_queue.put(('error', str(e)))
            
            # Start read in thread
            read_thread = threading.Thread(target=do_read, daemon=True)
            read_thread.start()
            
            # Wait for result with timeout
            try:
                status, result = result_queue.get(timeout=timeout)
                if status == 'success':
                    return result
                else:
                    logger.error(f"[AUDIO] Read error: {result}")
                    return b''
            except queue.Empty:
                logger.warning(f"[AUDIO] Read timeout after {timeout}s - no data from device")
                return b''
                
        except Exception as e:
            logger.error(f"[AUDIO] Failed to read audio: {e}")
            return b''
    
    def write_audio(self, data: bytes) -> bool:
        """Write audio to output stream"""
        if not self.output_stream:
            logger.warning("[AUDIO] Output stream not started")
            return False
        
        try:
            self.output_stream.write(data)
            return True
        except Exception as e:
            logger.error(f"[AUDIO] Failed to write audio: {e}")
            return False
    
    def get_input_sample_rate(self) -> int:
        """Get actual input stream sample rate"""
        return self.actual_input_sample_rate
    
    def get_output_sample_rate(self) -> int:
        """Get actual output stream sample rate"""
        return self.actual_output_sample_rate
    
    def stop_input_stream(self):
        """Stop input stream"""
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None
                logger.info("[AUDIO] Input stream stopped")
            except Exception as e:
                logger.error(f"[AUDIO] Error stopping input stream: {e}")
    
    def stop_output_stream(self):
        """Stop output stream"""
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
                logger.info("[AUDIO] Output stream stopped")
            except Exception as e:
                logger.error(f"[AUDIO] Error stopping output stream: {e}")
    
    def stop_all(self):
        """Stop all streams"""
        self.stop_input_stream()
        self.stop_output_stream()
    
    def shutdown(self):
        """Cleanup"""
        self.stop_all()
        self.pa.terminate()
        logger.info("[AUDIO] Shutdown complete")


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    manager = AudioManager()
    
    # List devices
    print("\n=== INPUT DEVICES ===")
    inputs = manager.list_input_devices()
    for dev in inputs:
        print(dev)
    
    print("\n=== OUTPUT DEVICES ===")
    outputs = manager.list_output_devices()
    for dev in outputs:
        print(dev)
    
    # Use defaults
    if inputs and outputs:
        manager.set_input_device(inputs[0].index)
        manager.set_output_device(outputs[0].index)
        
        print(f"\nSelected: {inputs[0].name} → {outputs[0].name}")
    
    manager.shutdown()
