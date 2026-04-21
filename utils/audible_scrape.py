import urllib.parse
import requests
import urllib
from bs4 import BeautifulSoup
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BookMetadata:
    asin: str = ""
    author: str = ""
    title: str = ""
    year: str = ""
    length: str = ""
    narrators: str = ""
    publisher: str = ""
    image: str = ""
    paths: list[str] = field(default_factory=list)


def get_book_data(
    asin: str,
) -> BookMetadata:
    """fetches book metadata from the audnexus api.

    Args:
        asin: The ASIN of the book to fetch data for.
    Returns:
        A dictionary containing the book's metadata, including:
            - asin: The ASIN of the book.
            - author: The author of the book.
            - title: The title of the book.
            - year: The release year of the book.
            - length: The length of the book in HH:MM format.
            - narrators: A comma-separated list of narrators of the book.
            - publisher: The publisher of the book.
            - image: The URL of the book's cover image.
    Raises:
        RuntimeError: If the API request fails or returns an error.
    """
    url = f"https://api.audnex.us/books/{asin}"
    api_call = requests.get(url)
    book_data = api_call.json()
    logger.debug(f"Audnexus repsonse: {book_data}")
    if not api_call.ok:
        message = f"Get request failed: {book_data}"
        logger.info(message)
        raise RuntimeError(message)
    hours, minutes = divmod(book_data["runtimeLengthMin"], 60)
    metadata = BookMetadata(
        asin=asin,
        author=book_data["authors"][0]["name"],
        title=book_data["title"],
        year=book_data["releaseDate"].split("-")[0],
        length=f"{hours:02d}:{minutes:02d}",
        narrators=", ".join(
            [narrator["name"] for narrator in book_data["narrators"]][0:5]
        )
        + (", ..." if len(book_data["narrators"]) > 5 else ""),
        publisher=book_data["publisherName"],
        image=book_data["image"],
    )
    return metadata


def maybe_get_books_data(asins: list[str]) -> list[BookMetadata]:
    """Fetches book metadata for a list of ASINs, ignoring any that fail.

    Args:
        asins: A list of ASINs to fetch data for.
    Returns:
        A list of dictionaries containing metadata for each successfully fetched book.
        See get_book_data for the structure of each dictionary.
    Raises:
        None. Any ASINs that fail to fetch will be ignored.
    """

    out = []
    for asin in asins:
        try:
            out.append(get_book_data(asin))
        except RuntimeError:
            pass
    return out


def lookup_book(query: str, limit: int = 20) -> list[BookMetadata]:
    """Retrieve book data from Audible and Audnexus based on a search query.

    First queries Audible for all ASINs displayed on the search results page for the given query,
    then looks up each ASIN in the Audnexus API to retrieve metadata for each book.
    Any ASINs that fail to fetch from Audnexus are ignored.

    Args:
        query: The search query to use.
        limit: The maximum number of search results to include.
    Returns:
        A list of dictionaries containing metadata for each successfully fetched book.
        See get_book_data for the structure of each dictionary.
    """
    logger.info(f"Querying Audible: {query}")
    results = requests.get(
        f"https://www.audible.com/search?keywords={urllib.parse.quote_plus(query)}"
    )
    soup = BeautifulSoup(results.content, "html.parser")
    book_divs = soup.find_all("div", class_="adbl-asin-impression")
    asins = []
    for i, book in enumerate(book_divs):
        if i > limit:
            break
        asins.append(book["data-asin"])
    logger.debug(f"ASINs found: {asins}")
    return maybe_get_books_data(asins)
