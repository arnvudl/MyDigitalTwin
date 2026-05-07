"""
logger.py — Logger centralisé pour le pipeline d'ingestion

Console : INFO+ (format court)
Fichier : DEBUG+ → data/logs/ingestion_YYYY-MM-DD.log
"""

import logging
import os
from datetime import datetime

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "data", "logs")

_CONSOLE_FMT = logging.Formatter("%(levelname)-8s %(message)s")
_FILE_FMT    = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(_CONSOLE_FMT)
    logger.addHandler(ch)

    os.makedirs(_LOG_DIR, exist_ok=True)
    log_file = os.path.join(_LOG_DIR, f"ingestion_{datetime.now().strftime('%Y-%m-%d')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FILE_FMT)
    logger.addHandler(fh)

    return logger
