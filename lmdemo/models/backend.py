from enum import Enum
from uuid import UUID

from pydantic import BaseModel  # pylint:disable=no-name-in-module


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
