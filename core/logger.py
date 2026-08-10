from __future__ import annotations

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str = "extrator") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
