import asyncio
import logging
import shlex
from typing import Dict, List, Tuple
from uuid import UUID, uuid1

from starlette.exceptions import HTTPException
from starlette.responses import Response

from ..app import app
from ..models.backend import Backend, BackendState
from ..models.qa import Answer, Question
from ..settings import settings
from ..utils.interactor import Interactor

MAX_BACKENDS = 1

backends: Dict[
    str,
    Tuple[Backend, Interactor, asyncio.Lock]
] = {}

backends_lock = asyncio.Lock()


@app.get('/qa', response_model=List[Backend])
def list_():
    return [v[0] for v in backends.values()]


@app.post('/qa', status_code=201, response_model=Backend)
async def create(wait: float = 0):
    logger = logging.getLogger(__name__)

    def func_started_cond(output_file: str, output_text: str) -> bool:
        return output_text.strip().lower().startswith('started')

    async def coro_on_started(uid):
        logger = logging.getLogger(__name__)
        logger.info('QA backend started: %s', uid)
        backend, _, lock, *_ = backends[uid]
        async with lock:
            backend.state = BackendState.started

    async def coro_on_terminated(uid):
        logger = logging.getLogger(__name__)
        logger.warning('QA backend terminated: %s', uid)
        async with backends_lock:
            try:
                del backends[uid]
            except KeyError:
                pass

    async with backends_lock:
        if len(backends) >= MAX_BACKENDS:
            raise HTTPException(
                status_code=403,
                detail='Max length of backends reached: {}'.format(
                    MAX_BACKENDS)
            )
        uid = uuid1()
        backend = Backend(
            uid=uid,
            program=settings.qa_program,
            args=settings.qa_args,
            cwd=settings.qa_cwd
        )
        logger.info('create QA backend: %s', backend)

        interactor = Interactor(
            backend.program, shlex.split(backend.args), backend.cwd,
            started_condition=func_started_cond,
            on_started=coro_on_started(uid),
            on_terminated=coro_on_terminated(uid),
        )
        lock = asyncio.Lock()
        backends[uid] = (backend, interactor, lock)
        await interactor.startup()

    return backend


@app.get('/qa/{uid}', response_model=Backend)
def get(uid: UUID):
    try:
        obj, *_ = backends[uid]
    except KeyError:
        raise HTTPException(403)
    return obj


@app.post('/qa/{uid}', response_model=Answer)
async def interact(uid: UUID, item: Question, timeout: float = 15):
    try:
        backend, interactor, lock, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    async with lock:
        if backend.state != BackendState.started:
            raise HTTPException(
                403, 'Invalid backend state "{}"'.format(backend.state))
        in_txt = '{title}<sep>{text}<sep><sep><|endoftext|>'.format(
            **item.dict())
        out_txt = await interactor.interact(in_txt, timeout=timeout)
        out_txt = out_txt.lstrip('>').lstrip().lstrip('▁').lstrip()
        answer = Answer(text=out_txt)

    return answer
