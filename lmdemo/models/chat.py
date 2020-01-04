from datetime import datetime
from enum import Enum
from typing import Any, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from .backend import Backend


class ChatBackend(Backend):
    personality: str = ''


class MessageDirection(str, Enum):
    incoming = 'incoming'
    outgoing = 'outgoing'


class Counselor(BaseModel):
    name: str = Field(...)
    tags: List[str] = []
    brief: str = ''
    detail: str = ''
    url: HttpUrl = None
    avatar: HttpUrl = None


class BaseMessage(BaseModel):
    type: str = Field(..., max_length=256)
    message: Any = Field(...)
    direction: MessageDirection = MessageDirection.incoming
    time: datetime = None


class TextMessage(BaseMessage):
    type: str = 'text'
    message: str = Field(..., max_length=1024)


class SuggestCounselorMessageBody(BaseModel):
    text: str
    counselors: List[Counselor] = Field(...)


class SuggestCounselorMessage(BaseMessage):
    type: str = 'suggest_counselor'
    direction: MessageDirection = MessageDirection.outgoing
    message: SuggestCounselorMessageBody


UnionMessageTypes = Union[TextMessage, SuggestCounselorMessage]
