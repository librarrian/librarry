import requests
import logging
from . import constants

logger = logging.getLogger(__name__)


def get_magnet(url: str | None):
    if not url:
        logger.error(
            f"Error fetching magnet URL: empty link",
        )

    try:
        if url.startswith("magnet:"):
            return url
        url = url.replace(
            constants.JACKETT_PUBLIC_ADDRESS, constants.JACKETT_INTERNAL_ADDRESS
        )
        response = requests.get(url, allow_redirects=False, timeout=60)
        if response.status_code in [301, 302]:
            return response.headers.get("Location", url)
    except Exception as e:
        logger.error(f"Error fetching magnet URL: %s", e)
        return url
    return url


def lookup_books(query):
    response = requests.get(
        f"{constants.JACKETT_INTERNAL_ADDRESS}/api/v2.0/indexers/all/results?"
        f"apikey={constants.JACKETT_API_KEY}&Query={query}&Tracker%5B%5D=audiobookbay",
        timeout=60,
    )
    if response.status_code != 200:
        logger.error("Error reading jackett: %s", response.text)
    try:
        logger.info(response.text)
        books = response.json()["Results"]
    except Exception as e:
        logger.error("Error reading jackett: %s", response.text)
        raise e
    # for book in books:
    #     if not book.get("MagnetUri"):
    #         book["MagnetUri"] = get_magnet(book.get("Link"))
    return books
