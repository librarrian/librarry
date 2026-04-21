from openai import OpenAI, OpenAIError
import sys

# from . import audible_scrape
# from . import dir


import json
import os
from typing import List, Literal
import backoff
import logging
from . import schema, directory_tree, constants, audible_scrape

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
        logger.debug(f"Group files input: {inputs}")
        response = client.responses.parse(
            model=constants.GPT_MODEL, input=inputs, text_format=schema.Books
        )
        logger.debug(f"Group files response: {response}")
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI error: {e}")
    books = response.output_parsed
    logger.info(f"Books found: {[book.title for book in books.books]}")
    if not books:
        raise RuntimeError("Unable to group book files")
    return books


def create_books_input_content(books: schema.Books):
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
    logger.info(f"Fiding asins: {input_books}")
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

                inputs.append(function_call)
                inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": str(result),
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
            logger.debug(response)
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
) -> list[dict]:
    output_books = find_asins(input_content)
    logger.info(f"Matched books: {"\n".join([book.asin for book in output_books])}")
    books = []
    for book in output_books:
        data_list = audible_scrape.maybe_get_books_data([book.asin])
        data: dict = data_list[0] if data_list else {"asin": ""}
        data["paths"] = []
        for file_range in files_dict[book.id]:
            for i in range(file_range.start, file_range.end):
                data["paths"] += [root.all_files[i].full_path]
        books.append(data)
    if not books:
        raise RuntimeError("No books found in the response from GPT.")

    return books


def find_books(collection_name: str, files: list[str]) -> list[dict]:
    root = directory_tree.Root()
    for file in files:
        root.add_file(file)
    book_files = group_book_files(collection_name, root)
    input_content, files_dict = create_books_input_content(book_files)
    logger.debug(input_content)
    logger.debug(files_dict)
    return gpt_scrape(input_content, files_dict, root)
