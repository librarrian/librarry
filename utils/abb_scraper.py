from collections.abc import Generator
from bs4 import BeautifulSoup
import requests
from urllib.parse import quote
import datetime
import logging
import re
from . import environment

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}
TRACKERS: set[str] = set()
TRACKERS_UPDATE_TIME = datetime.datetime.fromtimestamp(0)
FLARESOLVERR_SESSION = "audiobookbay"
SOURCE = "scrape"


class AudioBookBayError(Exception):
    pass


def create_flaresolverr_session():
    requests.post(
        f"{environment.FLARESOLVERR_ADDRESS}/v1",
        json={"cmd": "sessions.create", "session": FLARESOLVERR_SESSION},
    )


def destroy_flaresolverr_session():
    requests.post(
        f"{environment.FLARESOLVERR_ADDRESS}/v1",
        json={"cmd": "sessions.destroy", "session": FLARESOLVERR_SESSION},
    )


def get_html(url: str) -> str:
    if not environment.FLARESOLVERR_ADDRESS:
        response = requests.get(url, headers=HEADERS, timeout=60)
        if not response.ok:
            logger.error(f"Error fetching URL {url}: {response.status_code}")
            raise AudioBookBayError(
                f"HTTP error {response.status_code} for URL '{url}': {response.text}"
            )
        return response.text

    response = requests.post(
        f"{environment.FLARESOLVERR_ADDRESS}/v1",
        json={
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
            "session": FLARESOLVERR_SESSION,
        },
    )
    data = response.json()
    if data["status"] != "ok":
        logger.error(
            f"Failed to fetch URL with FlareSolverr: {data.get('message', 'Unknown error')}"
        )
        raise AudioBookBayError(
            f"FlareSolverr error: {data.get('message', 'Unknown error')}"
        )
    return data["solution"]["response"]


def update_trackers():
    global TRACKERS, TRACKERS_UPDATE_TIME
    if TRACKERS and (
        datetime.datetime.now() - TRACKERS_UPDATE_TIME
    ) < datetime.timedelta(days=1):
        return
    response = requests.get(
        "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt",
        timeout=60,
    )
    if response.status_code != 200:
        logger.error(f"Error fetching trackers: {response.status_code}")
        return
    trackers = set()
    for line in response.text.splitlines():
        line = line.strip()
        if line:
            trackers.add(line)
    TRACKERS_UPDATE_TIME = datetime.datetime.now()
    TRACKERS = trackers
    logger.info("Fetched %d trackers from ngosang/trackerslist", len(TRACKERS))
    logger.debug("Trackers: %s", ", ".join(list(TRACKERS)))
    return


def get_book_details(
    book: dict[str, str],
) -> dict[str, str] | None:
    html = get_html(book["Details"])
    soup = BeautifulSoup(html, "html.parser")
    hash_val = None
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2 and cells[0].get_text(strip=True).lower().startswith(
            "info hash:"
        ):
            hash_val = cells[1].get_text(strip=True)
    if not hash_val:
        logger.error(
            f"Error fetching book details for {book['Title']} ({book['Details']}): No hash found"
        )
        raise AudioBookBayError(f"No hash found for book: {book['Title']}")
    tr_params = "&".join(f"tr={quote(t, safe='')}" for t in TRACKERS)
    magnet = (
        f"magnet:?xt=urn:btih:{hash_val}&dn={quote(book['Title'], safe='')}&{tr_params}"
    )
    book["Link"] = magnet
    logger.info(f"Book discovered: {book['Title']}")
    postContent = soup.find("div", class_="postContent")
    book["Poster"] = ""
    if postContent:
        img = postContent.select("p img")
        if img:
            book["Poster"] = str(img[0].get("src", ""))
    logger.debug("%s: %s", book["Title"], book)
    return book


def get_magnet_link(url: str, book_title: str) -> str:
    update_trackers()
    html = get_html(url)
    soup = BeautifulSoup(html, "html.parser")
    hash_val = None
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2 and cells[0].get_text(strip=True).lower().startswith(
            "info hash:"
        ):
            hash_val = cells[1].get_text(strip=True)
    if not hash_val:
        logger.error(f"Error fetching book details for {book_title}: No hash found")
        raise AudioBookBayError(f"No hash found for book: {book_title}")
    tr_params = "&".join(f"tr={quote(t, safe='')}" for t in TRACKERS)
    logger.info(f"book_title: {type(book_title)}")

    return f"magnet:?xt=urn:btih:{hash_val}&dn={quote(book_title, safe='')}&{tr_params}"


def get_books(
    query: str, title_only: bool = True, base_url: str = "https://audiobookbay.lu"
) -> Generator[dict[str, str]]:  # list[dict[str, str]]:
    query = quote(query.lower(), safe="")
    url = f"{base_url}?s={query}{"&tt=1" if title_only else ""}"
    logger.info("Search URL: %s", url)
    html = get_html(url)
    logger.info("Fetched search results for query: %s", query)
    soup = BeautifulSoup(html, "html.parser")
    book_divs = soup.find_all("div", class_="post")

    for div in book_divs:
        book: dict[str, str] = {}
        post_title = div.find("div", class_="postTitle")
        if not post_title:
            continue
        a = post_title.find("a")
        if not a:
            continue
        title = a.text
        link = a.get("href")
        if not link or not title:
            continue
        book["Title"] = title
        book["Details"] = f"{base_url}{link}"

        post_content = div.find("div", class_="postContent")
        book["Poster"] = ""
        if post_content:
            img = post_content.find("img")
            if img:
                book["Poster"] = str(img.get("src", ""))
        match = re.search(r"Posted:\s+(\d\s+\w+\s+\d+)", str(post_content))
        book["Date"] = match.group(1) if match else ""
        match = re.search(r"Format:\s+<[^>]+>([^<]*)", str(post_content))
        book["Format"] = match.group(1) if match else ""
        match = re.search(r"Bitrate:\s+<[^>]+>([^<]*)", str(post_content))
        book["Bitrate"] = match.group(1) if match else ""
        match = re.search(
            r"File Size:\s+<[^>]+>([^<]*)<[^>]*>([^<]*)", str(post_content)
        )
        if match:
            book["fileSize"] = f"{match.group(1).strip()} {match.group(2).strip()}"
        else:
            book["fileSize"] = ""
        post_info = div.find("div", class_="postInfo")
        match = re.search(r"Language:\s([^<]+)", str(post_info))
        book["Language"] = match.group(1) if match else ""

        logger.info("Found book: %s", title)
        logger.debug("Book details: %s", book)
        for key, value in book.items():
            if value == "?":
                book[key] = ""
        book["Link"] = book["Details"]
        book["Source"] = SOURCE
        yield book

    #     found_books.append(book)
    # if not found_books:
    #     logger.info("No books found for query: %s", query)
    #     return []
    # update_trackers()
    # # books=[]
    # for found_book in found_books:
    #     try:
    #         book = get_book_details(found_book)
    #         if book:
    #             yield book
    #             # books.append(book)
    #     except Exception as e:
    #         logger.error(f"Error fetching details for book {found_book['Title']}: {e}")
    # # logger.info(f"Total books found: {len(found_books)}")
    # return books


# import sys
# for book in get_books(sys.argv[1]):
#     print(book)
