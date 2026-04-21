import os
import requests
import backoff
import logging
import json
import re
from . import constants, gpt_lib
from .audible_scrape import BookMetadata

logger = logging.getLogger(__name__)


@backoff.on_predicate(backoff.expo, lambda x: x == [], max_time=120)
@backoff.on_exception(backoff.expo, RuntimeError, max_time=120)
def get_files(hash: str) -> list[str]:
    response = requests.get(
        f"{constants.QBITTORRENT_ADDRESS}/api/v2/torrents/files?hash={hash}"
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to get torrent info for hash {hash}")
    files = []
    for file in response.json():
        _, extension = os.path.splitext(file["name"])
        if file["priority"] > 0 and extension in {".m4a", ".m4b", ".mp3", ".flac"}:
            files.append(os.path.join("/audiobooks", file["name"]))
    return sorted(files)


def get_book_data(
    torrent_info: dict,
) -> list[BookMetadata]:

    files = get_files(torrent_info["hash"])
    torrent_name = torrent_info["name"]
    logger.debug(f"Files found for {torrent_name}: {files}")

    books = gpt_lib.find_books(torrent_name, files)
    found = [book for book in books if book.asin]

    return found
