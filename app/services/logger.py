from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("acq")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
