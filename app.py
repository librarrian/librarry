from flask import Flask, request, jsonify, wrappers
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


def get_torrent_info(
    request: wrappers.Request, torrent_info: dict
) -> tuple[wrappers.Response, int] | None:
    hash = request.args.get("hash")
    tor_interface = qbittorrent_interface.QBittorrentInterface(
        address=constants.QBITTORRENT_ADDRESS
    )
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
        torrent_info.update(tor_interface.get_torrent_info(hash))
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
    if "name" not in torrent_info:
        torrent_info["name"] = ""
    return


@app.route("/torrent_complete", methods=["POST"])
def torrent_complete():
    torrent_info = {}
    response = get_torrent_info(request, torrent_info)
    if response:
        return response

    name = torrent_info["name"]
    logger.info(f"Torrent found: {name}")
    logger.debug(f"Torrent info: {json.dumps(torrent_info, indent=2)}")
    if not torrent_info.get("category") == "audiobook":
        return (
            jsonify({"status": "success", "message": f"Non audiobook torrent: {name}"}),
            200,
        )

    overwrite = {
        "true": True,
        "1": True,
        "false": False,
        "0": False,
    }.get(request.args.get("overwrite", "false").lower(), False)
    try:
        import_books(torrent_info, overwrite=overwrite)
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"{e}"}),
            500,
        )

    return (
        jsonify({"status": "success", "message": f"Audiobook complete: {name}"}),
        200,
    )


@app.route("/health_check", methods=["GET"])
def health_check():
    return jsonify({"status": "success", "message": "Server is healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=constants.FLASK_PORT, debug=True)
