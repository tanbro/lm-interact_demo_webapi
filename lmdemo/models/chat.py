from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    pending = 'pending'
    started = 'started'
    terminated = 'terminated'

class Conversation(BaseModel):
    uid: UUID
    state: ConversationState = ConversationState.pending
    pid: int = 0
    program: str = ''
    args: str = ''
    cwd: str = ''
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
