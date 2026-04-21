from . import parse_books
import logging

logger = logging.getLogger(__name__)


def import_books(torrent_info: dict[str : str | int]) -> None:
    books = parse_books.get_book_data(torrent_info)
    import json

    logging.debug(
        f"Books found: {'\n'.join([json.dumps(book, indent=2) for book in books])}"
    )
