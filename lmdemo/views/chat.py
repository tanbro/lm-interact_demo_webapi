import asyncio.subprocess
import logging
import os
import shlex
import signal
from datetime import datetime
from functools import partial
from typing import Dict, List, Tuple, Union
from uuid import UUID, uuid1

from fastapi import HTTPException
from starlette.responses import Response, StreamingResponse
from starlette.websockets import WebSocket

from ..app import app
from ..models.chat import (BaseMessage, Conversation, ConversationState,
                           MessageDirection, TextMessage)
from ..settings import settings
from ..utils.interactor import Interactor
from time import time

MAX_CONVERSATIONS = 1


conversations: Dict[
    str,
    Tuple[Conversation, Interactor, asyncio.Lock, List[BaseMessage]]
] = {}


@app.get('/chat', response_model=List[Conversation])
def list_():
    return [v[0] for v in conversations.values()]


@app.post('/chat', status_code=201, response_model=Conversation)
async def create(wait: float = 0):
    if len(conversations) >= MAX_CONVERSATIONS:
        raise HTTPException(
            status_code=409,
            detail='Max length of conversations reached: {}'.format(
                MAX_CONVERSATIONS)
        )

    logger = logging.getLogger('{}.create'.format(__name__))

    # todo: 关闭现有！

    # 新建聊天进程
    uid = uuid1()
    obj = Conversation(
        uid=uid,
        program=settings.chat_program,
        args=settings.chat_args,
        cwd=settings.chat_cwd
    )
    logger.info('%s', obj)

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
        _obj.state = ConversationState.started
        logging.getLogger(__name__).info('started: %s', _obj)

    def fn_on_terminated(_obj):
        try:
            del conversations[_obj.uid]
        except KeyError:
            pass

    inter = Interactor(
        obj.program, shlex.split(obj.args), obj.cwd,
        started_condition=partial(fn_started_condition, obj),
        on_started=partial(fn_on_started, obj),
        on_terminated=partial(fn_on_terminated, obj),
    )
    lock = asyncio.Lock()
    conversations[uid] = (obj, inter, lock, [])

    async with lock:
        try:
            await inter.startup()
        except:
            del conversations[uid]
            raise

    logger.info('%s: proc=%s', uid, inter.proc)
    obj.pid = inter.proc.pid
    return obj


@app.get('/chat/{uid}', response_model=Conversation)
def get(uid: UUID):
    try:
        obj, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    return obj


@app.post('/chat/{uid}', response_model=TextMessage)
async def interact(uid: UUID, msg: TextMessage, timeout: float = 15):
    try:
        _, inter, lock, msg_list, *_ = conversations[uid]
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
        time=datetime.now()
    )
    msg_list.append(out_msg)

    return out_msg


@app.delete('/chat/{uid}')
async def delete(uid: UUID):
    try:
        _, inter, lock, *_ = conversations.pop(uid)
    except KeyError:
        raise HTTPException(404)

    async with lock:
        inter.terminate()


@app.get('/chat/{uid}/history', response_model=List[TextMessage])
async def get_history(uid: UUID):
    try:
        _, _, _, msg_list, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    return msg_list


@app.delete('/chat/{uid}/history')
async def delete_history(uid: UUID):
    try:
        _, inter, lock, msg_list, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    async with lock:
        inter.signal(signal.SIGHUP)
        while msg_list:
            del msg_list[0]


@app.get('/chat/{uid}/trace')
async def trace(uid: UUID, timeout:float=15):
    """trace before started
    """
    try:
        _, inter, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    if inter.started:
        raise HTTPException(409)

    async def generate_read(conv_uid, max_alive=15, wait_timeout=1):
        def cb_output(q, *args):
            q.put_nowait(args)

        ts = time()
        queue = asyncio.Queue()
        cb_output_func = partial(cb_output, queue)

        while time()-ts < max_alive:
            try:
                _, inter, *_ = conversations[conv_uid]
            except KeyError:
                break
            if inter.started:
                break
            if inter.terminated:
                break
            inter.on_output = cb_output_func
            try:
                task = asyncio.create_task(queue.get())
                try:
                    data = await asyncio.wait_for(task, timeout=wait_timeout)
                except asyncio.TimeoutError:
                    pass
                else:
                    name, txt = data
                    yield '{}:{}{}'.format(name, txt, os.linesep)
            finally:
                inter.on_output = None

    generator = generate_read(uid, timeout)
    response = StreamingResponse(generator)
    return response
