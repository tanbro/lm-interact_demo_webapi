import asyncio.subprocess
import logging
import os
import shlex
import signal
from datetime import datetime, timezone
from functools import partial
from time import time
from typing import Dict, List, Tuple, Union
from uuid import UUID, uuid1

from fastapi import HTTPException
from starlette.responses import Response, StreamingResponse

from ..app import app
from ..models.backend import BackendState
from ..models.chat import (BaseMessage, ChatBackend, MessageDirection,
                           TextMessage)
from ..settings import settings
from ..utils.interactor import Interactor

MAX_BACKENDS = 1


backends: Dict[
    str,
    Tuple[ChatBackend, Interactor, asyncio.Lock, List[BaseMessage]]
] = {}


@app.get('/chat', response_model=List[ChatBackend])
def list_():
    return [v[0] for v in backends.values()]


@app.post('/chat', status_code=201, response_model=ChatBackend)
async def create():
    logger = logging.getLogger('__name__')

    if len(backends) >= MAX_BACKENDS:
        raise HTTPException(
            status_code=403,
            detail='Max length of backends reached: {}'.format(
                MAX_BACKENDS)
        )

    # 新建聊天进程
    uid = uuid1()
    obj = ChatBackend(
        uid=uid,
        program=settings.chat_program,
        args=settings.chat_args,
        cwd=settings.chat_cwd
    )
    logger.info('create Chat backend: %s', obj)

    def fn_started_condition(_obj, _name, _line):
        if _name.strip().lower() == 'stdout':
            personality = (
                _line
                .lstrip('>').lstrip()
                .lstrip('▁').lstrip()
            )
            _obj.personality = personality
            return True
        return False

    def fn_on_started(_obj):
        _obj.state = BackendState.started
        logging.getLogger(__name__).info('started: %s', _obj)

    def fn_on_terminated(_obj):
        try:
            del backends[_obj.uid]
        except KeyError:
            pass

    inter = Interactor(
        obj.program, shlex.split(obj.args), obj.cwd,
        started_condition=partial(fn_started_condition, obj),
        on_started=partial(fn_on_started, obj),
        on_terminated=partial(fn_on_terminated, obj),
    )
    lock = asyncio.Lock()
    backends[uid] = (obj, inter, lock, [])

    async with lock:
        try:
            await inter.startup()
        except:
            del backends[uid]
            raise

    logger.info('%s: proc=%s', uid, inter.proc)
    obj.pid = inter.proc.pid
    return obj


@app.get('/chat/{uid}', response_model=ChatBackend)
def get(uid: UUID):
    try:
        obj, *_ = backends[uid]
    except KeyError:
        raise HTTPException(403)

    return obj


@app.post('/chat/{uid}', response_model=TextMessage)
async def interact(uid: UUID, msg: TextMessage, timeout: float = 15):
    try:
        _, inter, lock, msg_list, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    msg.direction = MessageDirection.incoming
    msg_list.append(msg)

    async with lock:
        out_txt = await inter.interact(msg.message, timeout=timeout)

    out_txt = out_txt.lstrip('>').lstrip().lstrip('▁').lstrip()
    out_msg = TextMessage(
        direction=MessageDirection.outgoing,
        message=out_txt,
        time=datetime.now(timezone.utc)
    )
    msg_list.append(out_msg)

    return out_msg


@app.delete('/chat/{uid}')
async def delete(uid: UUID):
    try:
        _, inter, lock, *_ = backends.pop(uid)
    except KeyError:
        raise HTTPException(404)

    async with lock:
        inter.terminate()


@app.get('/chat/{uid}/history', response_model=List[TextMessage])
async def get_history(uid: UUID):
    try:
        _, _, _, msg_list, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    return msg_list


@app.delete('/chat/{uid}/history')
async def delete_history(uid: UUID):
    try:
        _, inter, lock, msg_list, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    async with lock:
        inter.signal(signal.SIGHUP)
        while msg_list:
            del msg_list[0]


@app.get('/chat/{uid}/trace')
async def trace(uid: UUID, timeout: float = 15):
    """trace before started
    """
    try:
        _, inter, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    if inter.started:
        return Response(status_code=204)
    if inter.terminated:
        raise HTTPException(403, detail='backend process terminated')

    async def streaming(inter, max_alive=15, wait_timeout=1):
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
                    data = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    pass
                else:
                    name, txt = data
                    yield '{}:{}{}'.format(name, txt, os.linesep)
        finally:
            inter.on_output = None

    gen = streaming(inter, timeout)
    response = StreamingResponse(gen, status_code=206, media_type="text/plain")
    return response
