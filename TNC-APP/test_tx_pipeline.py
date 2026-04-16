#!/usr/bin/env python3
"""Test TX Pipeline directly"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

from audio_manager import AudioManager
from tx_pipeline import TXPipeline

logger.info("Starting TX Pipeline test...")

try:
    logger.info("Creating AudioManager...")
    audio_mgr = AudioManager()
    logger.info("AudioManager created OK")
    
    logger.info("Starting output stream (auto-fallback enabled)...")
    audio_mgr.start_output_stream()
    logger.info("Output stream started OK")
    
    logger.info("Creating TX Pipeline...")
    tx = TXPipeline(audio_mgr)
    logger.info("TX Pipeline created OK")
    
    logger.info("Starting TX Pipeline thread...")
    tx.start()
    logger.info("TX Pipeline thread started OK")
    
    logger.info("All systems initialized!")
    
except Exception as e:
    logger.error(f"ERROR: {e}", exc_info=True)
