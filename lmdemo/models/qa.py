from pydantic import BaseModel, Field  # pylint:disable=no-name-in-module


class Question(BaseModel):
    title: str = Field(..., max_length=256)
    text: str = Field(..., max_length=512)


class Answer(BaseModel):
    text: str = Field(...)
