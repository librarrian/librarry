import requests
import logging
from . import environment

logger = logging.getLogger(__name__)

SOURCE = "jackett"

def make_jackett_url_public(url: str) -> str:
    return url.replace(
        environment.JACKETT_INTERNAL_ADDRESS, environment.JACKETT_PUBLIC_ADDRESS
    )


def get_magnet(url: str) -> str:
    if not url:
        logger.error(
            f"Error fetching magnet URL: empty link",
        )

    try:
        logging.info("Fetching magnet URL for: %s", url)
        if url.startswith("magnet:"):
            return url
        response = requests.get(url, allow_redirects=False, timeout=60)
        logger.info(
            "code: %s, Redirected URL: %s",
            response.status_code,
            response.headers.get("Location"),
        )
        if response.status_code in [301, 302]:
            return response.headers.get("Location", url)
    except Exception as e:
        logger.error(f"Error fetching magnet URL: %s", e)
        return url
    return url


def lookup_books(query):
    response = requests.get(
        f"{environment.JACKETT_INTERNAL_ADDRESS}/api/v2.0/indexers/all/results?"
        f"apikey={environment.JACKETT_API_KEY}&Query={query}&Tracker%5B%5D=audiobookbay",
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
    for book in books:
        logger.info(book)
        if book.get("MagnetUri"):
            book["Link"] = book["MagnetUri"]
        if book.get("Poster"):
            book["Poster"] = make_jackett_url_public(book["Poster"])
        book["Source"] = SOURCE
        yield book
