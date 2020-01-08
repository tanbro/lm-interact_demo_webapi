from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from .backend import Backend


class ChatBackend(Backend):
    personality: str = ''


class MessageDirection(str, Enum):
    incoming = 'incoming'
    outgoing = 'outgoing'


class Counselor(BaseModel):
    id: int = Field(...)
    name: str = Field(...)
    tags: List[str] = []
    brief: str = ''
    detail: str = ''
    avatar: Optional[HttpUrl] = None


class BaseMessage(BaseModel):
    type: str = Field(..., max_length=256)
    message: Any = Field(...)
    direction: MessageDirection = MessageDirection.incoming
    time: Optional[datetime] = None
    tags: Optional[List[Any]] = None


class TextMessage(BaseMessage):
    type: str = 'text'
    message: str = Field(..., max_length=1024)


class SuggestMessageBody(BaseModel):
    text: str
    counselors: List[Counselor] = Field(...)



class SuggestMessage(BaseMessage):
    type: str = 'suggest'
    message: SuggestMessageBody


class SuggestResultMessageBody(BaseModel):
    value: int = Field(...)

class SuggestResultMessage(BaseMessage):
    type: str = 'suggest.result'
    message: SuggestResultMessageBody = Field(...)
    direction: MessageDirection = MessageDirection.incoming


class PromptMessageBody(BaseModel):
    text: str = Field(...)
    yes_label: str = ''
    no_label: str = ''


class PromptMessage(BaseMessage):
    type: str = 'prompt'
    direction: MessageDirection = MessageDirection.outgoing
    message: PromptMessageBody


class PromptResultValue(str, Enum):
    yes = 'yes'
    no = 'no'


class PromptResultMessageBody(BaseModel):
    value: PromptResultValue = Field(...)


class PromptResultMessage(BaseMessage):
    type: str = 'prompt.result'
    direction: MessageDirection = MessageDirection.incoming
    message: PromptResultMessageBody


IncomingMessages = Union[TextMessage, SuggestResultMessage, PromptResultMessage]
OutgoingMessages = Union[TextMessage, SuggestMessage, PromptMessage]
AllMessages = Union[TextMessage, SuggestMessage, SuggestResultMessage, PromptMessage, PromptResultMessage]
