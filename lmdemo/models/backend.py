from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class BackendState(str, Enum):
    pending = 'pending'
    started = 'started'
    terminated = 'terminated'


class Backend(BaseModel):
    uid: UUID
    state: BackendState = BackendState.pending
    pid: int = 0
    program: str = ''
    args: str = ''
    cwd: str = ''
