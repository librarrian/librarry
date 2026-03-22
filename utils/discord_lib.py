import requests
import os
from . import constants
from .audible_scrape import BookMetadata

GREEN = 48640
RED = 15466496
ORANGE = 16737792


def send_message(
    embed: dict = {},
    title: str | None = None,
    description: str | None = None,
    color: int | None = None,
):
    if not constants.DISCORD_WEBHOOK:
        return
    if not embed:
        if title:
            embed["title"] = title
        if description:
            embed["description"] = description
        if color:
            embed["color"] = color
    requests.post(
        constants.DISCORD_WEBHOOK,
        json={"embeds": [embed]},
        headers={"Content-Type": "application/json"},
    )


def embed_len(embed: dict):
    out = 0
    if embed.get("title"):
        out += len(embed["title"])
    if embed.get("description"):
        out += len(embed["description"])
    return out


def single_message(books: list[BookMetadata], torrent_name) -> list[dict]:
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
        not_found_title = (
            f"{len(not_found)} books not found for torrent '{torrent_name}'"
        )
    else:
        color = RED
        not_found_title = (
            f"No books found for torrent '{torrent_name}' ({len(not_found)} total)"
        )

    embeds = []
    if found:
        embeds.append(
            {
                "title": f"{len(found)} books found for torrent '{torrent_name}'",
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


def multiple_messages(books: list[BookMetadata], torrent_name: str) -> list[dict]:
    embeds = []
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
            continue
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
        description = f"""Audiobook torrent completed; importing to library. The following information has been found:

* **Author**: {book.author}
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
    return embeds


def send_book_info(books: list[BookMetadata], torrent_name: str, max_embeds: int):
    if not constants.DISCORD_WEBHOOK:
        return
    if len(books) > max_embeds:
        embeds = single_message(books, torrent_name)
    else:
        embeds = multiple_messages(books, torrent_name)
    for embed in embeds:
        send_message(embed=embed)
