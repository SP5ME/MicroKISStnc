#!/usr/bin/env python3
"""
MicroKISStnc Desktop Application v1.0
PyQt6-based GUI for APRS TNC operations
"""

import re
import sys
import logging
import os
import html
import ctypes
import json
from datetime import datetime
from collections import deque
from pathlib import Path
import socket
import threading
import queue
import time

import numpy as np
import sounddevice
import serial
import serial.tools.list_ports
from threading import Event
from typing import Optional, Dict, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QGroupBox, QLabel, QComboBox, QPushButton, QCheckBox,
    QSpinBox, QProgressBar, QTextEdit, QHBoxLayout, QMessageBox, QLineEdit,
    QScrollArea, QGridLayout, QSizePolicy, QSystemTrayIcon, QMenu, QStackedWidget, QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont, QWheelEvent, QIcon, QFontMetrics

from components.config_manager import ConfigManager
from components.audio_monitor import AudioMonitor, AudioMeterDisplay
from components.test_tone_gen import TestToneGenerator
from components.kiss_server_app import KISSServerApp
from components.rx_pipeline_live_dsp import RXPipelineLiveDSP as RXPipeline
from components.hdlc_codec import HDLCEncoder
from components.afsk_modem import AFSKModulator
from components.system_volume import SystemVolumeMonitor
from components.web_control_server import WebControlServer

logger = logging.getLogger(__name__)

APP_ICON_FILE = "Ikona-MicroKISStnc.ico"
APP_USER_MODEL_ID = "MicroKISStnc.Desktop.public_v1"

WEB_UI_PORT = 8765
WEB_UI_BIND_HOST = "0.0.0.0"
WEB_UI_LOCAL_HOST = "127.0.0.1"
KISS_SERVER_PORT = 8001
LAN_TRUSTED_CLIENT_IPS = [ip.strip() for ip in os.getenv("MICROKISS_TRUSTED_IPS", "").split(",") if ip.strip()]
WEB_CONTROL_TOKEN = os.getenv("MICROKISS_WEB_TOKEN", "").strip()
KISS_MAX_CLIENTS = int(os.getenv("MICROKISS_KISS_MAX_CLIENTS", "4"))
KISS_MAX_BUFFER_BYTES = int(os.getenv("MICROKISS_KISS_MAX_BUFFER_BYTES", "65536"))
KISS_MAX_PAYLOAD_BYTES = int(os.getenv("MICROKISS_KISS_MAX_PAYLOAD_BYTES", "330"))
WEB_MAX_POST_BYTES = int(os.getenv("MICROKISS_WEB_MAX_POST_BYTES", "16384"))
ALLOW_ALL_IP_TOKEN = "0.0.0.0"
DEFAULT_TX_DELAY_MS = 250
DEFAULT_TX_TAIL_MS = 30

LAYOUT_SWITCH_INITIAL_WIDTH = 1240
LAYOUT_SWITCH_TO_HORIZONTAL_WIDTH = 1280
LAYOUT_SWITCH_TO_VERTICAL_WIDTH = 1160


RIG_MODEL_PROFILES = [
    {"id": "ICOM_IC705", "label": "Icom IC-705", "protocol": "ICOM_CIV", "default_civ": "0xA4"},
    {"id": "ICOM_IC7300", "label": "Icom IC-7300", "protocol": "ICOM_CIV", "default_civ": "0x94"},
    {"id": "ICOM_IC9700", "label": "Icom IC-9700", "protocol": "ICOM_CIV", "default_civ": "0xA2"},
    {"id": "ICOM_IC7100", "label": "Icom IC-7100", "protocol": "ICOM_CIV", "default_civ": "0x88"},
    {"id": "ICOM_IC7610", "label": "Icom IC-7610", "protocol": "ICOM_CIV", "default_civ": "0x98"},
    {"id": "ICOM_IC718", "label": "Icom IC-718", "protocol": "ICOM_CIV", "default_civ": "0x5E"},
    {"id": "ICOM_CUSTOM", "label": "Icom Custom CI-V", "protocol": "ICOM_CIV", "default_civ": None},
    {"id": "YAESU_FT817", "label": "Yaesu FT-817/818", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FT857", "label": "Yaesu FT-857D", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FT891", "label": "Yaesu FT-891", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FT991A", "label": "Yaesu FT-991A", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FT710", "label": "Yaesu FT-710", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FTDX10", "label": "Yaesu FTDX10", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "YAESU_FTDX101", "label": "Yaesu FTDX101", "protocol": "YAESU_CAT", "default_civ": None},
    {"id": "KENWOOD_TS2000", "label": "Kenwood TS-2000", "protocol": "KENWOOD_CAT", "default_civ": None},
    {"id": "KENWOOD_TS480", "label": "Kenwood TS-480", "protocol": "KENWOOD_CAT", "default_civ": None},
    {"id": "KENWOOD_TS590", "label": "Kenwood TS-590SG", "protocol": "KENWOOD_CAT", "default_civ": None},
    {"id": "KENWOOD_TS890", "label": "Kenwood TS-890", "protocol": "KENWOOD_CAT", "default_civ": None},
    {"id": "KENWOOD_TM710", "label": "Kenwood TM-D710", "protocol": "KENWOOD_CAT", "default_civ": None},
    {"id": "ELECRAFT_K3", "label": "Elecraft K3/K3S", "protocol": "ELECRAFT_CAT", "default_civ": None},
    {"id": "ELECRAFT_K4", "label": "Elecraft K4", "protocol": "ELECRAFT_CAT", "default_civ": None},
    {"id": "ELECRAFT_KX3", "label": "Elecraft KX3/KX2", "protocol": "ELECRAFT_CAT", "default_civ": None},
    {"id": "ALINCO_DXSR9", "label": "Alinco DX-SR9", "protocol": "ALINCO_CAT", "default_civ": None},
    {"id": "GENERIC", "label": "Generic rigctld/TCP", "protocol": "GENERIC", "default_civ": None},
]


GENERIC_WINDOWS_DEVICE_TOKENS = (
    "microsoft sound mapper",
    "mapowanie dzwieku microsoft",
    "mapowanie dĹşwiÄ™ku microsoft",
    "primary sound capture driver",
    "primary sound driver",
    "podstawowy sterownik przechwytywania dzwieku",
    "podstawowy sterownik przechwytywania dĹşwiÄ™ku",
    "podstawowy sterownik dzwieku",
    "podstawowy sterownik dĹşwiÄ™ku",
)

GENERIC_ENDPOINT_BASES = {
    "speakers",
    "output",
    "input",
    "microphone",
    "line in",
    "line input",
    "spdif out",
}


class ClickSelectComboBox(QComboBox):
    """Prevent accidental mouse-wheel selection changes when popup is closed."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class StartupAbortError(RuntimeError):
    """Raised when startup preconditions are not met."""


def is_tcp_port_available(port: int) -> bool:
    """Check whether a TCP port can be bound by this process."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", int(port)))
        sock.close()
        return True
    except OSError:
        return False


def show_kiss_port_busy_dialog(port: int) -> None:
    """Display a blocking message when KISS server port is already occupied."""
    # Default language is English; if user has existing config, honor saved UI language.
    lang = "en"
    try:
        cfg_path = Path.home() / ".microkisstnc" / "config.json"
        if cfg_path.exists():
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            selected = str(raw.get("application", {}).get("ui_language", "en") or "en").lower()
            if selected in ("en", "de", "fr", "es", "pl"):
                lang = selected
    except Exception:
        lang = "en"

    title_map = {
        "en": "KISS Server Unavailable",
        "de": "KISS-Server nicht verfugbar",
        "fr": "Serveur KISS indisponible",
        "es": "Servidor KISS no disponible",
        "pl": "Serwer KISS niedostępny",
    }
    text_map = {
        "en": (
            "PORT {port} ALREADY IN USE!\n\n"
            "Application startup has been cancelled to avoid duplicate instance."
        ),
        "de": (
            "PORT {port} WIRD BEREITS VERWENDET!\n\n"
            "Der Start wurde abgebrochen, um eine doppelte Instanz zu vermeiden."
        ),
        "fr": (
            "LE PORT {port} EST DEJA UTILISE !\n\n"
            "Le demarrage a ete annule pour eviter une instance en double."
        ),
        "es": (
            "EL PUERTO {port} YA ESTA EN USO!\n\n"
            "El inicio de la aplicacion se cancelo para evitar una instancia duplicada."
        ),
        "pl": (
            "PORT {port} JEST JUŻ ZAJĘTY!\n\n"
            "Uruchomienie aplikacji anulowano, aby uniknąć duplikatu instancji."
        ),
    }

    port_busy_box = QMessageBox()
    port_busy_box.setIcon(QMessageBox.Icon.Warning)
    port_busy_box.setWindowTitle(title_map.get(lang, title_map["en"]))
    port_busy_box.setText(text_map.get(lang, text_map["en"]).format(port=int(port)))
    port_busy_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    port_busy_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    port_busy_box.exec()


