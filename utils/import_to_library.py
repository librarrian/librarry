import logging
from dataclasses import asdict
import json
import contextlib
import tempfile
import re
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import audiobook_tool
from . import parse_books, constants, discord_lib

logger = logging.getLogger(__name__)


def save_book_data(torrent_info: dict) -> None:
    books = parse_books.get_book_data(torrent_info)
    discord_lib.send_book_info(books, torrent_info["name"], torrent_complete=False)


def import_books(torrent_info: dict, overwrite: bool) -> None:
    books = parse_books.get_book_data(torrent_info)

    discord_lib.send_book_info(books, torrent_info["name"], torrent_complete=True)

    logging.debug(
        f"Books found: {'\n'.join([json.dumps(asdict(book), indent=2) for book in books])}"
    )
    for book in books:
        with contextlib.ExitStack() as stack:
            if (
                len(book.paths) == 1
                and book.paths[0].endswith(".m4b")
                or book.paths[0].endswith(".m4a")
            ):
                path = book.paths[0]
                merge = False
            else:
                path = stack.enter_context(tempfile.TemporaryDirectory())
                merge = True
                for file in book.paths:
                    filename = re.sub(
                        r"[^a-zA-Z0-9\s\.\-_]", "", os.path.basename(file)
                    )
                    shutil.copy(file, os.path.join(path, filename))

            try:
                logging.info(f"Moving '{book.title}' to library")
                audiobook_tool.process_audiobook(
                    path,
                    constants.AUDIOBOOKS_DIR,
                    book.asin,
                    merge=merge,
                    force=overwrite,
                )
                logging.info(f"{book.title} imported!")
            except FileExistsError as e:
                logging.error("%s", e)
                logging.error(
                    f'To overwrite, run `docker exec librarry sh -c "'
                    f'curl -X POST \\"http://localhost:{constants.FLASK_PORT}/torrent_complete'
                    f'?hash={torrent_info["hash"]}&overwrite=true\\""`'
                )
                discord_lib.send_message(
                    title="Audiobook already in library",
                    description=(
                        "Overwrite:\n"
                        f'```docker exec librarry sh -c "'
                        f'curl -X POST \\"http://localhost:{constants.FLASK_PORT}/torrent_complete'
                        f'?hash={torrent_info["hash"]}&overwrite=true\\""```'
                    ),
                    color=discord_lib.RED,
                )
                raise e
