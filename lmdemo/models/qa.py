from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Question(BaseModel):
    title: str = Field(..., max_length=256)
    text: str = Field(..., max_length=512)


class Answer(BaseModel):
    text: str = Field(...)
