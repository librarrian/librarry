from flask import Flask, request, jsonify
import os
import logging
import json
import requests
import sys


from utils import qbittorrent_interface, constants, logging_setup
from utils.import_to_library import import_books

logging_setup.run()
constants.validate_env()

app = Flask(__name__)

app.logger.propagate = True
logger = logging.getLogger(__name__)


@app.route("/torrent_complete", methods=["POST"])
def interactions():
    tor_interface = qbittorrent_interface.QBittorrentInterface(
        address=constants.QBITTORRENT_ADDRESS, logger=logger
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


@app.route("/health_check", methods=["GET"])
def health_check():
    return jsonify({"status": "success", "message": "Server is healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=constants.FLASK_PORT, debug=True)