def set_windows_appusermodel_id() -> None:
    """Set explicit Windows AppUserModelID so taskbar uses app identity/icon consistently."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception as e:
        logger.debug(f"[APP] Could not set AppUserModelID: {e}")


class MicroKISStnc(QMainWindow):
    """Main application window"""
    SUPPORTED_UI_LANGS = ("en", "de", "fr", "es", "pl")
    UI_TRANSLATIONS = {
        "en": {
            "hide_to_tray": "Hide to tray",
            "language": "Language",
            "kiss_port": "KISS port:",
            "audio_tab": "Audio",
            "ptt_control_tab": "PTT Control",
            "delay_group": "Delay",
            "created_by": "Created by SP5ME",
            "config_subtitle": "Basic settings",
            "config_mode": "Config mode:",
            "basic_mode": "Basic",
            "advanced_mode": "Advanced",
            "basic_tab": "Basic",
            "net_config": "Net Config",
            "main_tab_monitor": "Monitor",
            "main_tab_config": "Configuration",
            "main_tab_about": "About",
            "about_title": "About application",
            "about_description": "Desktop APRS/KISS TNC for audio, PTT and network control.",
            "about_build": "Build:",
            "about_kiss": "KISS server:",
            "about_web": "Web UI:",
            "web_enabled": "Web interface enabled",
            "allowed_addresses": "Allowed addresses",
            "allowed_placeholder": "0.0.0.0, 192.168.1.20 or 192.168.1.0/24",
            "toggle": "Add/Remove",
            "localhost_hint": "Localhost always allowed: 127.0.0.1, ::1 | You can add single IP or CIDR network (e.g. 192.168.1.0/24)",
            "devices_group": "DEVICES IN/OUT",
            "audio_input": "Audio INPUT (Microphones):",
            "audio_output": "Audio OUTPUT (Speakers):",
            "refresh": "Refresh",
            "select_mic": "-- Select Microphone --",
            "select_speaker": "-- Select Speaker --",
            "signal_level": "Signal Level:",
            "test_tones": "Test Tones:",
            "both": "Both",
            "ptt_group": "PTT CONTROL",
            "ptt_type": "PTT Type:",
            "ptt_desc": "(RIG/CAT, DTR, RTS, VOX) - Hamlib model",
            "select_mode": "-- Select Mode --",
            "rig_cat_control": "RIG / CAT Control",
            "rig_model": "RIG model:",
            "ptt_path_serial": "PTT serial port:",
            "civaddr_label": "CI-V address:",
            "select_com": "-- Select COM Port --",
            "ptt_share": "ptt_share",
            "cat_connection": "CAT connection:",
            "tcp_connection": "TCP connection",
            "serial_connection": "Serial connection",
            "hamlib_host": "Hamlib Host:",
            "port": "Port:",
            "test": "Test",
            "connection_test": "Connection test",
            "hamlib_not_tested": "Hamlib: not tested",
            "monitor_group": "MONITOR - Frame Log",
            "monitor_freeze": "Freeze monitor:",
            "config_toggle": "Configuration",
            "config_toggle_off": "Configuration OFF",
            "ptt_active_low": "Invert",
            "rts_on": "RTS forced ON",
            "dtr_on": "DTR forced ON",
            "ptt_test": "PTT TEST",
            "tx_delay": "TX Delay (ms):",
            "tx_tail": "TX Tail (ms):",
            "rts_active_low": "RTS active low",
            "dtr_active_low": "DTR active low",
            "tt_ptt_mode": "Selects PTT keying method: RIG/CAT, DTR, RTS, or no PTT.",
            "tt_rig_model": "CAT radio profile. In Serial mode, model-specific commands are sent.",
            "tt_ptt_port": "Serial port used for DTR/RTS keying.",
            "tt_ptt_active_low": "Inverts the currently selected DTR or RTS PTT line. Each line keeps its own saved invert setting.",
            "tt_civaddr": "Radio CI-V address (hex), e.g. 0xA4 for IC-705.",
            "tt_rts_on": "Force RTS=ON on the RIG CAT serial port.",
            "tt_dtr_on": "Force DTR=ON on the RIG CAT serial port.",
            "tt_cat_connection": "CAT transport for RIG: TCP to rigctld or direct serial connection.",
            "tt_cat_serial_port": "COM port used for CAT commands (CI-V) when Serial connection is selected.",
            "tt_cat_serial_baud": "CAT speed on serial port. Must match radio settings.",
            "tt_hamlib_host": "rigctld host address (Hamlib TCP), usually 127.0.0.1.",
            "tt_hamlib_port": "rigctld port (default 4532).",
            "tt_hamlib_test": "Queries radio frequency and checks the CAT response.",
            "tt_ptt_test": "Manual PTT test toggle (green=OFF, red=ON).",
            "tt_rts_active_low": "Invert RTS logic: LOW=TX, HIGH=RX.",
            "tt_dtr_active_low": "Invert DTR logic: LOW=TX, HIGH=RX.",
            "ptt_reset_defaults": "Reset TX/PTT defaults",
            "tt_ptt_reset_defaults": "Restore default TX/PTT settings.",
            "cat_serial_port": "CAT serial port:",
            "baud": "Baud:",
            "data_bits": "Data bits:",
            "parity": "Parity:",
            "stop_bits": "Stop bits:",
            "web_interface": "Web Interface",
            "web_start_error": "Could not start web interface.",
            "kiss_error_title": "KISS Server Error",
        },
        "de": {
            "hide_to_tray": "In Tray minimieren", "language": "Sprache", "kiss_port": "KISS-Port:",
            "audio_tab": "Audio", "ptt_control_tab": "PTT Control",
            "delay_group": "Delay",
            "created_by": "Created by SP5ME",
            "config_subtitle": "Grundeinstellungen",
            "config_mode": "Konfigurationsmodus:",
            "basic_mode": "Einfach",
            "advanced_mode": "Erweitert",
            "basic_tab": "Einfach",
            "net_config": "Netzwerk",
            "main_tab_monitor": "Monitor",
            "main_tab_config": "Konfiguration",
            "main_tab_about": "Info",
            "about_title": "Informationen zur Anwendung",
            "about_description": "Desktop-APRS/KISS-TNC für Audio-, PTT- und Netzwerksteuerung.",
            "about_build": "Build:",
            "about_kiss": "KISS-Server:",
            "about_web": "Web UI:",
            "web_enabled": "WeboberflĂ¤che aktiviert", "allowed_addresses": "Erlaubte Adressen", "toggle": "Hinzufugen/Entfernen",
            "devices_group": "GERĂ„TE IN/OUT", "refresh": "Aktualisieren", "signal_level": "Signalpegel:",
            "test_tones": "TesttĂ¶ne:", "both": "Beide", "ptt_group": "PTT-STEUERUNG",
            "ptt_type": "PTT-Typ:", "rig_cat_control": "RIG / CAT Steuerung", "test": "Test",
            "connection_test": "Verbindungstest",
            "monitor_group": "MONITOR - Frame-Protokoll",
            "config_toggle": "Konfiguration", "config_toggle_off": "Konfiguration AUS",
            "ptt_active_low": "Invert",
            "rts_on": "RTS fest EIN", "dtr_on": "DTR fest EIN", "ptt_test": "PTT TEST", "tx_delay": "TX Delay (ms):",
            "tx_tail": "TX Tail (ms):",
            "rts_active_low": "RTS aktiv low",
            "dtr_active_low": "DTR aktiv low",
            "tt_ptt_mode": "Wahlt die PTT-Tastmethode: RIG/CAT, DTR, RTS oder kein PTT.",
            "tt_rig_model": "CAT-Funkprofil. Im seriellen Modus werden modellspezifische Befehle gesendet.",
            "tt_ptt_port": "Serieller Port fur DTR/RTS-Tastung.",
            "tt_ptt_active_low": "Invertiert DTR/RTS-Logik: LOW=TX, HIGH=RX.",
            "tt_civaddr": "CI-V-Adresse des Funkgerats (hex), z. B. 0xA4 fur IC-705.",
            "tt_rts_on": "Erzwingt RTS=ON als festen Zustand (unabhangig vom PTT-Impuls).",
            "tt_dtr_on": "Erzwingt DTR=ON als festen Zustand (unabhangig vom PTT-Impuls).",
            "tt_cat_connection": "CAT-Transport fur RIG: TCP zu rigctld oder direkte serielle Verbindung.",
            "tt_cat_serial_port": "COM-Port fur CAT-Befehle (CI-V), wenn serielle Verbindung aktiv ist.",
            "tt_cat_serial_baud": "CAT-Geschwindigkeit am seriellen Port. Muss zu den Funkgerat-Einstellungen passen.",
            "tt_hamlib_host": "rigctld-Hostadresse (Hamlib TCP), meist 127.0.0.1.",
            "tt_hamlib_port": "rigctld-Port (Standard 4532).",
            "tt_hamlib_test": "Fragt die Radiofrequenz ab und prueft die CAT-Antwort.",
            "tt_ptt_test": "Manueller PTT-Testschalter (grun=OFF, rot=ON).",
            "tt_rts_active_low": "Invertiert die RTS-Logik: LOW=TX, HIGH=RX.",
            "tt_dtr_active_low": "Invertiert die DTR-Logik: LOW=TX, HIGH=RX.",
            "ptt_reset_defaults": "TX/PTT auf Standard",
            "tt_ptt_reset_defaults": "Stellt die Standardwerte fur TX/PTT wieder her.",
            "civaddr_label": "CI-V-Adresse:",
            "cat_serial_port": "CAT-Seriellport:",
            "baud": "Baud:",
            "data_bits": "Datenbits:",
            "parity": "Paritat:",
            "stop_bits": "Stoppbits:"
        },
        "fr": {
            "hide_to_tray": "RĂ©duire dans la zone", "language": "Langue", "kiss_port": "Port KISS :",
            "audio_tab": "Audio", "ptt_control_tab": "PTT Control",
            "delay_group": "Delai",
            "created_by": "Created by SP5ME",
            "config_subtitle": "Parametres de base",
            "config_mode": "Mode de configuration :",
            "basic_mode": "Basique",
            "advanced_mode": "Avance",
            "basic_tab": "Basique",
            "net_config": "Reseau",
            "main_tab_monitor": "Moniteur",
            "main_tab_config": "Configuration",
            "main_tab_about": "A propos",
            "about_title": "A propos de l'application",
            "about_description": "TNC de bureau APRS/KISS pour l'audio, le PTT et le reseau.",
            "about_build": "Build :",
            "about_kiss": "Serveur KISS :",
            "about_web": "Web UI :",
            "web_enabled": "Interface web activĂ©e", "allowed_addresses": "Adresses autorisĂ©es", "toggle": "Ajouter/Retirer",
            "devices_group": "PĂ‰RIPHĂ‰RIQUES IN/OUT", "refresh": "RafraĂ®chir", "signal_level": "Niveau du signal :",
            "test_tones": "TonalitĂ©s de test :", "both": "Les deux", "ptt_group": "CONTRĂ”LE PTT",
            "ptt_type": "Type PTT :", "rig_cat_control": "ContrĂ´le RIG / CAT", "test": "Tester",
            "connection_test": "Test connexion",
            "monitor_group": "MONITEUR - Journal des trames",
            "config_toggle": "Configuration", "config_toggle_off": "Configuration OFF",
            "ptt_active_low": "Invert",
            "rts_on": "RTS force ON", "dtr_on": "DTR force ON", "ptt_test": "TEST PTT", "tx_delay": "Delai TX (ms) :",
            "tx_tail": "Queue TX (ms) :",
            "rts_active_low": "RTS actif bas",
            "dtr_active_low": "DTR actif bas",
            "tt_ptt_mode": "Selectionne la methode de commande PTT : RIG/CAT, DTR, RTS ou aucun PTT.",
            "tt_rig_model": "Profil radio CAT. En mode serie, des commandes specifiques au modele sont envoyees.",
            "tt_ptt_port": "Port serie utilise pour la commande DTR/RTS.",
            "tt_ptt_active_low": "Inverse la logique DTR/RTS : BAS=TX, HAUT=RX.",
            "tt_civaddr": "Adresse CI-V de la radio (hex), ex. 0xA4 pour IC-705.",
            "tt_rts_on": "Force RTS=ON en etat fixe (independant de l'impulsion PTT).",
            "tt_dtr_on": "Force DTR=ON en etat fixe (independant de l'impulsion PTT).",
            "tt_cat_connection": "Transport CAT pour RIG : TCP vers rigctld ou liaison serie directe.",
            "tt_cat_serial_port": "Port COM pour les commandes CAT (CI-V) quand la connexion serie est selectionnee.",
            "tt_cat_serial_baud": "Vitesse CAT du port serie. Doit correspondre aux reglages de la radio.",
            "tt_hamlib_host": "Adresse hote rigctld (Hamlib TCP), generalement 127.0.0.1.",
            "tt_hamlib_port": "Port rigctld (par defaut 4532).",
            "tt_hamlib_test": "Interroge la frequence radio et verifie la reponse CAT.",
            "tt_ptt_test": "Bascule test PTT manuel (vert=OFF, rouge=ON).",
            "tt_rts_active_low": "Inverse la logique RTS : BAS=TX, HAUT=RX.",
            "tt_dtr_active_low": "Inverse la logique DTR : BAS=TX, HAUT=RX.",
            "ptt_reset_defaults": "Reinitialiser TX/PTT",
            "tt_ptt_reset_defaults": "Restaure les valeurs par defaut TX/PTT.",
            "civaddr_label": "Adresse CI-V :",
            "cat_serial_port": "Port serie CAT :",
            "baud": "Baud :",
            "data_bits": "Bits de donnees :",
            "parity": "Parite :",
            "stop_bits": "Bits d'arret :"
        },
        "es": {
            "hide_to_tray": "Ocultar en bandeja", "language": "Idioma", "kiss_port": "Puerto KISS:",
            "audio_tab": "Audio", "ptt_control_tab": "PTT Control",
            "delay_group": "Retardo",
            "created_by": "Created by SP5ME",
            "config_subtitle": "Ajustes basicos",
            "config_mode": "Modo de configuracion:",
            "basic_mode": "Basico",
            "advanced_mode": "Avanzado",
            "basic_tab": "Basico",
            "net_config": "Red",
            "main_tab_monitor": "Monitor",
            "main_tab_config": "Configuracion",
            "main_tab_about": "Acerca de",
            "about_title": "Acerca de la aplicacion",
            "about_description": "TNC APRS/KISS de escritorio para audio, PTT y control de red.",
            "about_build": "Build:",
            "about_kiss": "Servidor KISS:",
            "about_web": "Web UI:",
            "web_enabled": "Interfaz web habilitada", "allowed_addresses": "Direcciones permitidas", "toggle": "Agregar/Quitar",
            "devices_group": "DISPOSITIVOS IN/OUT", "refresh": "Actualizar", "signal_level": "Nivel de seĂ±al:",
            "test_tones": "Tonos de prueba:", "both": "Ambos", "ptt_group": "CONTROL PTT",
            "ptt_type": "Tipo de PTT:", "rig_cat_control": "Control RIG / CAT", "test": "Probar",
            "connection_test": "Probar conexion",
            "monitor_group": "MONITOR - Registro de tramas",
            "config_toggle": "Configuracion", "config_toggle_off": "Configuracion OFF",
            "ptt_active_low": "Invert",
            "rts_on": "RTS forzado ON", "dtr_on": "DTR forzado ON", "ptt_test": "PRUEBA PTT", "tx_delay": "Retardo TX (ms):",
            "tx_tail": "Cola TX (ms):",
            "rts_active_low": "RTS activo en bajo",
            "dtr_active_low": "DTR activo en bajo",
            "tt_ptt_mode": "Selecciona el metodo de activacion PTT: RIG/CAT, DTR, RTS o sin PTT.",
            "tt_rig_model": "Perfil de radio CAT. En modo serie se envian comandos especificos del modelo.",
            "tt_ptt_port": "Puerto serie usado para activacion DTR/RTS.",
            "tt_ptt_active_low": "Invierte la logica DTR/RTS: BAJO=TX, ALTO=RX.",
            "tt_civaddr": "Direccion CI-V de la radio (hex), p. ej. 0xA4 para IC-705.",
            "tt_rts_on": "Fuerza RTS=ON como estado fijo (independiente del pulso PTT).",
            "tt_dtr_on": "Fuerza DTR=ON como estado fijo (independiente del pulso PTT).",
            "tt_cat_connection": "Transporte CAT para RIG: TCP a rigctld o conexion serie directa.",
            "tt_cat_serial_port": "Puerto COM para comandos CAT (CI-V) cuando se selecciona conexion serie.",
            "tt_cat_serial_baud": "Velocidad CAT del puerto serie. Debe coincidir con la configuracion de la radio.",
            "tt_hamlib_host": "Direccion del host rigctld (Hamlib TCP), normalmente 127.0.0.1.",
            "tt_hamlib_port": "Puerto rigctld (predeterminado 4532).",
            "tt_hamlib_test": "Consulta la frecuencia de la radio y verifica la respuesta CAT.",
            "tt_ptt_test": "Conmutador manual de prueba PTT (verde=OFF, rojo=ON).",
            "tt_rts_active_low": "Invierte la logica RTS: BAJO=TX, ALTO=RX.",
            "tt_dtr_active_low": "Invierte la logica DTR: BAJO=TX, ALTO=RX.",
            "ptt_reset_defaults": "Restablecer TX/PTT",
            "tt_ptt_reset_defaults": "Restaura los valores predeterminados de TX/PTT.",
            "civaddr_label": "Direccion CI-V:",
            "cat_serial_port": "Puerto serie CAT:",
            "baud": "Baudios:",
            "data_bits": "Bits de datos:",
            "parity": "Paridad:",
            "stop_bits": "Bits de parada:"
        },
        "pl": {
            "hide_to_tray": "Ukryj do traya",
            "language": "Język",
            "kiss_port": "Port KISS:",
            "audio_tab": "Audio",
            "ptt_control_tab": "PTT Control",
            "delay_group": "Opóźnienia",
            "created_by": "Created by SP5ME",
            "config_subtitle": "Ustawienia podstawowe",
            "config_mode": "Tryb konfiguracji:",
            "basic_mode": "Podstawowy",
            "advanced_mode": "Zaawansowany",
            "basic_tab": "Podstawowy",
            "net_config": "Sieć",
            "main_tab_monitor": "Monitor",
            "main_tab_config": "Konfiguracja",
            "main_tab_about": "O aplikacji",
            "about_title": "O aplikacji",
            "about_description": "Desktopowy TNC APRS/KISS do audio, PTT i sterowania siecią.",
            "about_build": "Wersja:",
            "about_kiss": "Serwer KISS:",
            "about_web": "Web UI:",
            "web_enabled": "Interfejs web włączony",
            "allowed_addresses": "Dozwolone adresy",
            "allowed_placeholder": "0.0.0.0, 192.168.1.20 lub 192.168.1.0/24",
            "toggle": "Dodaj/Usuń",
            "localhost_hint": "Localhost zawsze dozwolony: 127.0.0.1, ::1 | Możesz dodać pojedyncze IP lub sieć CIDR (np. 192.168.1.0/24)",
            "devices_group": "URZĄDZENIA IN/OUT",
            "audio_input": "Audio INPUT (Mikrofony):",
            "audio_output": "Audio OUTPUT (Głośniki):",
            "refresh": "Odśwież",
            "select_mic": "-- Wybierz mikrofon --",
            "select_speaker": "-- Wybierz głośnik --",
            "signal_level": "Poziom sygnału:",
            "test_tones": "Tony testowe:",
            "both": "Oba",
            "ptt_group": "KONTROLA PTT",
            "ptt_type": "Typ PTT:",
            "ptt_desc": "(RIG/CAT, DTR, RTS, VOX) - model Hamlib",
            "select_mode": "-- Wybierz tryb --",
            "rig_cat_control": "Kontrola RIG / CAT",
            "rig_model": "Model RIG:",
            "ptt_path_serial": "Port PTT (szeregowy):",
            "civaddr_label": "Adres CI-V:",
            "select_com": "-- Wybierz port COM --",
            "cat_connection": "Połączenie CAT:",
            "tcp_connection": "Połączenie TCP",
            "serial_connection": "Połączenie szeregowe",
            "hamlib_host": "Host Hamlib:",
            "port": "Port:",
            "test": "Test",
            "connection_test": "Test połączenia",
            "hamlib_not_tested": "Hamlib: nie testowano",
            "monitor_group": "MONITOR - Log ramek",
            "monitor_freeze": "Zamroź monitor:",
            "config_toggle": "Konfiguracja",
            "config_toggle_off": "Konfiguracja OFF",
            "ptt_active_low": "Invert",
            "rts_on": "RTS wymuszone ON",
            "dtr_on": "DTR wymuszone ON",
            "ptt_test": "TEST PTT",
            "tx_delay": "TX Delay (ms):",
            "tx_tail": "TX Tail (ms):",
            "rts_active_low": "RTS aktywne stanem niskim",
            "dtr_active_low": "DTR aktywne stanem niskim",
            "tt_ptt_mode": "Wybiera metodę kluczowania PTT: RIG/CAT, DTR, RTS albo brak PTT.",
            "tt_rig_model": "Profil radia dla CAT. W trybie szeregowym wysyłane są komendy zależne od modelu.",
            "tt_ptt_port": "Port szeregowy używany do kluczowania DTR/RTS.",
            "tt_ptt_active_low": "Odwraca aktualnie wybraną linię DTR albo RTS. Każda linia pamięta własne ustawienie inwersji.",
            "tt_civaddr": "Adres CI-V radia (hex), np. 0xA4 dla IC-705.",
            "tt_rts_on": "Wymusza RTS=ON na szeregowym porcie CAT w trybie RIG.",
            "tt_dtr_on": "Wymusza DTR=ON na szeregowym porcie CAT w trybie RIG.",
            "tt_cat_connection": "Transport CAT dla RIG: TCP do rigctld albo bezpośrednie połączenie szeregowe.",
            "tt_cat_serial_port": "Port COM używany do komend CAT (CI-V), gdy wybrane jest połączenie szeregowe.",
            "tt_cat_serial_baud": "Prędkość CAT na porcie szeregowym. Musi zgadzać się z ustawieniami radia.",
            "tt_hamlib_host": "Adres hosta rigctld (Hamlib TCP), zwykle 127.0.0.1.",
            "tt_hamlib_port": "Port rigctld (domyślnie 4532).",
            "tt_hamlib_test": "Odpytuje radio o częstotliwość i sprawdza odpowiedź CAT.",
            "tt_ptt_test": "Ręczny test PTT (zielony=OFF, czerwony=ON).",
            "tt_rts_active_low": "Odwraca logikę RTS: NISKI=TX, WYSOKI=RX.",
            "tt_dtr_active_low": "Odwraca logikę DTR: NISKI=TX, WYSOKI=RX.",
            "ptt_reset_defaults": "Reset TX/PTT do domyślnych",
            "tt_ptt_reset_defaults": "Przywraca domyślne ustawienia TX/PTT.",
            "cat_serial_port": "Port szeregowy CAT:",
            "baud": "Baud:",
            "data_bits": "Bity danych:",
            "parity": "Parzystość:",
            "stop_bits": "Bity stopu:",
            "web_interface": "Interfejs web",
            "web_start_error": "Nie udało się uruchomić interfejsu web.",
            "kiss_error_title": "Błąd serwera KISS"
        },
    }
    
    # Qt Signals for thread-safe GUI updates
    sig_monitor_line = pyqtSignal(str, str, str)  # (direction, timestamp, frame_info)
    sig_kiss_error = pyqtSignal(str)  # (error_message) - thread-safe error display
    sig_tx_audio = pyqtSignal(list)  # (audio_data as list) - thread-safe audio output from KISS thread
    
    def __init__(self):
        super().__init__()
        
        # Initialize system tray early (may be used in closeEvent)
        self.tray_icon = None
        self.app_icon = QIcon()
        
        # Initialize components
        self.config = ConfigManager()
        self.ui_language = str(self.config.get("application.ui_language", "en") or "en").lower()
        if self.ui_language not in self.SUPPORTED_UI_LANGS:
            self.ui_language = "en"
        self.app_build_tag = "1.1.0"
        self.ax25_local_callsign = str(self.config.get("ax25.local_callsign", "N0CALL-1") or "N0CALL-1").upper()
        self.ax25_l2_enabled = bool(self.config.get("ax25.l2_enabled", True))
        self.ax25_l2_sessions: Dict[str, Dict[str, int]] = {}
        self.audio_monitor_in = AudioMonitor()
        self.audio_monitor_out = AudioMonitor()
        self.tone_gen = TestToneGenerator(sample_rate=44100)  # Initialize with default rate
        
        # System volume monitor (Windows) - syncs TX/RX levels with system volume
        self.system_volume_monitor = SystemVolumeMonitor(callback=self.on_system_volume_changed)
        self.current_tx_amplitude = 0.8  # Start with default
        
        # Track active tone button
        self.active_tone_button = None
        
        # Audio streaming
        self.audio_stream_in = None
        self.audio_stream_out = None
        self.audio_chunk_size = 2048  # Samples per chunk
        self.actual_output_sample_rate = 44100  # Store ACTUAL device rate (not requested)
        self.actual_input_sample_rate = 44100   # Store ACTUAL input device rate
        self._last_output_meter_update_ts = 0.0
        self.tx_intent_want = False
        self.tx_intent_ptt_on = False
        self.tx_intent_started_monotonic = 0.0
        
        # PTT control (Hamlib-aligned model, LGPL-2.1 naming semantics)
        self.ppt_serial: Optional[serial.Serial] = None
        legacy_mode = str(self.config.get("ppt.mode", "VOX") or "VOX")
        self.ptt_type = str(self.config.get("ptt.ptt_type", self._normalize_ptt_type(legacy_mode)))
        self.ptt_port = str(self.config.get("ptt.path", "") or "")
        self.ptt_share = bool(self.config.get("ptt.share", False))
        self.ptt_active_low = bool(self.config.get("ptt.active_low", False))
        self.civaddr = str(self.config.get("ptt.civaddr", "0x00") or "0x00")
        self.dtr_state = str(self.config.get("ptt.dtr_state", "Unset") or "Unset")
        self.rts_state = str(self.config.get("ptt.rts_state", "Unset") or "Unset")
        self.ptt_mode = self.ptt_type  # Backward compatibility with old key naming.
        self.ptt_active = False
        self.hamlib_host = str(self.config.get("ptt.hamlib_host", "127.0.0.1"))
        try:
            self.hamlib_port = int(self.config.get("ptt.hamlib_port", 4532))
        except Exception:
            self.hamlib_port = 4532
        self.rig_connection = self._normalize_rig_connection(self.config.get("ptt.rig_connection", "TCP"))
        self.cat_serial_port = str(self.config.get("ptt.rig_serial_path", "") or "")
        try:
            self.cat_serial_baud = int(self.config.get("ptt.rig_serial_baud", 19200))
        except Exception:
            self.cat_serial_baud = 19200
        try:
            self.cat_serial_data_bits = int(self.config.get("ptt.rig_serial_data_bits", 8))
        except Exception:
            self.cat_serial_data_bits = 8
        self.cat_serial_data_bits = 8 if self.cat_serial_data_bits not in (5, 6, 7, 8) else self.cat_serial_data_bits
        self.cat_serial_parity = str(self.config.get("ptt.rig_serial_parity", "N") or "N").upper()
        if self.cat_serial_parity not in ("N", "E", "O"):
            self.cat_serial_parity = "N"
        self.cat_serial_stop_bits = str(self.config.get("ptt.rig_serial_stop_bits", "1") or "1")
        if self.cat_serial_stop_bits not in ("1", "2"):
            self.cat_serial_stop_bits = "1"
        self.rig_model = self._normalize_rig_model(self.config.get("ptt.rig_model", "ICOM_CUSTOM"))
        try:
            self.tx_delay_ms = int(self.config.get("ptt.tx_delay_ms", self.config.get("ptt.vox_delay_ms", DEFAULT_TX_DELAY_MS)))
        except Exception:
            self.tx_delay_ms = DEFAULT_TX_DELAY_MS
        self.tx_delay_ms = max(0, min(5000, int(self.tx_delay_ms)))
        try:
            self.tx_tail_ms = int(self.config.get("ptt.tx_tail_ms", DEFAULT_TX_TAIL_MS))
        except Exception:
            self.tx_tail_ms = DEFAULT_TX_TAIL_MS
        self.tx_tail_ms = max(0, min(5000, int(self.tx_tail_ms)))
        self.pre_tx_flags_enabled = True
        self.post_tx_flags_enabled = True
        self.dtr_active_low = bool(self.config.get("ptt.dtr_active_low", self.ptt_active_low))
        self.rts_active_low = bool(self.config.get("ptt.rts_active_low", self.ptt_active_low))
        self._tx_last_segments = {"preamble_samples": 0, "frame_samples": 0, "postamble_samples": 0}
        self.hamlib_timeout_s = 1.0
        self.web_ui_enabled = bool(self.config.get("application.web_ui_enabled", True))
        try:
            self.kiss_port = int(self.config.get("kiss.port", KISS_SERVER_PORT))
        except Exception:
            self.kiss_port = KISS_SERVER_PORT
        self.kiss_port = max(1, min(65535, int(self.kiss_port)))
        self.close_to_tray_enabled = bool(self.config.get("application.close_to_tray_enabled", True))
        self.show_config_sections = bool(self.config.get("application.show_config_sections", True))
        self.config_ui_mode = self._normalize_config_ui_mode(self.config.get("application.config_ui_mode", "basic"))
        self.web_ui_running = False
        cfg_allow_ips = self.config.get("application.allow_ips", None)
        if isinstance(cfg_allow_ips, list):
            self.allowed_remote_ips = {str(ip).strip() for ip in cfg_allow_ips if str(ip).strip()}
        else:
            self.allowed_remote_ips = set(LAN_TRUSTED_CLIENT_IPS)
        if not self.allowed_remote_ips:
            self.allowed_remote_ips = {ALLOW_ALL_IP_TOKEN}
        
        # KISS server (runs in background thread)
        self.kiss_server = KISSServerApp(
            port=self.kiss_port,
            on_frame_received=self.on_kiss_frame_received,
            on_error=self.on_kiss_error,
            allowed_ips=self.allowed_remote_ips,
            max_clients=KISS_MAX_CLIENTS,
            max_buffer_bytes=KISS_MAX_BUFFER_BYTES,
            max_payload_bytes=KISS_MAX_PAYLOAD_BYTES,
        )

        # Local web interface (development v5)
        self.web_server = WebControlServer(
            host=WEB_UI_BIND_HOST,
            port=WEB_UI_PORT,
            get_status=self._get_web_status,
            allowed_ips=self.allowed_remote_ips,
            control_token=WEB_CONTROL_TOKEN,
            max_post_bytes=WEB_MAX_POST_BYTES,
        )
        self.last_monitor_line = ""
        self.monitor_lines = []
        self.monitor_line_kinds = []
        self.monitor_frozen = False
        self.last_tx_source_callsign = ""
        self._audio_switch_in_progress = False
        self.tx_echo_suppression_window_s = float(self.config.get("monitor.tx_echo_suppression_window_s", 2.5))
        self._recent_tx_frames = deque(maxlen=128)
        self._recent_tx_lock = threading.Lock()
        
        # RX Pipeline (audio decoding) - initialized with default, will be re-created when input stream starts
        # This ensures RX uses ACTUAL device sample rate, not hardcoded value
        self.rx_pipeline = RXPipeline(
            sample_rate=44100,
            on_frame_decoded=self.on_rx_frame_decoded,
            require_fcs=True,
            use_bandpass=True,
            rms_gate=0.003,
        )
        self.rx_pipeline_lock = threading.Lock()

        # RX worker decouples heavy DSP from real-time audio callback
        self.rx_audio_queue = queue.Queue(maxsize=8)
        self.rx_worker_thread = None
        self.rx_worker_running = False
        
        # TX Pipeline components (KISS â†’ HDLC â†’ AFSK â†’ Audio)
        self.hdlc_encoder = HDLCEncoder()
        # Note: AFSKModulator created dynamically per frame with device sample rate
        
        # Setup UI
        self.init_ui()
        self._apply_app_icon()
        self.restore_geometry()
        
        # Connect signals for thread-safe GUI updates
        self.sig_monitor_line.connect(self.add_monitor_line)
        self.sig_kiss_error.connect(self.show_kiss_error_dialog)
        self.sig_tx_audio.connect(self.on_tx_audio_data)  # THREAD-SAFE audio output
        
        # Timer for updating meters
        self.meter_update_timer = QTimer()
        self.meter_update_timer.timeout.connect(self.update_meters)
        self.meter_update_timer.start(200)  # Update every 200ms
        
        # Start audio monitoring
        self.start_audio_monitoring()
        
        # Start audio output stream for TX
        self.start_audio_output()
        
        # Start KISS server only when port remains available at init time.
        # This is a second safety check in case port state changed after preflight.
        if not self.check_port_available(self.kiss_port):
            logger.error(f"[APP] Port {self.kiss_port} became busy during initialization. Aborting startup.")
            show_kiss_port_busy_dialog(self.kiss_port)
            raise StartupAbortError(f"KISS port {self.kiss_port} is busy")

        self.kiss_server.start()

        # Register web control handlers and apply persisted web UI state.
        self._register_web_handlers()
        self._set_web_ui_enabled(self.web_ui_enabled, persist=False)
        
        # Setup system tray icon for minimize to tray functionality
        self.setup_system_tray()
        self._apply_ui_texts()
        
        logger.info(f"[APP] MicroKISStnc Desktop v1.0 initialized ({self.app_build_tag})")

    def _iter_icon_candidates(self):
        """Yield potential icon locations for source and frozen onefile builds."""
        seen = set()
        candidates = []

        script_dir = Path(__file__).resolve().parent
        candidates.append(script_dir / APP_ICON_FILE)
        candidates.append(script_dir.parent / APP_ICON_FILE)

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / APP_ICON_FILE)
            candidates.append(exe_dir.parent / APP_ICON_FILE)

            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                candidates.append(Path(meipass) / APP_ICON_FILE)

        candidates.append(Path.cwd() / APP_ICON_FILE)

        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            yield candidate

    def _apply_app_icon(self):
        """Apply app icon for window/taskbar/tray from known icon locations."""
        for icon_path in self._iter_icon_candidates():
            if not icon_path.exists():
                continue

            icon = QIcon(str(icon_path))
            if icon.isNull():
                continue

            self.app_icon = icon
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)
            logger.info(f"[APP] Loaded icon: {icon_path}")
            return

        logger.warning("[APP] Custom icon not found. Using default Qt/system icon.")

    def _t(self, key: str) -> str:
        lang_map = self.UI_TRANSLATIONS.get(self.ui_language, {})
        en_map = self.UI_TRANSLATIONS["en"]
        return str(lang_map.get(key, en_map.get(key, key)))

    def _set_ui_language(self, lang: str, persist: bool = True) -> None:
        selected = str(lang or "en").lower()
        if selected not in self.SUPPORTED_UI_LANGS:
            selected = "en"
        self.ui_language = selected
        if persist:
            self.config.set("application.ui_language", self.ui_language)
            self.config.save()
        self._apply_ui_texts()

    def _apply_ui_texts(self) -> None:
        if hasattr(self, "check_close_to_tray"):
            self.check_close_to_tray.setText(self._t("hide_to_tray"))
        if hasattr(self, "check_close_to_tray_monitor"):
            self.check_close_to_tray_monitor.setText(self._t("hide_to_tray"))
        if hasattr(self, "label_lang"):
            self.label_lang.setText(self._t("language"))
        if hasattr(self, "label_lang_monitor"):
            self.label_lang_monitor.setText(self._t("language"))
        if hasattr(self, "combo_ui_lang"):
            self._set_combo_by_data(self.combo_ui_lang, self.ui_language)
        if hasattr(self, "combo_ui_lang_monitor"):
            self._set_combo_by_data(self.combo_ui_lang_monitor, self.ui_language)
        if hasattr(self, "label_subtitle"):
            self.label_subtitle.setText(self._t("config_subtitle"))
        if hasattr(self, "label_created_by"):
            self.label_created_by.setText(self._t("created_by"))
        if hasattr(self, "main_stack") and self.main_stack.count() >= 3:
            self.main_stack.setTabText(0, self._t("main_tab_monitor"))
            self.main_stack.setTabText(1, self._t("main_tab_config"))
            self.main_stack.setTabText(2, self._t("main_tab_about"))
        if hasattr(self, "label_about_desc"):
            self.label_about_desc.setText(self._t("about_description"))
        if hasattr(self, "label_about_build"):
            self.label_about_build.setText(f"{self._t('about_build')} {self.app_build_tag}")
        if hasattr(self, "label_about_kiss"):
            self.label_about_kiss.setText(f"{self._t('about_kiss')} 127.0.0.1:{self.kiss_port}")
        if hasattr(self, "label_about_web"):
            self.label_about_web.setText(f"{self._t('about_web')} {WEB_UI_BIND_HOST}:{WEB_UI_PORT}")
        if hasattr(self, "label_about_author"):
            self.label_about_author.setText(self._t("created_by"))
        if hasattr(self, "label_config_mode"):
            self.label_config_mode.setText(self._t("config_mode"))
        if hasattr(self, "combo_config_mode") and self.combo_config_mode.count() >= 2:
            self.combo_config_mode.setItemText(0, self._t("basic_mode"))
            self.combo_config_mode.setItemText(1, self._t("advanced_mode"))
        if hasattr(self, "config_tabs") and self.config_tabs.count() > 0:
            audio_index = self.config_tabs.indexOf(self.audio_config_page) if hasattr(self, "audio_config_page") else -1
            ptt_index = self.config_tabs.indexOf(self.ptt_config_page) if hasattr(self, "ptt_config_page") else -1
            net_index = self.config_tabs.indexOf(self.net_config_page) if hasattr(self, "net_config_page") else -1
            if audio_index >= 0:
                self.config_tabs.setTabText(audio_index, self._t("audio_tab"))
            if ptt_index >= 0:
                self.config_tabs.setTabText(ptt_index, self._t("ptt_control_tab"))
            if net_index >= 0:
                self.config_tabs.setTabText(net_index, self._t("net_config"))
        if hasattr(self, "section_devices"):
            self.section_devices.setTitle(self._t("devices_group"))
        if hasattr(self, "label_audio_input"):
            self.label_audio_input.setText(f"{self._t('audio_input')}")
        if hasattr(self, "label_audio_output"):
            self.label_audio_output.setText(f"{self._t('audio_output')}")
        if hasattr(self, "btn_refresh_input"):
            self.btn_refresh_input.setText(self._t("refresh"))
        if hasattr(self, "btn_refresh_output"):
            self.btn_refresh_output.setText(self._t("refresh"))
        if hasattr(self, "label_in_signal"):
            self.label_in_signal.setText(self._t("signal_level"))
        if hasattr(self, "label_out_signal"):
            self.label_out_signal.setText(self._t("signal_level"))
        if hasattr(self, "label_test_tones"):
            self.label_test_tones.setText(self._t("test_tones"))
        if hasattr(self, "btn_tone_both"):
            self.btn_tone_both.setText(self._t("both"))
        if hasattr(self, "section_ptt"):
            self.section_ptt.setTitle(self._t("ptt_group"))
        if hasattr(self, "label_ptt_type"):
            self.label_ptt_type.setText(self._t("ptt_type"))
        if hasattr(self, "label_ptt_desc"):
            self.label_ptt_desc.setText(self._t("ptt_desc"))
        if hasattr(self, "combo_ppt") and self.combo_ppt.count() > 0:
            self.combo_ppt.setItemText(0, self._t("select_mode"))
            self.combo_ppt.setToolTip(self._t("tt_ptt_mode"))
        if hasattr(self, "label_rig_control_title"):
            self.label_rig_control_title.setText(self._t("rig_cat_control"))
        if hasattr(self, "label_rig_model"):
            self.label_rig_model.setText(self._t("rig_model"))
        if hasattr(self, "combo_rig_model"):
            self.combo_rig_model.setToolTip(self._t("tt_rig_model"))
        if hasattr(self, "label_ptt_path"):
            self.label_ptt_path.setText(self._t("ptt_path_serial"))
        if hasattr(self, "label_civaddr"):
            self.label_civaddr.setText(self._t("civaddr_label"))
        if hasattr(self, "combo_ptt_port") and self.combo_ptt_port.count() > 0:
            self.combo_ptt_port.setItemText(0, self._t("select_com"))
            self.combo_ptt_port.setToolTip(self._t("tt_ptt_port"))
        if hasattr(self, "check_ptt_share"):
            self.check_ptt_share.setText(self._t("ptt_share"))
        if hasattr(self, "check_ptt_active_low"):
            self.check_ptt_active_low.setText(self._t("ptt_active_low"))
            self.check_ptt_active_low.setToolTip(self._t("tt_ptt_active_low"))
        if hasattr(self, "check_rts"):
            self.check_rts.setText(self._t("rts_on"))
            self.check_rts.setToolTip(self._t("tt_rts_on"))
        if hasattr(self, "check_dts"):
            self.check_dts.setText(self._t("dtr_on"))
            self.check_dts.setToolTip(self._t("tt_dtr_on"))
        if hasattr(self, "btn_ptt_test"):
            self.btn_ptt_test.setText(self._t("ptt_test"))
            self.btn_ptt_test.setToolTip(self._t("tt_ptt_test"))
        if hasattr(self, "label_tx_delay"):
            self.label_tx_delay.setText(self._t("tx_delay"))
        if hasattr(self, "label_tx_tail"):
            self.label_tx_tail.setText(self._t("tx_tail"))
        if hasattr(self, "group_tx_delay"):
            self.group_tx_delay.setTitle(self._t("delay_group"))
        if hasattr(self, "btn_ptt_reset_defaults"):
            self.btn_ptt_reset_defaults.setText(self._t("ptt_reset_defaults"))
            self.btn_ptt_reset_defaults.setToolTip(self._t("tt_ptt_reset_defaults"))
        if hasattr(self, "section_network"):
            self.section_network.setTitle(self._t("net_config"))
        if hasattr(self, "label_kiss_port_info"):
            self.label_kiss_port_info.setText(self._t("kiss_port"))
        if hasattr(self, "check_web_ui_enabled"):
            self.check_web_ui_enabled.setText(self._t("web_enabled"))
        if hasattr(self, "label_allow_caption"):
            self.label_allow_caption.setText(self._t("allowed_addresses"))
        if hasattr(self, "combo_allow_ips") and self.combo_allow_ips.lineEdit() is not None:
            self.combo_allow_ips.lineEdit().setPlaceholderText(self._t("allowed_placeholder"))
        if hasattr(self, "btn_allow_ip_toggle"):
            self.btn_allow_ip_toggle.setText(self._t("toggle"))
        if hasattr(self, "label_allow_ip_hint"):
            self.label_allow_ip_hint.setText(self._t("localhost_hint"))
        if hasattr(self, "label_cat_connection"):
            self.label_cat_connection.setText(self._t("cat_connection"))
        if hasattr(self, "combo_rig_connection") and self.combo_rig_connection.count() >= 2:
            self.combo_rig_connection.setItemText(0, self._t("tcp_connection"))
            self.combo_rig_connection.setItemText(1, self._t("serial_connection"))
            self.combo_rig_connection.setToolTip(self._t("tt_cat_connection"))
        if hasattr(self, "combo_cat_serial_port") and self.combo_cat_serial_port.count() > 0:
            self.combo_cat_serial_port.setItemText(0, self._t("select_com"))
            self.combo_cat_serial_port.setToolTip(self._t("tt_cat_serial_port"))
        if hasattr(self, "spin_cat_serial_baud"):
            self.spin_cat_serial_baud.setToolTip(self._t("tt_cat_serial_baud"))
        if hasattr(self, "label_hamlib_host"):
            self.label_hamlib_host.setText(self._t("hamlib_host"))
        if hasattr(self, "input_hamlib_host"):
            self.input_hamlib_host.setToolTip(self._t("tt_hamlib_host"))
        if hasattr(self, "label_hamlib_port"):
            self.label_hamlib_port.setText(self._t("port"))
        if hasattr(self, "spin_hamlib_port"):
            self.spin_hamlib_port.setToolTip(self._t("tt_hamlib_port"))
        if hasattr(self, "btn_hamlib_test"):
            self.btn_hamlib_test.setText(self._t("connection_test"))
            self.btn_hamlib_test.setToolTip(self._t("tt_hamlib_test"))
        if hasattr(self, "input_civaddr"):
            self.input_civaddr.setToolTip(self._t("tt_civaddr"))
        if hasattr(self, "section_monitor"):
            self.section_monitor.setTitle(self._t("monitor_group"))
        if hasattr(self, "btn_toggle_config_sections"):
            self.btn_toggle_config_sections.setText(self._t("config_toggle"))
        if hasattr(self, "label_cat_serial_port"):
            self.label_cat_serial_port.setText(self._t("cat_serial_port"))
        if hasattr(self, "label_cat_baud"):
            self.label_cat_baud.setText(self._t("baud"))
        if hasattr(self, "label_cat_data_bits"):
            self.label_cat_data_bits.setText(self._t("data_bits"))
        if hasattr(self, "label_cat_parity"):
            self.label_cat_parity.setText(self._t("parity"))
        if hasattr(self, "label_cat_stop_bits"):
            self.label_cat_stop_bits.setText(self._t("stop_bits"))
        if hasattr(self, "label_monitor_freeze"):
            self.label_monitor_freeze.setText(self._t("monitor_freeze"))
        self._update_translated_control_widths()

    def _fit_button_width(self, button: QPushButton, texts: List[str], min_width: int = 80, max_width: int = 260) -> None:
        if button is None:
            return
        fm = QFontMetrics(button.font())
        text_width = max((fm.horizontalAdvance(str(t)) for t in texts if str(t)), default=0)
        target = max(min_width, min(max_width, text_width + 26))
        button.setFixedWidth(target)

    def _update_translated_control_widths(self) -> None:
        if hasattr(self, "btn_refresh_input"):
            self._fit_button_width(self.btn_refresh_input, [self._t("refresh")], min_width=80, max_width=180)
        if hasattr(self, "btn_refresh_output"):
            self._fit_button_width(self.btn_refresh_output, [self._t("refresh")], min_width=80, max_width=180)
        if hasattr(self, "btn_hamlib_test"):
            self._fit_button_width(self.btn_hamlib_test, [self._t("connection_test")], min_width=130, max_width=240)
        if hasattr(self, "btn_ptt_test"):
            self._fit_button_width(self.btn_ptt_test, [self._t("ptt_test")], min_width=140, max_width=220)
        if hasattr(self, "btn_tone_both"):
            self._fit_button_width(self.btn_tone_both, [self._t("both")], min_width=120, max_width=220)
        if hasattr(self, "btn_toggle_config_sections"):
            self._fit_button_width(
                self.btn_toggle_config_sections,
                [self._t("config_toggle"), self._t("config_toggle_off")],
                min_width=120,
                max_width=260,
            )

    def _normalize_ptt_type(self, value: str) -> str:
        """Normalize PTT mode and keep backward compatibility with legacy NONE."""
        v = str(value or "VOX").strip().upper()
        if v in ("RIG", "DTR", "RTS", "VOX"):
            return v
        if v == "NONE":
            return "VOX"
        if v == "HAMLIB":
            return "RIG"
        if v.startswith("COM"):
            return "RTS"
        return "VOX"

    def _normalize_config_ui_mode(self, value: str) -> str:
        """Normalize config UI mode to basic or advanced."""
        v = str(value or "basic").strip().lower()
        if v in ("advanced", "adv", "pro"):
            return "advanced"
        return "basic"

    def _state_to_bool(self, state: str) -> Optional[bool]:
        """Convert Hamlib-style line state string to optional bool."""
        v = str(state or "Unset").strip().upper()
        if v == "ON":
            return True
        if v == "OFF":
            return False
        return None

    def _normalize_rig_connection(self, value: str) -> str:
        """Normalize CAT transport mode for RIG PTT."""
        v = str(value or "TCP").strip().upper()
        if v in ("SERIAL", "SER"):
            return "SERIAL"
        return "TCP"

    def _normalize_rig_model(self, value: str) -> str:
        """Normalize rig model profile for direct serial CAT commands."""
        v = str(value or "ICOM_CUSTOM").strip().upper()
        valid_ids = {item["id"] for item in RIG_MODEL_PROFILES}
        aliases = {
            "IC705": "ICOM_IC705",
            "ICOM705": "ICOM_IC705",
            "IC7300": "ICOM_IC7300",
            "ICOM7300": "ICOM_IC7300",
            "IC9700": "ICOM_IC9700",
            "ICOM9700": "ICOM_IC9700",
            "RIGCTLD": "GENERIC",
            "TCP_GENERIC": "GENERIC",
        }
        if v in aliases:
            return aliases[v]
        if v in valid_ids:
            return v
        return "ICOM_CUSTOM"

    def _rig_profile(self, model_id: Optional[str] = None) -> dict:
        """Return profile metadata for a selected rig model ID."""
        mid = self._normalize_rig_model(model_id or self.rig_model)
        for item in RIG_MODEL_PROFILES:
            if item["id"] == mid:
                return item
        return {"id": "ICOM_CUSTOM", "label": "Icom Custom CI-V", "protocol": "ICOM_CIV", "default_civ": None}

    def _rig_protocol(self, model_id: Optional[str] = None) -> str:
        """Return CAT protocol identifier for selected rig model."""
        return str(self._rig_profile(model_id).get("protocol", "GENERIC"))

    def _rig_uses_civ(self, model_id: Optional[str] = None) -> bool:
        """Check whether model uses Icom CI-V addressing."""
        return self._rig_protocol(model_id) == "ICOM_CIV"

    def _default_civ_for_model(self, model: str) -> Optional[str]:
        """Return default CI-V address for known Icom models."""
        return self._rig_profile(model).get("default_civ")

    def _update_rig_profile_hint(self) -> None:
        """Update short info text describing selected model protocol."""
        if not hasattr(self, "label_rig_profile_hint"):
            return
        profile = self._rig_profile(self.rig_model)
        protocol = profile.get("protocol", "GENERIC")
        if protocol == "ICOM_CIV":
            self.label_rig_profile_hint.setText("Protocol: Icom CI-V (requires CI-V address)")
        elif protocol == "KENWOOD_CAT":
            self.label_rig_profile_hint.setText("Protocol: Kenwood CAT (ASCII)")
        elif protocol == "YAESU_CAT":
            self.label_rig_profile_hint.setText("Protocol: Yaesu CAT")
        elif protocol == "ELECRAFT_CAT":
            self.label_rig_profile_hint.setText("Protocol: Elecraft CAT")
        elif protocol == "ALINCO_CAT":
            self.label_rig_profile_hint.setText("Protocol: Alinco CAT")
        else:
            self.label_rig_profile_hint.setText("Protocol: Generic (recommended rigctld/TCP)")

    def _apply_line_overrides(self) -> None:
        """Apply dtr_state/rts_state static overrides to the opened serial port."""
        if self.ppt_serial is None or not self.ppt_serial.is_open:
            return
        mode = self._normalize_ptt_type(self.ptt_type)
        dtr_force = self._state_to_bool(self.dtr_state)
        rts_force = self._state_to_bool(self.rts_state)
        # Do not override the line currently used as PTT, otherwise PTT logic
        # (including active_low inversion) gets masked.
        if dtr_force is not None and mode != "DTR":
            self.ppt_serial.dtr = dtr_force
        if rts_force is not None and mode != "RTS":
            self.ppt_serial.rts = rts_force

    def _serial_ptt_idle_level(self) -> bool:
        """Return serial line level that represents inactive PTT (RX state)."""
        return True if self.ptt_active_low else False

    def _apply_serial_idle_for_mode(self) -> None:
        """Apply deterministic idle levels to serial control lines for current PTT mode."""
        if self.ppt_serial is None or not self.ppt_serial.is_open:
            return
        mode = self._normalize_ptt_type(self.ptt_type)
        if mode == "DTR":
            idle = True if self.dtr_active_low else False
            self.ppt_serial.dtr = idle
            self.ppt_serial.rts = False
        elif mode == "RTS":
            idle = True if self.rts_active_low else False
            self.ppt_serial.rts = idle
            self.ppt_serial.dtr = False

    def _get_current_serial_invert(self) -> bool:
        """Return the saved invert state for the currently selected serial PTT line."""
        mode = self._normalize_ptt_type(self.ptt_type)
        if mode == "DTR":
            return bool(self.dtr_active_low)
        if mode == "RTS":
            return bool(self.rts_active_low)
        return bool(self.ptt_active_low)

    def _sync_ptt_invert_checkbox(self) -> None:
        """Reflect DTR/RTS-specific saved invert state in the single visible checkbox."""
        if not hasattr(self, "check_ptt_active_low"):
            return
        value = self._get_current_serial_invert()
        self.ptt_active_low = bool(value)
        self.check_ptt_active_low.blockSignals(True)
        self.check_ptt_active_low.setChecked(bool(value))
        self.check_ptt_active_low.blockSignals(False)

    def _sync_tx_timing_controls(self) -> None:
        """Basic mode shows fixed defaults; Advanced mode exposes saved timing values."""
        advanced = self.config_ui_mode == "advanced"
        delay_value = int(self.tx_delay_ms) if advanced else DEFAULT_TX_DELAY_MS
        tail_value = int(self.tx_tail_ms) if advanced else DEFAULT_TX_TAIL_MS

        if hasattr(self, "spin_vox_delay"):
            self.spin_vox_delay.blockSignals(True)
            self.spin_vox_delay.setValue(max(0, min(5000, delay_value)))
            self.spin_vox_delay.setEnabled(advanced)
            self.spin_vox_delay.setVisible(advanced)
            self.spin_vox_delay.blockSignals(False)
        if hasattr(self, "spin_tx_tail"):
            self.spin_tx_tail.blockSignals(True)
            self.spin_tx_tail.setValue(max(0, min(5000, tail_value)))
            self.spin_tx_tail.setEnabled(advanced)
            self.spin_tx_tail.setVisible(advanced)
            self.spin_tx_tail.blockSignals(False)
        if hasattr(self, "label_tx_delay"):
            self.label_tx_delay.setVisible(advanced)
        if hasattr(self, "label_tx_tail"):
            self.label_tx_tail.setVisible(advanced)
        if hasattr(self, "group_tx_delay"):
            self.group_tx_delay.setVisible(advanced)

    def _save_ptt_config(self) -> None:
        """Persist Hamlib-style PTT configuration keys and legacy compatibility key."""
        self.config.set("ptt.ptt_type", self.ptt_type)
        self.config.set("ptt.path", self.ptt_port)
        self.config.set("ptt.share", self.ptt_share)
        self.config.set("ptt.active_low", self.ptt_active_low)
        self.config.set("ptt.civaddr", self.civaddr)
        self.config.set("ptt.rig_model", self.rig_model)
        self.config.set("ptt.dtr_state", self.dtr_state)
        self.config.set("ptt.rts_state", self.rts_state)
        self.config.set("ptt.tx_delay_ms", int(self.tx_delay_ms))
        self.config.set("ptt.tx_tail_ms", int(self.tx_tail_ms))
        self.config.set("ptt.pre_tx_flags_enabled", True)
        self.config.set("ptt.post_tx_flags_enabled", True)
        self.config.set("ptt.dtr_active_low", bool(self.dtr_active_low))
        self.config.set("ptt.rts_active_low", bool(self.rts_active_low))
        # Legacy compatibility key used by older UI/web clients.
        self.config.set("ptt.vox_delay_ms", int(self.tx_delay_ms))

        # Legacy compatibility for already existing installs.
        legacy_mode = "HAMLIB" if self.ptt_type == "RIG" else self.ptt_type
        self.config.set("ppt.mode", legacy_mode)
        self.config.save()

    def _save_rig_connection_config(self) -> None:
        """Persist CAT transport settings used when ptt_type is RIG."""
        self.config.set("ptt.rig_connection", self.rig_connection)
        self.config.set("ptt.rig_serial_path", self.cat_serial_port)
        self.config.set("ptt.rig_serial_baud", int(self.cat_serial_baud))
        self.config.set("ptt.rig_serial_data_bits", int(self.cat_serial_data_bits))
        self.config.set("ptt.rig_serial_parity", self.cat_serial_parity)
        self.config.set("ptt.rig_serial_stop_bits", self.cat_serial_stop_bits)
        self.config.set("ptt.rig_model", self.rig_model)
        self.config.save()

    def _reset_hamlib_status(self) -> None:
        """Reset Hamlib status after CAT settings change."""
        if hasattr(self, "label_hamlib_status"):
            self.label_hamlib_status.setText(self._t("hamlib_not_tested"))
            self.label_hamlib_status.setStyleSheet("color: gray;")
    
    def check_port_available(self, port: int) -> bool:
        """Check if port is available for binding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return True
        except OSError:
            return False

    def _update_kiss_port_labels(self) -> None:
        """Refresh visible KISS endpoint labels after a port change."""
        if hasattr(self, "label_about_kiss"):
            self.label_about_kiss.setText(f"{self._t('about_kiss')} 127.0.0.1:{self.kiss_port}")
        if hasattr(self, "spin_kiss_port"):
            self.spin_kiss_port.blockSignals(True)
            self.spin_kiss_port.setValue(int(self.kiss_port))
            self.spin_kiss_port.blockSignals(False)
        self._update_monitor_config_summary()

    def _monitor_summary_combo_text(self, combo_name: str, empty_text: str = "-") -> str:
        combo = getattr(self, combo_name, None)
        if combo is None:
            return empty_text
        data = combo.currentData()
        text = combo.currentText().strip()
        if data is None or not text:
            return empty_text
        return text.rsplit(" (", 1)[0]

    def _update_monitor_config_summary(self) -> None:
        """Refresh compact runtime configuration summary above monitor log."""
        if not hasattr(self, "label_monitor_config_summary"):
            return

        audio_in = self._monitor_summary_combo_text("combo_input")
        audio_out = self._monitor_summary_combo_text("combo_output")
        ptt = self._normalize_ptt_type(self.ptt_type or "VOX")
        kiss = str(int(self.kiss_port))
        web = str(WEB_UI_PORT) if bool(self.web_ui_enabled) else "OFF"
        summary = f"Audio in: {audio_in}   Audio out: {audio_out}   PTT: {ptt}   KISS: {kiss}   Web: {web}"
        self.label_monitor_config_summary.setText(summary)

    def _on_kiss_port_changed(self, value: int) -> None:
        """Persist and apply KISS TCP port changes from Net Config."""
        new_port = max(1, min(65535, int(value)))
        old_port = int(self.kiss_port)
        if new_port == old_port:
            return

        if not self.check_port_available(new_port):
            QMessageBox.warning(
                self,
                self._t("kiss_error_title"),
                f"KISS port {new_port} is already in use."
            )
            self._update_kiss_port_labels()
            return

        was_running = bool(self.kiss_server and self.kiss_server.is_running)
        if was_running:
            self.kiss_server.stop()

        self.kiss_port = new_port
        self.config.set("kiss.port", int(self.kiss_port))
        self.config.save()

        self.kiss_server = KISSServerApp(
            port=self.kiss_port,
            on_frame_received=self.on_kiss_frame_received,
            on_error=self.on_kiss_error,
            allowed_ips=self.allowed_remote_ips,
            max_clients=KISS_MAX_CLIENTS,
            max_buffer_bytes=KISS_MAX_BUFFER_BYTES,
            max_payload_bytes=KISS_MAX_PAYLOAD_BYTES,
        )
        if was_running:
            self.kiss_server.start()

        self._update_kiss_port_labels()
        logger.info(f"[KISS] Port changed: {old_port} -> {self.kiss_port}")
    
    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle(f"MicroKISStnc - APRS TNC [{self.app_build_tag}]")
        self.setGeometry(100, 100, 1000, 900)

        self.layout_mode = None

        # Central widget and root layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll area keeps the app usable on short windows without clipping the bottom.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(12)
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)

        # Build sections once, then move them between layouts as needed.
        self.section_header = self.create_header_section()
        self.section_devices = self.create_devices_section()
        self.section_ptt = self.create_ptt_section()
        self.section_network = self.create_network_section()
        self.section_monitor = self.create_monitor_section()

        self.section_devices.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.section_ptt.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.section_network.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.section_monitor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.main_stack = QTabWidget()
        self.main_stack.setDocumentMode(True)
        self.main_stack.setMovable(False)
        self.main_stack.setUsesScrollButtons(False)
        self.main_stack.tabBar().setExpanding(True)
        self.main_stack.setStyleSheet(
            "QTabWidget::pane {"
            "border-top: 1px solid #c8d3dc;"
            "}"
            "QTabBar::tab {"
            "background: #f2f4f6;"
            "color: #333333;"
            "padding: 7px 18px;"
            "border: 1px solid #c8d3dc;"
            "border-bottom: none;"
            "margin-right: 2px;"
            "}"
            "QTabBar::tab:selected {"
            "background: #dceaf7;"
            "color: #0b4d7a;"
            "border-top: 3px solid #2f83bd;"
            "font-weight: 600;"
            "}"
            "QTabBar::tab:hover:!selected {"
            "background: #e8eef3;"
            "}"
        )

        # Monitor view: only monitor section.
        self.monitor_page = QWidget()
        monitor_layout = QVBoxLayout()
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        self.monitor_top_controls = self.create_monitor_top_controls()
        monitor_layout.addWidget(self.monitor_top_controls)
        self.label_monitor_config_summary = QLabel("")
        self.label_monitor_config_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.label_monitor_config_summary.setStyleSheet(
            "QLabel {"
            "background: #f7fafc;"
            "color: #314452;"
            "border-bottom: 1px solid #d7e1ea;"
            "padding: 5px 10px;"
            "font: 11px 'Segoe UI';"
            "}"
        )
        monitor_layout.addWidget(self.label_monitor_config_summary)
        monitor_layout.addWidget(self.section_monitor, 1)
        self.monitor_page.setLayout(monitor_layout)
        self.main_stack.addTab(self.monitor_page, self._t("main_tab_monitor"))

        self.config_page = QWidget()
        config_page_layout = QVBoxLayout()
        config_page_layout.setContentsMargins(0, 0, 0, 0)
        config_page_layout.setSpacing(0)

        self.config_tabs = QTabWidget()

        self.audio_config_page = QWidget()
        audio_scroll = QScrollArea()
        audio_scroll.setWidgetResizable(True)
        audio_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        audio_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        audio_scroll_content = QWidget()
        audio_layout = QVBoxLayout()
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setSpacing(12)
        audio_layout.addWidget(self.section_devices)
        audio_layout.addStretch()
        audio_scroll_content.setLayout(audio_layout)
        audio_scroll.setWidget(audio_scroll_content)
        audio_page_layout = QVBoxLayout()
        audio_page_layout.setContentsMargins(0, 0, 0, 0)
        audio_page_layout.addWidget(audio_scroll)
        self.audio_config_page.setLayout(audio_page_layout)

        self.ptt_config_page = QWidget()
        ptt_scroll = QScrollArea()
        ptt_scroll.setWidgetResizable(True)
        ptt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ptt_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        ptt_scroll_content = QWidget()
        ptt_layout = QVBoxLayout()
        ptt_layout.setContentsMargins(0, 0, 0, 0)
        ptt_layout.setSpacing(12)
        ptt_layout.addWidget(self.section_ptt)
        ptt_layout.addStretch()
        ptt_scroll_content.setLayout(ptt_layout)
        ptt_scroll.setWidget(ptt_scroll_content)
        ptt_page_layout = QVBoxLayout()
        ptt_page_layout.setContentsMargins(0, 0, 0, 0)
        ptt_page_layout.addWidget(ptt_scroll)
        self.ptt_config_page.setLayout(ptt_page_layout)

        self.net_config_page = QWidget()
        net_scroll = QScrollArea()
        net_scroll.setWidgetResizable(True)
        net_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        net_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        net_scroll_content = QWidget()
        net_layout = QVBoxLayout()
        net_layout.setContentsMargins(0, 0, 0, 0)
        net_layout.setSpacing(12)
        net_layout.addWidget(self.section_network)
        net_layout.addStretch()
        net_scroll_content.setLayout(net_layout)
        net_scroll.setWidget(net_scroll_content)
        net_page_layout = QVBoxLayout()
        net_page_layout.setContentsMargins(0, 0, 0, 0)
        net_page_layout.addWidget(net_scroll)
        self.net_config_page.setLayout(net_page_layout)

        self.config_tabs.addTab(self.audio_config_page, self._t("audio_tab"))
        self.config_tabs.addTab(self.ptt_config_page, self._t("ptt_control_tab"))
        self.config_tabs.addTab(self.net_config_page, self._t("net_config"))
        self.config_tabs.currentChanged.connect(self._on_config_tab_changed)

        config_page_layout.addWidget(self.section_header)
        config_page_layout.addWidget(self.config_tabs)
        self.config_page.setLayout(config_page_layout)
        self.main_stack.addTab(self.config_page, self._t("main_tab_config"))

        self.about_page = self.create_about_page()
        self.main_stack.addTab(self.about_page, self._t("main_tab_about"))

        self.main_stack.currentChanged.connect(self._on_main_tab_changed)

        root_layout.addWidget(self.main_stack)
        central_widget.setLayout(root_layout)

        self.show_monitor_view(persist=False)
        self._apply_config_ui_mode(self.config_ui_mode, persist=False)
        
        # Populate device lists after UI is ready
        self.populate_devices()
        
        # Restore saved device selections from config
        self.restore_device_selection()
        self._update_monitor_config_summary()
        
        # Add demo/startup message to monitor
        self.add_monitor_line("SYS", "", f"MicroKISStnc APRS TNC Ready ({self.app_build_tag})")
        
        # Start system volume monitoring (Windows)
        self.system_volume_monitor.start_monitoring()
        logger.info("[APP] System volume monitoring started")

    def _on_main_tab_changed(self, index: int) -> None:
        """Synchronize main tab selection with current view."""
        if index == 0:
            self.show_monitor_view(persist=False)
        elif index == 1:
            self.show_config_view(persist=False)
        elif index == 2:
            self.show_about_view(persist=False)

    def _set_config_sections_visible(self, visible: bool, persist: bool = True) -> None:
        """Compatibility shim: switch between monitor and configuration view."""
        if bool(visible):
            self.show_config_view(persist=persist)
        else:
            self.show_monitor_view(persist=persist)

    def show_monitor_view(self, persist: bool = True) -> None:
        self.show_config_sections = False
        if persist:
            self.config.set("application.show_config_sections", False)
            self.config.save()
        if hasattr(self, "main_stack"):
            self.main_stack.blockSignals(True)
            self.main_stack.setCurrentIndex(0)
            self.main_stack.blockSignals(False)
        if hasattr(self, "btn_toggle_config_sections"):
            self.btn_toggle_config_sections.blockSignals(True)
            self.btn_toggle_config_sections.setChecked(False)
            self.btn_toggle_config_sections.setText(self._t("config_toggle"))
            self.btn_toggle_config_sections.blockSignals(False)

    def show_config_view(self, persist: bool = True) -> None:
        self.show_config_sections = True
        if persist:
            self.config.set("application.show_config_sections", True)
            self.config.save()
        if hasattr(self, "main_stack"):
            self.main_stack.blockSignals(True)
            self.main_stack.setCurrentIndex(1)
            self.main_stack.blockSignals(False)
        if hasattr(self, "btn_toggle_config_sections"):
            self.btn_toggle_config_sections.blockSignals(True)
            self.btn_toggle_config_sections.setChecked(True)
            self.btn_toggle_config_sections.setText(self._t("config_toggle"))
            self.btn_toggle_config_sections.blockSignals(False)

    def show_about_view(self, persist: bool = True) -> None:
        if hasattr(self, "main_stack"):
            self.main_stack.blockSignals(True)
            self.main_stack.setCurrentIndex(2)
            self.main_stack.blockSignals(False)

    def _on_config_tab_changed(self, index: int) -> None:
        """Keep config mode combo and tab state aligned."""
        if not hasattr(self, "config_tabs"):
            return
        current = self.config_tabs.widget(index)
        if hasattr(self, "net_config_page") and current is self.net_config_page and self.config_ui_mode != "advanced":
            self._apply_config_ui_mode("advanced", persist=True)

    def _apply_config_ui_mode(self, mode: str, persist: bool = True) -> None:
        """Show or hide advanced configuration UI."""
        normalized = self._normalize_config_ui_mode(mode)
        self.config_ui_mode = normalized
        if persist:
            self.config.set("application.config_ui_mode", normalized)
            self.config.save()

        if hasattr(self, "combo_config_mode"):
            self.combo_config_mode.blockSignals(True)
            self._set_combo_by_data(self.combo_config_mode, normalized)
            self.combo_config_mode.blockSignals(False)

        if hasattr(self, "net_config_page"):
            self.net_config_page.setVisible(normalized == "advanced")
        if hasattr(self, "config_tabs"):
            self.config_tabs.blockSignals(True)
            net_index = self.config_tabs.indexOf(self.net_config_page) if hasattr(self, "net_config_page") else -1
            if normalized == "advanced" and net_index < 0 and hasattr(self, "net_config_page"):
                self.config_tabs.addTab(self.net_config_page, self._t("net_config"))
            elif normalized != "advanced" and net_index >= 0:
                self.config_tabs.removeTab(net_index)
            if normalized != "advanced" and hasattr(self, "net_config_page") and self.config_tabs.currentWidget() is self.net_config_page:
                self.config_tabs.setCurrentIndex(0)
            self.config_tabs.blockSignals(False)

        if hasattr(self, "advanced_ptt_widget"):
            self.advanced_ptt_widget.setVisible(normalized == "advanced")
        self._sync_tx_timing_controls()
        if hasattr(self, "combo_ppt"):
            self._update_ptt_mode_controls(self.combo_ppt.currentData() or self.ptt_type)
        self._update_monitor_config_summary()

    def on_config_ui_mode_changed(self, _index: int) -> None:
        """Persist configuration UI mode change."""
        if not hasattr(self, "combo_config_mode"):
            return
        self._apply_config_ui_mode(self.combo_config_mode.currentData() or "basic", persist=True)

    def resizeEvent(self, event):
        """Default resize handler."""
        super().resizeEvent(event)
    
    def create_header_section(self) -> QWidget:
        """Create header section - no frame"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Close behavior toggle (top-right, near window controls)
        close_behavior_row = QHBoxLayout()
        close_behavior_row.setContentsMargins(0, 0, 0, 0)
        close_behavior_row.addStretch()
        self.label_lang = QLabel(self._t("language"))
        close_behavior_row.addWidget(self.label_lang)
        self.combo_ui_lang = QComboBox()
        self.combo_ui_lang.addItem("EN", "en")
        self.combo_ui_lang.addItem("DE", "de")
        self.combo_ui_lang.addItem("FR", "fr")
        self.combo_ui_lang.addItem("ES", "es")
        self.combo_ui_lang.addItem("PL", "pl")
        self._set_combo_by_data(self.combo_ui_lang, self.ui_language)
        self.combo_ui_lang.currentIndexChanged.connect(lambda _i: self._set_ui_language(self.combo_ui_lang.currentData(), persist=True))
        close_behavior_row.addWidget(self.combo_ui_lang)
        self.check_close_to_tray = QCheckBox(self._t("hide_to_tray"))
        self.check_close_to_tray.setChecked(self.close_to_tray_enabled)
        self.check_close_to_tray.toggled.connect(self.on_close_behavior_toggle_changed)
        close_behavior_row.addWidget(self.check_close_to_tray)
        layout.addLayout(close_behavior_row)
        
        # Title
        title = QLabel("MicroKISStnc")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        self.label_subtitle = QLabel(self._t("config_subtitle"))
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        self.label_subtitle.setFont(subtitle_font)
        self.label_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_subtitle)

        self.label_created_by = QLabel(self._t("created_by"))
        created_by_font = QFont()
        created_by_font.setPointSize(10)
        self.label_created_by.setFont(created_by_font)
        self.label_created_by.setStyleSheet("color: gray;")
        self.label_created_by.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_created_by)

        mode_row = QHBoxLayout()
        mode_row.addStretch()
        self.label_config_mode = QLabel(self._t("config_mode"))
        mode_row.addWidget(self.label_config_mode)
        self.combo_config_mode = QComboBox()
        self.combo_config_mode.addItem(self._t("basic_mode"), "basic")
        self.combo_config_mode.addItem(self._t("advanced_mode"), "advanced")
        self._set_combo_by_data(self.combo_config_mode, self.config_ui_mode)
        self.combo_config_mode.currentIndexChanged.connect(self.on_config_ui_mode_changed)
        mode_row.addWidget(self.combo_config_mode)
        mode_row.addStretch()
        layout.addLayout(mode_row)
        
        widget.setLayout(layout)
        return widget

    def create_monitor_top_controls(self) -> QWidget:
        """Create monitor view top-row controls (tray/language)."""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)
        layout.addStretch()

        self.label_lang_monitor = QLabel(self._t("language"))
        layout.addWidget(self.label_lang_monitor)

        self.combo_ui_lang_monitor = QComboBox()
        self.combo_ui_lang_monitor.addItem("EN", "en")
        self.combo_ui_lang_monitor.addItem("DE", "de")
        self.combo_ui_lang_monitor.addItem("FR", "fr")
        self.combo_ui_lang_monitor.addItem("ES", "es")
        self.combo_ui_lang_monitor.addItem("PL", "pl")
        self._set_combo_by_data(self.combo_ui_lang_monitor, self.ui_language)
        self.combo_ui_lang_monitor.currentIndexChanged.connect(
            lambda _i: self._set_ui_language(self.combo_ui_lang_monitor.currentData(), persist=True)
        )
        layout.addWidget(self.combo_ui_lang_monitor)

        self.check_close_to_tray_monitor = QCheckBox(self._t("hide_to_tray"))
        self.check_close_to_tray_monitor.setChecked(self.close_to_tray_enabled)
        self.check_close_to_tray_monitor.toggled.connect(self.on_close_behavior_toggle_changed)
        layout.addWidget(self.check_close_to_tray_monitor)

        widget.setLayout(layout)
        return widget
    
    def create_devices_section(self) -> QGroupBox:
        """Create devices in/out section"""
        group = QGroupBox(self._t("devices_group"))
        self.section_devices = group
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 20, 8, 10)
        layout.setSpacing(8)
        
        # Audio IN (with refresh button)
        input_label_layout = QHBoxLayout()
        self.label_audio_input = QLabel(f"{self._t('audio_input')}")
        input_label_layout.addWidget(self.label_audio_input)
        self.btn_refresh_input = QPushButton(self._t("refresh"))
        self.btn_refresh_input.setMaximumWidth(80)
        self.btn_refresh_input.clicked.connect(self.refresh_input_devices)
        input_label_layout.addStretch()
        input_label_layout.addWidget(self.btn_refresh_input)
        layout.addLayout(input_label_layout)
        
        self.combo_input = ClickSelectComboBox()
        self.combo_input.addItem(self._t("select_mic"), None)
        self.combo_input.currentIndexChanged.connect(self.on_input_device_changed)
        layout.addWidget(self.combo_input)
        
        self.label_in_signal = QLabel(self._t("signal_level"))
        layout.addWidget(self.label_in_signal)
        self.progress_in = QProgressBar()
        self.progress_in.setMaximum(100)
        self.progress_in.setValue(0)
        layout.addWidget(self.progress_in)
        self.label_in_levels = QLabel("Peak: 0% (-96.0 dBFS) | RMS: 0% (-96.0 dBFS)")
        self.label_in_levels.setStyleSheet("color: gray;")
        layout.addWidget(self.label_in_levels)
        
        layout.addSpacing(12)
        
        # Audio OUT (with refresh button)
        output_label_layout = QHBoxLayout()
        self.label_audio_output = QLabel(f"{self._t('audio_output')}")
        output_label_layout.addWidget(self.label_audio_output)
        self.btn_refresh_output = QPushButton(self._t("refresh"))
        self.btn_refresh_output.setMaximumWidth(80)
        self.btn_refresh_output.clicked.connect(self.refresh_output_devices)
        output_label_layout.addStretch()
        output_label_layout.addWidget(self.btn_refresh_output)
        layout.addLayout(output_label_layout)
        
        self.combo_output = ClickSelectComboBox()
        self.combo_output.addItem(self._t("select_speaker"), None)
        self.combo_output.currentIndexChanged.connect(self.on_output_device_changed)
        layout.addWidget(self.combo_output)
        
        # Sample Rate selection is kept internally for compatibility but hidden in GUI.
        self.combo_sample_rate = ClickSelectComboBox()
        self.combo_sample_rate.addItems(["44100", "48000", "96000"])
        self.combo_sample_rate.currentIndexChanged.connect(self.on_sample_rate_changed)
        
        self.label_out_signal = QLabel(self._t("signal_level"))
        layout.addWidget(self.label_out_signal)
        self.progress_out = QProgressBar()
        self.progress_out.setMaximum(100)
        self.progress_out.setValue(0)
        layout.addWidget(self.progress_out)
        self.label_out_levels = QLabel("Peak: 0% (-96.0 dBFS) | RMS: 0% (-96.0 dBFS)")
        self.label_out_levels.setStyleSheet("color: gray;")
        layout.addWidget(self.label_out_levels)
        
        # Test tone buttons
        self.label_test_tones = QLabel(self._t("test_tones"))
        layout.addWidget(self.label_test_tones)
        tone_layout = QHBoxLayout()
        tone_layout.setSpacing(10)
        tone_layout.setContentsMargins(0, 2, 0, 6)
        
        self.btn_tone_1200 = QPushButton("1200 Hz")
        self.btn_tone_1200.setCheckable(True)
        self.btn_tone_1200.setFixedHeight(34)
        self.btn_tone_1200.setFixedWidth(120)
        self.btn_tone_1200.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_tone_1200.clicked.connect(self.toggle_tone_1200)
        tone_layout.addStretch()
        tone_layout.addWidget(self.btn_tone_1200)
        
        self.btn_tone_both = QPushButton(self._t("both"))
        self.btn_tone_both.setCheckable(True)
        self.btn_tone_both.setFixedHeight(34)
        self.btn_tone_both.setFixedWidth(120)
        self.btn_tone_both.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_tone_both.clicked.connect(self.toggle_tone_both)
        tone_layout.addWidget(self.btn_tone_both)
        
        self.btn_tone_2200 = QPushButton("2200 Hz")
        self.btn_tone_2200.setCheckable(True)
        self.btn_tone_2200.setFixedHeight(34)
        self.btn_tone_2200.setFixedWidth(120)
        self.btn_tone_2200.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_tone_2200.clicked.connect(self.toggle_tone_2200)
        tone_layout.addWidget(self.btn_tone_2200)
        tone_layout.addStretch()
        
        layout.addLayout(tone_layout)
        layout.addSpacing(8)
        
        group.setLayout(layout)
        return group
    
    def create_ptt_section(self) -> QGroupBox:
        """Create PTT CONTROL section"""
        group = QGroupBox(self._t("ptt_group"))
        self.section_ptt = group
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 20, 8, 10)
        layout.setSpacing(8)
        
        ptt_mode_layout = QHBoxLayout()
        self.label_ptt_type = QLabel(self._t("ptt_type"))
        ptt_mode_layout.addWidget(self.label_ptt_type)
        self.label_ptt_desc = QLabel(self._t("ptt_desc"))
        self.label_ptt_desc.setStyleSheet("color: gray;")
        ptt_mode_layout.addWidget(self.label_ptt_desc)
        ptt_mode_layout.addStretch()
        layout.addLayout(ptt_mode_layout)
        
        self.combo_ppt = QComboBox()
        self.combo_ppt.addItem(self._t("select_mode"), None)
        self.combo_ppt.setToolTip(self._t("tt_ptt_mode"))
        self.combo_ppt.currentTextChanged.connect(self.on_ptt_mode_changed)
        layout.addWidget(self.combo_ppt)

        # Serial path used for DTR/RTS type
        serial_layout = QHBoxLayout()
        self.label_ptt_path = QLabel(self._t("ptt_path_serial"))
        serial_layout.addWidget(self.label_ptt_path)
        self.combo_ptt_port = QComboBox()
        self.combo_ptt_port.addItem(self._t("select_com"), None)
        self.combo_ptt_port.setToolTip(self._t("tt_ptt_port"))
        self.combo_ptt_port.currentIndexChanged.connect(self._on_ptt_port_changed)
        serial_layout.addWidget(self.combo_ptt_port)
        serial_layout.addStretch()
        layout.addLayout(serial_layout)

        self.check_ptt_active_low = QCheckBox(self._t("ptt_active_low"))
        self.check_ptt_active_low.setToolTip(self._t("tt_ptt_active_low"))
        self.check_ptt_active_low.toggled.connect(self._on_ptt_active_low_changed)
        layout.addWidget(self.check_ptt_active_low)

        self.label_rig_control_title = QLabel(self._t("rig_cat_control"))
        self.label_rig_control_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.label_rig_control_title)

        rig_model_layout = QHBoxLayout()
        self.label_rig_model = QLabel(self._t("rig_model"))
        rig_model_layout.addWidget(self.label_rig_model)
        self.combo_rig_model = QComboBox()
        for item in RIG_MODEL_PROFILES:
            self.combo_rig_model.addItem(item["label"], item["id"])
        self.combo_rig_model.setToolTip(self._t("tt_rig_model"))
        self._set_combo_by_data(self.combo_rig_model, self.rig_model)
        self.combo_rig_model.currentIndexChanged.connect(self._on_rig_model_changed)
        rig_model_layout.addWidget(self.combo_rig_model)
        rig_model_layout.addStretch()
        layout.addLayout(rig_model_layout)

        self.label_rig_profile_hint = QLabel("")
        self.label_rig_profile_hint.setStyleSheet("color: gray;")
        layout.addWidget(self.label_rig_profile_hint)

        cat_conn_layout = QHBoxLayout()
        self.label_cat_connection = QLabel(self._t("cat_connection"))
        cat_conn_layout.addWidget(self.label_cat_connection)
        self.combo_rig_connection = QComboBox()
        self.combo_rig_connection.addItem(self._t("tcp_connection"), "TCP")
        self.combo_rig_connection.addItem(self._t("serial_connection"), "SERIAL")
        self.combo_rig_connection.setToolTip(self._t("tt_cat_connection"))
        self.combo_rig_connection.currentIndexChanged.connect(self._on_rig_connection_changed)
        cat_conn_layout.addWidget(self.combo_rig_connection)
        cat_conn_layout.addStretch()
        layout.addLayout(cat_conn_layout)

        cat_serial_layout = QHBoxLayout()
        self.label_cat_serial_port = QLabel(self._t("cat_serial_port"))
        cat_serial_layout.addWidget(self.label_cat_serial_port)
        self.combo_cat_serial_port = QComboBox()
        self.combo_cat_serial_port.addItem(self._t("select_com"), None)
        self.combo_cat_serial_port.setToolTip(self._t("tt_cat_serial_port"))
        self.combo_cat_serial_port.currentIndexChanged.connect(self._on_cat_serial_port_changed)
        cat_serial_layout.addWidget(self.combo_cat_serial_port)
        self.label_cat_baud = QLabel(self._t("baud"))
        cat_serial_layout.addWidget(self.label_cat_baud)
        self.spin_cat_serial_baud = QSpinBox()
        self.spin_cat_serial_baud.setRange(1200, 115200)
        self.spin_cat_serial_baud.setSingleStep(1200)
        self.spin_cat_serial_baud.setToolTip(self._t("tt_cat_serial_baud"))
        self.spin_cat_serial_baud.setValue(int(self.cat_serial_baud))
        self.spin_cat_serial_baud.valueChanged.connect(self._on_cat_serial_baud_changed)
        cat_serial_layout.addWidget(self.spin_cat_serial_baud)
        cat_serial_layout.addStretch()
        layout.addLayout(cat_serial_layout)

        hamlib_layout = QHBoxLayout()
        self.label_hamlib_host = QLabel(self._t("hamlib_host"))
        hamlib_layout.addWidget(self.label_hamlib_host)
        self.input_hamlib_host = QLineEdit()
        self.input_hamlib_host.setPlaceholderText("127.0.0.1")
        self.input_hamlib_host.setToolTip(self._t("tt_hamlib_host"))
        self.input_hamlib_host.setText(self.hamlib_host)
        hamlib_layout.addWidget(self.input_hamlib_host)

        self.label_hamlib_port = QLabel(self._t("port"))
        hamlib_layout.addWidget(self.label_hamlib_port)
        self.spin_hamlib_port = QSpinBox()
        self.spin_hamlib_port.setRange(1, 65535)
        self.spin_hamlib_port.setToolTip(self._t("tt_hamlib_port"))
        self.spin_hamlib_port.setValue(self.hamlib_port)
        hamlib_layout.addWidget(self.spin_hamlib_port)

        layout.addLayout(hamlib_layout)

        self.input_hamlib_host.editingFinished.connect(self._save_hamlib_config_from_ui)
        self.spin_hamlib_port.valueChanged.connect(self._save_hamlib_config_from_ui)

        # Initialize checkbox states from persisted Hamlib-style line states.
        self._set_combo_by_data(self.combo_rig_connection, self.rig_connection)
        self._update_rig_profile_hint()

        self.advanced_ptt_widget = QWidget()
        advanced_ptt_layout = QVBoxLayout()
        advanced_ptt_layout.setContentsMargins(0, 0, 0, 0)
        advanced_ptt_layout.setSpacing(8)

        civ_layout = QHBoxLayout()
        self.label_civaddr = QLabel(self._t("civaddr_label"))
        civ_layout.addWidget(self.label_civaddr)
        self.input_civaddr = QLineEdit()
        self.input_civaddr.setPlaceholderText("0x00")
        self.input_civaddr.setToolTip(self._t("tt_civaddr"))
        self.input_civaddr.setText(self.civaddr)
        self.input_civaddr.setMaxLength(4)
        self.input_civaddr.setFixedWidth(72)
        self.input_civaddr.editingFinished.connect(self._on_civaddr_changed)
        civ_layout.addWidget(self.input_civaddr)
        civ_layout.addStretch()
        advanced_ptt_layout.addLayout(civ_layout)

        pin_layout = QHBoxLayout()
        self.check_rts = QCheckBox(self._t("rts_on"))
        self.check_dts = QCheckBox(self._t("dtr_on"))
        self.check_rts.setToolTip(self._t("tt_rts_on"))
        self.check_dts.setToolTip(self._t("tt_dtr_on"))
        pin_layout.addWidget(self.check_rts)
        pin_layout.addWidget(self.check_dts)
        pin_layout.addStretch()
        advanced_ptt_layout.addLayout(pin_layout)
        self.check_rts.toggled.connect(self._on_rts_state_changed)
        self.check_dts.toggled.connect(self._on_dtr_state_changed)

        cat_serial_format_layout = QHBoxLayout()
        self.label_cat_data_bits = QLabel(self._t("data_bits"))
        cat_serial_format_layout.addWidget(self.label_cat_data_bits)
        self.combo_cat_data_bits = QComboBox()
        self.combo_cat_data_bits.addItem("5", 5)
        self.combo_cat_data_bits.addItem("6", 6)
        self.combo_cat_data_bits.addItem("7", 7)
        self.combo_cat_data_bits.addItem("8", 8)
        self._set_combo_by_data(self.combo_cat_data_bits, self.cat_serial_data_bits)
        self.combo_cat_data_bits.currentIndexChanged.connect(self._on_cat_serial_data_bits_changed)
        cat_serial_format_layout.addWidget(self.combo_cat_data_bits)

        self.label_cat_parity = QLabel(self._t("parity"))
        cat_serial_format_layout.addWidget(self.label_cat_parity)
        self.combo_cat_parity = QComboBox()
        self.combo_cat_parity.addItem("None", "N")
        self.combo_cat_parity.addItem("Even", "E")
        self.combo_cat_parity.addItem("Odd", "O")
        self._set_combo_by_data(self.combo_cat_parity, self.cat_serial_parity)
        self.combo_cat_parity.currentIndexChanged.connect(self._on_cat_serial_parity_changed)
        cat_serial_format_layout.addWidget(self.combo_cat_parity)

        self.label_cat_stop_bits = QLabel(self._t("stop_bits"))
        cat_serial_format_layout.addWidget(self.label_cat_stop_bits)
        self.combo_cat_stop_bits = QComboBox()
        self.combo_cat_stop_bits.addItem("1", "1")
        self.combo_cat_stop_bits.addItem("2", "2")
        self._set_combo_by_data(self.combo_cat_stop_bits, self.cat_serial_stop_bits)
        self.combo_cat_stop_bits.currentIndexChanged.connect(self._on_cat_serial_stop_bits_changed)
        cat_serial_format_layout.addWidget(self.combo_cat_stop_bits)
        cat_serial_format_layout.addStretch()
        advanced_ptt_layout.addLayout(cat_serial_format_layout)

        self.advanced_ptt_widget.setLayout(advanced_ptt_layout)
        layout.addWidget(self.advanced_ptt_widget)

        hamlib_status_layout = QHBoxLayout()
        self.btn_hamlib_test = QPushButton(self._t("connection_test"))
        self.btn_hamlib_test.setToolTip(self._t("tt_hamlib_test"))
        self.btn_hamlib_test.clicked.connect(self.test_hamlib_connection)
        hamlib_status_layout.addWidget(self.btn_hamlib_test)
        self.label_hamlib_status = QLabel(self._t("hamlib_not_tested"))
        self.label_hamlib_status.setStyleSheet("color: gray;")
        hamlib_status_layout.addWidget(self.label_hamlib_status)
        hamlib_status_layout.addStretch()
        layout.addLayout(hamlib_status_layout)

        self.group_tx_delay = QGroupBox(self._t("delay_group"))
        tx_timing_layout = QVBoxLayout()
        tx_timing_layout.setContentsMargins(8, 18, 8, 8)
        tx_timing_layout.setSpacing(8)

        tx_delay_layout = QHBoxLayout()
        self.label_tx_delay = QLabel(self._t("tx_delay"))
        tx_delay_layout.addWidget(self.label_tx_delay)
        self.spin_vox_delay = QSpinBox()
        self.spin_vox_delay.setMinimum(0)
        self.spin_vox_delay.setMaximum(5000)
        self.spin_vox_delay.setSingleStep(10)
        self.spin_vox_delay.setValue(DEFAULT_TX_DELAY_MS)
        self.spin_vox_delay.valueChanged.connect(self._on_tx_delay_changed)
        tx_delay_layout.addWidget(self.spin_vox_delay)
        tx_delay_layout.addStretch()
        tx_timing_layout.addLayout(tx_delay_layout)

        tx_tail_layout = QHBoxLayout()
        self.label_tx_tail = QLabel(self._t("tx_tail"))
        tx_tail_layout.addWidget(self.label_tx_tail)
        self.spin_tx_tail = QSpinBox()
        self.spin_tx_tail.setMinimum(0)
        self.spin_tx_tail.setMaximum(5000)
        self.spin_tx_tail.setSingleStep(10)
        self.spin_tx_tail.setValue(DEFAULT_TX_TAIL_MS)
        self.spin_tx_tail.valueChanged.connect(self._on_tx_tail_changed)
        tx_tail_layout.addWidget(self.spin_tx_tail)
        tx_tail_layout.addStretch()
        tx_timing_layout.addLayout(tx_tail_layout)
        self.group_tx_delay.setLayout(tx_timing_layout)
        layout.addWidget(self.group_tx_delay)

        layout.addStretch()

        ptt_test_layout = QHBoxLayout()
        ptt_test_layout.addStretch()
        self.btn_ptt_test = QPushButton(self._t("ptt_test"))
        self.btn_ptt_test.setCheckable(True)
        self.btn_ptt_test.setFixedHeight(34)
        self.btn_ptt_test.setFixedWidth(140)
        self.btn_ptt_test.setToolTip(self._t("tt_ptt_test"))
        self.btn_ptt_test.setStyleSheet(
            "QPushButton {"
            "background-color: #2e7d32;"
            "color: white;"
            "border: 1px solid #1b5e20;"
            "font-weight: bold;"
            "}"
            "QPushButton:checked {"
            "background-color: #b71c1c;"
            "border: 1px solid #7f0000;"
            "color: white;"
            "}"
        )
        self.btn_ptt_test.toggled.connect(self.toggle_ptt_test)
        ptt_test_layout.addWidget(self.btn_ptt_test)
        self.btn_ptt_reset_defaults = QPushButton(self._t("ptt_reset_defaults"))
        self.btn_ptt_reset_defaults.setToolTip(self._t("tt_ptt_reset_defaults"))
        self.btn_ptt_reset_defaults.clicked.connect(self._reset_ptt_tx_defaults)
        ptt_test_layout.addWidget(self.btn_ptt_reset_defaults)
        layout.addLayout(ptt_test_layout)

        # Default state for controls before first mode change
        self._update_ptt_mode_controls(self.ptt_type)
        
        group.setLayout(layout)
        return group

    def create_network_section(self) -> QGroupBox:
        """Create TCP/IP and Web UI section."""
        group = QGroupBox(self._t("net_config"))
        self.section_network = group
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 20, 8, 10)
        layout.setSpacing(8)

        kiss_port_row = QHBoxLayout()
        self.label_kiss_port_info = QLabel(self._t("kiss_port"))
        kiss_port_row.addWidget(self.label_kiss_port_info)
        self.spin_kiss_port = QSpinBox()
        self.spin_kiss_port.setRange(1, 65535)
        self.spin_kiss_port.setValue(int(self.kiss_port))
        self.spin_kiss_port.valueChanged.connect(self._on_kiss_port_changed)
        kiss_port_row.addWidget(self.spin_kiss_port)
        kiss_port_row.addStretch()
        layout.addLayout(kiss_port_row)

        web_toggle_row = QHBoxLayout()
        web_toggle_row.addStretch()
        self.check_web_ui_enabled = QCheckBox(self._t("web_enabled"))
        self.check_web_ui_enabled.setChecked(self.web_ui_enabled)
        self.check_web_ui_enabled.toggled.connect(self.on_web_ui_toggle_changed)
        web_toggle_row.addWidget(self.check_web_ui_enabled)
        web_toggle_row.addStretch()
        layout.addLayout(web_toggle_row)

        web_url = f"http://{WEB_UI_LOCAL_HOST}:{WEB_UI_PORT}"
        self.label_web_link = QLabel(
            f'<span style="color:#000000; text-decoration:none;">Web: </span>'
            f'<a href="{web_url}"><span style="color:#0b63c9;">{web_url}</span></a>'
        )
        self.label_web_link.setTextFormat(Qt.TextFormat.RichText)
        self.label_web_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.label_web_link.setOpenExternalLinks(True)
        self.label_web_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_web_link)

        self.label_allow_caption = QLabel(self._t("allowed_addresses"))
        self.label_allow_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_allow_caption)

        allow_row = QHBoxLayout()
        allow_row.addStretch()
        self.combo_allow_ips = QComboBox()
        self.combo_allow_ips.setEditable(True)
        self.combo_allow_ips.setMinimumWidth(360)
        self.combo_allow_ips.setMaximumWidth(520)
        self.combo_allow_ips.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.combo_allow_ips.lineEdit() is not None:
            self.combo_allow_ips.lineEdit().setPlaceholderText(self._t("allowed_placeholder"))
            self.combo_allow_ips.lineEdit().returnPressed.connect(self.on_allow_ip_toggle_clicked)
        allow_row.addWidget(self.combo_allow_ips)
        self.btn_allow_ip_toggle = QPushButton(self._t("toggle"))
        self.btn_allow_ip_toggle.setMaximumWidth(90)
        self.btn_allow_ip_toggle.clicked.connect(self.on_allow_ip_toggle_clicked)
        allow_row.addWidget(self.btn_allow_ip_toggle)
        allow_row.addStretch()
        layout.addLayout(allow_row)

        self.label_allow_ip_status = QLabel("Allowed IPs: --")
        self.label_allow_ip_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_allow_ip_status)
        self.label_allow_ip_hint = QLabel(self._t("localhost_hint"))
        self.label_allow_ip_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_allow_ip_hint.setStyleSheet("color: gray;")
        layout.addWidget(self.label_allow_ip_hint)
        self._refresh_allow_ip_controls()
        self._update_web_link_visibility()
        self._update_monitor_config_summary()

        group.setLayout(layout)
        return group
    
    def _update_ptt_mode_controls(self, mode: str) -> None:
        """Enable/disable PTT control groups based on selected mode."""
        mode_norm = self._normalize_ptt_type(mode)
        is_rig = (mode_norm == "RIG")
        is_serial = mode_norm in ("DTR", "RTS")
        is_vox = mode_norm == "VOX"
        is_advanced = self.config_ui_mode == "advanced"

        def set_visible(widget, visible: bool) -> None:
            if widget is not None and hasattr(widget, "setVisible"):
                widget.setVisible(bool(visible))

        def set_visible_attr(name: str, visible: bool) -> None:
            set_visible(getattr(self, name, None), visible)

        def set_enabled_attr(name: str, enabled: bool) -> None:
            widget = getattr(self, name, None)
            if widget is not None and hasattr(widget, "setEnabled"):
                widget.setEnabled(bool(enabled))

        set_enabled_attr("combo_ptt_port", is_serial)
        set_enabled_attr("check_ptt_share", is_serial)
        set_enabled_attr("check_ptt_active_low", is_serial)

        set_enabled_attr("input_hamlib_host", is_rig)
        set_enabled_attr("spin_hamlib_port", is_rig)
        set_enabled_attr("btn_hamlib_test", is_rig)
        set_enabled_attr("label_hamlib_status", is_rig)
        set_enabled_attr("combo_rig_connection", is_rig)
        set_enabled_attr("combo_rig_model", is_rig)
        set_enabled_attr("btn_ptt_test", not is_vox)

        is_cat_serial = is_rig and self.rig_connection == "SERIAL"
        is_cat_tcp = is_rig and self.rig_connection == "TCP"
        set_enabled_attr("check_rts", is_cat_serial)
        set_enabled_attr("check_dts", is_cat_serial)
        set_enabled_attr("combo_cat_serial_port", is_cat_serial)
        set_enabled_attr("spin_cat_serial_baud", is_cat_serial)
        set_enabled_attr("combo_cat_data_bits", is_cat_serial)
        set_enabled_attr("combo_cat_parity", is_cat_serial)
        set_enabled_attr("combo_cat_stop_bits", is_cat_serial)
        set_enabled_attr("input_hamlib_host", is_cat_tcp)
        set_enabled_attr("spin_hamlib_port", is_cat_tcp)
        set_enabled_attr("input_civaddr", is_cat_serial and self._rig_uses_civ(self.rig_model))
        self._sync_ptt_invert_checkbox()

        set_visible_attr("label_rig_control_title", is_rig)
        set_visible_attr("label_rig_model", is_rig)
        set_visible_attr("combo_rig_model", is_rig)
        set_visible_attr("label_rig_profile_hint", is_rig)
        set_visible_attr("label_cat_connection", is_rig)
        set_visible_attr("combo_rig_connection", is_rig)
        set_visible_attr("label_cat_serial_port", is_rig and is_cat_serial)
        set_visible_attr("combo_cat_serial_port", is_rig and is_cat_serial)
        set_visible_attr("label_cat_baud", is_rig and is_cat_serial)
        set_visible_attr("spin_cat_serial_baud", is_rig and is_cat_serial)
        set_visible_attr("label_hamlib_host", is_rig and is_cat_tcp)
        set_visible_attr("input_hamlib_host", is_rig and is_cat_tcp)
        set_visible_attr("label_hamlib_port", is_rig and is_cat_tcp)
        set_visible_attr("spin_hamlib_port", is_rig and is_cat_tcp)
        set_visible_attr("btn_hamlib_test", is_rig)
        set_visible_attr("label_hamlib_status", is_rig)
        set_visible_attr("label_ptt_path", is_serial)
        set_visible_attr("combo_ptt_port", is_serial)
        set_visible_attr("check_ptt_active_low", is_serial)
        set_visible_attr("btn_ptt_test", not is_vox)
        set_visible_attr("btn_ptt_reset_defaults", True)

        set_visible_attr("advanced_ptt_widget", is_advanced)
        set_visible_attr("label_civaddr", is_advanced and is_rig)
        set_visible_attr("input_civaddr", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("check_rts", is_advanced and is_cat_serial)
        set_visible_attr("check_dts", is_advanced and is_cat_serial)
        set_visible_attr("label_cat_data_bits", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("combo_cat_data_bits", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("label_cat_parity", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("combo_cat_parity", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("label_cat_stop_bits", is_advanced and is_rig and is_cat_serial)
        set_visible_attr("combo_cat_stop_bits", is_advanced and is_rig and is_cat_serial)

    def _on_rig_connection_changed(self, _index: int) -> None:
        """Switch CAT transport mode between TCP and serial."""
        value = self.combo_rig_connection.currentData() if hasattr(self, "combo_rig_connection") else "TCP"
        self.rig_connection = self._normalize_rig_connection(value)
        self._update_ptt_mode_controls(self.ptt_type)
        self._save_rig_connection_config()
        self._reset_hamlib_status()

    def _on_cat_serial_port_changed(self, _index: int) -> None:
        """Persist CAT serial port selection."""
        value = self.combo_cat_serial_port.currentData() if hasattr(self, "combo_cat_serial_port") else None
        self.cat_serial_port = str(value or "")
        self._save_rig_connection_config()
        self._reset_hamlib_status()

    def _on_cat_serial_baud_changed(self, value: int) -> None:
        """Persist CAT serial baudrate selection."""
        self.cat_serial_baud = int(value)
        self._save_rig_connection_config()
        self._reset_hamlib_status()

    def _on_cat_serial_data_bits_changed(self, _index: int) -> None:
        """Persist CAT serial data bits."""
        value = self.combo_cat_data_bits.currentData() if hasattr(self, "combo_cat_data_bits") else 8
        self.cat_serial_data_bits = int(value or 8)
        self._save_rig_connection_config()

    def _on_cat_serial_parity_changed(self, _index: int) -> None:
        """Persist CAT serial parity."""
        value = self.combo_cat_parity.currentData() if hasattr(self, "combo_cat_parity") else "N"
        self.cat_serial_parity = str(value or "N")
        self._save_rig_connection_config()

    def _on_cat_serial_stop_bits_changed(self, _index: int) -> None:
        """Persist CAT serial stop bits."""
        value = self.combo_cat_stop_bits.currentData() if hasattr(self, "combo_cat_stop_bits") else "1"
        self.cat_serial_stop_bits = str(value or "1")
        self._save_rig_connection_config()

    def _on_rig_model_changed(self, _index: int) -> None:
        """Persist selected CAT rig model and apply model defaults."""
        value = self.combo_rig_model.currentData() if hasattr(self, "combo_rig_model") else "ICOM_CUSTOM"
        self.rig_model = self._normalize_rig_model(value)

        default_civ = self._default_civ_for_model(self.rig_model)
        if default_civ:
            self.civaddr = default_civ
            if hasattr(self, "input_civaddr"):
                self.input_civaddr.setText(default_civ)

        self._save_ptt_config()
        self._save_rig_connection_config()
        self._update_rig_profile_hint()
        self._update_ptt_mode_controls(self.ptt_type)
        self._reset_hamlib_status()

    def _on_ptt_port_changed(self, _index: int) -> None:
        """Update serial ptt_path from combo selection."""
        value = self.combo_ptt_port.currentData() if hasattr(self, "combo_ptt_port") else None
        self.ptt_port = str(value or "")
        if self.ptt_type in ("DTR", "RTS") and self.ptt_port:
            self.open_ptt_port(self.ptt_port)
        self._save_ptt_config()

    def _on_ptt_share_changed(self, checked: bool) -> None:
        """Persist ptt_share setting."""
        self.ptt_share = bool(checked)
        self._save_ptt_config()

    def _on_ptt_active_low_changed(self, checked: bool) -> None:
        """Persist invert state for the currently selected DTR or RTS PTT line."""
        value = bool(checked)
        mode = self._normalize_ptt_type(self.ptt_type)
        if mode == "DTR":
            self.dtr_active_low = value
        elif mode == "RTS":
            self.rts_active_low = value
        self.ptt_active_low = value
        self._save_ptt_config()
        if self.ptt_type in ("DTR", "RTS") and self.ppt_serial is not None and self.ppt_serial.is_open:
            self.set_ppt(bool(self.ptt_active))

    def _on_civaddr_changed(self) -> None:
        """Persist civaddr setting."""
        self.civaddr = self.input_civaddr.text().strip() or "0x00"
        self._save_ptt_config()

    def _on_rts_state_changed(self, checked: bool) -> None:
        """Persist and apply rts_state setting."""
        self.rts_state = "ON" if checked else "Unset"
        self._save_ptt_config()
        self._apply_line_overrides()

    def _on_dtr_state_changed(self, checked: bool) -> None:
        """Persist and apply dtr_state setting."""
        self.dtr_state = "ON" if checked else "Unset"
        self._save_ptt_config()
        self._apply_line_overrides()

    def _on_tx_delay_changed(self, value: int) -> None:
        """Persist TX delay used for preamble flags before APRS frame payload."""
        if self.config_ui_mode != "advanced":
            self._sync_tx_timing_controls()
            return
        self.tx_delay_ms = max(0, min(5000, int(value)))
        self._save_ptt_config()

    def _on_tx_tail_changed(self, value: int) -> None:
        """Persist TX tail after end of frame and trailing flags."""
        if self.config_ui_mode != "advanced":
            self._sync_tx_timing_controls()
            return
        self.tx_tail_ms = max(0, min(5000, int(value)))
        self._save_ptt_config()

    def _on_pre_tx_flags_toggled(self, checked: bool) -> None:
        self.pre_tx_flags_enabled = bool(checked)
        self._save_ptt_config()

    def _on_post_tx_flags_toggled(self, checked: bool) -> None:
        self.post_tx_flags_enabled = bool(checked)
        self._save_ptt_config()

    def _reset_ptt_tx_defaults(self) -> None:
        """Restore default TX/PTT values for quick recovery."""
        self.tx_delay_ms = DEFAULT_TX_DELAY_MS
        self.tx_tail_ms = DEFAULT_TX_TAIL_MS
        self.ptt_active_low = False
        self.rts_active_low = False
        self.dtr_active_low = False
        self.rts_state = "Unset"
        self.dtr_state = "Unset"
        self.pre_tx_flags_enabled = True
        self.post_tx_flags_enabled = True

        if hasattr(self, "spin_vox_delay"):
            self.spin_vox_delay.blockSignals(True)
            self.spin_vox_delay.setValue(self.tx_delay_ms)
            self.spin_vox_delay.blockSignals(False)
        if hasattr(self, "spin_tx_tail"):
            self.spin_tx_tail.blockSignals(True)
            self.spin_tx_tail.setValue(self.tx_tail_ms)
            self.spin_tx_tail.blockSignals(False)
        self._sync_tx_timing_controls()
        if hasattr(self, "check_ptt_active_low"):
            self._sync_ptt_invert_checkbox()
        if hasattr(self, "check_rts"):
            self.check_rts.blockSignals(True)
            self.check_rts.setChecked(False)
            self.check_rts.blockSignals(False)
        if hasattr(self, "check_dts"):
            self.check_dts.blockSignals(True)
            self.check_dts.setChecked(False)
            self.check_dts.blockSignals(False)

        self._apply_line_overrides()
        self._save_ptt_config()
        logger.info("[PTT] TX/PTT defaults restored by user action")
    
    def create_monitor_section(self) -> QGroupBox:
        """Create MONITOR section for frame log"""
        group = QGroupBox(self._t("monitor_group"))
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 20, 8, 10)
        layout.setSpacing(8)

        freeze_layout = QHBoxLayout()
        self.btn_toggle_config_sections = QPushButton(self._t("config_toggle"))
        self.btn_toggle_config_sections.setMinimumHeight(22)
        self.btn_toggle_config_sections.setMaximumHeight(22)
        self.btn_toggle_config_sections.clicked.connect(lambda: self.show_config_view(persist=True))
        self.btn_toggle_config_sections.setVisible(False)
        freeze_layout.addStretch()

        freeze_button_style = (
            "QPushButton {"
            "min-width: 74px;"
            "max-width: 74px;"
            "min-height: 22px;"
            "max-height: 22px;"
            "padding: 0px;"
            "border: 1px solid #5a5a5a;"
            "background-color: #6a6a6a;"
            "color: #d0d0d0;"
            "font-weight: bold;"
            "}"
            "QPushButton:checked {"
            "background-color: #b12626;"
            "border: 1px solid #7f1a1a;"
            "color: white;"
            "}"
        )

        self.btn_monitor_freeze = QPushButton("Freeze")
        self.btn_monitor_freeze.setCheckable(True)
        self.btn_monitor_freeze.setStyleSheet(freeze_button_style)
        self.btn_monitor_freeze.toggled.connect(self._on_monitor_freeze_toggled)
        freeze_layout.addWidget(self.btn_monitor_freeze)
        layout.addLayout(freeze_layout)
        
        self.text_monitor = QTextEdit()
        self.text_monitor.setReadOnly(True)
        self.text_monitor.setUndoRedoEnabled(False)
        self.text_monitor.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.text_monitor.setFont(QFont("Courier New", 9))
        self.text_monitor.setStyleSheet("background-color: black; color: #00ff00;")
        self.text_monitor.setMinimumHeight(200)  # Ensure monitor has minimum height
        self.text_monitor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_monitor.customContextMenuRequested.connect(self._show_monitor_context_menu)
        self.text_monitor.clear()  # Clear monitor on startup - don't load previous session
        layout.addWidget(self.text_monitor)
        
        group.setLayout(layout)
        group.setMinimumHeight(250)  # Ensure group has height too
        return group

    def create_about_page(self) -> QWidget:
        """Create about page."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        group = QGroupBox(self._t("about_title"))
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(8, 18, 8, 10)
        group_layout.setSpacing(8)

        self.label_about_desc = QLabel(self._t("about_description"))
        self.label_about_desc.setWordWrap(True)
        group_layout.addWidget(self.label_about_desc)

        self.label_about_build = QLabel(f"{self._t('about_build')} {self.app_build_tag}")
        group_layout.addWidget(self.label_about_build)

        self.label_about_kiss = QLabel(f"{self._t('about_kiss')} 127.0.0.1:{self.kiss_port}")
        group_layout.addWidget(self.label_about_kiss)

        self.label_about_web = QLabel(f"{self._t('about_web')} {WEB_UI_BIND_HOST}:{WEB_UI_PORT}")
        group_layout.addWidget(self.label_about_web)

        self.label_about_author = QLabel(self._t("created_by"))
        group_layout.addWidget(self.label_about_author)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def on_ptt_mode_changed(self, mode: str):
        """Handle PTT mode change"""
        # Ignore empty placeholder
        if mode == self._t("select_mode") or not mode:
            return
        
        self.ptt_type = str(mode).upper()
        self.ppt_mode = self.ptt_type
        self._update_ptt_mode_controls(self.ptt_type)
        is_serial = self.ptt_type in ("DTR", "RTS")
        
        # Setup serial port if DTR/RTS mode selected
        if is_serial:
            selected_port = self.combo_ptt_port.currentData() if hasattr(self, "combo_ptt_port") else None
            if selected_port:
                self.ptt_port = str(selected_port)
            if self.ptt_port:
                self.open_ptt_port(self.ptt_port)
        else:
            self.close_ppt_port()
            if hasattr(self, "btn_ptt_test") and self.btn_ptt_test.isChecked():
                self.btn_ptt_test.blockSignals(True)
                self.btn_ptt_test.setChecked(False)
                self.btn_ptt_test.blockSignals(False)

        self._save_ptt_config()
        
        logger.info(f"[PTT] Type changed to: {self.ptt_type}")
        self._update_monitor_config_summary()

    def toggle_ptt_test(self, checked: bool) -> None:
        """Manual PTT test toggle from desktop UI."""
        try:
            self.set_ppt(bool(checked))
        except Exception as e:
            logger.warning(f"[PTT] Manual test toggle error: {e}")
            if hasattr(self, "btn_ptt_test"):
                self.btn_ptt_test.blockSignals(True)
                self.btn_ptt_test.setChecked(False)
                self.btn_ptt_test.blockSignals(False)
    
    def toggle_tone_1200(self):
        """Toggle 1200 Hz test tone"""
        self._toggle_tone_button(self.btn_tone_1200, "1200")
    
    def toggle_tone_both(self):
        """Toggle Both test tones"""
        self._toggle_tone_button(self.btn_tone_both, "both")
    
    def toggle_tone_2200(self):
        """Toggle 2200 Hz test tone"""
        self._toggle_tone_button(self.btn_tone_2200, "2200")
    
    def _toggle_tone_button(self, clicked_button, tone_type: str):
        """
        Handle exclusive tone button toggling
        Only one tone can be active at a time
        """
        # Check if tone is currently running
        is_tone_running = self.tone_gen.is_running()
        
        # If same button clicked and tone is running, turn off
        if is_tone_running and self.active_tone_button == clicked_button:
            logger.info(f"[TONE] Stopping tone")
            self.tone_gen.stop_continuous()
            self.set_ppt(False)
            # Uncheck all buttons
            self.btn_tone_1200.setChecked(False)
            self.btn_tone_both.setChecked(False)
            self.btn_tone_2200.setChecked(False)
            self.active_tone_button = None
            return
        
        # Different button clicked or button checked while nothing running
        if is_tone_running and self.active_tone_button != clicked_button:
            logger.info(f"[TONE] Switching tone from {self.active_tone_button} to {clicked_button}")
            # Uncheck previous button
            if self.active_tone_button:
                self.active_tone_button.setChecked(False)
            # Stop current tone
            self.tone_gen.stop_continuous()
            self.set_ppt(False)
        
        # Start new tone
        logger.info(f"[TONE] Starting {tone_type} Hz tone")
        # Setup audio output callback
        self.tone_gen.on_audio_ready = self.on_tone_audio_ready
        # Start audio output stream if not running
        if self.audio_stream_out is None:
            logger.info(f"[TONE] Output stream not running, starting it...")
            self.start_audio_output()
        
        # CRITICAL: Verify actual sample rate right before tone generation
        logger.info(f"[TONE] *** CRITICAL VERIFICATION ***")
        logger.info(f"[TONE] actual_output_sample_rate before tone: {self.actual_output_sample_rate} Hz")
        logger.info(f"[TONE] audio_stream_out.samplerate: {self.audio_stream_out.samplerate if self.audio_stream_out else 'None'} Hz")
        
        # Start tone generation with small chunks for smooth audio (20ms)
        # Pass actual sample rate to ensure correct frequency generation
        logger.info(f"[TONE] Calling start_continuous() with sample_rate={self.actual_output_sample_rate} Hz")
        self.tone_gen.start_continuous(tone_type, self.on_tone_audio_ready, chunk_duration=0.02, sample_rate=self.actual_output_sample_rate)
        self.set_ppt(True)
        
        # Mark button as active and checked
        clicked_button.setChecked(True)
        self.active_tone_button = clicked_button
    
    def update_meters(self):
        """Update signal level meters"""
        # Input meter
        levels_in = self.audio_monitor_in.get_all_levels()
        self.progress_in.setValue(int(levels_in["peak_pct"]))
        self.label_in_levels.setText(
            f"Peak: {levels_in['peak_pct']:.0f}% ({levels_in['peak_dbfs']:.1f} dBFS) | "
            f"RMS: {levels_in['rms_pct']:.0f}% ({levels_in['rms_dbfs']:.1f} dBFS)"
        )
        
        # Output meter
        # If no TX/output samples were received recently, clear stale output level.
        if (time.time() - self._last_output_meter_update_ts) > 1.0:
            self.audio_monitor_out.reset()
        levels_out = self.audio_monitor_out.get_all_levels()
        self.progress_out.setValue(int(levels_out["peak_pct"]))
        self.label_out_levels.setText(
            f"Peak: {levels_out['peak_pct']:.0f}% ({levels_out['peak_dbfs']:.1f} dBFS) | "
            f"RMS: {levels_out['rms_pct']:.0f}% ({levels_out['rms_dbfs']:.1f} dBFS)"
        )
    
    def _normalize_callsign(self, callsign: str) -> str:
        """Normalize callsign to uppercase AX.25 format for comparisons."""
        return str(callsign or "").strip().upper()

    def _decode_ax25_address(self, addr: bytes) -> dict:
        """Decode one 7-byte AX.25 address field."""
        if len(addr) != 7:
            return {"full": "UNKNOWN", "base": "UNKNOWN", "ssid": 0, "repeated": False, "last": True}

        base = ""
        for i in range(6):
            c = (addr[i] >> 1) & 0x7F
            if 32 <= c <= 126:
                base += chr(c)
        base = base.strip() or "NULL"
        ssid = (addr[6] >> 1) & 0x0F
        repeated = bool(addr[6] & 0x80)  # H bit for digipeaters
        last = bool(addr[6] & 0x01)
        full = f"{base}-{ssid}" if ssid > 0 else base
        return {
            "full": full,
            "base": base,
            "ssid": ssid,
            "repeated": repeated,
            "last": last,
        }

    def _parse_ax25_addresses(self, frame_data: bytes) -> tuple:
        """Parse AX.25 address list and return (addresses, next_pos)."""
        addresses = []
        pos = 0
        while pos + 7 <= len(frame_data) and len(addresses) < 10:
            raw = frame_data[pos:pos + 7]
            decoded = self._decode_ax25_address(raw)
            decoded["raw"] = raw
            addresses.append(decoded)
            pos += 7
            if decoded["last"]:
                break
        return addresses, pos

    def _parse_ax25_control(self, control: int) -> dict:
        """Decode AX.25 control byte to frame class metadata."""
        if (control & 0x01) == 0:
            return {
                "class": "I",
                "name": "I",
                "ns": (control >> 1) & 0x07,
                "nr": (control >> 5) & 0x07,
                "pf": (control >> 4) & 0x01,
            }

        if (control & 0x03) == 0x01:
            s_map = {0: "RR", 1: "RNR", 2: "REJ", 3: "SREJ"}
            code = (control >> 2) & 0x03
            return {
                "class": "S",
                "name": s_map.get(code, "S"),
                "nr": (control >> 5) & 0x07,
                "pf": (control >> 4) & 0x01,
            }

        base = control & 0xEF  # clear P/F bit for U-frame identification
        u_map = {
            0x03: "UI",
            0x2F: "SABM",
            0x6F: "SABME",
            0x43: "DISC",
            0x63: "UA",
            0x0F: "DM",
            0x87: "FRMR",
            0xAF: "XID",
            0xE3: "TEST",
        }
        return {
            "class": "U",
            "name": u_map.get(base, f"U(0x{control:02X})"),
            "pf": (control >> 4) & 0x01,
        }

    def _encode_ax25_address(self, callsign: str, last: bool = False, repeated: bool = False) -> bytes:
        """Encode callsign-ssid string to one 7-byte AX.25 address field."""
        call = self._normalize_callsign(callsign)
        ssid = 0
        if "-" in call:
            base, ssid_str = call.split("-", 1)
            call = base
            try:
                ssid = max(0, min(15, int(ssid_str)))
            except ValueError:
                ssid = 0

        call = (call[:6]).ljust(6)
        out = bytearray(7)
        for i, ch in enumerate(call):
            out[i] = (ord(ch) << 1) & 0xFE

        ssid_byte = 0x60 | ((ssid & 0x0F) << 1)
        if repeated:
            ssid_byte |= 0x80
        if last:
            ssid_byte |= 0x01
        out[6] = ssid_byte
        return bytes(out)

    def _build_ax25_frame(self, dest: str, src: str, control: int, pid: Optional[int] = None, info: bytes = b"", digis: Optional[list] = None) -> bytes:
        """Build AX.25 frame bytes from address/control fields."""
        digis = digis or []
        addr_fields = [dest, src] + list(digis)
        parts = []
        for idx, cs in enumerate(addr_fields):
            parts.append(self._encode_ax25_address(cs, last=(idx == len(addr_fields) - 1), repeated=False))

        frame = b"".join(parts) + bytes([control & 0xFF])
        if pid is not None:
            frame += bytes([pid & 0xFF])
        if info:
            frame += info
        return frame
    
    def _format_tnc2(self, frame_data: bytes) -> str:
        """Format AX.25 frame as TNC2 string: SRC>DEST,DIGI*,...:INFO"""
        try:
            if len(frame_data) < 15:
                return frame_data.hex().upper()

            addresses, pos = self._parse_ax25_addresses(frame_data)
            if len(addresses) < 2:
                return frame_data.hex().upper()

            dest = addresses[0]["full"]
            src = addresses[1]["full"]
            digis = addresses[2:]

            control = frame_data[pos] if pos < len(frame_data) else 0x03
            ctrl_meta = self._parse_ax25_control(control)
            pos += 1

            pid = None
            if ctrl_meta["name"] in ("UI", "I") and pos < len(frame_data):
                pid = frame_data[pos]
                pos += 1

            info_bytes = frame_data[pos:] if pos < len(frame_data) else b""
            info = info_bytes.decode("latin-1", errors="replace")

            path_items = []
            for digi in digis:
                item = digi["full"] + ("*" if digi.get("repeated") else "")
                path_items.append(item)

            header = f"{src}>{dest}"
            if path_items:
                header += "," + ",".join(path_items)

            if ctrl_meta["name"] == "UI":
                tnc2 = f"{header}:{info}"
            elif ctrl_meta["name"] == "I":
                ctrl_txt = f"I N(S)={ctrl_meta['ns']} N(R)={ctrl_meta['nr']}"
                if info:
                    tnc2 = f"{header}:<{ctrl_txt}> {info}"
                else:
                    tnc2 = f"{header}:<{ctrl_txt}>"
            elif ctrl_meta["class"] == "S":
                tnc2 = f"{header}:<{ctrl_meta['name']} N(R)={ctrl_meta['nr']}>"
            else:
                tnc2 = f"{header}:<{ctrl_meta['name']}>"

            if pid is not None and ctrl_meta["name"] != "UI":
                tnc2 += f" [PID=0x{pid:02X}]"

            return tnc2
        except Exception as e:
            logger.debug(f"[FRAME] TNC2 format error: {e}")
            return frame_data.hex().upper()

    def _send_l2_response_rf(self, frame_data: bytes, reason: str) -> None:
        """Send auto-generated AX.25 response frame over RF/audio path."""
        try:
            self._transmit_ax25_frame(frame_data, tx_tag=f"L2/{reason}")
            if self.kiss_server:
                self.kiss_server.send_frame(frame_data)
        except Exception as e:
            logger.warning(f"[L2] Failed to send {reason}: {e}")

    def _handle_ax25_l2(self, frame_data: bytes) -> None:
        """Minimal AX.25 L2 state handling (SABM/UA, DISC/UA, I/RR)."""
        if not self.ax25_l2_enabled:
            return

        try:
            addresses, pos = self._parse_ax25_addresses(frame_data)
            if len(addresses) < 2 or pos >= len(frame_data):
                return

            dest = self._normalize_callsign(addresses[0]["full"])
            src = self._normalize_callsign(addresses[1]["full"])
            local = self._normalize_callsign(self.ax25_local_callsign)
            if dest != local:
                return

            ctrl = self._parse_ax25_control(frame_data[pos])
            key = f"{src}>{dest}"

            if ctrl["name"] in ("SABM", "SABME"):
                self.ax25_l2_sessions[key] = {"vr": 0, "vs": 0, "va": 0}
                ua = self._build_ax25_frame(dest=src, src=dest, control=0x63)
                self._send_l2_response_rf(ua, "UA")
                self.sig_monitor_line.emit("L2", "", f"L2: CONNECT {src} -> {dest} (UA)")
                return

            if ctrl["name"] == "DISC":
                if key in self.ax25_l2_sessions:
                    self.ax25_l2_sessions.pop(key, None)
                ua = self._build_ax25_frame(dest=src, src=dest, control=0x63)
                self._send_l2_response_rf(ua, "UA")
                self.sig_monitor_line.emit("L2", "", f"L2: DISCONNECT {src} -> {dest} (UA)")
                return

            if ctrl["name"] == "I":
                vr = (int(ctrl.get("ns", 0)) + 1) % 8
                self.ax25_l2_sessions.setdefault(key, {"vr": 0, "vs": 0, "va": 0})["vr"] = vr
                rr_ctrl = 0x01 | ((vr & 0x07) << 5)
                rr = self._build_ax25_frame(dest=src, src=dest, control=rr_ctrl)
                self._send_l2_response_rf(rr, "RR")
                self.sig_monitor_line.emit("L2", "", f"L2: ACK {src} N(R)={vr} (RR)")
                return

            if ctrl["name"] == "RR" and key in self.ax25_l2_sessions:
                self.ax25_l2_sessions[key]["va"] = int(ctrl.get("nr", 0))

        except Exception as e:
            logger.debug(f"[L2] Handler error: {e}")

    def _transmit_ax25_frame(self, frame_data: bytes, tx_tag: str = "KISS") -> None:
        """TX processing path: AX.25 -> HDLC -> AFSK -> audio output."""
        logger.info(f"[TX/{tx_tag}] Starting processing of {len(frame_data)} bytes...")
        logger.info(f"[TX/{tx_tag}] TX queued")

        # Track outbound frames to suppress immediate local audio loopback in RX monitor.
        self._remember_recent_tx_frame(frame_data)

        device_sample_rate = self.actual_output_sample_rate
        logger.info(f"[TX/{tx_tag}] Using actual_output_sample_rate: {device_sample_rate} Hz")

        frame_bits = self.hdlc_encoder.encode_frame(frame_data)
        tx_delay_ms = self._get_tx_delay_ms()
        preamble_flags = 0
        preamble_bits = []
        if bool(self.pre_tx_flags_enabled):
            # 1200 bps => 1 bit ~= 0.833 ms; one HDLC flag = 8 bits.
            # Number of flags approximating requested TX delay:
            # ceil((tx_delay_ms * 1200 / 1000) / 8) == ceil(tx_delay_ms * 3 / 20)
            preamble_flags = max(1, (tx_delay_ms * 3 + 19) // 20)
            preamble_bits = self.hdlc_encoder.generate_preamble(num_flags=preamble_flags)

        postamble_flags = 15 if bool(self.post_tx_flags_enabled) else 0
        postamble_bits = self.hdlc_encoder.generate_preamble(num_flags=postamble_flags) if postamble_flags > 0 else []
        full_bits = preamble_bits + frame_bits + postamble_bits

        afsk_mod = AFSKModulator(sample_rate=device_sample_rate)
        tx_amp = float(getattr(self, "current_tx_amplitude", 0.9))
        tx_amp = max(0.5, min(1.0, tx_amp))
        audio_data = afsk_mod.modulate_continuous(full_bits, amplitude=tx_amp)
        # Keep margin from full-scale to avoid clipping/overdeviation on some audio paths.
        peak = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
        if peak > 0.95:
            audio_data = (audio_data * (0.95 / peak)).astype(np.float32, copy=False)
        preamble_samples = 0
        frame_samples = 0
        postamble_samples = 0
        if full_bits:
            total_bits = len(full_bits)
            total_samples = len(audio_data)
            preamble_samples = int(total_samples * (len(preamble_bits) / total_bits)) if total_bits > 0 else 0
            frame_samples = int(total_samples * (len(frame_bits) / total_bits)) if total_bits > 0 else 0
            postamble_samples = max(0, total_samples - preamble_samples - frame_samples)
        self._tx_last_segments = {
            "preamble_samples": preamble_samples,
            "frame_samples": frame_samples,
            "postamble_samples": postamble_samples,
        }
        audio_list = audio_data.tolist() if isinstance(audio_data, np.ndarray) else audio_data
        self.tx_intent_want = True
        self.sig_tx_audio.emit(audio_list)
        logger.info(f"[TX/{tx_tag}] TX amplitude={tx_amp:.2f}, post-limit peak={float(np.max(np.abs(audio_data))):.3f}")
        logger.info(
            f"[TX/{tx_tag}] TX delay={tx_delay_ms} ms mapped to {preamble_flags} preamble flags; "
            f"post_flags={postamble_flags}; pre_enabled={self.pre_tx_flags_enabled}; post_enabled={self.post_tx_flags_enabled}"
        )
        logger.info(f"[TX/{tx_tag}] Audio data emitted to GUI thread for playback")

    def _get_tx_delay_ms(self) -> int:
        """Resolve TX delay in milliseconds, counted from PTT ON to audio write."""
        if self.config_ui_mode != "advanced":
            return DEFAULT_TX_DELAY_MS
        delay = self.config.get("ptt.tx_delay_ms", self.config.get("ptt.vox_delay_ms", self.tx_delay_ms))
        if hasattr(self, "spin_vox_delay"):
            try:
                delay = int(self.spin_vox_delay.value())
            except Exception:
                pass
        try:
            delay_ms = int(delay)
        except Exception:
            delay_ms = DEFAULT_TX_DELAY_MS
        return max(0, min(5000, delay_ms))

    def _get_tx_tail_ms(self) -> int:
        """Resolve TX tail in milliseconds, counted from last audio sample to PTT OFF."""
        if self.config_ui_mode != "advanced":
            return DEFAULT_TX_TAIL_MS
        tail = self.config.get("ptt.tx_tail_ms", self.tx_tail_ms)
        try:
            tail_ms = int(tail)
        except Exception:
            tail_ms = DEFAULT_TX_TAIL_MS
        return max(0, min(5000, tail_ms))

    def _remember_recent_tx_frame(self, frame_data: bytes) -> None:
        """Store recently transmitted frame payload for local loopback suppression."""
        if not frame_data:
            return

        now = time.monotonic()
        payload = bytes(frame_data)
        with self._recent_tx_lock:
            self._recent_tx_frames.append((now, payload))

    def _is_recent_tx_echo(self, frame_data: bytes) -> bool:
        """Return True when RX payload matches a frame we have just transmitted."""
        if not frame_data:
            return False

        now = time.monotonic()
        payload = bytes(frame_data)

        with self._recent_tx_lock:
            # Drop stale entries first.
            while self._recent_tx_frames and (now - self._recent_tx_frames[0][0]) > self.tx_echo_suppression_window_s:
                self._recent_tx_frames.popleft()

            for _, tx_payload in self._recent_tx_frames:
                if tx_payload == payload:
                    return True

        return False
    
    def add_monitor_line(self, direction: str, timestamp: str, frame_info: str):
        """
        Add line to monitor display
        
        Args:
            direction: "RX" or "TX"
            timestamp: Timestamp string
            frame_info: Frame description (APRS format)
        """
        ts = timestamp.strip() if isinstance(timestamp, str) else ""
        if not ts:
            ts = datetime.now().strftime("%H:%M:%S")

        direction_u = str(direction or "").upper()
        kind = "RX_DIGI" if direction_u == "DIGI" else direction_u
        display_direction = "RX" if direction_u == "DIGI" else direction_u

        line = f"[{display_direction}] {ts} | {frame_info}\n"
        self.last_monitor_line = line.strip()
        self.monitor_lines.insert(0, self.last_monitor_line)
        self.monitor_line_kinds.insert(0, kind)
        if len(self.monitor_lines) > 250:
            self.monitor_lines = self.monitor_lines[:250]
            self.monitor_line_kinds = self.monitor_line_kinds[:250]

        if self.monitor_frozen:
            return

        self._render_monitor_text()

    def _render_monitor_text(self) -> None:
        """Render current monitor buffer with newest entries at the top."""
        if not hasattr(self, "text_monitor"):
            return

        def _line_color(line: str, kind: str) -> str:
            kind_u = str(kind or "").upper()
            if kind_u == "RX_DIGI":
                return "#66b3ff"
            if kind_u == "RX" or line.startswith("[RX]"):
                return "#00ff00"
            if kind_u == "TX" or line.startswith("[TX]"):
                return "#ff4d4d"
            return "#cfcfcf"

        html_lines = []
        for i, raw_line in enumerate(self.monitor_lines):
            safe_line = html.escape(raw_line)
            kind = self.monitor_line_kinds[i] if i < len(self.monitor_line_kinds) else ""
            color = _line_color(raw_line, kind)
            html_lines.append(f'<div style="color: {color};">{safe_line}</div>')

        monitor_html = '<div style="font-family: \'Courier New\'; font-size: 9pt;">' + "".join(html_lines) + "</div>"
        self.text_monitor.setHtml(monitor_html)

        # Keep viewport at top so newest entries remain immediately visible.
        self.text_monitor.verticalScrollBar().setValue(
            self.text_monitor.verticalScrollBar().minimum()
        )

    def _on_monitor_freeze_toggled(self, frozen: bool) -> None:
        """Freeze/unfreeze monitor updates while still buffering incoming frames."""
        self.monitor_frozen = bool(frozen)

        if not self.monitor_frozen:
            self._render_monitor_text()

    def _show_monitor_context_menu(self, pos) -> None:
        """Show monitor context menu with copy and full clear action."""
        menu = QMenu(self.text_monitor)

        copy_action = QAction("Copy", self.text_monitor)
        copy_action.setEnabled(self.text_monitor.textCursor().hasSelection())
        copy_action.triggered.connect(self.text_monitor.copy)
        menu.addAction(copy_action)

        menu.addSeparator()

        clear_action = QAction("Clear all", self.text_monitor)
        clear_action.triggered.connect(self._clear_monitor_all)
        menu.addAction(clear_action)

        menu.exec(self.text_monitor.mapToGlobal(pos))

    def _clear_monitor_all(self) -> None:
        """Clear monitor UI and in-memory monitor cache."""
        self.text_monitor.clear()
        self.monitor_lines.clear()
        self.monitor_line_kinds.clear()
        self.last_monitor_line = ""
    
    def populate_devices(self):
        """Populate device and port combo boxes"""
        try:
            device_list_snapshot = self._query_devices_snapshot()

            # Get audio INPUT devices (microphones, line-in)
            input_devices = self.get_input_devices(device_list_snapshot)
            self.combo_input.blockSignals(True)  # Prevent callback during clear/add
            self.combo_input.clear()
            self.combo_input.addItem(self._t("select_mic"), None)
            for dev in input_devices:
                display_name = f"{dev['name']} ({dev['channels']}ch)"
                self.combo_input.addItem(display_name, dev["id"])
                logger.debug(f"[DEVICES] Audio INPUT: {display_name}")
            self.combo_input.blockSignals(False)  # Re-enable callback
            logger.info(f"[DEVICES] Found {len(input_devices)} audio INPUT devices")
            
            # Get audio OUTPUT devices (speakers, line-out, headphones)
            output_devices = self.get_output_devices(device_list_snapshot)
            self.combo_output.blockSignals(True)  # Prevent callback during clear/add
            self.combo_output.clear()
            self.combo_output.addItem(self._t("select_speaker"), None)
            for dev in output_devices:
                display_name = f"{dev['name']} ({dev['channels']}ch)"
                self.combo_output.addItem(display_name, dev["id"])
                logger.debug(f"[DEVICES] Audio OUTPUT: {display_name}")
            self.combo_output.blockSignals(False)  # Re-enable callback
            logger.info(f"[DEVICES] Found {len(output_devices)} audio OUTPUT devices")
            
            # Get serial ports for PTT
            serial_ports = self.get_serial_ports()
            self.combo_ppt.blockSignals(True)  # Prevent callback during clear/add
            self.combo_ppt.clear()
            self.combo_ppt.addItem(self._t("select_mode"), None)
            self.combo_ppt.addItem("RIG", "RIG")
            self.combo_ppt.addItem("DTR", "DTR")
            self.combo_ppt.addItem("RTS", "RTS")
            self.combo_ppt.addItem("VOX", "VOX")
            self.combo_ppt.blockSignals(False)  # Re-enable callback

            if hasattr(self, "combo_ptt_port"):
                self.combo_ptt_port.blockSignals(True)
                self.combo_ptt_port.clear()
                self.combo_ptt_port.addItem(self._t("select_com"), None)
                for port in serial_ports:
                    self.combo_ptt_port.addItem(port, port)
                self.combo_ptt_port.blockSignals(False)
            if hasattr(self, "combo_cat_serial_port"):
                self.combo_cat_serial_port.blockSignals(True)
                self.combo_cat_serial_port.clear()
                self.combo_cat_serial_port.addItem(self._t("select_com"), None)
                for port in serial_ports:
                    self.combo_cat_serial_port.addItem(port, port)
                self.combo_cat_serial_port.blockSignals(False)
            logger.info(f"[DEVICES] Found {len(serial_ports)} COM ports")
            
        except Exception as e:
            logger.error(f"[DEVICES] Error populating devices: {e}")

    def _query_devices_snapshot(self):
        """Query device list once for a single UI refresh/action cycle."""
        try:
            return sounddevice.query_devices()
        except Exception as e:
            logger.warning(f"[DEVICES] Error querying audio devices: {e}")
            return []

    def _device_info_from_list(self, device_id: int, device_list=None):
        """Best-effort device info lookup from an existing snapshot list."""
        if device_list is None:
            return None
        try:
            if isinstance(device_list, dict):
                return device_list if device_id == 0 else None
            if isinstance(device_list, list) and 0 <= int(device_id) < len(device_list):
                return device_list[int(device_id)]
        except Exception:
            return None
        return None
    
    def restore_device_selection(self):
        """Restore saved device selections from config.json"""
        try:
            # Restore INPUT device
            saved_input = self.config.get("audio.input_device", None)
            saved_input_id = self.config.get("audio.input_device_id", None)
            found_input = False
            if isinstance(saved_input_id, int):
                for i in range(self.combo_input.count()):
                    if self.combo_input.itemData(i) == saved_input_id:
                        self.combo_input.setCurrentIndex(i)
                        logger.info(f"[CONFIG] Restored INPUT device by ID: {saved_input_id}")
                        found_input = True
                        break
            if saved_input and not found_input:
                for i in range(self.combo_input.count()):
                    item_id = self.combo_input.itemData(i)
                    txt = self.combo_input.itemText(i)
                    raw_name = self._device_name_from_id(int(item_id)) if isinstance(item_id, int) else ""
                    if raw_name == saved_input or txt.startswith(f"{saved_input} ("):
                        self.combo_input.setCurrentIndex(i)
                        logger.info(f"[CONFIG] Restored INPUT device by name: {saved_input}")
                        found_input = True
                        break
            
            # If no saved or not found, select first available (skip placeholder)
            if not found_input and self.combo_input.count() > 1:
                self.combo_input.setCurrentIndex(1)
                logger.info(f"[CONFIG] Auto-selected first INPUT device: {self.combo_input.itemData(1)}")
            
            # Restore OUTPUT device
            saved_output = self.config.get("audio.output_device", None)
            saved_output_id = self.config.get("audio.output_device_id", None)
            found_output = False
            if isinstance(saved_output_id, int):
                for i in range(self.combo_output.count()):
                    if self.combo_output.itemData(i) == saved_output_id:
                        self.combo_output.setCurrentIndex(i)
                        logger.info(f"[CONFIG] Restored OUTPUT device by ID: {saved_output_id}")
                        found_output = True
                        break
            if saved_output and not found_output:
                for i in range(self.combo_output.count()):
                    item_id = self.combo_output.itemData(i)
                    txt = self.combo_output.itemText(i)
                    raw_name = self._device_name_from_id(int(item_id)) if isinstance(item_id, int) else ""
                    if raw_name == saved_output or txt.startswith(f"{saved_output} ("):
                        self.combo_output.setCurrentIndex(i)
                        logger.info(f"[CONFIG] Restored OUTPUT device by name: {saved_output}")
                        found_output = True
                        break
            
            # If no saved or not found, select first available (skip placeholder)
            if not found_output and self.combo_output.count() > 1:
                self.combo_output.setCurrentIndex(1)
                logger.info(f"[CONFIG] Auto-selected first OUTPUT device: {self.combo_output.itemData(1)}")
            
            # Restore Sample Rate
            saved_sample_rate = self.config.get("audio.sample_rate", "44100")
            sr_str = str(saved_sample_rate)
            idx = self.combo_sample_rate.findText(sr_str)
            if idx >= 0:
                self.combo_sample_rate.blockSignals(True)
                self.combo_sample_rate.setCurrentIndex(idx)
                self.combo_sample_rate.blockSignals(False)
                logger.info(f"[CONFIG] Restored sample rate: {sr_str} Hz")
            else:
                logger.warning(f"[CONFIG] Saved sample rate {sr_str} Hz not in combo options")
            
            # Restore PTT type
            saved_ppt_mode = self.config.get("ptt.ptt_type", self._normalize_ptt_type(self.config.get("ppt.mode", "VOX")))
            if saved_ppt_mode and saved_ppt_mode != "disabled":
                for i in range(self.combo_ppt.count()):
                    if str(self.combo_ppt.itemData(i) or "").upper() == str(saved_ppt_mode).upper():
                        self.combo_ppt.setCurrentIndex(i)
                        logger.info(f"[CONFIG] Restored PTT type: {saved_ppt_mode}")
                        break

            # Restore serial ptt_path
            if hasattr(self, "combo_ptt_port"):
                saved_ptt_port = str(self.config.get("ptt.path", self.ptt_port) or "")
                if saved_ptt_port:
                    for i in range(self.combo_ptt_port.count()):
                        if self.combo_ptt_port.itemData(i) == saved_ptt_port:
                            self.combo_ptt_port.setCurrentIndex(i)
                            logger.info(f"[CONFIG] Restored ptt_path: {saved_ptt_port}")
                            break

            # Restore CAT transport (RIG mode)
            saved_rig_conn = self._normalize_rig_connection(self.config.get("ptt.rig_connection", self.rig_connection))
            self.rig_connection = saved_rig_conn
            if hasattr(self, "combo_rig_connection"):
                self._set_combo_by_data(self.combo_rig_connection, saved_rig_conn)

            saved_cat_serial_port = str(self.config.get("ptt.rig_serial_path", self.cat_serial_port) or "")
            self.cat_serial_port = saved_cat_serial_port
            if saved_cat_serial_port and hasattr(self, "combo_cat_serial_port"):
                self._set_combo_by_data(self.combo_cat_serial_port, saved_cat_serial_port)

            try:
                self.cat_serial_baud = int(self.config.get("ptt.rig_serial_baud", self.cat_serial_baud))
            except Exception:
                pass
            if hasattr(self, "spin_cat_serial_baud"):
                self.spin_cat_serial_baud.setValue(int(self.cat_serial_baud))

            self._update_ptt_mode_controls(self.ptt_type)
        
        except Exception as e:
            logger.debug(f"[CONFIG] Could not restore device selection: {e}")
    
    def get_input_devices(self, device_list=None) -> list:
        """Get list of audio INPUT devices with their stable sounddevice IDs."""
        devices = []
        try:
            if device_list is None:
                device_list = self._query_devices_snapshot()
            if isinstance(device_list, dict):
                max_ch = int(device_list.get("max_input_channels", 0) or 0)
                if max_ch > 0:
                    devices.append(
                        {
                            "id": 0,
                            "name": str(device_list.get("name", "Unknown") or "Unknown").strip(),
                            "channels": max_ch,
                        }
                    )
            else:
                for idx, device in enumerate(device_list):
                    try:
                        if isinstance(device, dict):
                            max_ch = int(device.get("max_input_channels", 0) or 0)
                            name = str(device.get("name", "Unknown") or "Unknown").strip()
                        else:
                            max_ch = int(getattr(device, "max_input_channels", 0) or 0)
                            name = str(getattr(device, "name", "Unknown") or "Unknown").strip()

                        if max_ch > 0:
                            devices.append({"id": idx, "name": name, "channels": max_ch})
                            logger.debug(f"[DEVICES] INPUT device {idx}: {name}")
                    except Exception as dev_err:
                        logger.debug(f"[DEVICES] Error processing INPUT device {idx}: {dev_err}")
        except Exception as e:
            logger.warning(f"[DEVICES] Error processing input devices: {e}")
        return devices
    
    def get_output_devices(self, device_list=None) -> list:
        """Get list of audio OUTPUT devices with their stable sounddevice IDs."""
        devices = []
        try:
            if device_list is None:
                device_list = self._query_devices_snapshot()
            if isinstance(device_list, dict):
                max_ch = int(device_list.get("max_output_channels", 0) or 0)
                if max_ch > 0:
                    devices.append(
                        {
                            "id": 0,
                            "name": str(device_list.get("name", "Unknown") or "Unknown").strip(),
                            "channels": max_ch,
                        }
                    )
            else:
                for idx, device in enumerate(device_list):
                    try:
                        if isinstance(device, dict):
                            max_ch = int(device.get("max_output_channels", 0) or 0)
                            name = str(device.get("name", "Unknown") or "Unknown").strip()
                        else:
                            max_ch = int(getattr(device, "max_output_channels", 0) or 0)
                            name = str(getattr(device, "name", "Unknown") or "Unknown").strip()

                        if max_ch > 0:
                            devices.append({"id": idx, "name": name, "channels": max_ch})
                            logger.debug(f"[DEVICES] OUTPUT device {idx}: {name}")
                    except Exception as dev_err:
                        logger.debug(f"[DEVICES] Error processing OUTPUT device {idx}: {dev_err}")
        except Exception as e:
            logger.warning(f"[DEVICES] Error processing output devices: {e}")
        return devices

    def _normalize_device_name(self, name: str) -> str:
        """Normalize endpoint name for stable deduplication."""
        if not name:
            return ""
        normalized = name.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _base_endpoint_name(self, name: str) -> str:
        """Return endpoint base name (part before adapter in brackets)."""
        if not name:
            return ""
        base = name.split("(", 1)[0].strip()
        return base or name.strip()

    def _extract_endpoint_parts(self, name: str) -> tuple:
        """Split endpoint into (base, adapter) from 'Base (Adapter)' format."""
        if not name:
            return "", ""
        m = re.match(r"^\s*(.*?)\s*\((.*?)\)\s*$", name)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return name.strip(), ""

    def _display_endpoint_name(self, raw_name: str) -> str:
        """Format endpoint label close to Windows panel style."""
        base, adapter = self._extract_endpoint_parts(raw_name)
        if base and adapter:
            return f"{base} - {adapter}"
        return raw_name.strip() or "Unknown"

    def _hostapi_rank(self, hostapi_name: str) -> int:
        """Prefer modern Windows backends in UI deduplication."""
        host = (hostapi_name or "").lower()
        if "wasapi" in host:
            return 4
        if "wdm" in host or "ks" in host:
            return 3
        if "mme" in host:
            return 2
        if "directsound" in host:
            return 1
        return 0

    def _is_generic_windows_alias(self, device_name: str) -> bool:
        """Filter out generic aliases typically hidden in Windows apps."""
        normalized = self._normalize_device_name(device_name)
        return any(token in normalized for token in GENERIC_WINDOWS_DEVICE_TOKENS)

    def _device_variant_penalty(self, device_name: str) -> int:
        """Lower penalty means more user-facing/typical endpoint naming."""
        n = self._normalize_device_name(device_name)
        penalty = 0
        if "point" in n:
            penalty += 2
        if "mapper" in n or "primary" in n:
            penalty += 3
        base, _adapter = self._extract_endpoint_parts(device_name)
        if self._normalize_device_name(base) in GENERIC_ENDPOINT_BASES:
            penalty += 1
        return penalty

    def _should_hide_as_alias(self, candidate: dict, all_candidates: list) -> bool:
        """Hide technical aliases when clearer sibling endpoint exists."""
        raw = candidate.get("raw_name", candidate.get("name", ""))
        base, adapter = self._extract_endpoint_parts(raw)
        base_n = self._normalize_device_name(base)
        adapter_n = self._normalize_device_name(adapter)

        # Hide VB-Audio Point variants when Virtual Cable endpoint is available.
        if "vb-audio point" in adapter_n:
            for other in all_candidates:
                if other is candidate:
                    continue
                o_raw = other.get("raw_name", other.get("name", ""))
                _ob, oa = self._extract_endpoint_parts(o_raw)
                if "vb-audio virtual cable" in self._normalize_device_name(oa):
                    return True

        # Hide very generic endpoint names when same adapter has a clearer label.
        if base_n in GENERIC_ENDPOINT_BASES and adapter_n:
            for other in all_candidates:
                if other is candidate:
                    continue
                o_raw = other.get("raw_name", other.get("name", ""))
                ob, oa = self._extract_endpoint_parts(o_raw)
                if self._normalize_device_name(oa) == adapter_n and self._normalize_device_name(ob) not in GENERIC_ENDPOINT_BASES:
                    return True

        return False

    def _get_filtered_audio_devices(self, direction: str) -> list:
        """
        Return deduplicated endpoint list:
        [{"id": int, "name": str, "channels": int, "hostapi": str}, ...]
        """
        result = []
        try:
            device_list = sounddevice.query_devices()
            hostapis = sounddevice.query_hostapis()
            is_input = direction == "input"
            max_key = "max_input_channels" if is_input else "max_output_channels"

            if isinstance(device_list, dict):
                device_list = [device_list]

            candidates = []
            for idx, device in enumerate(device_list):
                if isinstance(device, dict):
                    channels = int(device.get(max_key, 0) or 0)
                    name = str(device.get("name", "Unknown") or "Unknown").strip()
                    hostapi_idx = int(device.get("hostapi", -1) or -1)
                else:
                    channels = int(getattr(device, max_key, 0) or 0)
                    name = str(getattr(device, "name", "Unknown") or "Unknown").strip()
                    hostapi_idx = int(getattr(device, "hostapi", -1) or -1)

                if channels <= 0 or self._is_generic_windows_alias(name):
                    continue

                hostapi_name = "unknown"
                if isinstance(hostapis, list) and 0 <= hostapi_idx < len(hostapis):
                    api = hostapis[hostapi_idx]
                    hostapi_name = str(api.get("name", "unknown") if isinstance(api, dict) else getattr(api, "name", "unknown"))

                candidate = {
                    "id": idx,
                    "name": name,
                    "raw_name": name,
                    "channels": channels,
                    "hostapi": hostapi_name,
                }
                candidates.append(candidate)

            filtered_candidates = [c for c in candidates if not self._should_hide_as_alias(c, candidates)]

            best_by_name = {}
            for candidate in filtered_candidates:
                key = self._normalize_device_name(candidate.get("raw_name", candidate["name"]))

                current = best_by_name.get(key)
                if current is None:
                    best_by_name[key] = candidate
                else:
                    cur_rank = self._hostapi_rank(current["hostapi"])
                    new_rank = self._hostapi_rank(candidate["hostapi"])
                    cur_penalty = self._device_variant_penalty(current.get("raw_name", current["name"]))
                    new_penalty = self._device_variant_penalty(candidate.get("raw_name", candidate["name"]))
                    if (
                        new_rank > cur_rank
                        or (new_rank == cur_rank and new_penalty < cur_penalty)
                        or (new_rank == cur_rank and new_penalty == cur_penalty and candidate["channels"] > current["channels"])
                    ):
                        best_by_name[key] = candidate

            result = sorted(best_by_name.values(), key=lambda d: d["name"].lower())

            for dev in result:
                logger.debug(
                    f"[DEVICES] {direction.upper()} endpoint: {dev['name']} [{dev.get('raw_name', dev['name'])}] ({dev['channels']}ch, {dev['hostapi']}, id={dev['id']})"
                )
        except Exception as e:
            logger.warning(f"[DEVICES] Error filtering {direction} devices: {e}")

        return result
    
    def get_audio_devices(self) -> list:
        """DEPRECATED: Get list of audio input/output device names"""
        devices = []
        try:
            device_list = sounddevice.query_devices()
            if isinstance(device_list, dict):
                # Single device
                devices.append(device_list.get('name', 'Unknown'))
            else:
                # Multiple devices - filter to avoid duplicates
                seen = set()
                for device in device_list:
                    name = device.get('name', 'Unknown').strip()
                    # Avoid adding the same device name multiple times
                    if name not in seen:
                        devices.append(name)
                        seen.add(name)
        except Exception as e:
            logger.warning(f"[DEVICES] Error querying audio devices: {e}")
        return devices
    
    def refresh_input_devices(self):
        """Refresh INPUT devices list (called by Refresh button)"""
        logger.info("[DEVICES] Refreshing INPUT devices list...")
        self.populate_devices()
        self._update_monitor_config_summary()
        logger.info("[DEVICES] INPUT devices list refreshed")
        QMessageBox.information(self, "Refresh Complete", "Input devices list has been refreshed!")
    
    def refresh_output_devices(self):
        """Refresh OUTPUT devices list (called by Refresh button)"""
        logger.info("[DEVICES] Refreshing OUTPUT devices list...")
        self.populate_devices()
        self._update_monitor_config_summary()
        logger.info("[DEVICES] OUTPUT devices list refreshed")
        QMessageBox.information(self, "Refresh Complete", "Output devices list has been refreshed!")
    
    def on_input_device_changed(self, index: int):
        """Callback when input device selection changes"""
        if self._audio_switch_in_progress:
            return

        if index < 0:
            return

        self._audio_switch_in_progress = True
        try:
            device_id = self.combo_input.itemData(index)
            if device_id is None:
                logger.debug("[AUDIO] Input device selection cleared")
                return

            device_name = self._device_name_from_id(int(device_id))
            if not device_name:
                device_name = self.combo_input.itemText(index).rsplit(" (", 1)[0]

            logger.info(f"[AUDIO] Input device changed to: {device_name} (id={device_id})")
            self.config.set("audio.input_device_id", int(device_id))
            self.config.set("audio.input_device", device_name)
            self.config.save()

            # Restart audio input stream with new device
            self.stop_audio_monitoring()
            self.start_audio_monitoring()
        except Exception as e:
            logger.error(f"[AUDIO] Input device switch failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Audio INPUT", f"Could not switch input device:\n{e}")
        finally:
            self._audio_switch_in_progress = False
            self._update_monitor_config_summary()
    
    def on_output_device_changed(self, index: int):
        """Callback when output device selection changes"""
        if self._audio_switch_in_progress:
            return

        if index < 0:
            return

        self._audio_switch_in_progress = True
        try:
            device_id = self.combo_output.itemData(index)
            if device_id is None:
                logger.debug("[AUDIO] Output device selection cleared")
                return

            device_name = self._device_name_from_id(int(device_id))
            if not device_name:
                device_name = self.combo_output.itemText(index).rsplit(" (", 1)[0]

            logger.info(f"[AUDIO] Output device changed to: {device_name} (id={device_id})")

            # Stop tone generator before closing stream to avoid callback writes to stale stream.
            logger.info("[AUDIO] Stopping tone generator before device switch...")
            try:
                self.tone_gen.stop_continuous()
            except Exception as tone_err:
                logger.debug(f"[AUDIO] Error stopping tone generator: {tone_err}")

            self.config.set("audio.output_device_id", int(device_id))
            self.config.set("audio.output_device", device_name)
            self.config.save()

            # Restart audio output stream with new device
            self.stop_audio_output()
            self.start_audio_output()
        except Exception as e:
            logger.error(f"[AUDIO] Output device switch failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Audio OUTPUT", f"Could not switch output device:\n{e}")
        finally:
            self._audio_switch_in_progress = False
            self._update_monitor_config_summary()
    
    def on_sample_rate_changed(self, index: int):
        """Callback when sample rate selection changes"""
        if self._audio_switch_in_progress:
            return

        if index < 0:
            return

        self._audio_switch_in_progress = True
        try:
            sample_rate_str = self.combo_sample_rate.currentText()
            sample_rate = int(sample_rate_str)
            logger.info(f"[AUDIO] Sample rate changed to: {sample_rate} Hz")
            self.config.set("audio.sample_rate", sample_rate)
            self.config.save()

            # Restart audio streams with new sample rate
            self.stop_audio_monitoring()
            self.stop_audio_output()
            self.start_audio_monitoring()
            self.start_audio_output()
        except ValueError:
            logger.warning(f"[AUDIO] Invalid sample rate: {sample_rate_str}")
        except Exception as e:
            logger.error(f"[AUDIO] Sample rate switch failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Sample Rate", f"Could not apply sample rate:\n{e}")
        finally:
            self._audio_switch_in_progress = False
    
    def get_serial_ports(self) -> list:
        """Get list of available COM ports"""
        ports = []
        try:
            port_list = serial.tools.list_ports.comports()
            for port in port_list:
                ports.append(port.device)
        except Exception as e:
            logger.warning(f"[DEVICES] Error querying COM ports: {e}")
        return ports
    
    def save_geometry(self):
        """Save window geometry to config"""
        geom = self.geometry()
        self.config.set("ui.geometry", [geom.x(), geom.y(), geom.width(), geom.height()])
        self.config.save()
    
    def restore_geometry(self):
        """Restore window geometry from config"""
        geom_list = self.config.get("ui.geometry", None)
        if isinstance(geom_list, list) and len(geom_list) == 4:
            self.setGeometry(geom_list[0], geom_list[1], geom_list[2], geom_list[3])
    
    def closeEvent(self, event):
        """Handle application close - hide to tray instead of closing"""
        # On Windows, behavior is user-configurable and persisted in config.
        if self.close_to_tray_enabled and self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            # If tray is not available, perform actual shutdown
            self._perform_shutdown()
            event.accept()
    
    def changeEvent(self, event):
        """Handle window state changes"""
        # Standard minimize behavior - don't intercept, let it minimize to taskbar normally
        super().changeEvent(event)
    
    def _perform_shutdown(self):
        """Actually close and shutdown the application"""
        try:
            logger.info("[APP] Shutting down...")
            
            # Stop all background operations
            self.tone_gen.stop_continuous()
            self.active_tone_button = None
            self.stop_audio_monitoring()
            self.stop_audio_output()
            self.system_volume_monitor.stop_monitoring()
            self._stop_web_ui()
            self.kiss_server.stop()
            self.meter_update_timer.stop()
            
            # Close serial port if open
            if self.ppt_serial is not None:
                try:
                    self.ppt_serial.close()
                except:
                    pass
            
            # Save configuration
            self.save_geometry()
            
            logger.info("[APP] Application closed")
        except Exception as e:
            logger.error(f"[APP] Error during shutdown: {e}")
        finally:
            app = QApplication.instance()
            if app is not None:
                app.quit()
            else:
                sys.exit(0)
    
    def setup_system_tray(self):
        """Setup system tray icon with minimize/restore functionality"""
        try:
            # Create tray icon
            self.tray_icon = QSystemTrayIcon(self)
            
            # Always prefer custom app icon for tray; fallback to window/system icon.
            if self.app_icon and not self.app_icon.isNull():
                self.tray_icon.setIcon(self.app_icon)
            else:
                icon = self.windowIcon()
                if icon and not icon.isNull():
                    self.tray_icon.setIcon(icon)
                else:
                    self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
            
            # Create tray menu
            tray_menu = QMenu(self)
            
            # Show/Restore action
            show_action = tray_menu.addAction("Show/Restore")
            show_action.triggered.connect(self.show_restore_window)
            
            tray_menu.addSeparator()
            
            # Exit action
            exit_action = tray_menu.addAction("Exit MicroKISStnc")
            exit_action.triggered.connect(self.exit_app)
            
            # Set the menu
            self.tray_icon.setContextMenu(tray_menu)
            
            # Connect double-click to restore
            self.tray_icon.activated.connect(self.on_tray_icon_activated)
            
            # Show tray icon
            self.tray_icon.show()
            
            logger.info("[APP] System tray icon initialized")
        except Exception as e:
            logger.warning(f"[APP] Failed to setup system tray: {e}")
            self.tray_icon = None
    
    def on_tray_icon_activated(self, reason):
        """Handle tray icon activation (click/double-click)"""
        from PyQt6.QtWidgets import QSystemTrayIcon
        
        # Show/restore on double-click or middle-click
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, 
                      QSystemTrayIcon.ActivationReason.MiddleClick):
            self.show_restore_window()
    
    def show_restore_window(self):
        """Show and restore the application window"""
        self.show()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
    
    def exit_app(self):
        """Exit application from tray menu"""
        logger.info("[APP] Exit requested from system tray")
        self._perform_shutdown()
    
    def start_audio_monitoring(self):
        """Start audio input monitoring stream"""
        try:
            # Ensure only one input stream is active.
            if self.audio_stream_in is not None:
                self.stop_audio_monitoring()

            sample_rate = self.config.get("audio.sample_rate", 44100)
            device_list_snapshot = self._query_devices_snapshot()
            device_id = self.get_default_input_device(device_list_snapshot)
            logger.info(f"[AUDIO] Starting input stream: device={device_id}, requested_rate={sample_rate}Hz")

            # Build fallback list: selected first, then other input devices.
            device_ids_to_try = []
            if device_id is not None:
                device_ids_to_try.append(device_id)
            try:
                for dev in self.get_input_devices(device_list_snapshot):
                    did = dev.get("id")
                    if isinstance(did, int) and did not in device_ids_to_try:
                        device_ids_to_try.append(did)
            except Exception as e:
                logger.debug(f"[AUDIO] Could not get input fallback devices: {e}")

            started = False
            for attempt_device_id in device_ids_to_try:
                try:
                    self.audio_stream_in = sounddevice.InputStream(
                        device=attempt_device_id,
                        samplerate=sample_rate,
                        channels=1,
                        blocksize=self.audio_chunk_size,
                        callback=self.audio_input_callback,
                        dtype=np.float32
                    )
                    self.audio_stream_in.start()
                    self.actual_input_sample_rate = int(self.audio_stream_in.samplerate)
                    logger.info(f"[AUDIO] Input stream started (device={attempt_device_id}, rate={sample_rate}Hz)")
                    logger.info(f"[AUDIO]   - Actual input sample rate: {self.actual_input_sample_rate} Hz")
                    logger.info(f"[AUDIO]   - Stream vs Device rate match: {self.actual_input_sample_rate == sample_rate}")

                    # Persist fallback input device if selected one failed.
                    if attempt_device_id != device_id and device_id is not None:
                        try:
                            fallback_name = self._device_name_from_id(int(attempt_device_id))
                            self.config.set("audio.input_device_id", int(attempt_device_id))
                            if fallback_name:
                                self.config.set("audio.input_device", fallback_name)
                            self.config.save()
                            logger.info(f"[AUDIO] Saved fallback input device to config: id={attempt_device_id}")
                        except Exception as save_err:
                            logger.warning(f"[AUDIO] Could not save fallback input device: {save_err}")

                    # Reinitialize RX pipeline with actual device sample rate.
                    with self.rx_pipeline_lock:
                        if self.rx_pipeline is None or self.rx_pipeline.sample_rate != self.actual_input_sample_rate:
                            logger.info(f"[RX] Reinitializing demodulator: {self.rx_pipeline.sample_rate if self.rx_pipeline else 'None'} Hz â†’ {self.actual_input_sample_rate} Hz")
                            self.rx_pipeline = RXPipeline(
                                sample_rate=self.actual_input_sample_rate,
                                on_frame_decoded=self.on_rx_frame_decoded,
                                require_fcs=True,
                                use_bandpass=True,
                                rms_gate=0.003,
                            )
                            logger.info(f"[RX] RX pipeline now uses {self.actual_input_sample_rate} Hz (prevents frequency shift)")

                    self._start_rx_worker()
                    started = True
                    break
                except Exception as dev_err:
                    logger.warning(f"[AUDIO] Input device {attempt_device_id} failed: {dev_err}")
                    if self.audio_stream_in is not None:
                        try:
                            self.audio_stream_in.close()
                        except Exception:
                            pass
                        self.audio_stream_in = None

            if not started:
                logger.warning("[AUDIO] Could not start input stream on any available device")
        except Exception as e:
            logger.warning(f"[AUDIO] Could not start input stream: {e}")
    
    def stop_audio_monitoring(self):
        """Stop audio input monitoring stream"""
        self._stop_rx_worker()

        if self.audio_stream_in is not None:
            try:
                self.audio_stream_in.stop()
                self.audio_stream_in.close()
                self.audio_stream_in = None
                logger.info("[AUDIO] Input stream stopped")
            except Exception as e:
                logger.warning(f"[AUDIO] Error stopping input stream: {e}")

    def _start_rx_worker(self):
        """Start background RX worker thread if not running."""
        if self.rx_worker_running:
            return

        self.rx_worker_running = True
        self.rx_worker_thread = threading.Thread(target=self._rx_worker_loop, daemon=True)
        self.rx_worker_thread.start()
        logger.info("[RX] Worker thread started")

    def _stop_rx_worker(self):
        """Stop background RX worker thread and clear pending blocks."""
        if not self.rx_worker_running:
            return

        self.rx_worker_running = False
        try:
            self.rx_audio_queue.put_nowait(None)
        except queue.Full:
            pass

        if self.rx_worker_thread and self.rx_worker_thread.is_alive():
            self.rx_worker_thread.join(timeout=1.0)

        self.rx_worker_thread = None

        while not self.rx_audio_queue.empty():
            try:
                self.rx_audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("[RX] Worker thread stopped")

    def _rx_worker_loop(self):
        """Consume audio chunks and run heavy DSP outside callback context."""
        while self.rx_worker_running:
            try:
                audio_samples = self.rx_audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if audio_samples is None:
                continue

            try:
                with self.rx_pipeline_lock:
                    pipeline = self.rx_pipeline
                if pipeline is not None:
                    pipeline.process_audio(audio_samples)
            except Exception as e:
                logger.error(f"[RX] Worker processing error: {e}", exc_info=True)
    
    def audio_input_callback(self, indata, frames, time, status):
        """Callback for audio input stream"""
        try:
            if status:
                logger.warning(f"[AUDIO] Stream status: {status}")
            
            # Send samples to monitor
            audio_samples = indata[:, 0].flatten()  # Get first channel
            
            # Debug: log every 100 calls to avoid spam
            self.audio_callback_count = getattr(self, 'audio_callback_count', 0) + 1
            if self.audio_callback_count % 100 == 0:
                logger.debug(f"[AUDIO] RX Callback executing (call #{self.audio_callback_count}), samples={len(audio_samples)}")
            
            # Update monitor (safe for thread)
            try:
                self.audio_monitor_in.update(audio_samples)
            except Exception as e:
                logger.debug(f"[AUDIO] Monitor update error: {e}")
            
            # Feed DSP worker queue (keep callback fast to avoid dropouts)
            try:
                block = np.copy(audio_samples)
                try:
                    self.rx_audio_queue.put_nowait(block)
                except queue.Full:
                    # Drop oldest buffered block and enqueue latest.
                    try:
                        self.rx_audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.rx_audio_queue.put_nowait(block)
            except Exception as e:
                logger.error(f"[AUDIO] RX queue error: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"[AUDIO] Input callback error: {e}", exc_info=True)
    
    def get_default_input_device(self, device_list=None):
        """Get device ID of selected audio input device"""
        selected = self.combo_input.currentData()
        if selected is None:
            # Try to get default input device
            try:
                return sounddevice.default.device[0]
            except:
                return None

        if isinstance(selected, int):
            return selected
        
        # Find device by name
        device_id = self._find_device_id_by_name(selected, device_list=device_list)
        if device_id is not None:
            logger.info(f"[AUDIO] Found input device '{selected}' at ID {device_id}")
        else:
            logger.warning(f"[AUDIO] Input device '{selected}' not found, using default")
        return device_id
    
    def start_audio_output(self):
        """Start audio output stream for test tone generation with fallback device selection"""
        try:
            logger.info("[AUDIO] Attempting to start output stream...")
            if self.audio_stream_out is not None:
                logger.info("[AUDIO] Output stream already running")
                return  # Already running
            
            # Get sample rate from combo if available, otherwise from config
            try:
                sr_str = self.combo_sample_rate.currentText()
                sample_rate = int(sr_str) if sr_str else self.config.get("audio.sample_rate", 44100)
            except:
                sample_rate = self.config.get("audio.sample_rate", 44100)
            
            device_list_snapshot = self._query_devices_snapshot()
            device_id = self.get_default_output_device(device_list_snapshot)
            logger.info(f"[AUDIO] Requested sample_rate: {sample_rate}, Primary output device ID: {device_id}")
            
            # Try to open stream with primary device, if fails use fallback
            device_ids_to_try = []
            if device_id is not None:
                device_ids_to_try.append(device_id)
            
            # Add fallback devices from available output devices
            try:
                available_devices = self.get_output_devices(device_list_snapshot)
                for dev in available_devices:
                    dev_id = dev["id"]
                    if dev_id not in device_ids_to_try:
                        device_ids_to_try.append(dev_id)
            except Exception as e:
                logger.debug(f"[AUDIO] Could not get fallback devices: {e}")

            # Prefer fallback devices that are similar to the selected endpoint (radio path),
            # and push generic/system outputs to the end.
            generic_alias_names = (
                "mapowanie dĹşwiÄ™ku microsoft - output",
                "microsoft sound mapper - output",
            )
            device_name_cache = {}
            if isinstance(device_list_snapshot, dict):
                device_name_cache[0] = str(device_list_snapshot.get("name", "") or "").strip().lower()
            else:
                for idx, device in enumerate(device_list_snapshot):
                    if isinstance(device, dict):
                        raw_name = device.get("name", "")
                    else:
                        raw_name = getattr(device, "name", "")
                    device_name_cache[idx] = str(raw_name or "").strip().lower()
            primary_name = ""
            if device_id is not None:
                try:
                    primary_name = device_name_cache.get(device_id, "")
                    if not primary_name:
                        primary_info = sounddevice.query_devices(device_id)
                        primary_name = str(primary_info.get("name", "") if isinstance(primary_info, dict) else getattr(primary_info, "name", "") or "").strip().lower()
                except Exception:
                    primary_name = ""

            def _name_tokens(raw_name: str) -> set:
                words = re.findall(r"[a-z0-9]+", (raw_name or "").lower())
                skip = {"audio", "device", "default", "high", "definition", "output", "input", "speaker", "speakers"}
                return {w for w in words if len(w) > 2 and w not in skip}

            primary_tokens = _name_tokens(primary_name)
            scored_ids = []
            for did in device_ids_to_try:
                score = 100
                try:
                    name = device_name_cache.get(did, "")
                    if not name:
                        info = sounddevice.query_devices(did)
                        name = str(info.get("name", "") if isinstance(info, dict) else getattr(info, "name", "") or "").strip().lower()
                except Exception:
                    name = ""

                if device_id is not None and did == device_id:
                    score -= 1000

                if any(alias in name for alias in generic_alias_names):
                    score += 1000

                # Keep USB PnP / VB-Audio families together when selected device belongs to one.
                if "usb pnp" in primary_name and "usb pnp" in name:
                    score -= 120
                if "vb-audio" in primary_name and "vb-audio" in name:
                    score -= 120

                overlap = len(primary_tokens.intersection(_name_tokens(name)))
                score -= overlap * 25

                # De-prioritize monitor/GPU outputs unless explicitly selected.
                if any(tag in name for tag in ("nvidia", "vg", "hdmi", "display")) and "usb pnp" in primary_name:
                    score += 200

                scored_ids.append((score, did))

            scored_ids.sort(key=lambda x: x[0])
            device_ids_to_try = [did for _, did in scored_ids]
            
            logger.info(f"[AUDIO] Will try output devices in order: {device_ids_to_try}")
            
            # Try each device until one works
            for attempt_device_id in device_ids_to_try:
                try:
                    success = self._try_open_output_stream(attempt_device_id, sample_rate)
                    if success:
                        # Update UI combo to reflect which device was actually selected
                        if attempt_device_id != device_id and device_id is not None:
                            logger.warning(f"[AUDIO] âš  Primary device {device_id} failed, switched to device {attempt_device_id}")
                            # Find and select the working device in combo
                            for i in range(self.combo_output.count()):
                                if self.combo_output.itemData(i) == attempt_device_id:
                                    self.combo_output.blockSignals(True)
                                    self.combo_output.setCurrentIndex(i)
                                    self.combo_output.blockSignals(False)
                                    break
                            # Persist fallback device to avoid selecting broken endpoint again on next startup.
                            try:
                                fallback_name = self._device_name_from_id(int(attempt_device_id), device_list=device_list_snapshot)
                                if not fallback_name:
                                    for i in range(self.combo_output.count()):
                                        if self.combo_output.itemData(i) == attempt_device_id:
                                            fallback_name = self.combo_output.itemText(i).rsplit(" (", 1)[0]
                                            break
                                self.config.set("audio.output_device_id", int(attempt_device_id))
                                if fallback_name:
                                    self.config.set("audio.output_device", fallback_name)
                                self.config.save()
                                logger.info(f"[AUDIO] Saved fallback output device to config: id={attempt_device_id}")
                            except Exception as save_err:
                                logger.warning(f"[AUDIO] Could not save fallback output device: {save_err}")
                        return
                except Exception as e:
                    logger.warning(f"[AUDIO] Device {attempt_device_id} failed: {e}")
                    continue
            
            logger.error("[AUDIO] âťŚ All output devices failed - no stream created")
        except Exception as e:
            logger.error(f"[AUDIO] Could not start output stream: {e}", exc_info=True)
    
    def _try_open_output_stream(self, device_id, sample_rate):
        """Attempt to open output stream on specific device. Returns True if successful."""
        try:
            # Get device info and name
            dev_info = sounddevice.query_devices(device_id)
            device_name = dev_info.get('name', '') if isinstance(dev_info, dict) else getattr(dev_info, 'name', '')
            logger.info(f"[AUDIO] Attempting device {device_id}: {device_name}")
            
            # WORKAROUND: VB-Audio Virtual Cable is known to only support 44100 Hz
            sample_rate_to_use = sample_rate
            name_lower = device_name.lower() if device_name else ""
            if "vb-audio" in name_lower and ("virtual" in name_lower or "cable" in name_lower):
                logger.warning(f"[AUDIO] Detected VB-Audio Virtual Cable - forcing 44100 Hz")
                sample_rate_to_use = 44100
            
            # Try opening a test stream to verify format is supported
            try:
                test_stream = sounddevice.OutputStream(
                    device=device_id,
                    samplerate=sample_rate_to_use,
                    channels=1,
                    blocksize=self.audio_chunk_size,
                    dtype=np.float32
                )
                test_stream.start()
                actual_tested_rate = int(test_stream.samplerate)
                test_stream.stop()
                test_stream.close()
                
                if actual_tested_rate != sample_rate_to_use:
                    logger.warning(f"[AUDIO] Device {device_id}: Requested {sample_rate_to_use} Hz â†’ actual {actual_tested_rate} Hz")
                    sample_rate_to_use = actual_tested_rate
                else:
                    logger.info(f"[AUDIO] Device {device_id} supports {sample_rate_to_use} Hz âś“")
            except Exception as e:
                logger.warning(f"[AUDIO] Could not verify sample rate for device {device_id}: {e}")
            
            # Create actual output stream
            logger.info(f"[AUDIO] Creating OutputStream (device={device_id}, rate={sample_rate_to_use}Hz)...")
            self.audio_stream_out = sounddevice.OutputStream(
                device=device_id,
                samplerate=sample_rate_to_use,
                channels=1,
                blocksize=self.audio_chunk_size,
                dtype=np.float32
            )
            self.audio_stream_out.start()
            
            # Query actual stream properties
            stream_samplerate = self.audio_stream_out.samplerate
            self.actual_output_sample_rate = int(stream_samplerate)
            logger.info(f"[AUDIO] âś“ Output stream created successfully")
            logger.info(f"[AUDIO]   Device: {device_name} (ID={device_id})")
            logger.info(f"[AUDIO]   Sample rate: {self.actual_output_sample_rate} Hz")
            logger.info(f"[AUDIO]   Channels: {self.audio_stream_out.channels}")
            
            # Update tone generator with actual sample rate
            self.tone_gen.set_sample_rate(self.actual_output_sample_rate)
            logger.info(f"[TONE] Tone generator updated to {self.actual_output_sample_rate} Hz")
            
            return True
        except Exception as e:
            logger.debug(f"[AUDIO] Failed to open device {device_id}: {str(e)[:100]}")
            # Cleanup if partial open happened
            if self.audio_stream_out is not None:
                try:
                    self.audio_stream_out.stop()
                    self.audio_stream_out.close()
                except:
                    pass
                self.audio_stream_out = None
            return False
    
    def stop_audio_output(self):
        """Stop audio output stream"""
        if self.audio_stream_out is not None:
            try:
                self.audio_stream_out.stop()
                self.audio_stream_out.close()
                self.audio_stream_out = None
                logger.info("[AUDIO] Output stream stopped")
            except Exception as e:
                logger.warning(f"[AUDIO] Error stopping output stream: {e}")
    
    def on_tone_audio_ready(self, audio_chunk):
        """Callback from test tone generator - send audio to output stream"""
        if self.audio_stream_out is not None:
            try:
                # Ensure audio is 2D array (n_samples, n_channels)
                if audio_chunk.ndim == 1:
                    audio_chunk = audio_chunk.reshape(-1, 1)

                # Update TX/output meter from the first channel.
                try:
                    self.audio_monitor_out.update(audio_chunk[:, 0].flatten())
                    self._last_output_meter_update_ts = time.time()
                except Exception as e:
                    logger.debug(f"[AUDIO] Output monitor update error: {e}")

                self.audio_stream_out.write(audio_chunk)
                logger.debug(f"[AUDIO] Wrote {audio_chunk.shape} to output stream")
            except Exception as e:
                logger.warning(f"[AUDIO] Error writing to output stream: {e}")
        else:
            logger.warning(f"[AUDIO] Output stream is None in callback!")
    
    def get_default_output_device(self, device_list=None):
        """Get device ID of selected audio output device"""
        selected = self.combo_output.currentData()
        if selected is None:
            # Try to get default output device
            try:
                return sounddevice.default.device[1]
            except:
                return None

        if isinstance(selected, int):
            return selected
        
        # Find device by name
        device_id = self._find_device_id_by_name(selected, device_list=device_list)
        if device_id is not None:
            logger.info(f"[AUDIO] Found output device '{selected}' at ID {device_id}")
            # Get device info
            try:
                dev_info = self._device_info_from_list(device_id, device_list)
                if dev_info is None:
                    dev_info = sounddevice.query_devices(device_id)
                default_sr = dev_info.get('default_samplerate', 'unknown') if isinstance(dev_info, dict) else getattr(dev_info, 'default_samplerate', 'unknown')
                logger.info(f"[AUDIO]   Device {device_id} default_samplerate: {default_sr} Hz")
            except Exception as e:
                logger.warning(f"[AUDIO]   Could not query device {device_id}: {e}")
        else:
            logger.warning(f"[AUDIO] Output device '{selected}' not found, using default")
        return device_id
    
    def _find_device_id_by_name(self, device_name: str, device_list=None) -> Optional[int]:
        """Find device ID by name (PARTIAL MATCH - not exact)"""
        try:
            if device_list is None:
                device_list = self._query_devices_snapshot()
            logger.debug(f"[AUDIO] Searching for device: '{device_name}'")
            
            if isinstance(device_list, dict):
                # Single device (rare)
                dev_name = device_list.get('name', '').strip()
                logger.debug(f"[AUDIO] Single device: {repr(dev_name)}")
                if device_name in dev_name:  # PARTIAL MATCH
                    return 0
            else:
                # Multiple devices - list of device objects/dicts
                for idx, device in enumerate(device_list):
                    try:
                        # Get device name - try attribute first (sounddevice object)
                        if hasattr(device, 'name'):
                            dev_name = getattr(device, 'name', '')
                        elif isinstance(device, dict):
                            dev_name = device.get('name', '')
                        else:
                            continue
                        
                        dev_name = str(dev_name).strip() if dev_name else ''
                        
                        # USE PARTIAL MATCH: if config.json has "GĹ‚oĹ›niki (High" it should match "GĹ‚oĹ›niki (High Definition Audio"
                        if device_name in dev_name:
                            logger.info(f"[AUDIO] Found device '{device_name}' â†’ actual: '{dev_name}' at ID {idx}")
                            return idx
                    except Exception as e:
                        logger.debug(f"[AUDIO] Error checking device {idx}: {e}")
                        continue
            
            logger.warning(f"[AUDIO] Device '{device_name}' not found in list")
        except Exception as e:
            logger.warning(f"[AUDIO] Error finding device '{device_name}': {e}")
        return None

    def _device_name_from_id(self, device_id: int, device_list=None) -> str:
        """Resolve full sounddevice endpoint name for a numeric device ID."""
        try:
            info = self._device_info_from_list(device_id, device_list)
            if info is None:
                info = sounddevice.query_devices(device_id)
            if isinstance(info, dict):
                return str(info.get("name", "") or "").strip()
            return str(getattr(info, "name", "") or "").strip()
        except Exception as e:
            logger.debug(f"[AUDIO] Could not resolve name for device id={device_id}: {e}")
            return ""
    
    def open_ptt_port(self, port_name: str):
        """Open serial port for PTT control"""
        try:
            self.close_ppt_port()  # Close existing port first
            self.ppt_serial = serial.Serial(
                port=port_name,
                baudrate=9600,
                timeout=0.1,
                rtscts=False,
                dsrdtr=False
            )
            self.ptt_port = port_name
            self._apply_serial_idle_for_mode()
            self._apply_line_overrides()
            if self.ptt_type in ("DTR", "RTS"):
                self.set_ppt(False)
            self._save_ptt_config()
            logger.info(f"[PTT] Opened serial port {port_name}")
        except Exception as e:
            logger.warning(f"[PTT] Could not open port {port_name}: {e}")

    def _hamlib_endpoint(self) -> tuple:
        """Return currently configured Hamlib endpoint as (host, port)."""
        host = self.input_hamlib_host.text().strip() if hasattr(self, "input_hamlib_host") else self.hamlib_host
        if not host:
            host = "127.0.0.1"
        port = int(self.spin_hamlib_port.value()) if hasattr(self, "spin_hamlib_port") else int(self.hamlib_port)
        return host, port

    def _parse_civ_addr(self) -> int:
        """Parse civaddr field to one-byte integer."""
        raw = str(self.civaddr or "").strip()
        if not raw:
            raise ValueError("empty civaddr")
        try:
            if raw.lower().startswith("0x"):
                value = int(raw, 16)
            elif re.fullmatch(r"[0-9a-fA-F]{1,2}", raw):
                value = int(raw, 16)
            else:
                value = int(raw, 10)
        except Exception as exc:
            raise ValueError(f"invalid civaddr: {raw}") from exc
        if value < 0 or value > 0xFF:
            raise ValueError("civaddr out of range")
        return value

    def _cat_serial_connection_settings(self) -> tuple[str, int, int, int, int]:
        """Return serial CAT connection settings."""
        port = str(self.cat_serial_port or "").strip()
        if not port:
            port = str(self.ptt_port or "").strip()
        if not port:
            raise RuntimeError("CAT serial port is empty")

        baud = int(self.cat_serial_baud or 19200)
        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        bytesize_map = {
            5: serial.FIVEBITS,
            6: serial.SIXBITS,
            7: serial.SEVENBITS,
            8: serial.EIGHTBITS,
        }
        stopbits_map = {
            "1": serial.STOPBITS_ONE,
            "2": serial.STOPBITS_TWO,
        }
        bytesize = bytesize_map.get(int(self.cat_serial_data_bits or 8), serial.EIGHTBITS)
        parity = parity_map.get(str(self.cat_serial_parity or "N"), serial.PARITY_NONE)
        stopbits = stopbits_map.get(str(self.cat_serial_stop_bits or "1"), serial.STOPBITS_ONE)
        return port, baud, bytesize, parity, stopbits

    def _open_cat_serial_port(self) -> serial.Serial:
        """Open the CAT serial port with the current settings."""
        port, baud, bytesize, parity, stopbits = self._cat_serial_connection_settings()
        return serial.Serial(
            port=port,
            baudrate=baud,
            timeout=0.75,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
        )

    def _format_frequency_text(self, frequency_hz: Optional[int]) -> str:
        """Format frequency for status text."""
        if frequency_hz is None:
            return "unknown"
        if frequency_hz >= 1_000_000:
            return f"{frequency_hz / 1_000_000:.6f} MHz"
        if frequency_hz >= 1_000:
            return f"{frequency_hz / 1_000:.3f} kHz"
        return f"{frequency_hz} Hz"

    def _parse_ascii_frequency_response(self, response: str) -> Optional[int]:
        """Parse ASCII CAT frequency response such as FA00007000000;."""
        if not response:
            return None
        match = re.search(r"(?:FA|FB|IF)?(\d{6,11})", response.upper())
        if not match:
            match = re.search(r"(\d{6,11})", response)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    def _parse_icom_civ_frequency_response(self, response: bytes) -> Optional[int]:
        """Parse Icom CI-V frequency response into Hz."""
        if not response or len(response) < 10:
            return None
        if response[0] != 0xFE or response[1] != 0xFE or response[-1] != 0xFD:
            return None
        try:
            command_index = response.index(0x03)
        except ValueError:
            return None
        data = response[command_index + 1:-1]
        if len(data) < 5:
            return None
        digits = "".join(f"{byte:02X}" for byte in reversed(data[:5]))
        try:
            return int(digits)
        except Exception:
            return None

    def _query_serial_frequency(self) -> tuple[Optional[int], str]:
        """Query frequency from the selected CAT serial protocol."""
        protocol = self._rig_protocol(self.rig_model)
        if protocol == "GENERIC":
            raise RuntimeError("Serial CAT generic profile is not implemented")

        with self._open_cat_serial_port() as ser:
            dtr_force = self._state_to_bool(self.dtr_state)
            rts_force = self._state_to_bool(self.rts_state)
            if dtr_force is not None:
                ser.dtr = dtr_force
            if rts_force is not None:
                ser.rts = rts_force
            ser.reset_input_buffer()

            if protocol == "ICOM_CIV":
                civ = self._parse_civ_addr()
                query = bytes([0xFE, 0xFE, civ, 0xE0, 0x03, 0xFD])
                ser.write(query)
                ser.flush()
                for _ in range(4):
                    response = ser.read_until(b"\xFD")
                    if not response:
                        break
                    if response == query:
                        logger.debug(f"[PTT-CAT] Ignoring echoed CI-V query: {response.hex(' ')}")
                        continue
                    frequency_hz = self._parse_icom_civ_frequency_response(response)
                    if frequency_hz is not None:
                        return frequency_hz, f"CI-V response ({response.hex(' ')})"
                    return None, f"CI-V response ({response.hex(' ')})"
                return None, "no response"

            query = b"FA;"
            ser.write(query)
            ser.flush()
            for _ in range(4):
                response = ser.read_until(b";")
                if not response:
                    break
                response_text = response.decode("utf-8", errors="ignore").strip()
                if response_text == query.decode("ascii"):
                    logger.debug(f"[PTT-CAT] Ignoring echoed CAT query: {response_text}")
                    continue
                frequency_hz = self._parse_ascii_frequency_response(response_text)
                if frequency_hz is not None:
                    return frequency_hz, response_text or "frequency response"
                return None, response_text
            return None, "no response"

    def _send_serial_cat_ptt(self, active: bool) -> None:
        """Send CAT PTT command over selected serial CAT port by model protocol."""
        protocol = self._rig_protocol(self.rig_model)
        if protocol == "GENERIC":
            raise RuntimeError("Serial CAT generic profile is not implemented. Use rigctld TCP or choose Icom profile")

        port, baud, bytesize, parity, stopbits = self._cat_serial_connection_settings()
        if protocol == "ICOM_CIV":
            civ = self._parse_civ_addr()
            value = 0x01 if active else 0x00
            # Icom CI-V: FE FE <to> <from> 1C 00 <value> FD
            frame = bytes([0xFE, 0xFE, civ, 0xE0, 0x1C, 0x00, value, 0xFD])
        elif protocol in ("KENWOOD_CAT", "ELECRAFT_CAT"):
            frame = b"TX;" if active else b"RX;"
        elif protocol in ("YAESU_CAT", "ALINCO_CAT"):
            frame = b"TX1;" if active else b"TX0;"
        else:
            raise RuntimeError(f"Serial CAT profile '{self.rig_model}' is not implemented yet")

        with serial.Serial(
            port=port,
            baudrate=baud,
            timeout=0.25,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
        ) as ser:
            dtr_force = self._state_to_bool(self.dtr_state)
            rts_force = self._state_to_bool(self.rts_state)
            if dtr_force is not None:
                ser.dtr = dtr_force
            if rts_force is not None:
                ser.rts = rts_force
            ser.reset_input_buffer()
            ser.write(frame)
            ser.flush()

    def _save_hamlib_config_from_ui(self) -> None:
        """Persist Hamlib endpoint changes from UI widgets."""
        host, port = self._hamlib_endpoint()
        self.hamlib_host = host
        self.hamlib_port = port
        self.config.set("ptt.hamlib_host", host)
        self.config.set("ptt.hamlib_port", port)
        self.config.save()

    def _hamlib_send_command(self, command: str) -> str:
        """Send one command to rigctld and return raw response text."""
        host, port = self._hamlib_endpoint()
        payload = (command.strip() + "\n").encode("ascii", errors="ignore")
        with socket.create_connection((host, port), timeout=self.hamlib_timeout_s) as sock:
            sock.settimeout(self.hamlib_timeout_s)
            sock.sendall(payload)
            data = sock.recv(1024)
        return data.decode("utf-8", errors="ignore").strip()

    def test_hamlib_connection(self) -> bool:
        """Query frequency to verify the configured CAT path and response."""
        try:
            if self.rig_connection == "SERIAL":
                frequency_hz, details = self._query_serial_frequency()
                if frequency_hz is not None:
                    msg = f"CAT serial: OK ({self._format_frequency_text(frequency_hz)}) [{details}]"
                    self.label_hamlib_status.setText(msg)
                    self.label_hamlib_status.setStyleSheet("color: #29a34a;")
                    logger.info(f"[PTT-CAT] {msg}")
                    return True
                self.label_hamlib_status.setText(f"CAT serial: error ({details})")
                self.label_hamlib_status.setStyleSheet("color: #c46b00;")
                logger.warning(f"[PTT-CAT] Serial frequency query failed: {details}")
                return False

            self._save_hamlib_config_from_ui()
            response = self._hamlib_send_command("f")
            frequency_hz = None
            try:
                frequency_hz = int(response.strip())
            except Exception:
                frequency_hz = None
            if frequency_hz is not None and "RPRT -" not in response:
                self.label_hamlib_status.setText(
                    f"Hamlib TCP: OK ({self._format_frequency_text(frequency_hz)})"
                )
                self.label_hamlib_status.setStyleSheet("color: #29a34a;")
                logger.info(f"[PTT-HAMLIB] Frequency OK: {response}")
                return True
            self.label_hamlib_status.setText(f"Hamlib TCP: error ({response or 'no response'})")
            self.label_hamlib_status.setStyleSheet("color: #c46b00;")
            logger.warning(f"[PTT-HAMLIB] Unexpected response: {response}")
            return False
        except Exception as e:
            mode = "CAT serial" if self.rig_connection == "SERIAL" else "Hamlib TCP"
            self.label_hamlib_status.setText(f"{mode}: offline ({e})")
            self.label_hamlib_status.setStyleSheet("color: #b00020;")
            logger.warning(f"[PTT-HAMLIB] Connection failed: {e}")
            return False
    
    def close_ppt_port(self):
        """Close PTT serial port"""
        if self.ppt_serial is not None:
            try:
                # Make sure PTT is off
                self.set_ppt(False)
                self.ppt_serial.close()
                self.ppt_serial = None
                logger.info("[PTT] Closed serial port")
            except Exception as e:
                logger.warning(f"[PTT] Error closing port: {e}")
    
    def set_ppt(self, active: bool) -> bool:
        """Set PTT state according to selected ptt_type semantics."""
        mode = self.combo_ppt.currentData() if hasattr(self, "combo_ppt") else self.ptt_type
        mode_str = self._normalize_ptt_type(mode or self.ptt_type or "VOX")

        try:
            if mode_str == "RIG":
                if self.rig_connection == "SERIAL":
                    self._send_serial_cat_ptt(active)
                    logger.info(
                        f"[PTT-CAT] PTT {'ON' if active else 'OFF'} "
                        f"({self.cat_serial_port or 'n/a'} @ {self.cat_serial_baud}, civ={self.civaddr})"
                    )
                else:
                    cmd = "T 1" if active else "T 0"
                    response = self._hamlib_send_command(cmd)
                    ok = ("RPRT 0" in response) or response in ("0", "1") or response == ""
                    if not ok:
                        logger.warning(f"[PTT-HAMLIB] Command '{cmd}' failed: {response}")
                        return
                self.ptt_active = active
                if self.rig_connection != "SERIAL":
                    logger.info(f"[PTT-RIG] PTT {'ON' if active else 'OFF'} ({response or 'ok'})")
                return True

            if mode_str in ("DTR", "RTS"):
                if self.ppt_serial is None or not self.ppt_serial.is_open:
                    logger.warning("[PTT] Serial PTT selected but ptt_path is not open")
                    return False

                dtr_force = self._state_to_bool(self.dtr_state)
                rts_force = self._state_to_bool(self.rts_state)

                if mode_str == "DTR":
                    ptt_line_active = (not active) if self.dtr_active_low else active
                    self.ppt_serial.dtr = ptt_line_active
                    # Respect optional static override for RTS even when unused as PTT line.
                    if rts_force is not None:
                        self.ppt_serial.rts = rts_force
                    else:
                        self.ppt_serial.rts = False
                else:  # RTS
                    ptt_line_active = (not active) if self.rts_active_low else active
                    self.ppt_serial.rts = ptt_line_active
                    # Respect optional static override for DTR even when unused as PTT line.
                    if dtr_force is not None:
                        self.ppt_serial.dtr = dtr_force
                    else:
                        self.ppt_serial.dtr = False

                self.ptt_active = active
                logger.info(
                    f"[PTT-SERIAL] PTT {'ON' if active else 'OFF'} "
                    f"(type={mode_str}, port={self.ptt_port or 'n/a'}, "
                    f"dtr_active_low={self.dtr_active_low}, rts_active_low={self.rts_active_low})"
                )
                return True

            # VOX: no line toggle, only visible state in UI/web monitor.
            self.ptt_active = active
            return True
        except Exception as e:
            logger.warning(f"[PTT] Error setting PTT state in mode {mode_str}: {e}")
            return False
        finally:
            if hasattr(self, "btn_ptt_test"):
                self.btn_ptt_test.blockSignals(True)
                self.btn_ptt_test.setChecked(bool(self.ptt_active))
                self.btn_ptt_test.blockSignals(False)
    
    def on_rx_frame_decoded(self, frame_data: bytes, parsed: Optional[dict] = None):
        """Callback when RX pipeline decodes a frame"""
        try:
            if self._is_recent_tx_echo(frame_data):
                logger.info("[RX] Suppressed local TX echo (monitor loopback protection)")
                return

            # Format as TNC2
            tnc2_str = self._format_tnc2(frame_data)
            display = tnc2_str
            
            # Broadcast decoded RF frames to connected KISS clients.
            if self.kiss_server and frame_data:
                try:
                    self.kiss_server.send_frame(frame_data)
                    logger.info(f"[KISS-RX] Broadcasted {len(frame_data)} bytes to KISS clients on port {self.kiss_port}")
                except Exception as kiss_err:
                    logger.error(f"[KISS-RX] Failed to send frame to KISS server: {kiss_err}")
            
            # Emit signal for thread-safe GUI update (from audio thread context)
            monitor_direction = "RX"
            try:
                addresses, _ = self._parse_ax25_addresses(frame_data)
                src_callsign = ""
                if len(addresses) >= 2:
                    src_callsign = self._normalize_callsign(addresses[1]["full"])
                has_repeated_hop = any(bool(d.get("repeated")) for d in addresses[2:])

                if has_repeated_hop and src_callsign and src_callsign == self.last_tx_source_callsign:
                    monitor_direction = "DIGI"
            except Exception:
                monitor_direction = "RX"

            self.sig_monitor_line.emit(monitor_direction, "", display)
            self._handle_ax25_l2(frame_data)
            logger.info(f"[RX] Frame decoded: {display}")
        except Exception as e:
            logger.warning(f"[RX] Parse error: {e}")
    
    def on_kiss_frame_received(self, frame_data: bytes, addr: str):
        """Callback when KISS server receives a frame (called from KISS server thread!)"""
        try:
            try:
                addresses, _ = self._parse_ax25_addresses(frame_data)
                if len(addresses) >= 2:
                    self.last_tx_source_callsign = self._normalize_callsign(addresses[1]["full"])
            except Exception:
                pass

            # Format as TNC2
            tnc2_str = self._format_tnc2(frame_data)
            display = tnc2_str
            
            # Emit signal for thread-safe GUI update (from KISS server thread context)
            self.sig_monitor_line.emit("TX", "", display)
            logger.info(f"[KISS] TX from {addr}: {display}")
            
            # TX Processing: AX.25 â†’ HDLC â†’ AFSK â†’ Audio (copied from kiss_tx_rf_ok.py which works correctly)
            try:
                self._transmit_ax25_frame(frame_data, tx_tag="KISS")
                    
            except Exception as e:
                logger.error(f"[TX] Processing error: {e}", exc_info=True)
                
        except Exception as e:
            logger.warning(f"[KISS] Frame error: {e}", exc_info=True)
    
    def on_kiss_error(self, error_msg: str):
        """Callback when KISS server encounters an error (called from KISS server thread)"""
        logger.error(f"[KISS-ERROR] {error_msg}")
        # Emit signal for thread-safe GUI update
        self.sig_kiss_error.emit(error_msg)
    
    def on_tx_audio_data(self, audio_data):
        """Slot: Output audio data to sounddevice stream (runs on GUI thread - THREAD-SAFE!)"""
        logger.info(f"[TX-AUDIO] *** SLOT CALLED! ***")  # DEBUG: Verify slot is invoked
        try:
            logger.info(f"[TX-AUDIO] Checking audio_stream_out... {self.audio_stream_out}")
            if self.audio_stream_out is not None:
                logger.info(f"[TX-AUDIO] Stream exists! Active: {self.audio_stream_out.active}")
                # Convert list back to numpy array if needed
                if isinstance(audio_data, list):
                    audio_data = np.array(audio_data, dtype=np.float32)
                    logger.info(f"[TX-AUDIO] Converted list to numpy array")
                # Ensure audio is 2D array (n_samples, n_channels) for sounddevice
                if audio_data.ndim == 1:
                    audio_data = audio_data.reshape(-1, 1)
                    logger.info(f"[TX-AUDIO] Reshaped to {audio_data.shape}")

                # Update TX/output meter from the first channel.
                try:
                    self.audio_monitor_out.update(audio_data[:, 0].flatten())
                    self._last_output_meter_update_ts = time.time()
                    # Ensure short frame bursts are visible immediately in desktop UI.
                    self.update_meters()
                except Exception as e:
                    logger.debug(f"[TX-AUDIO] Output monitor update error: {e}")
                
                logger.info(f"[TX-AUDIO] Data shape={audio_data.shape}, dtype={audio_data.dtype}, min={audio_data.min():.3f}, max={audio_data.max():.3f}")
                logger.info(f"[TX-AUDIO] Writing {audio_data.shape} to output stream...")
                mode = self.combo_ppt.currentData() if hasattr(self, "combo_ppt") else self.ptt_type
                mode_str = self._normalize_ptt_type(mode or self.ptt_type or "VOX")
                use_hardware_ptt_timing = mode_str in ("RIG", "DTR", "RTS")
                ts = lambda: f"{time.time():.3f}"
                if self.tx_intent_want and not self.tx_intent_ptt_on:
                    logger.info(f"[TX-STAGE {ts()}] PTT ON requested")
                    ptt_ok = self.set_ppt(True)
                    self.tx_intent_ptt_on = bool(ptt_ok)
                    self.tx_intent_started_monotonic = time.monotonic() if ptt_ok else 0.0
                    logger.info(f"[TX-STAGE {ts()}] PTT ON done")
                try:
                    seg = getattr(self, "_tx_last_segments", {}) or {}
                    pre_s = int(seg.get("preamble_samples", 0) or 0)
                    frame_s = int(seg.get("frame_samples", 0) or 0)
                    post_s = int(seg.get("postamble_samples", 0) or 0)
                    sample_rate = float(self.actual_output_sample_rate or 44100.0)
                    pre_t = pre_s / sample_rate if sample_rate > 0 else 0.0
                    frame_t = frame_s / sample_rate if sample_rate > 0 else 0.0
                    post_t = post_s / sample_rate if sample_rate > 0 else 0.0
                    if pre_s > 0:
                        logger.info(f"[TX-STAGE {ts()}] preamble start")
                        logger.info(f"[TX-STAGE {ts()}] preamble end (expected +{pre_t:.3f}s)")
                    logger.info(f"[TX-STAGE {ts()}] frame/audio send start")
                    self.audio_stream_out.write(audio_data)
                    logger.info(f"[TX-STAGE {ts()}] frame/audio send end")
                    if post_s > 0:
                        logger.info(f"[TX-STAGE {ts()}] tail flags start")
                        logger.info(f"[TX-STAGE {ts()}] tail flags end (expected +{post_t:.3f}s)")
                finally:
                    if self.tx_intent_ptt_on:
                        if use_hardware_ptt_timing:
                            tx_tail_ms = self._get_tx_tail_ms()
                            if tx_tail_ms > 0:
                                logger.info(f"[TX-STAGE {ts()}] TXTail start ({tx_tail_ms} ms)")
                                time.sleep(tx_tail_ms / 1000.0)
                                logger.info(f"[TX-STAGE {ts()}] TXTail end")
                        logger.info(f"[TX-STAGE {ts()}] PTT OFF requested")
                        self.set_ppt(False)
                        logger.info(f"[TX-STAGE {ts()}] PTT OFF done")
                    self.tx_intent_want = False
                    self.tx_intent_ptt_on = False
                    self.tx_intent_started_monotonic = 0.0
                logger.info(f"[TX-AUDIO] âś“ Audio data written successfully!")
            else:
                logger.error(f"[TX-AUDIO] *** audio_stream_out is NONE! ***")
                self.tx_intent_want = False
                self.tx_intent_ptt_on = False
                self.tx_intent_started_monotonic = 0.0
        except Exception as e:
            logger.error(f"[TX-AUDIO] Failed to write: {e}", exc_info=True)
            self.tx_intent_want = False
            self.tx_intent_ptt_on = False
            self.tx_intent_started_monotonic = 0.0
    
    def on_system_volume_changed(self, volume: float):
        """Callback when system volume changes (0.0 to 1.0)"""
        # Keep TX drive stable for reliable AFSK decode, independent from OS volume changes.
        self.current_tx_amplitude = 0.9
        logger.info(
            f"[VOLUME] System volume changed to {volume:.1%}; "
            f"keeping fixed TX amplitude: {self.current_tx_amplitude:.1%}"
        )

    def show_kiss_error_dialog(self, error_msg: str):
        """Show error dialog on main thread and exit"""
        QMessageBox.critical(
            self,
            self._t("kiss_error_title"),
            error_msg,
            QMessageBox.StandardButton.Ok
        )
        # Exit application after error
        logger.error(f"[APP] KISS error - shutting down: {error_msg}")
        sys.exit(1)

    def _register_web_handlers(self) -> None:
        """Register all desktop control endpoints exposed to web UI."""
        self.web_server.register_handler("input-device", self._web_set_input_device)
        self.web_server.register_handler("output-device", self._web_set_output_device)
        self.web_server.register_handler("sample-rate", self._web_set_sample_rate)
        self.web_server.register_handler("ppt-mode", self._web_set_ppt_mode)
        self.web_server.register_handler("ptt-mode", self._web_set_ppt_mode)
        self.web_server.register_handler("ptt-pins", self._web_set_ptt_pins)
        self.web_server.register_handler("ptt-path", self._web_set_ptt_path)
        self.web_server.register_handler("ptt-share", self._web_set_ptt_share)
        self.web_server.register_handler("ptt-invert", self._web_set_ptt_invert)
        self.web_server.register_handler("civaddr", self._web_set_civaddr)
        self.web_server.register_handler("vox-delay", self._web_set_vox_delay)
        self.web_server.register_handler("hamlib-config", self._web_set_hamlib_config)
        self.web_server.register_handler("cat-connection", self._web_set_cat_connection)
        self.web_server.register_handler("allow-ip-toggle", self._web_toggle_allow_ip)
        self.web_server.register_handler("refresh-devices", self._web_refresh_devices)
        self.web_server.register_handler("tone", self._web_control_tone)
        self.web_server.register_handler("ptt-test", self._web_set_ptt_test)

    def _start_web_ui(self) -> bool:
        """Start local web UI server if it is not already running."""
        if self.web_ui_running:
            return True
        try:
            self.web_server.start()
            self.web_ui_running = True
            logger.info("[WEB] Desktop toggle: enabled")
            return True
        except Exception as e:
            logger.error(f"[WEB] Could not start web server: {e}")
            self.web_ui_running = False
            return False

    def _stop_web_ui(self) -> None:
        """Stop local web UI server if running."""
        if not self.web_ui_running:
            return
        try:
            self.web_server.stop()
            logger.info("[WEB] Desktop toggle: disabled")
        except Exception as e:
            logger.warning(f"[WEB] Could not stop web server cleanly: {e}")
        finally:
            self.web_ui_running = False

    def _update_web_link_visibility(self) -> None:
        """Show/hide web link under the web UI toggle based on active state."""
        if hasattr(self, "label_web_link"):
            self.label_web_link.setVisible(bool(self.web_ui_enabled))

    def _set_web_ui_enabled(self, enabled: bool, persist: bool = True) -> None:
        """Apply desktop web UI state, persist it, and refresh header controls."""
        target = bool(enabled)
        if target:
            started = self._start_web_ui()
            self.web_ui_enabled = bool(started)
            if target and not started:
                QMessageBox.warning(
                    self,
                    self._t("web_interface"),
                    self._t("web_start_error")
                )
        else:
            self._stop_web_ui()
            self.web_ui_enabled = False

        if persist:
            self.config.set("application.web_ui_enabled", self.web_ui_enabled)
            self.config.save()

        if hasattr(self, "check_web_ui_enabled"):
            self.check_web_ui_enabled.blockSignals(True)
            self.check_web_ui_enabled.setChecked(self.web_ui_enabled)
            self.check_web_ui_enabled.blockSignals(False)

        self._update_web_link_visibility()

    def on_web_ui_toggle_changed(self, enabled: bool) -> None:
        """Header toggle callback for enabling/disabling local web UI."""
        self._set_web_ui_enabled(enabled, persist=True)

    def _set_close_behavior(self, hide_to_tray: bool, persist: bool = True) -> None:
        """Apply close button behavior and optionally persist setting."""
        self.close_to_tray_enabled = bool(hide_to_tray)

        if persist:
            self.config.set("application.close_to_tray_enabled", self.close_to_tray_enabled)
            self.config.save()

        if hasattr(self, "check_close_to_tray"):
            self.check_close_to_tray.blockSignals(True)
            self.check_close_to_tray.setChecked(self.close_to_tray_enabled)
            self.check_close_to_tray.blockSignals(False)
        if hasattr(self, "check_close_to_tray_monitor"):
            self.check_close_to_tray_monitor.blockSignals(True)
            self.check_close_to_tray_monitor.setChecked(self.close_to_tray_enabled)
            self.check_close_to_tray_monitor.blockSignals(False)

    def on_close_behavior_toggle_changed(self, enabled: bool) -> None:
        """Header toggle callback for close button behavior."""
        self._set_close_behavior(enabled, persist=True)

    def _get_web_status(self) -> dict:
        """Build a lightweight app snapshot for the local web UI."""
        try:
            levels_in = self.audio_monitor_in.get_all_levels()
            levels_out = self.audio_monitor_out.get_all_levels()
        except Exception:
            levels_in = {"peak_pct": 0.0, "peak_dbfs": -96.0, "rms_pct": 0.0, "rms_dbfs": -96.0}
            levels_out = {"peak_pct": 0.0, "peak_dbfs": -96.0, "rms_pct": 0.0, "rms_dbfs": -96.0}

        input_name = self.combo_input.currentText() if hasattr(self, "combo_input") else ""
        output_name = self.combo_output.currentText() if hasattr(self, "combo_output") else ""
        sample_rate = self.combo_sample_rate.currentText() if hasattr(self, "combo_sample_rate") else "44100"
        ptt_mode = self.combo_ppt.currentText() if hasattr(self, "combo_ppt") else self.ptt_type

        tone_active = ""
        if self.active_tone_button == self.btn_tone_1200:
            tone_active = "1200"
        elif self.active_tone_button == self.btn_tone_both:
            tone_active = "both"
        elif self.active_tone_button == self.btn_tone_2200:
            tone_active = "2200"

        input_devices = self._combo_items_with_ids(self.combo_input) if hasattr(self, "combo_input") else []
        output_devices = self._combo_items_with_ids(self.combo_output) if hasattr(self, "combo_output") else []
        ptt_modes = self._combo_items(self.combo_ppt) if hasattr(self, "combo_ppt") else ["RIG", "DTR", "RTS", "VOX"]
        ptt_paths = self._combo_items(self.combo_ptt_port) if hasattr(self, "combo_ptt_port") else []
        ptt_path = self.combo_ptt_port.currentText() if hasattr(self, "combo_ptt_port") else self.ptt_port

        input_device_id = None
        output_device_id = None
        if hasattr(self, "combo_input"):
            current_id = self.combo_input.currentData()
            if isinstance(current_id, int):
                input_device_id = current_id
        if hasattr(self, "combo_output"):
            current_id = self.combo_output.currentData()
            if isinstance(current_id, int):
                output_device_id = current_id

        return {
            "app_running": True,
            "kiss_listen": f"0.0.0.0:{self.kiss_port}",
            "web_listen": f"{WEB_UI_BIND_HOST}:{WEB_UI_PORT}",
            "web_enabled": bool(self.web_ui_enabled),
            "sample_rate": int(sample_rate) if str(sample_rate).isdigit() else sample_rate,
            "sample_rates": ["44100", "48000", "96000"],
            "ptt_mode": ptt_mode,
            "ptt_type": self.ptt_type,
            "ptt_path": ptt_path,
            "ptt_paths": ptt_paths,
            "ptt_share": bool(self.ptt_share),
            "ptt_active_low": bool(self._get_current_serial_invert()),
            "civaddr": self.civaddr,
            "dtr_state": self.dtr_state,
            "rts_state": self.rts_state,
            "input_device": input_name,
            "output_device": output_name,
            "input_device_id": input_device_id,
            "output_device_id": output_device_id,
            "input_devices": input_devices,
            "output_devices": output_devices,
            "ptt_modes": ptt_modes,
            "hamlib_host": self.hamlib_host,
            "hamlib_port": self.hamlib_port,
            "rig_model": self.rig_model,
            "rig_connection": self.rig_connection,
            "cat_serial_port": self.cat_serial_port,
            "cat_serial_baud": int(self.cat_serial_baud),
            "allowed_ips": self._effective_allowed_ips_display(),
            "rx_peak_pct": float(levels_in.get("peak_pct", 0.0)),
            "tx_peak_pct": float(levels_out.get("peak_pct", 0.0)),
            "rx_peak_dbfs": float(levels_in.get("peak_dbfs", -96.0)),
            "tx_peak_dbfs": float(levels_out.get("peak_dbfs", -96.0)),
            "rx_rms_pct": float(levels_in.get("rms_pct", 0.0)),
            "tx_rms_pct": float(levels_out.get("rms_pct", 0.0)),
            "rx_rms_dbfs": float(levels_in.get("rms_dbfs", -96.0)),
            "tx_rms_dbfs": float(levels_out.get("rms_dbfs", -96.0)),
            "last_monitor_line": self.last_monitor_line,
            "monitor_lines": self.monitor_lines[-120:],
            "use_rts": bool(self.check_rts.isChecked()) if hasattr(self, "check_rts") else False,
            "use_dts": bool(self.check_dts.isChecked()) if hasattr(self, "check_dts") else False,
            "vox_delay_ms": int(self._get_tx_delay_ms()),
            "tx_delay_ms": int(self._get_tx_delay_ms()),
            "tx_tail_ms": int(self._get_tx_tail_ms()),
            "pre_tx_flags_enabled": bool(self.pre_tx_flags_enabled),
            "post_tx_flags_enabled": bool(self.post_tx_flags_enabled),
            "dtr_active_low": bool(self.dtr_active_low),
            "rts_active_low": bool(self.rts_active_low),
            "ptt_active": bool(self.ptt_active),
            "tone_active": tone_active,
            "build": self.app_build_tag,
        }

    def _combo_items(self, combo: QComboBox) -> list:
        """Return non-placeholder combo texts as user-visible values."""
        items = []
        for i in range(combo.count()):
            text = combo.itemText(i).strip()
            data = combo.itemData(i)
            if text and data is not None:
                items.append(text)
        return items

    def _combo_items_with_ids(self, combo: QComboBox) -> list:
        """Return combo entries as {id, label} for web UI device lists."""
        items = []
        for i in range(combo.count()):
            text = combo.itemText(i).strip()
            data = combo.itemData(i)
            if text and data is not None:
                items.append({"id": data, "label": text})
        return items

    def _set_combo_by_data(self, combo: QComboBox, value) -> bool:
        """Set combo by exact itemData match."""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return True
        return False

    def _set_combo_by_text(self, combo: QComboBox, value: str) -> bool:
        """Set combo by exact text first, then by substring fallback."""
        target = str(value or "").strip().lower()
        if not target:
            return False

        for i in range(combo.count()):
            text = combo.itemText(i).strip()
            if text and text.lower() == target:
                combo.setCurrentIndex(i)
                return True

        for i in range(combo.count()):
            text = combo.itemText(i).strip()
            if text and target in text.lower():
                combo.setCurrentIndex(i)
                return True

        return False
    
    def _web_set_input_device(self, data: dict) -> dict:
        """Web control: set input device."""
        device_id = data.get("device_id", None)
        device = data.get("device", "")
        if device_id is None and not device:
            return {"error": "empty device"}
        try:
            if device_id is not None:
                try:
                    parsed_id = int(device_id)
                except (TypeError, ValueError):
                    return {"error": "invalid device_id"}
                if self._set_combo_by_data(self.combo_input, parsed_id):
                    logger.info(f"[WEB] Set input device id: {parsed_id}")
                    return {"ok": True}
            if device and self._set_combo_by_text(self.combo_input, device):
                logger.info(f"[WEB] Set input device: {device}")
                return {"ok": True}
            return {"error": "device not found"}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_output_device(self, data: dict) -> dict:
        """Web control: set output device."""
        device_id = data.get("device_id", None)
        device = data.get("device", "")
        if device_id is None and not device:
            return {"error": "empty device"}
        try:
            if device_id is not None:
                try:
                    parsed_id = int(device_id)
                except (TypeError, ValueError):
                    return {"error": "invalid device_id"}
                if self._set_combo_by_data(self.combo_output, parsed_id):
                    logger.info(f"[WEB] Set output device id: {parsed_id}")
                    return {"ok": True}
            if device and self._set_combo_by_text(self.combo_output, device):
                logger.info(f"[WEB] Set output device: {device}")
                return {"ok": True}
            return {"error": "device not found"}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_sample_rate(self, data: dict) -> dict:
        """Web control: set sample rate."""
        rate = data.get('rate', 44100)
        rate_str = str(rate)
        try:
            idx = self.combo_sample_rate.findText(rate_str)
            if idx >= 0:
                self.combo_sample_rate.setCurrentIndex(idx)
                logger.info(f"[WEB] Set sample rate: {rate} Hz")
                return {"ok": True}
            return {"error": f"sample rate {rate} not available"}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ppt_mode(self, data: dict) -> dict:
        """Web control: set PTT mode."""
        mode = data.get('mode', 'VOX')
        try:
            normalized = self._normalize_ptt_type(str(mode))
            if self._set_combo_by_text(self.combo_ppt, normalized):
                logger.info(f"[WEB] Set PTT type: {normalized}")
                return {"ok": True}
            return {"error": f"PTT type {normalized} not found"}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ptt_pins(self, data: dict) -> dict:
        """Web control: set line-state style toggles for RTS/DTR."""
        try:
            rts = bool(data.get("rts", False))
            dts = bool(data.get("dts", False))
            self.check_rts.setChecked(rts)
            self.check_dts.setChecked(dts)
            logger.info(f"[WEB] Set PTT pins: RTS={rts}, DTS={dts}")
            return {"ok": True, "rts": rts, "dts": dts}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ptt_path(self, data: dict) -> dict:
        """Web control: set serial ptt_path."""
        try:
            path = str(data.get("path", "") or "").strip()
            if not path:
                return {"error": "empty path"}
            if hasattr(self, "combo_ptt_port") and self._set_combo_by_text(self.combo_ptt_port, path):
                self.ptt_port = path
                if self.ptt_type in ("DTR", "RTS"):
                    self.open_ptt_port(path)
                self._save_ptt_config()
                return {"ok": True, "path": path}
            return {"error": "ptt_path not found"}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ptt_share(self, data: dict) -> dict:
        """Web control: set ptt_share."""
        try:
            value = bool(data.get("share", False))
            if hasattr(self, "check_ptt_share"):
                self.check_ptt_share.setChecked(value)
            self.ptt_share = value
            self._save_ptt_config()
            return {"ok": True, "share": value}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ptt_invert(self, data: dict) -> dict:
        """Web control: set active-low inversion for serial PTT lines."""
        try:
            value = bool(data.get("active_low", False))
            if hasattr(self, "check_ptt_active_low"):
                self.check_ptt_active_low.setChecked(value)
            mode = self._normalize_ptt_type(self.ptt_type)
            if mode == "DTR":
                self.dtr_active_low = value
            elif mode == "RTS":
                self.rts_active_low = value
            self.ptt_active_low = value
            self._save_ptt_config()
            return {"ok": True, "active_low": value}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_ptt_test(self, data: dict) -> dict:
        """Web control: toggle manual PTT test like desktop button."""
        try:
            active = bool(data.get("active", False))
            self.set_ppt(active)
            return {"ok": True, "active": bool(self.ptt_active)}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_civaddr(self, data: dict) -> dict:
        """Web control: set civaddr value used by Hamlib-like config."""
        try:
            civaddr = str(data.get("civaddr", "") or "").strip()
            if not civaddr:
                return {"error": "empty civaddr"}
            self.civaddr = civaddr
            if hasattr(self, "input_civaddr"):
                self.input_civaddr.setText(civaddr)
            self._save_ptt_config()
            return {"ok": True, "civaddr": civaddr}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_vox_delay(self, data: dict) -> dict:
        """Web control: set TX delay (legacy endpoint name kept for compatibility)."""
        try:
            if self.config_ui_mode != "advanced":
                self._sync_tx_timing_controls()
                return {"error": "TX timing can be changed only in Advanced mode"}
            delay = int(data.get("delay_ms", 500))
            delay = max(0, min(5000, delay))
            self.spin_vox_delay.setValue(delay)
            self.tx_delay_ms = delay
            self.config.set("ptt.tx_delay_ms", delay)
            self.config.set("ptt.vox_delay_ms", delay)
            self.config.save()
            self._sync_tx_timing_controls()
            logger.info(f"[WEB] Set TX delay: {delay} ms")
            return {"ok": True, "delay_ms": delay}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_hamlib_config(self, data: dict) -> dict:
        """Web control: set Hamlib host/port and optionally test connection."""
        try:
            host = str(data.get("host", self.hamlib_host)).strip() or "127.0.0.1"
            raw_port = data.get("port", self.hamlib_port)
            try:
                port = int(raw_port)
            except (TypeError, ValueError):
                return {"error": "invalid port"}
            if port < 1 or port > 65535:
                return {"error": "port out of range"}

            self.hamlib_host = host
            self.hamlib_port = port
            if hasattr(self, "input_hamlib_host"):
                self.input_hamlib_host.setText(host)
            if hasattr(self, "spin_hamlib_port"):
                self.spin_hamlib_port.setValue(port)

            self.config.set("ptt.hamlib_host", host)
            self.config.set("ptt.hamlib_port", port)
            self.config.save()

            if bool(data.get("test", False)):
                ok = self.test_hamlib_connection()
                return {"ok": ok, "host": host, "port": port}

            return {"ok": True, "host": host, "port": port}
        except Exception as e:
            return {"error": str(e)}

    def _web_set_cat_connection(self, data: dict) -> dict:
        """Web control: set CAT transport mode and serial path/baud for RIG PTT."""
        try:
            mode = self._normalize_rig_connection(data.get("mode", self.rig_connection))
            self.rig_connection = mode

            raw_baud = data.get("baud", self.cat_serial_baud)
            try:
                baud = int(raw_baud)
            except (TypeError, ValueError):
                return {"error": "invalid baud"}
            if baud < 1200 or baud > 115200:
                return {"error": "baud out of range"}
            self.cat_serial_baud = baud

            model = self._normalize_rig_model(data.get("rig_model", self.rig_model))
            self.rig_model = model

            path = str(data.get("path", self.cat_serial_port) or "").strip()
            self.cat_serial_port = path

            if hasattr(self, "combo_rig_connection"):
                self._set_combo_by_data(self.combo_rig_connection, mode)
            if path and hasattr(self, "combo_cat_serial_port"):
                self._set_combo_by_text(self.combo_cat_serial_port, path)
            if hasattr(self, "spin_cat_serial_baud"):
                self.spin_cat_serial_baud.setValue(baud)
            if hasattr(self, "combo_rig_model"):
                self._set_combo_by_data(self.combo_rig_model, model)

            self._save_rig_connection_config()
            self._update_ptt_mode_controls(self.ptt_type)
            self._update_rig_profile_hint()
            self._reset_hamlib_status()

            if bool(data.get("test", False)):
                ok = self.test_hamlib_connection()
                return {"ok": ok, "mode": mode, "path": path, "baud": baud, "rig_model": model}

            return {"ok": True, "mode": mode, "path": path, "baud": baud, "rig_model": model}
        except Exception as e:
            return {"error": str(e)}

    def _web_toggle_allow_ip(self, data: dict) -> dict:
        """Web control: toggle allowed remote IP (add/remove)."""
        try:
            ip = str(data.get("ip", "") or "").strip()
            if not ip:
                return {"error": "empty ip"}
            if ip in {"127.0.0.1", "::1"}:
                # Localhost is always allowed implicitly and is not part of user-managed list.
                return {"ok": True, "action": "ignored_localhost_fixed", "allowed_ips": self._effective_allowed_ips_display()}

            if ip in self.allowed_remote_ips:
                self.allowed_remote_ips.remove(ip)
                action = "removed"
            else:
                self.allowed_remote_ips.add(ip)
                action = "added"

            if not self.allowed_remote_ips:
                self.allowed_remote_ips.add(ALLOW_ALL_IP_TOKEN)
                action = "reset_to_default"

            self.config.set("application.allow_ips", sorted(self.allowed_remote_ips))
            self.config.save()

            logger.info(f"[WEB] Allow IP toggle: {ip} -> {action}; current={sorted(self.allowed_remote_ips)}")
            self._refresh_allow_ip_controls()
            return {"ok": True, "action": action, "allowed_ips": self._effective_allowed_ips_display()}
        except Exception as e:
            return {"error": str(e)}

    def _effective_allowed_ips_display(self) -> list:
        """Return user-managed allowlist for UI/status (localhost excluded from list)."""
        return sorted(ip for ip in self.allowed_remote_ips if ip not in {"127.0.0.1", "::1"})

    def _refresh_allow_ip_controls(self) -> None:
        """Refresh centered allow-address widgets in header."""
        ips = self._effective_allowed_ips_display() if self.allowed_remote_ips else [ALLOW_ALL_IP_TOKEN]
        if hasattr(self, "combo_allow_ips"):
            typed = self.combo_allow_ips.currentText()
            self.combo_allow_ips.blockSignals(True)
            self.combo_allow_ips.clear()
            for ip in ips:
                self.combo_allow_ips.addItem(ip)
            self.combo_allow_ips.setCurrentText(typed)
            self.combo_allow_ips.blockSignals(False)
        if hasattr(self, "label_allow_ip_status"):
            self.label_allow_ip_status.setText("Allowed IPs: " + ", ".join(ips))

    def on_allow_ip_toggle_clicked(self) -> None:
        """Desktop header action: toggle allow IP from centered input."""
        ip = self.combo_allow_ips.currentText().strip() if hasattr(self, "combo_allow_ips") else ""
        if not ip:
            return
        result = self._web_toggle_allow_ip({"ip": ip})
        if isinstance(result, dict) and result.get("error"):
            QMessageBox.warning(self, "Allow Address", f"Operation failed: {result.get('error')}")
            return
        if hasattr(self, "combo_allow_ips"):
            self.combo_allow_ips.setCurrentText("")

    def _web_refresh_devices(self, _data: dict) -> dict:
        """Web control: refresh input/output/PTT lists."""
        try:
            self.populate_devices()
            return {
                "ok": True,
                "input_count": max(0, self.combo_input.count() - 1),
                "output_count": max(0, self.combo_output.count() - 1),
                "ptt_modes": max(0, self.combo_ppt.count() - 1),
            }
        except Exception as e:
            return {"error": str(e)}

    def _web_control_tone(self, data: dict) -> dict:
        """Web control: start/stop test tone."""
        tone = data.get('tone', 'stop').lower()
        try:
            if tone == "stop":
                if self.tone_gen.is_running() or self.active_tone_button:
                    self.tone_gen.stop_continuous()
                    self.set_ppt(False)
                    self.btn_tone_1200.setChecked(False)
                    self.btn_tone_both.setChecked(False)
                    self.btn_tone_2200.setChecked(False)
                    self.active_tone_button = None
                    logger.info("[WEB] Tone stopped")
                return {"ok": True}
            elif tone in ("1200", "both", "2200"):
                if self.tone_gen.is_running():
                    self.tone_gen.stop_continuous()
                    self.set_ppt(False)
                self.tone_gen.on_audio_ready = self.on_tone_audio_ready
                if self.audio_stream_out is None:
                    self.start_audio_output()
                self.tone_gen.start_continuous(tone, self.on_tone_audio_ready, chunk_duration=0.02, sample_rate=self.actual_output_sample_rate)
                self.set_ppt(True)

                # Keep desktop/UI tone state synchronized for web toggle logic.
                self.btn_tone_1200.setChecked(tone == "1200")
                self.btn_tone_both.setChecked(tone == "both")
                self.btn_tone_2200.setChecked(tone == "2200")
                if tone == "1200":
                    self.active_tone_button = self.btn_tone_1200
                elif tone == "both":
                    self.active_tone_button = self.btn_tone_both
                else:
                    self.active_tone_button = self.btn_tone_2200

                logger.info(f"[WEB] Started tone: {tone}")
                return {"ok": True}
            return {"error": f"unknown tone: {tone}"}
        except Exception as e:
            return {"error": str(e)}


def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)-8s] %(name)-15s | %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info("MicroKISStnc Desktop Application v1.0")
    logger.info("=" * 80)
    logger.info(f"[APP] Launching script: {Path(__file__).resolve()}")
    
    set_windows_appusermodel_id()
    app = QApplication(sys.argv)
    try:
        startup_kiss_port = int(ConfigManager().get("kiss.port", KISS_SERVER_PORT))
    except Exception:
        startup_kiss_port = KISS_SERVER_PORT
    startup_kiss_port = max(1, min(65535, int(startup_kiss_port)))

    # Fail fast: do not construct/show main window when KISS port is occupied.
    if not is_tcp_port_available(startup_kiss_port):
        logger.error(f"[APP] Port {startup_kiss_port} is already in use. Startup cancelled.")
        show_kiss_port_busy_dialog(startup_kiss_port)
        sys.exit(1)

    try:
        window = MicroKISStnc()
    except StartupAbortError as exc:
        logger.error(f"[APP] Startup aborted: {exc}")
        sys.exit(1)

    window.showMaximized()
    
    logger.info("Starting event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


