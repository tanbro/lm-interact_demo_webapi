from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


from .backend import Backend


class ChatBackend(Backend):
    personality: str = ''


class MessageDirection(str, Enum):
    incoming = 'incoming'
    outgoing = 'outgoing'


class BaseMessage(BaseModel):
    type: str = Field(..., max_length=256)
    message: Any = Field(...)
    direction: MessageDirection = MessageDirection.incoming
    time: datetime = None


class TextMessage(BaseMessage):
    type: str = 'text'
    message: str = Field(..., max_length=1024)
