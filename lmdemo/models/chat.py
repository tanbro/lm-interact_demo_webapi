from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl  # pylint:disable=no-name-in-module

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
    is_input: bool = False
    is_result: bool = False
    message: Any = Field(...)
    direction: MessageDirection = MessageDirection.incoming
    time: Optional[datetime] = None
    tags: Optional[List[Any]] = None


class TextMessage(BaseMessage):
    type: str = 'text'
    message: str = Field(..., max_length=1024)


class BaseInputtingMessage(BaseMessage):
    is_input: bool = True
    direction: MessageDirection = MessageDirection.outgoing


class BaseResultBody(BaseModel):
    value: Any = None


class BaseResultMessage(BaseMessage):
    is_result: bool = True
    message: BaseResultBody = Field(...)
    direction: MessageDirection = MessageDirection.incoming


class SuggestBody(BaseModel):
    text: str
    counselors: List[Counselor] = Field(...)


class SuggestMessage(BaseInputtingMessage):
    type: str = 'suggest'
    message: SuggestBody


class SuggestResultBody(BaseResultBody):
    value: int = Field(...)


class SuggestResultMessage(BaseResultMessage):
    type: str = 'suggest.result'
    message: SuggestResultBody = Field(...)


class PromptBody(BaseResultBody):
    text: str = Field(...)
    yes_label: str = ''
    no_label: str = ''


class PromptMessage(BaseInputtingMessage):
    type: str = 'prompt'
    message: PromptBody = Field(...)


class PromptResultValue(str, Enum):
    yes = 'yes'
    no = 'no'


class PromptResultBody(BaseModel):
    value: PromptResultValue = Field(...)


class PromptResultMessage(BaseResultMessage):
    type: str = 'prompt.result'
    message: PromptResultBody = Field(...)


IncomingMessages = Union[TextMessage, SuggestResultMessage, PromptResultMessage]
OutgoingMessages = Union[TextMessage, SuggestMessage, PromptMessage]
AllMessages = Union[TextMessage, SuggestMessage, SuggestResultMessage, PromptMessage, PromptResultMessage]
