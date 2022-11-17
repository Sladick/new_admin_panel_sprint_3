import uuid
from typing import Optional, Union
# from datetime import datetime

from pydantic import BaseModel


class PersonPD(BaseModel):
    """Validation pydantic class for Person model."""

    id: uuid.UUID
    name: str


class FilmworkPD(BaseModel):
    """Validation pydantic class for Filmwork model."""

    id: uuid.UUID
    title: str
    imdb_rating: Union[float, None] = 0
    description: Optional[str] = ''

    director: list[str] = []
    genre: list[str] = []
    actors_names: list[str] = []
    writers_names: list[str] = []

    actors: list[PersonPD] = []
    writers: list[PersonPD] = []
