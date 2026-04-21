import os
import sys
import logging
from logging import handlers
from . import constants


def run():

    # Format logs
    fmt = "%(levelname)s %(asctime)s %(filename)s:%(lineno)d] %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(
        level="DEBUG",
        format=fmt,
        datefmt=datefmt,
        stream=sys.stdout,
        force=True,
    )
    formatter = logging.Formatter(
        fmt=fmt,
        datefmt=datefmt,
    )

    # stdout handler
    logging.getLogger().handlers[0].setLevel(constants.LOG_LEVEL)

    # File handler per level
    os.makedirs(constants.LOG_DIR, exist_ok=True)
    for log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        handler = handlers.RotatingFileHandler(
            filename=os.path.join(constants.LOG_DIR, f"{log_level.lower()}.log"),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
        )
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        logging.getLogger().addHandler(handler)
