#!/usr/bin/env python3
"""
GUI with Audio Settings Tab (ttk.Notebook)
KISS Server auto-start on app launch
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import logging
from pathlib import Path
import sys
import socket

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_manager import AudioManager, AudioDevice
from tx_pipeline import TXPipeline

logger = logging.getLogger(__name__)


class KISSServerThread(threading.Thread):
    """KISS Server running in background"""
    
    def __init__(self, host="127.0.0.1", port=8001, tx_pipeline=None):
        super().__init__(daemon=True, name="KISSServer")
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.clients = []
        self.lock = threading.Lock()
        self.tx_pipeline = tx_pipeline
        
    def run(self):
        """Run KISS server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            logger.info(f"[KISS] Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, client_addr = self.server_socket.accept()
                    logger.info(f"[KISS] Client connected: {client_addr}")
                    
                    with self.lock:
                        self.clients.append(client_socket)
                    
                    # Handle client in thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    pass
                except Exception as e:
                    if self.running:
                        logger.error(f"[KISS] Accept error: {e}")
                    
        except Exception as e:
            logger.error(f"[KISS] Server error: {e}")
        finally:
            self.stop()
    
    def _handle_client(self, client_socket, client_addr):
        """Handle individual client"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                # Log received data
                logger.debug(f"[KISS] RX from {client_addr}: {len(data)} bytes")
                
                # Route to TX pipeline if available
                if self.tx_pipeline:
                    self.tx_pipeline.send_kiss_frame(data)
                    logger.debug(f"[KISS] Queued for TX: {len(data)} bytes")
                
        except Exception as e:
            logger.error(f"[KISS] Client error: {e}")
        finally:
            try:
                with self.lock:
                    if client_socket in self.clients:
                        self.clients.remove(client_socket)
                client_socket.close()
            except:
                pass
            logger.info(f"[KISS] Client disconnected: {client_addr}")
    
    def stop(self):
        """Stop KISS server"""
        self.running = False
        
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("[KISS] Server stopped")

class TNCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TNC-APP - VHF APRS Terminal Node Controller")
        self.root.geometry("1000x600")
        
        # Audio manager
        self.audio_manager = AudioManager()
        
        # Start output stream (needed for audio transmission)
        self.audio_manager.start_output_stream()
        
        # TX Pipeline
        self.tx_pipeline = TXPipeline(self.audio_manager)
        self.tx_pipeline.on_tx_start = self._on_tx_start
        self.tx_pipeline.on_tx_complete = self._on_tx_complete
        self.tx_pipeline.on_tx_error = self._on_tx_error
        self.tx_pipeline.start()
        
        # KISS server state
        self.kiss_server = KISSServerThread(host="127.0.0.1", port=8001, tx_pipeline=self.tx_pipeline)
        self.kiss_server.start()
        self.server_running = True
        self.kiss_queue = queue.Queue()
        
        # Setup UI
        self._setup_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_ui(self):
        """Setup tabbed interface"""
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.monitor_frame = ttk.Frame(self.notebook)
        self.audio_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.monitor_frame, text="📊 Monitor")
        self.notebook.add(self.audio_frame, text="🎙️ Audio")
        
        # Setup each tab
        self._setup_monitor_tab()
        self._setup_audio_tab()
        
    def _setup_monitor_tab(self):
        """Monitor tab - packet display and server control"""
        # Top frame: Server controls
        top_frame = ttk.Frame(self.monitor_frame)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="KISS Server:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        self.server_status_label = ttk.Label(top_frame, text="● Running", foreground="green")
        self.server_status_label.pack(side=tk.LEFT, padx=10)
        
        self.server_start_btn = ttk.Button(top_frame, text="▶ Start Server", command=self._start_server, state=tk.DISABLED)
        self.server_start_btn.pack(side=tk.LEFT, padx=5)
        
        self.server_stop_btn = ttk.Button(top_frame, text="⏹ Stop Server", command=self._stop_server)
        self.server_stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Monitor display
        monitor_label = ttk.Label(self.monitor_frame, text="Packet Monitor:", font=("Arial", 9, "bold"))
        monitor_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.monitor_text = scrolledtext.ScrolledText(
            self.monitor_frame,
            height=20,
            width=120,
            bg="black",
            fg="green",
            font=("Courier", 9)
        )
        self.monitor_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Configure tags for coloring
        self.monitor_text.tag_config("info", foreground="cyan")
        self.monitor_text.tag_config("tx", foreground="yellow")
        self.monitor_text.tag_config("rx", foreground="lime green")
        self.monitor_text.tag_config("error", foreground="red")
        
        # Log initial message
        self._log_monitor("[INFO] TNC-APP Started - KISS server running on port 8001\n", "info")
        
    def _setup_audio_tab(self):
        """Audio tab - device selection and testing"""
        # Create a scrolled frame for audio settings
        canvas = tk.Canvas(self.audio_frame, bg="white")
        scrollbar = ttk.Scrollbar(self.audio_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # INPUT DEVICE Section
        input_frame = ttk.LabelFrame(scrollable_frame, text="🎤 Input Device (Microphone)", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(input_frame, text="Select Device:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        
        self.input_device_var = tk.StringVar()
        self.input_combo = ttk.Combobox(
            input_frame,
            textvariable=self.input_device_var,
            state="readonly",
            width=60
        )
        self.input_combo.pack(fill=tk.X, pady=5)
        self.input_combo.bind("<<ComboboxSelected>>", self._on_input_device_changed)
        
        # Input device info
        self.input_info_text = tk.Text(input_frame, height=3, width=70, bg="#f0f0f0")
        self.input_info_text.pack(fill=tk.X, pady=5)
        self.input_info_text.config(state=tk.DISABLED)
        
        # Test button
        ttk.Button(input_frame, text="🎤 Test Microphone (5 sec)", command=self._test_microphone).pack(side=tk.LEFT, padx=5, pady=5)
        
        # OUTPUT DEVICE Section
        output_frame = ttk.LabelFrame(scrollable_frame, text="🔊 Output Device (Speaker)", padding=10)
        output_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(output_frame, text="Select Device:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        
        self.output_device_var = tk.StringVar()
        self.output_combo = ttk.Combobox(
            output_frame,
            textvariable=self.output_device_var,
            state="readonly",
            width=60
        )
        self.output_combo.pack(fill=tk.X, pady=5)
        self.output_combo.bind("<<ComboboxSelected>>", self._on_output_device_changed)
        
        # Output device info
        self.output_info_text = tk.Text(output_frame, height=3, width=70, bg="#f0f0f0")
        self.output_info_text.pack(fill=tk.X, pady=5)
        self.output_info_text.config(state=tk.DISABLED)
        
        # Test button
        ttk.Button(output_frame, text="🔊 Test Speaker (1 kHz tone)", command=self._test_speaker).pack(side=tk.LEFT, padx=5, pady=5)
        
        # AUDIO CONFIGURATION Section
        config_frame = ttk.LabelFrame(scrollable_frame, text="⚙️ Audio Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        config_text = (
            "Sample Rate: 44100 Hz (CD quality)\n"
            "Bit Depth: 16-bit signed PCM\n"
            "Channels: 1 (Mono)\n"
            "Bell 202 AFSK: 1200 Hz (mark), 2200 Hz (space)\n"
            "Bitrate: 1200 bps (standard APRS VHF)"
        )
        
        config_label = tk.Text(config_frame, height=5, width=70, bg="#f0f0f0")
        config_label.pack(fill=tk.X)
        config_label.insert(tk.END, config_text)
        config_label.config(state=tk.DISABLED)
        
        # Populate device lists
        self._refresh_audio_devices()
        
    def _refresh_audio_devices(self):
        """Populate audio device comboboxes"""
        # Input devices
        input_devices = self.audio_manager.list_input_devices()
        input_options = [f"{dev.name} ({dev.max_input_channels}ch)" for dev in input_devices]
        self.input_combo['values'] = input_options
        
        # Auto-select best input device
        default_input = self.audio_manager._get_default_input_device()
        if default_input:
            for i, dev in enumerate(input_devices):
                if dev.index == default_input.index:
                    self.input_combo.current(i)
                    self._show_input_info(dev)
                    break
        elif input_devices:
            self.input_combo.current(0)
            self._show_input_info(input_devices[0])
        
        # Output devices
        output_devices = self.audio_manager.list_output_devices()
        output_options = [f"{dev.name} ({dev.max_output_channels}ch)" for dev in output_devices]
        self.output_combo['values'] = output_options
        
        # Auto-select best output device
        default_output = self.audio_manager._get_default_output_device()
        if default_output:
            for i, dev in enumerate(output_devices):
                if dev.index == default_output.index:
                    self.output_combo.current(i)
                    self._show_output_info(dev)
                    break
        elif output_devices:
            self.output_combo.current(0)
            self._show_output_info(output_devices[0])
    
    def _show_input_info(self, device: AudioDevice):
        """Display input device information"""
        info = f"Device: {device.name}\nIndex: {device.index}\nChannels: {device.max_input_channels}\nSample Rate: {int(device.sample_rate)} Hz"
        
        self.input_info_text.config(state=tk.NORMAL)
        self.input_info_text.delete("1.0", tk.END)
        self.input_info_text.insert(tk.END, info)
        self.input_info_text.config(state=tk.DISABLED)
    
    def _show_output_info(self, device: AudioDevice):
        """Display output device information"""
        info = f"Device: {device.name}\nIndex: {device.index}\nChannels: {device.max_output_channels}\nSample Rate: {int(device.sample_rate)} Hz"
        
        self.output_info_text.config(state=tk.NORMAL)
        self.output_info_text.delete("1.0", tk.END)
        self.output_info_text.insert(tk.END, info)
        self.output_info_text.config(state=tk.DISABLED)
    
    def _on_input_device_changed(self, event=None):
        """Handle input device selection"""
        index = self.input_combo.current()
        devices = self.audio_manager.list_input_devices()
        if 0 <= index < len(devices):
            device = devices[index]
            self.audio_manager.set_input_device(device.index)
            self._show_input_info(device)
            self._log_monitor(f"[INFO] Selected input device: {device.name}\n", "info")
    
    def _on_output_device_changed(self, event=None):
        """Handle output device selection"""
        index = self.output_combo.current()
        devices = self.audio_manager.list_output_devices()
        if 0 <= index < len(devices):
            device = devices[index]
            self.audio_manager.set_output_device(device.index)
            self._show_output_info(device)
            self._log_monitor(f"[INFO] Selected output device: {device.name}\n", "info")
    
    def _test_microphone(self):
        """Test microphone - record and playback"""
        def test_thread():
            try:
                self._log_monitor("[INFO] Recording from microphone (5 seconds)...\n", "info")
                self.root.update()
                
                # Record 5 seconds @ 44100 Hz
                audio_data = self.audio_manager.read_audio(44100 * 5)
                
                self._log_monitor(f"[INFO] Recorded {len(audio_data)} samples\n", "info")
                self._log_monitor("[INFO] Playing back recorded audio...\n", "info")
                self.root.update()
                
                # Play back
                self.audio_manager.write_audio(audio_data)
                
                self._log_monitor("[OK] Microphone test completed\n", "info")
            except Exception as e:
                self._log_monitor(f"[ERROR] Microphone test failed: {e}\n", "error")
        
        # Run in background thread
        thread = threading.Thread(target=test_thread, daemon=True)
        thread.start()
    
    def _test_speaker(self):
        """Test speaker - generate 1 kHz tone"""
        def test_thread():
            try:
                import numpy as np
                import math
                
                self._log_monitor("[INFO] Generating 1 kHz test tone...\n", "info")
                self.root.update()
                
                # Generate 1 kHz sine wave for 2 seconds @ 44100 Hz
                sample_rate = 44100
                duration = 2  # seconds
                frequency = 1000  # Hz
                
                t = np.arange(0, duration, 1/sample_rate)
                audio_data = 0.3 * np.sin(2 * math.pi * frequency * t).astype(np.float32)
                
                self._log_monitor("[INFO] Playing 1 kHz tone (2 seconds)...\n", "info")
                self.root.update()
                
                self.audio_manager.write_audio(audio_data)
                
                self._log_monitor("[OK] Speaker test completed\n", "info")
            except Exception as e:
                self._log_monitor(f"[ERROR] Speaker test failed: {e}\n", "error")
        
        # Run in background thread
        thread = threading.Thread(target=test_thread, daemon=True)
        thread.start()
    
    def _start_server(self):
        """Start KISS server"""
        if not self.kiss_server.running:
            self.kiss_server = KISSServerThread(host="127.0.0.1", port=8001)
            self.kiss_server.start()
            self.server_running = True
        
        self.server_status_label.config(text="● Running", foreground="green")
        self.server_start_btn.config(state=tk.DISABLED)
        self.server_stop_btn.config(state=tk.NORMAL)
        self._log_monitor("[INFO] KISS server started on port 8001\n", "info")
    
    def _stop_server(self):
        """Stop KISS server"""
        if self.kiss_server.running:
            self.kiss_server.stop()
            self.server_running = False
        
        self.server_status_label.config(text="● Stopped", foreground="red")
        self.server_start_btn.config(state=tk.NORMAL)
        self.server_stop_btn.config(state=tk.DISABLED)
        self._log_monitor("[INFO] KISS server stopped\n", "info")
    
    def _on_tx_start(self, msg: str):
        """TX started callback"""
        self._log_monitor(f"[TX] {msg}\n", "tx")
    
    def _on_tx_complete(self, msg: str):
        """TX completed callback"""
        self._log_monitor(f"[TX OK] {msg}\n", "tx")
    
    def _on_tx_error(self, msg: str):
        """TX error callback"""
        self._log_monitor(f"[TX ERROR] {msg}\n", "error")
    
    def _on_closing(self):
        """Handle window close"""
        self.tx_pipeline.stop()
        self._stop_server()
        self.root.destroy()
    
    def _log_monitor(self, message: str, tag: str = "info"):
        """Log message to monitor (handle encoding issues)"""
        # Clean up problematic characters
        message = message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        
        self.monitor_text.config(state=tk.NORMAL)
        self.monitor_text.insert(tk.END, message, tag)
        self.monitor_text.see(tk.END)
        self.monitor_text.config(state=tk.DISABLED)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    root = tk.Tk()
    app = TNCApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
