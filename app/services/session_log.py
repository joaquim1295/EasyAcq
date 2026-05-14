from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_session_log(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("acq.sessao")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(fmt="%(asctime)s | %(message)s", datefmt="%H:%M:%S")

    file_handler = RotatingFileHandler(
        filename=log_dir / "sessao.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
