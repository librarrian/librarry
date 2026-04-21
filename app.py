import logging
import json
from flask import (
    Flask,
    request,
    jsonify,
    wrappers,
    abort,
    send_from_directory,
    render_template,
)
from utils import constants, logging_setup

logging_setup.run()
from utils import import_to_library, qbittorrent_interface, jackett


constants.validate_env()

app = Flask(__name__)

app.logger.propagate = True
logger = logging.getLogger(__name__)


class ImmediateResponse(Exception):
    def __init__(self, response: wrappers.Response, code: int):
        self.response = (response, code)


def get_hash(request: wrappers.Request) -> str:
    torrent_hash = request.args.get("hash_v1")
    if not torrent_hash:
        torrent_hash = request.args.get("hash_v2")
    if not torrent_hash:
        message = "Neither hash_v1 nor hash_v2 not found in torrent_complete request. Add as url argument, e.g. /torrent_complete?hash_v1=abc123"
        logger.error(message)
        raise ImmediateResponse(
            jsonify(
                {
                    "status": "error",
                    "message": message,
                }
            ),
            400,
        )
    return torrent_hash


def get_torrent_info(torrent_hash: str) -> dict:
    tor_interface = qbittorrent_interface.QBittorrentInterface(
        address=constants.QBITTORRENT_ADDRESS
    )
    try:
        torrent_info = tor_interface.get_torrent_info(torrent_hash)
    except qbittorrent_interface.QbittorrentError as e:
        logger.error(e)
        raise ImmediateResponse(
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                }
            ),
            500,
        ) from e
    if "name" not in torrent_info:
        torrent_info["name"] = ""
    if not torrent_info.get("category") == "audiobook":
        raise ImmediateResponse(
            jsonify(
                {
                    "status": "success",
                    "message": f"Non audiobook torrent: {torrent_info["name"]}",
                }
            ),
            200,
        )
    return torrent_info


@app.route("/torrent_added", methods=["POST"])
def torrent_added():
    logger.info(
        "\n\n\n----------------------------------------------------TORRENT ADDED----------------------------------------------------"
    )
    try:
        torrent_hash = get_hash(request)
        import_to_library.mark_processing(torrent_hash)
        torrent_info = get_torrent_info(torrent_hash)
    except ImmediateResponse as e:
        return e.response

    name = torrent_info["name"]
    logger.info("Torrent found: %s", name)
    logger.debug("Torrent info: %s", {json.dumps(torrent_info, indent=2)})
    import_to_library.save_book_data(torrent_info)
    return (
        jsonify({"status": "success", "message": f"Audiobook data found: {name}"}),
        200,
    )


@app.route("/torrent_complete", methods=["POST"])
def torrent_complete():
    logger.info(
        "\n\n\n----------------------------------------------------TORRENT COMPLETE----------------------------------------------------"
    )
    try:
        torrent_hash = get_hash(request)
        torrent_info = get_torrent_info(torrent_hash)
    except ImmediateResponse as e:
        return e.response
    name = torrent_info["name"]
    logger.info("Torrent found: %s", name)
    logger.debug("Torrent info: %s", {json.dumps(torrent_info, indent=2)})
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
        import_to_library.import_books(torrent_info, overwrite=overwrite)
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


@app.route("/logs/<level>")
# @app.route("/logs/<level>/<duplicate>")
# def logs(level: str, duplicate: int):
def logs(level: str):
    file = {
        "debug": "debug.log",
        "info": "info.log",
        "warning": "warning.log",
        "error": "error.log",
        "critical": "critical.log",
    }.get(level.lower())
    if file:
        return send_from_directory(constants.LOG_DIR, file)
    else:
        abort(404)


@app.route("/add_torrent", methods=["GET", "POST"])
def add_torrent():
    link = request.json.get("link")
    if not link:
        abort(500)
    tor_interface = qbittorrent_interface.QBittorrentInterface(
        address=constants.QBITTORRENT_ADDRESS
    )
    tor_interface.add_torrent(link)
    return (
        jsonify({"status": "success", "message": f"Torrent added!"}),
        200,
    )


@app.route("/", methods=["GET", "POST"])
def main():
    books = []
    query = ""
    if request.method == "POST":
        query = request.form["query"]
        if query:
            books = jackett.lookup_books(query)
    for book in books:
        logger.info("Found book: %s", book.get("Title"))
    return render_template("search.html", books=books, query=query)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=constants.FLASK_PORT, debug=True)
