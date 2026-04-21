import requests
import os
from . import constants
from .audible_scrape import BookMetadata

GREEN = 48640
RED = 15466496
ORANGE = 16737792


def send_message(
    embed: dict | None = None,
    title: str | None = None,
    description: str | None = None,
    color: int | None = None,
    thumbnail: str | None = None,
):
    if not constants.DISCORD_WEBHOOK:
        return
    if not embed:
        embed = {}
    if title:
        embed["title"] = title
    if description:
        embed["description"] = description
    if color:
        embed["color"] = color
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    requests.post(
        constants.DISCORD_WEBHOOK,
        json={"embeds": [embed]},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )


def embed_len(embed: dict):
    out = 0
    if embed.get("title"):
        out += len(embed["title"])
    if embed.get("description"):
        out += len(embed["description"])
    return out


def single_message(
    books: list[BookMetadata], torrent_name: str, torrent_complete: bool
) -> list[dict]:
    found = []
    not_found = []

    for book in books:
        if not book.asin:
            not_found.append(f"* {book.paths[0] if book.paths else ""}\n")
        else:
            found.append(
                f"* **{book.title}**: {book.author}\n  * {book.asin}\n  * {book.paths[0] if book.paths else ""}\n"
            )

    if found:
        if not_found:
            color = ORANGE
        else:
            color = GREEN
        not_found_title = f"{len(not_found)} book(s) not found"
    else:
        color = RED
        not_found_title = f"'{torrent_name}' {"completed. " if torrent_complete else "started. "}No books found ({len(not_found)} total)"

    embeds = []
    if found:
        embeds.append(
            {
                "title": f"'{torrent_name}' {"completed. " if torrent_complete else "started. "}{len(found)} book(s) found",
                "color": color,
                "description": "",
            }
        )
    max_embed_length = 4000
    for book in found:
        if embed_len(embeds[-1]) + len(book) > max_embed_length:
            embeds.append({"title": "", "color": color, "description": ""})
        embeds[-1]["description"] += book

    if not_found:
        embeds.append(
            {
                "title": not_found_title,
                "color": RED,
                "description": "",
            }
        )
    for book in not_found:
        if embed_len(embeds[-1]) > max_embed_length:
            embeds.append({"title": "", "color": RED, "description": ""})
        embeds[-1]["description"] += book
    return embeds


def multiple_messages(
    books: list[BookMetadata], torrent_name: str, torrent_complete: bool
) -> list[dict]:
    embeds = []
    found = 0
    not_found = 0
    for book in books:
        dir = ""
        if len(book.paths) == 1:
            dir = book.paths[0]
        elif len(book.paths) > 1:
            dir = os.path.dirname(book.paths[0])

        if not book.asin:
            embeds.append(
                {
                    "title": "Book not found",
                    "description": f"No ASIN found for book in {dir}",
                    "color": RED,
                }
            )
            not_found = not_found + 1
            continue
        found = found + 1
        paths_string = ""
        if book.paths:
            book.paths
            if len(book.paths) == 1:
                paths_string = f"* **Path**: {book.paths[0]}"
            elif len(book.paths) > 1:
                if os.path.dirname(book.paths[-1]) == dir:
                    paths_string = (
                        f"* **Paths**: {dir} \n  "
                        f"* (1) {os.path.basename(book.paths[0])}\n  "
                        f"* ({len(book.paths)}) {os.path.basename(book.paths[-1])}"
                    )
                else:
                    paths_string = (
                        f"* **Paths**:\n  "
                        f"* (1) {book.paths[0]}\n  "
                        f"* ({len(book.paths)}) {book.paths[-1]}"
                    )
        description = f"""* **Author**: {book.author}
* **Length**: {book.length}
* **Year**: {book.year}
* **Narrators**: {book.narrators}
* **ASIN**: {book.asin}
* **Torrent Name**: {torrent_name}
{paths_string}
"""
        embeds.append(
            {
                "title": book.title,
                "description": description,
                "color": GREEN,
                "url": f"https://www.audible.com/pd/{book.asin}",
                "thumbnail": {"url": book.image},
            }
        )
    color = RED if found == 0 else (ORANGE if not_found > 0 else GREEN)
    embeds = [
        {
            "title": f"Torrent '{torrent_name}' {"**completed**." if torrent_complete else "**started**."}",
            "description": (
                f"{f"{found} book(s) matched. " if found > 0 else ""}"
                f"{f"{not_found} book(s) not matched." if not_found > 0 else ""}"
            ),
            "color": color,
        }
    ] + embeds
    return embeds


def send_book_info(
    books: list[BookMetadata], torrent_name: str, torrent_complete: bool
):
    if not constants.DISCORD_WEBHOOK:
        return
    if len(books) > constants.MAX_EMBEDS:
        embeds = single_message(books, torrent_name, torrent_complete)
    else:
        embeds = multiple_messages(books, torrent_name, torrent_complete)
    for embed in embeds:
        send_message(embed=embed)
