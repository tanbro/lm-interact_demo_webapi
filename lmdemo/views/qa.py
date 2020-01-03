import asyncio
import logging
import os
import shlex
from time import time
from typing import Dict, List, Tuple
from uuid import UUID, uuid1

from starlette.exceptions import HTTPException
from starlette.responses import Response, StreamingResponse

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
        async with backends_lock:
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
        backend.pid = interactor.proc.pid

    return backend


@app.get('/qa/{uid}', response_model=Backend)
async def get(uid: UUID):
    async with backends_lock:
        try:
            obj, *_ = backends[uid]
        except KeyError:
            raise HTTPException(403)
        return obj


@app.post('/qa/{uid}', response_model=Answer)
async def interact(uid: UUID, item: Question, timeout: float = 15):
    async with backends_lock:
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


@app.delete('/qa/{uid}')
async def delete(uid: UUID):
    async with backends_lock:
        try:
            _, interactor, lock, *_ = backends.pop(uid)
        except KeyError:
            raise HTTPException(404)

    async with lock:
        interactor.terminate()


@app.get('/qa/{uid}/trace')
async def trace(uid: UUID, timeout: float = 15):
    """trace before started
    """
    async with backends_lock:
        try:
            backend, interactor, lock, *_ = backends[uid]
        except KeyError:
            raise HTTPException(404)

        if interactor.started:
            return Response(status_code=204)
        if interactor.terminated:
            raise HTTPException(403, detail='backend process terminated')

    async def streaming(inter, max_alive=15, read_timeout=1):
        ts = time()
        queue = asyncio.Queue()

        inter.on_output = lambda k, v: queue.put_nowait((k, v))
        try:
            while (
                time()-ts < max_alive
                and not inter.started
                and not inter.terminated
            ):
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=read_timeout)
                except asyncio.TimeoutError:
                    pass
                else:
                    name, txt = data
                    yield '{}:{}{}'.format(name, txt, os.linesep)
        finally:
            inter.on_output = None

    coro = streaming(interactor, timeout)
    response = StreamingResponse(
        coro, status_code=206, media_type="text/plain")
    return response
