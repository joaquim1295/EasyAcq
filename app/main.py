from __future__ import annotations

import logging

from app.config import AppConfig
from app.prerequisites_check import warn_missing_prerequisites
from app.services.logger import setup_logger
from app.services.session_log import setup_session_log
from app.services.user_settings import load_user_settings, save_user_settings
from app.ui.app import MainWindow


def main() -> None:
    warn_missing_prerequisites()
    config = AppConfig()
    load_user_settings(config)
    config.ensure_dirs()
    logger = setup_logger(config.log_dir)
    setup_session_log(config.log_dir)
    if config.verbose_logging:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("acq.sessao").setLevel(logging.DEBUG)
    app = MainWindow(config)
    try:
        app.run()
    finally:
        save_user_settings(config)


if __name__ == "__main__":
    main()
