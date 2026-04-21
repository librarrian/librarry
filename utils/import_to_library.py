import logging
from dataclasses import asdict, fields
import json
import contextlib
import tempfile
import re
import os
import shutil
import redis
import backoff
from concurrent.futures import ThreadPoolExecutor, as_completed
import audiobook_tool
from . import parse_books, constants, discord_lib
from .audible_scrape import BookMetadata

logger = logging.getLogger(__name__)

PROCESSING_STRING = "PROCESSING"


class FakeRedis:
    def set(self, *args, **kwargs):
        return

    def getdel(self, *args, **kwargs):
        return


if constants.REDIS_HOST:
    r = redis.Redis(
        constants.REDIS_HOST,
        int(constants.REDIS_PORT),
        int(constants.REDIS_DB),
        decode_responses=True,
    )
else:
    r = FakeRedis
    logger.warning("No Redis host given. Cannot utilize database.")


class ProcessingError(Exception):
    pass


def mark_processing(torrent_hash: str):
    r.set(
        torrent_hash,
        PROCESSING_STRING,
        ex=int(constants.REDIS_TTL_HOURS) * 3600,
    )


# @backoff.on_predicate(backoff.expo, lambda x: x == PROCESSING_STRING, max_time=600)
@backoff.on_exception(backoff.expo, ProcessingError, max_time=600, logger=None)
def read_database(torrent_info: dict) -> str | None:
    try:
        books_string = r.get(torrent_info["hash"])
        if books_string == PROCESSING_STRING:
            logger.info("Import book: Torrent still processing...")
            raise ProcessingError(
                f"Torrent '{torrent_info["name"]}' still processing from import."
            )
        r.delete(torrent_info["hash"])
        return books_string
    except ConnectionError:
        logger.warning(
            "Unable to connect to Redis database: %s:%s - db:%s",
            constants.REDIS_HOST,
            constants.REDIS_PORT,
            constants.REDIS_DB,
        )
        return None


def save_book_data(torrent_info: dict) -> None:
    books = parse_books.get_book_data(torrent_info)
    try:
        discord_lib.send_book_info(books, torrent_info["name"], torrent_complete=False)
    except Exception as e:
        r.delete(torrent_info["hash"])
        raise e
    r.set(
        torrent_info["hash"],
        json.dumps([asdict(book) for book in books]),
        ex=int(constants.REDIS_TTL_HOURS) * 3600,
    )
    logger.info("Book data saved to database for '%s'", torrent_info["name"])


def import_books(torrent_info: dict, overwrite: bool) -> None:
    full_discord_message = True
    books_string = read_database(torrent_info)
    logging.debug("Read from databas: %s", books_string)
    torrent_name = torrent_info["name"]
    if not books_string:
        logger.debug("No book data found in database for '%s'", torrent_name)
        books = parse_books.get_book_data(torrent_info)
    else:
        logger.info("Book data retrieved from database for '%s'", torrent_name)
        try:
            books = [BookMetadata(**book) for book in json.loads(books_string)]
            if len([book for book in books if book.asin]) == 0:
                logger.warning(
                    "No ASINS found in database for '%s', retrying lookup.",
                    torrent_name,
                )
                books = parse_books.get_book_data(torrent_info)
            else:
                full_discord_message = False
        except json.JSONDecodeError:
            logger.error("Raw data could not be decoded to json: '%s'", books_string)
            books = parse_books.get_book_data(torrent_info)
        except TypeError as e:
            logger.error("Failed to convert raw data to BookMetdata: %s", e)
            logger.error("Raw data: %s", books_string)
            logger.error(
                "\nBookMetadata:\n  %s",
                {"\n  ".join([f"{f.name}: {f.type}" for f in fields(BookMetadata)])},
            )
            books = parse_books.get_book_data(torrent_info)

    if full_discord_message:
        discord_lib.send_book_info(books, torrent_name, torrent_complete=True)
    logger.debug(
        "Books found: %s",
        {"\n".join([json.dumps(asdict(book), indent=2) for book in books])},
    )

    errors = []
    for book in books:
        with contextlib.ExitStack() as stack:
            if len(book.paths) == 1 and (
                book.paths[0].endswith(".m4b") or book.paths[0].endswith(".m4a")
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
                logger.info("Moving '%s' to library", book.title)
                audiobook_tool.process_audiobook(
                    path,
                    constants.AUDIOBOOKS_DIR,
                    book.asin,
                    merge=False,
                    force=overwrite,
                )
                logger.info("%s imported!", book.title)
                discord_lib.send_message(
                    description=f"{book.title} imported to library!",
                    color=discord_lib.GREEN,
                )

            except FileExistsError as e:
                logger.error("%s", e)
                overwrite_command = (
                    f'docker exec librarry sh -c "'
                    f'curl -X POST \\"http://localhost:{constants.FLASK_PORT}/torrent_complete'
                    f'?hash_v1={torrent_info["hash"]}&overwrite=true\\""'
                )
                logger.error("To overwrite, run `%s`", overwrite_command)
                discord_lib.send_message(
                    title=f"Audiobook '{book.title}' already in library",
                    description=(f"Overwrite:\n```{overwrite_command}```"),
                    color=discord_lib.RED,
                    thumbnail=book.image,
                )
                errors.append(e)
    if errors:
        raise FileExistsError("\n".join([str(e) for e in errors]))
