from pydantic import BaseModel, Field
from typing import List


# --------------------------------- Classes for file grouping ---------------------------------
class FileRange(BaseModel):
    start: int = Field(
        ..., description="The id of the first file in the range (inclusive)"
    )
    end: int = Field(
        ..., description="The id of the last file in the range (exclusive)"
    )


class Book(BaseModel):
    title: str = Field(..., description="Title of the book")
    authors: list[str] = Field(
        ...,
        description=(
            "List of possible authors, sorted by likely hood. If there is a "
            "high degree of certainty in the author, include just that author. "
            "If there is a low degree of certainty, return an empty list."
        ),
    )
    files: List[FileRange] = Field(
        ...,
        description="List of ranges of files (by id) that are a part of the book. Ranges are [start, end), i.e. the start is included, and the end is not",
    )


class Books(BaseModel):
    books: list[Book] = Field(
        ...,
        description="A list of all individual books found in the input. Each element should represent a single book, never more than one.",
    )


# --------------------------------- Classes for book matching ---------------------------------


class MatchedBook(BaseModel):
    asin: str = Field(
        ...,
        description="Most likely ASIN matching the book. Leave blank if not found.",
    )
    id: int = Field(..., description="The id of the book given to you by the user")


class MatchedBooks(BaseModel):
    books: list[MatchedBook] = Field(
        ..., description="List of books successfully matched, identified by ASIN and id"
    )
