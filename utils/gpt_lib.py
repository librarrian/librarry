from openai import OpenAI, OpenAIError
from openai.types.responses import ParsedResponseFunctionToolCall
import sys
import json
import os
from typing import List, Literal
import backoff
import logging
from . import schema, directory_tree, constants, audible_scrape
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
logger = logging.getLogger(__name__)

with open(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "prompts", "match_books.txt"
    ),
    "r",
) as f:
    MATCH_BOOKS_PROMPT = f.read()
with open(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "prompts", "group_files.txt"
    ),
    "r",
) as f:
    GROUP_FILES_PROMPT = f.read()


def serialize_as_json(input):
    if isinstance(input, list):
        for i, val in enumerate(input):
            input[i] = serialize_as_json(val)
    if isinstance(input, dict):
        for k, v in input.items():
            input[k] = serialize_as_json(v)
    if isinstance(input, ParsedResponseFunctionToolCall):
        return input.to_dict()
    return input


@backoff.on_exception(backoff.constant, RuntimeError, max_tries=3, interval=0)
def group_book_files(collection_name: str, root: directory_tree.Root) -> schema.Books:
    """Uses GPT to group files in a torrent into individual books.

    Torrent file structure is extremely inconsistent. When a torrent contains multiple books,
    it is non trivial to determine which files belong to which book. This function queries GPT
    to group files into individual books, which can then be looked up separately.

    Args:
        collection_name: The name of the collection to which the files belong (often the title of the torrent).
        root: The directory tree of all the files in the torrent, represented as a Root object.
            This object contains all files that need to be grouped, each with a numeric ID ranging from 1 to N,
            where N is the total number of files in the torrent.
    Returns:
        A Books object, which contains a list of Book objects. Each Book object contains a list
        has a title, a list of possible authors, and a list of file ID ranges that belong to that book.
    Raises:
        RuntimeError: If GPT fails to respond or is unable to group the files. This error is capture by backoff
        and will be retried up to `max_tries` times.
    """
    content = {"collection_name": collection_name, "files": root.to_dict()}
    client = OpenAI()
    inputs = [
        {
            "role": "system",
            "content": GROUP_FILES_PROMPT,
        },
        {
            "role": "user",
            "content": str(content),
        },
    ]
    try:
        response = client.responses.parse(
            model=constants.GPT_MODEL, input=inputs, text_format=schema.Books
        )
        logger.debug(
            f"Group files response: {json.dumps(response.to_dict(), indent=2)}"
        )
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI error: {e}")
    books = response.output_parsed
    logger.info(
        f"Books found: \n{"\n".join([f"'{book.title}' - {book.authors[0]}'" for book in books.books])}"
    )
    if not books:
        raise RuntimeError("Unable to group book files")
    return books


def create_books_input_content(books: schema.Books):
    """
    Transform a Books object into dictionary input content and file mappings.

    Converts a collection of books into two dictionaries: one containing book metadata
    indexed by ID, and another mapping book IDs to their associated files.

    Args:
        books (schema.Books): A Books object returned in a OpenAI response.

    Returns:
        A tuple containing:
            - input_content (dict[int, dict]): Dictionary mapping book IDs to book metadata dictionaries.
              Each metadata dict contains 'id', 'title', 'possible authors', and 'previous queries'.
            - files (dict): Dictionary mapping book IDs to lists of FileRange objects.
    """
    input_content = {}
    files: dict[int, list[schema.FileRange]] = {}
    i = 1
    for book in books.books:
        input_content[i] = {
            "id": i,
            "title": book.title,
            "possible authors": book.authors,
            "previous queries": [],
        }
        files[i] = book.files
        i += 1
    return input_content, files


