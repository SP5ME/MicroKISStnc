#!/usr/bin/env python3
"""
TNC Application - Terminal Node Controller
Main entry point
"""

import sys
import logging
import os
import signal
import time
from pathlib import Path

# Dodaj TNC-APP folder do path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import AppConfig
from src.gui import TNCMainWindow

# Global reference do main window dla graceful shutdown
_main_window = None


def setup_logging():
    """Skonfiguruj logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('tnc.log'),
            logging.StreamHandler()
        ]
    )


def check_running_instance():
    """Sprawdź czy TNC już jest uruchomiona"""
    lock_file = Path("tnc.lock")
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            logger = logging.getLogger(__name__)
            logger.warning(f"[WARN] TNC Application might be running (PID: {pid})")
            logger.warning(f"   If that's wrong, delete tnc.lock")
        except:
            pass
    
    # Zapisz PID
    Path("tnc.lock").write_text(str(os.getpid()))


def signal_handler(signum, frame):
    """Handler dla sygnałów (Ctrl+C)"""
    logger = logging.getLogger(__name__)
    sig_name = signal.Signals(signum).name
    logger.info(f"[SHUTDOWN] Received signal {sig_name} ({signum})")
    
    global _main_window
    if _main_window:
        logger.info("[SHUTDOWN] Initiating graceful shutdown...")
        try:
            _main_window.on_closing()
        except Exception as e:
            logger.error(f"[ERROR] Error during shutdown: {e}", exc_info=True)
    
    # Force exit if shutdown takes too long
    time.sleep(2)
    logger.error("[SHUTDOWN] Forced exit - shutdown timeout")
    sys.exit(1)


def setup_signal_handlers():
    """Ustaw handlery dla sygnałów"""
    logger = logging.getLogger(__name__)
    try:
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Terminate
        logger.info("[OK] Signal handlers installed")
    except Exception as e:
        logger.error(f"[WARN] Could not install signal handlers: {e}")


def main():
    """Główna funkcja"""
    global _main_window
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("====== TNC Application v0.1.0 Starting ======")
    logger.info("[TIP] Press Ctrl+C to gracefully shutdown")
    
    check_running_instance()
    setup_signal_handlers()
    
    # Załaduj konfigurację
    config = AppConfig.load()
    logger.info(f"KISS Server: {config.kiss_server.host}:{config.kiss_server.port} "
                f"(enabled={config.kiss_server.enabled})")
    
    try:
        # Uruchom aplikację
        _main_window = TNCMainWindow(config)
        _main_window.run()
    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] KeyboardInterrupt caught")
    except Exception as e:
        logger.error(f"[ERROR] Application error: {e}", exc_info=True)
    finally:
        # Wyczyść lock file
        try:
            Path("tnc.lock").unlink()
            logger.info("[OK] Cleaned up lock file")
        except:
            pass
        logger.info("====== TNC Application Closed ======")


if __name__ == "__main__":
    main()

