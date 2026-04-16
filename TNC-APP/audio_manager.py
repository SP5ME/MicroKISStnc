"""
Audio Device Manager
- Automatic detection of audio devices
- Recording/Playback device configuration
"""

import pyaudio
import logging
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
        return f"{self.index}: {self.name} ({self.max_input_channels}in/{self.max_output_channels}out @ {self.sample_rate}Hz)"
    
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
    
    def _get_default_output_device(self) -> Optional[AudioDevice]:
        """Find best output device (prefer real speakers over virtual)"""
        devices = self.list_output_devices()
        
        # Preferred keywords (in order)
        preferences = [
            "speaker",  # Polskie: głośniki
            "headphone",
            "audio",
            "output",
        ]
        
        # Exclude keywords
        excludes = [
            "cable",
            "virtual",
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
    
    def start_input_stream(self) -> bool:
        """Start recording stream - try multiple devices if needed"""
        if self.input_device is None:
            logger.error("[AUDIO] Input device not set")
            return False
        
        # Try current device first
        devices_to_try = [self.input_device]
        
        # Add other input devices as fallback
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
                logger.info(f"[AUDIO] Input stream started: device {device_index} ({info['name']})")
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
                logger.debug(f"[AUDIO] Trying output device {device_index}...")
                
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
                
                info = self.pa.get_device_info_by_index(device_index)
                logger.info(f"[AUDIO] Output stream started: device {device_index} ({info['name']})")
                self.output_device = device_index
                return True
                
            except Exception as e:
                logger.debug(f"[AUDIO] Device {device_index} failed: {e}")
                self.output_stream = None
                continue
        
        logger.error("[AUDIO] Failed to start output stream on any device")
        return False
    
    def read_audio(self, num_frames: int = None) -> bytes:
        """Read audio from input stream"""
        if not self.input_stream:
            logger.warning("[AUDIO] Input stream not started")
            return b''
        
        try:
            if num_frames is None:
                num_frames = self.CHUNK_SIZE
            
            data = self.input_stream.read(num_frames, exception_on_overflow=False)
            return data
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