def find_asins(input_books: dict):
    """
    Use GPT to find ASINs (Amazon Standard Identification Numbers) for books.

    Matching books to their ASINs enables scraping for book metadata. This function has GPT query
    audible, and refine its serach until all books are matched or the lookup limit is reached.

    Args:
        input_books (dict): A dictionary where each key is a book ID and each value contains
                           book information (e.g., title, author, series) and a list of
                           'previous queries' made for that book.

    Returns:
        list[schema.MatchedBook]: A list of matched books containing ASIN information and other
                                  relevant details retrieved from Audible.

    Raises:
        RuntimeError: If an OpenAI API error occurs during the request.

    Notes:
        - The function uses the Audible search tool via OpenAI's function calling feature.
        - It will loop until either all books are matched, no more function calls are returned,
          or the maximum number of lookups (constants.NUM_LOOKUPS) is exceeded.
        - Matched books are removed from input_books as they are found.
        - Previous queries for each book are tracked to avoid duplicate searches.
    """
    logger.debug(f"Fiding asins: {json.dumps(input_books, indent=2)}")
    client = OpenAI()

    tools = [
        {
            "type": "function",
            "name": "query_audible",
            "description": "Search Audible for books, given a query. Queries can be any combination of book title, book series, and author.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        # "description": "Text query string to provide to Audible search, e.g. 'The Lord of the Rings: The Fellowship of the Ring', 'All About Love', or 'Phillip K. Dick'.",
                        "description": "Text query string to provide to Audible search",
                    },
                    "id": {
                        "type": "integer",
                        "description": "The id of the book, as given by the user.",
                    },
                },
                "required": ["query", "id"],
                "additionalProperties": False,
            },
        }
    ]
    i = 0
    function_calls = True

    all_matches: list[schema.MatchedBook] = []

    i = 0
    function_calls = []
    while True:
        i += 1
        inputs = [
            {
                "role": "system",
                "content": MATCH_BOOKS_PROMPT,
            },
        ]
        for function_call in function_calls:
            params = json.loads(function_call.arguments)
            query: str = params["query"]
            id = params["id"]
            if id in input_books:
                result = audible_scrape.lookup_book(query)
                result = str(result).replace(", paths=[]", "")
                inputs.append(function_call)
                inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": result,
                    }
                )
                input_books[id]["previous queries"] += [query]
            logger.debug(input_books)
        inputs.append(
            {
                "role": "user",
                "content": str(list(input_books.values())),
            }
        )
        try:
            response = client.responses.parse(
                model=constants.GPT_MODEL,
                input=inputs,
                tools=tools,
                text_format=schema.MatchedBooks,
            )
            logging.debug(
                f"Find ASINs request: {json.dumps(serialize_as_json(inputs), indent=2)}"
            )
            logger.debug(
                f"Find ASINs response: {json.dumps(response.to_dict(), indent=2)}"
            )
        except OpenAIError as e:
            raise RuntimeError(f"OpenAI error: {e}")
        matched_books = response.output_parsed
        if matched_books:
            all_matches += matched_books.books
            for book in matched_books.books:
                del input_books[book.id]

        function_calls = []
        for output in response.output:
            if output.type == "function_call":
                function_calls.append(output)
        if not function_calls:
            break
        if i > constants.NUM_LOOKUPS:
            break
    return all_matches


@backoff.on_exception(backoff.constant, RuntimeError, max_tries=3, interval=0)
def gpt_scrape(
    input_content: dict,
    files_dict: dict[int, list[schema.FileRange]],
    root: directory_tree.Root,
) -> list[audible_scrape.BookMetadata]:
    output_books = find_asins(input_content)
    books: list[audible_scrape.BookMetadata] = []
    for book in output_books:
        metadatas = audible_scrape.maybe_get_books_data([book.asin])
        metadata = metadatas[0] if metadatas else audible_scrape.BookMetadata()
        for file_range in files_dict[book.id]:
            for i in range(file_range.start, file_range.end):
                metadata.paths.append(root.all_files[i].full_path)
        books.append(metadata)
    logger.info(
        f"Matched books:\n{
            "\n".join([
                f"{book.asin} - {book.title}" 
                for book in books
            ])}"
    )
    if not books:
        raise RuntimeError("No books found in the response from GPT.")

    return books


def find_books(
    collection_name: str, files: list[str]
) -> list[audible_scrape.BookMetadata]:
    """Given a collection name and a list of files, group files into individual books and return
    with metadata

    Uses ChatGPT and scraping of audible to group files into books and retrieve metadata. Returns
    the books as dictionaries containing
    """

    root = directory_tree.Root()
    for file in files:
        root.add_file(file)
    book_files = group_book_files(collection_name, root)
    input_content, files_dict = create_books_input_content(book_files)
    return gpt_scrape(input_content, files_dict, root)
