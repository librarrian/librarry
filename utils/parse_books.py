import os
import requests
import backoff
import logging
import json
import re
from .gpt_lib import find_books

# import gpt_lib

qbittorrent_address = os.environ.get("QBITTORRENT_ADDRESS", "http://localhost:8080")
logger = logging.getLogger(__name__)


@backoff.on_predicate(backoff.expo, lambda x: x == [], max_time=120)
@backoff.on_exception(backoff.expo, RuntimeError, max_time=120)
def get_files(hash: str) -> list[str]:
    response = requests.get(f"{qbittorrent_address}/api/v2/torrents/files?hash={hash}")
    if response.status_code != 200:
        raise RuntimeError(f"Failed to get torrent info for hash {hash}")
    files = []
    for file in response.json():
        _, extension = os.path.splitext(file["name"])
        if file["priority"] > 0 and extension in {".m4a", ".m4b", ".mp3", ".flac"}:
            files.append(os.path.join("/audiobooks", file["name"]))
    return sorted(files)


def get_book_data(
    torrent_info: dict[str : str | int],
) -> list[dict]:

    files = get_files(torrent_info["hash"])
    logger.debug(f"Files found for {torrent_info['name']}: {files}")

    books = find_books(torrent_info["name"], files)
    found = [book for book in books if book.get("asin")]

    # json_file = re.sub(r"[^a-zA-Z0-9\s\.\-_]", "", torrent_info["name"])[:200]
    # with open(f"/tmp/{json_file}.json", "w") as f:
    #     json.dump(found, f)
    # with open(f"/tmp/{json_file}.json", "r") as f:
    #     found = json.load(f)

    # send_discord_message(found, torrent_name, max_embeds)
    return found
