"""
GUI aplikacji TNC - wersja development
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import logging
from datetime import datetime
from queue import Queue, Empty

from .config import AppConfig
from .servers import KISSServer, AGWPEServer
from .parser import KISSFrame, parse_ax25_frame, parse_aprs_from_ax25


logger = logging.getLogger(__name__)


class PacketProcessorThread(threading.Thread):
    """Wątek do przetwarzania pakietów"""
    
    def __init__(self, config: AppConfig, gui_callback=None, event_queue=None):
        super().__init__(daemon=False, name="PacketProcessor")
        self.config = config
        self.gui_callback = gui_callback
        self.event_queue = event_queue  # Thread-safe queue
        self.kiss_server: KISSServer = None
        self.agwpe_server: AGWPEServer = None
        self.aprs_is_gateway = None
        self.running = True

    def run(self):
        """Uruchom serwery"""
        # KISS Server
        if self.config.kiss_server.enabled:
            self.kiss_server = KISSServer(
                self.config.kiss_server.host,
                self.config.kiss_server.port
            )
            self.kiss_server.on_data_received = self._process_kiss_packet
            self.kiss_server.on_connected = lambda msg: self._callback("server_msg", f"[KISS] {msg}")
            self.kiss_server.on_disconnected = lambda msg: self._callback("server_msg", f"[KISS] {msg}")
            self.kiss_server.start()

        # AGWPE Server
        if self.config.agwpe_server.enabled:
            self.agwpe_server = AGWPEServer(
                self.config.agwpe_server.host,
                self.config.agwpe_server.port
            )
            self.agwpe_server.on_data_received = self._process_agwpe_packet
            self.agwpe_server.on_connected = lambda msg: self._callback("server_msg", f"[AGWPE] {msg}")
            self.agwpe_server.on_disconnected = lambda msg: self._callback("server_msg", f"[AGWPE] {msg}")
            self.agwpe_server.start()

        # Keep thread alive
        while self.running:
            threading.Event().wait(0.1)

    def start_aprs_is_gateway(self):
        """Uruchom APRS-IS Gateway"""
        # Sprawdź czy config istnieje
        if not self.config.debug_aprs_is:
            logger.error("APRS-IS Gateway not configured")
            return False
        
        try:
            from .aprs_is_gateway import APRSISGateway
            
            if self.aprs_is_gateway and self.aprs_is_gateway.running:
                logger.warning("APRS-IS Gateway already running")
                return False
            
            self.aprs_is_gateway = APRSISGateway(
                local_kiss_host="127.0.0.1",
                local_kiss_port=self.config.kiss_server.port
            )
            
            # Callback dla wstrzyknięć
            self.aprs_is_gateway.on_packet_injected = lambda msg: self._callback("packet", msg, "INET")
            # Callback dla broadcast ramek KISS
            self.aprs_is_gateway.on_frame_to_broadcast = self._broadcast_to_all_clients
            
            # Uruchom gateway
            debug = self.config.debug_aprs_is
            success = self.aprs_is_gateway.start(
                server=debug.server,
                port=debug.port,
                callsign=debug.callsign,
                passcode=debug.passcode,
                filter_cmd=debug.filter
            )
            
            if success:
                logger.info(f"APRS-IS Gateway started: {debug.server}:{debug.port}")
                self._callback("server_msg", f"[APRS-IS] Connected to {debug.server}")
                return True
            else:
                logger.error("Failed to start APRS-IS Gateway")
                return False
        except Exception as e:
            logger.error(f"Error starting APRS-IS Gateway: {e}")
            self._callback("server_msg", f"[APRS-IS ERROR] {str(e)}")
            return False
    
    def stop_aprs_is_gateway(self):
        """Zatrzymaj APRS-IS Gateway"""
        if self.aprs_is_gateway:
            self.aprs_is_gateway.stop()
            self.aprs_is_gateway = None
            logger.info("APRS-IS Gateway stopped")
            self._callback("server_msg", "[APRS-IS] Disconnected")

    def _callback(self, event_type: str, data: str, server_type: str = None):
        """Wyślij callback do GUI - thread-safe poprzez queue"""
        if self.event_queue:
            self.event_queue.put((event_type, data, server_type))
        elif self.gui_callback:
            self.gui_callback(event_type, data, server_type)

    def _broadcast_to_all_clients(self, kiss_frame: bytes):
        """Wyślij KISS ramkę do wszystkich połączonych KISS klientów"""
        if not self.kiss_server:
            return
        
        count = self.kiss_server.broadcast_to_clients(kiss_frame)
        if count > 0:
            logger.info(f"[APRS-IS] Broadcast to {count} KISS clients")

    def _process_kiss_packet(self, data: bytes):
        """Przetwórz pakiet KISS"""
        try:
            frame = KISSFrame.parse(data)
            if not frame:
                return

            # Komenda 0 = dane
            if frame.command == 0 and frame.data:
                ax25_frame = parse_ax25_frame(frame.data)
                if ax25_frame:
                    aprs_packet = parse_aprs_from_ax25(ax25_frame)
                    if aprs_packet:
                        output = f"[KISS] {aprs_packet.to_readable()}"
                        self._callback("packet", output, "KISS")
                    else:
                        output = f"[KISS] AX.25 Frame: {ax25_frame}"
                        self._callback("packet", output, "KISS")
                else:
                    output = f"[KISS] Raw packet (length={len(frame.data)}, hex={frame.data.hex()[:50]}...)"
                    self._callback("packet", output, "KISS")
        except Exception as e:
            logger.error(f"Error processing KISS packet: {e}")
            self._callback("packet", f"[KISS ERROR] {str(e)}", "KISS")

    def _process_agwpe_packet(self, data: bytes):
        """Przetwórz pakiet AGWPE"""
        try:
            from .parser import AGWPEFrame, parse_aprs_from_agwpe_data
            
            frame = AGWPEFrame.parse(data)
            if not frame:
                return

            # Tylko procesy data frames (command 'D' lub 'd' lub 'U')
            if frame.datakind in ['D', 'd', 'U'] and frame.data:
                aprs_packet = parse_aprs_from_agwpe_data(frame.data)
                if aprs_packet:
                    output = f"[AGWPE] {aprs_packet.to_readable()}"
                    self._callback("packet", output, "AGWPE")
                else:
                    output = f"[AGWPE] Data from {frame.call_from} to {frame.call_to} (len={len(frame.data)})"
                    self._callback("packet", output, "AGWPE")
            else:
                # Inne ramki (control frames)
                output = f"[AGWPE] Command '{frame.datakind}' from {frame.call_from} to {frame.call_to}"
                self._callback("packet", output, "AGWPE")
                
        except Exception as e:
            logger.error(f"Error processing AGWPE packet: {e}")
            self._callback("packet", f"[AGWPE ERROR] {str(e)}", "AGWPE")

    def stop_servers(self):
        """Zatrzymaj serwery - graceful shutdown"""
        logger.info("[SERVERS] Stopping servers...")
        self.running = False
        
        try:
            # Zatrzymaj KISS Server
            if self.kiss_server:
                logger.info("[SERVERS] Stopping KISS Server...")
                try:
                    self.kiss_server.stop()
                    logger.info("[OK] KISS Server stopped")
                except Exception as e:
                    logger.error(f"[ERROR] Error stopping KISS Server: {e}")
            
            # Zatrzymaj AGWPE Server
            if self.agwpe_server:
                logger.info("[SERVERS] Stopping AGWPE Server...")
                try:
                    self.agwpe_server.stop()
                    logger.info("[OK] AGWPE Server stopped")
                except Exception as e:
                    logger.error(f"[ERROR] Error stopping AGWPE Server: {e}")
            
            # Zatrzymaj APRS-IS Gateway
            if self.aprs_is_gateway:
                logger.info("[SERVERS] Stopping APRS-IS Gateway...")
                try:
                    self.aprs_is_gateway.stop()
                    logger.info("[OK] APRS-IS Gateway stopped")
                except Exception as e:
                    logger.error(f"[ERROR] Error stopping APRS-IS Gateway: {e}")
            
            logger.info("[OK] All servers stopped")
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error in stop_servers: {e}", exc_info=True)


class TNCMainWindow:
    """Główne okno aplikacji TNC"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.event_queue = Queue()  # Thread-safe event queue
        self.processor_thread: PacketProcessorThread = None
        self.aprs_is_gateway = None
        
        self.root = tk.Tk()
        self.root.title(config.window_title)
        self.root.geometry(f"{config.window_width}x{config.window_height}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self._setup_ui()
        self._start_servers()
        
        # Zacznij polling event queue
        self._poll_event_queue()

    def _setup_ui(self):
        """Skonfiguruj interfejs graficzny"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Servers & Filter Control", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Server status buttons
        servers_frame = ttk.Frame(control_frame)
        servers_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.kiss_button = tk.Button(
            servers_frame,
            text="🟥 KISS (OFF)",
            bg="#ff6b6b",
            fg="white",
            font=("Arial", 9, "bold"),
            height=1,
            state=tk.DISABLED,
            relief=tk.RAISED,
            bd=2
        )
        self.kiss_button.pack(side=tk.LEFT, padx=5)
        
        # AGWPE button hidden - not implemented yet
        # self.agwpe_button = tk.Button(
        #     servers_frame,
        #     text="🟥 AGWPE (OFF)",
        #     bg="#ff6b6b",
        #     fg="white",
        #     font=("Arial", 9, "bold"),
        #     height=1,
        #     state=tk.DISABLED,
        #     relief=tk.RAISED,
        #     bd=2
        # )
        # self.agwpe_button.pack(side=tk.LEFT, padx=5)
        
        servers_frame.pack_propagate(False)
        
        # Monitor filter buttons
        filter_frame = ttk.LabelFrame(control_frame, text="Monitor Filter", padding=5)
        filter_frame.pack(fill=tk.X, padx=0, pady=5)
        
        self.monitor_mode = tk.StringVar(value="ALL")
        self.monitor_mode.trace('w', self._on_filter_changed)  # Nasłuchuj zmiany
        
        self.filter_all = tk.Radiobutton(
            filter_frame,
            text="All Packets",
            variable=self.monitor_mode,
            value="ALL",
            font=("Arial", 9)
        )
        self.filter_all.pack(side=tk.LEFT, padx=5)
        
        self.filter_kiss = tk.Radiobutton(
            filter_frame,
            text="KISS Only",
            variable=self.monitor_mode,
            value="KISS",
            font=("Arial", 9)
        )
        self.filter_kiss.pack(side=tk.LEFT, padx=5)
        
        # AGWPE filter disabled - not implemented yet
        # self.filter_agwpe = tk.Radiobutton(
        #     filter_frame,
        #     text="AGWPE Only",
        #     variable=self.monitor_mode,
        #     value="AGWPE",
        #     font=("Arial", 9)
        # )
        # self.filter_agwpe.pack(side=tk.LEFT, padx=5)
        
        # Debug APRS-IS Gateway
        debug_frame = ttk.LabelFrame(control_frame, text="Debug Tools", padding=5)
        debug_frame.pack(fill=tk.X, padx=0, pady=5)
        
        self.aprs_is_enabled = tk.BooleanVar(value=False)
        self.aprs_is_checkbox = tk.Checkbutton(
            debug_frame,
            text="Enable APRS-IS Debug (Warsaw - inject internet packets)",
            variable=self.aprs_is_enabled,
            command=self._on_aprs_is_toggle,
            font=("Arial", 9)
        )
        self.aprs_is_checkbox.pack(side=tk.LEFT, padx=5)
        
        self.aprs_is_status = tk.Label(debug_frame, text="APRS-IS: OFF", fg="gray", font=("Arial", 8))
        self.aprs_is_status.pack(side=tk.LEFT, padx=10)
        
        # Status info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_kiss = tk.Label(info_frame, text="KISS: IDLE", fg="gray")
        self.status_kiss.pack(side=tk.LEFT, padx=5)
        
        # AGWPE status hidden - not implemented yet
        # self.status_agwpe = tk.Label(info_frame, text="AGWPE: IDLE", fg="gray")
        # self.status_agwpe.pack(side=tk.RIGHT, padx=5)
        
        # Packet display area
        display_frame = ttk.LabelFrame(main_frame, text="Decoded Packets", padding=5)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.packet_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            font=("Courier New", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            height=20
        )
        self.packet_display.pack(fill=tk.BOTH, expand=True)
        self.packet_display.config(state=tk.DISABLED)
        
        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            bg="gray",
            fg="white",
            anchor=tk.W,
            padx=5
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _start_servers(self):
        """Uruchom serwery"""
        self.processor_thread = PacketProcessorThread(self.config, self._on_event, self.event_queue)
        self.processor_thread.start()
        
        # Update buttons
        if self.config.kiss_server.enabled:
            self.kiss_button.config(state=tk.NORMAL)
            self.kiss_button.config(text="🟩 KISS Server (ON)", bg="#51cf66")

    def _on_event(self, event_type: str, data: str, server_type: str = None):
        """Obsłuż zdarzenia z serwera"""
        if event_type == "packet":
            self._display_packet(data, server_type)
        elif event_type == "server_msg":
            self._display_message(data)

    def _poll_event_queue(self):
        """Czytaj eventy z queue - thread-safe GUI updates"""
        try:
            while True:
                try:
                    event_type, data, server_type = self.event_queue.get_nowait()
                    self._on_event(event_type, data, server_type)
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error polling event queue: {e}")
        
        # Zaplanuj następny poll
        self.root.after(100, self._poll_event_queue)

    def _on_filter_changed(self, *args):
        """Callback gdy zmieni się filtr - wyczyść monitor"""
        self._clear_display()

    def _on_aprs_is_toggle(self):
        """Handler dla checkboxa APRS-IS Gateway"""
        try:
            if self.aprs_is_enabled.get():
                # Włącz
                self.aprs_is_checkbox.config(state=tk.DISABLED)
                self.aprs_is_status.config(text="APRS-IS: CONNECTING...", fg="orange")
                self.status_bar.config(text="Connecting to APRS-IS server...")
                self.root.update()
                
                success = self.processor_thread.start_aprs_is_gateway()
                if success:
                    self.aprs_is_status.config(text="APRS-IS: CONNECTED", fg="green")
                    self.status_bar.config(text="APRS-IS Gateway connected - receiving packets")
                    threading.Timer(5.0, lambda: self._enable_aprs_is_checkbox()).start()
                else:
                    self.aprs_is_enabled.set(False)
                    self.aprs_is_status.config(text="APRS-IS: FAILED TO CONNECT", fg="red")
                    self.status_bar.config(text="APRS-IS: Connection failed (check network/firewall)")
                    self.aprs_is_checkbox.config(state=tk.NORMAL)
            else:
                # Wyłącz
                self.processor_thread.stop_aprs_is_gateway()
                self.aprs_is_status.config(text="APRS-IS: OFF", fg="gray")
                self.status_bar.config(text="APRS-IS Gateway disabled")
                self.aprs_is_checkbox.config(state=tk.NORMAL)
        except Exception as e:
            logger.error(f"Error in APRS-IS toggle: {e}", exc_info=True)
            self.aprs_is_enabled.set(False)
            self.aprs_is_status.config(text=f"APRS-IS: ERROR - {str(e)[:30]}", fg="red")
            self.status_bar.config(text=f"APRS-IS Error: {str(e)}")
            self.aprs_is_checkbox.config(state=tk.NORMAL)
    
    def _enable_aprs_is_checkbox(self):
        """Włącz checkbox po opóźnieniu"""
        self.aprs_is_checkbox.config(state=tk.NORMAL)

    def _clear_display(self):
        """Wyczyść monitor pakietów"""
        self.packet_display.config(state=tk.NORMAL)
        self.packet_display.delete("1.0", tk.END)
        self.packet_display.config(state=tk.DISABLED)

    def _display_packet(self, packet_data: str, server_type: str = None):
        """Wyświetl pakiet jeśli przejdzie filtr"""
        # Sprawdź filtr
        mode = self.monitor_mode.get()
        
        # Jeśli "ALL" - wyświetl wszystko
        if mode == "ALL":
            self.packet_display.config(state=tk.NORMAL)
            self.packet_display.insert(tk.END, packet_data + "\n\n")
            self.packet_display.see(tk.END)
            self.packet_display.config(state=tk.DISABLED)
        # Jeśli "KISS" - wyświetl tylko KISS i INET
        elif mode == "KISS" and server_type in ["KISS", "INET"]:
            self.packet_display.config(state=tk.NORMAL)
            self.packet_display.insert(tk.END, packet_data + "\n\n")
            self.packet_display.see(tk.END)
            self.packet_display.config(state=tk.DISABLED)
        # Jeśli "AGWPE" - wyświetl tylko AGWPE
        elif mode == "AGWPE" and server_type == "AGWPE":
            self.packet_display.config(state=tk.NORMAL)
            self.packet_display.insert(tk.END, packet_data + "\n\n")
            self.packet_display.see(tk.END)
            self.packet_display.config(state=tk.DISABLED)

    def _display_message(self, message: str):
        """Wyświetl komunikat serwera"""
        self.packet_display.config(state=tk.NORMAL)
        self.packet_display.insert(tk.END, f"[SERVER] {message}\n")
        self.packet_display.see(tk.END)
        self.packet_display.config(state=tk.DISABLED)
        self.status_bar.config(text=message)

    def on_closing(self):
        """Obsłuż zamknięcie okna - graceful shutdown"""
        logger.info("[CLOSE] Closing TNC Application...")
        
        try:
            # Zatrzymaj APRS-IS Gateway jeśli działa
            if self.aprs_is_gateway:
                try:
                    logger.info("[SHUTDOWN] Stopping APRS-IS Gateway...")
                    self.processor_thread.stop_aprs_is_gateway()
                except Exception as e:
                    logger.error(f"[ERROR] Error stopping APRS-IS: {e}")
            
            # Zatrzymaj serwery
            if self.processor_thread:
                logger.info("[SHUTDOWN] Stopping servers...")
                self.processor_thread.stop_servers()
                
                # Czekaj na wątek by się zamknął (max 3 sekundy)
                logger.info("[SHUTDOWN] Waiting for processor thread to finish...")
                self.processor_thread.join(timeout=3.0)
                if self.processor_thread.is_alive():
                    logger.warning("[WARN] Processor thread did not exit cleanly")
                else:
                    logger.info("[OK] Processor thread stopped")
            
            # Zniszcz GUI
            logger.info("[SHUTDOWN] Destroying root window...")
            self.root.quit()
            self.root.destroy()
            logger.info("[OK] GUI closed")
        except Exception as e:
            logger.error(f"[ERROR] Error during on_closing: {e}", exc_info=True)
            try:
                self.root.destroy()
            except:
                pass

    def run(self):
        """Uruchom aplikację"""
        self.root.mainloop()

