from flask import Flask, request, jsonify
import os

import requests
from utils import qbittorrent_interface
import logging
from logging import handlers
import json
from utils.import_to_library import import_books
import sys

PORT = os.environ.get("FLASK_PORT", 8181)
qbittorrent_address = os.environ.get("QBITTORRENT_ADDRESS", "http://localhost:8080")

# Format logs
level = os.environ.get("LOG_LEVEL", "INFO").upper()
fmt = "%(levelname)s %(asctime)s %(filename)s:%(lineno)d]: %(message)s"
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
logging.getLogger().handlers[0].setLevel(level)

# File handler per level
LOG_DIR = os.environ.get("LOG_DIR", "/tmp/logs")
os.makedirs(LOG_DIR, exist_ok=True)
for log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    handler = handlers.RotatingFileHandler(
        filename=os.path.join(LOG_DIR, f"{log_level.lower()}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
    )
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    logging.getLogger().addHandler(handler)

app = Flask(__name__)
app.logger.propagate = True

logger = logging.getLogger(__name__)


@app.route("/torrent_complete", methods=["POST"])
def interactions():
    tor_interface = qbittorrent_interface.QBittorrentInterface(
        address=qbittorrent_address, logger=logger
    )

    hash = request.args.get("hash")
    if not hash:
        message = "Hash not found in torrent_complete request. Add as url argument, e.g. /torrent_complete?hash=abc123"
        logger.error(message)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": message,
                }
            ),
            400,
        )
    try:
        torrent_info = tor_interface.get_torrent_info(hash)
    except qbittorrent_interface.QbittorrentError as e:
        logger.error(e)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                }
            ),
            500,
        )
    name = torrent_info.get("name", hash)
    logger.info(f"Torrent found: {name}")
    logger.debug(f"Torrent info: {json.dumps(torrent_info, indent=2)}")
    if not torrent_info.get("category") == "audiobook":
        return (
            jsonify({"status": "success", "message": f"Non audiobook torrent: {name}"}),
            200,
        )

    import_books(torrent_info)

    return (
        jsonify({"status": "success", "message": f"Audiobook complete: {name}"}),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
