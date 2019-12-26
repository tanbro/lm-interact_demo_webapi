from enum import Enum
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


class TextMessage(BaseModel):
    text: str = Field(..., max_length=256)
