import asyncio.subprocess
import logging
import os
import shlex
from datetime import datetime
from functools import partial
from typing import Dict, List, Tuple, Union
from uuid import UUID, uuid1

from fastapi import HTTPException
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.websockets import WebSocket

from ..app import app
from ..models.chat import Conversation, ConversationState, TextMessage
from ..settings import settings
from ..utils.interactor import Interactor

MAX_CONVERSATIONS = 1

conversations: Dict[
    str,
    Tuple[Conversation, Interactor]
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
    conversations[uid] = (obj, inter)
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


@app.post('/chat/{uid}')
async def interact(uid: UUID, msg: TextMessage, timeout: float = 15):
    try:
        _, inter, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    output_line = await inter.interact(msg.text, timeout=timeout)
    msg = output_line.lstrip('>').lstrip().lstrip('▁').lstrip()
    return {
        'msg': msg,
        'time': datetime.now()
    }


@app.delete('/chat/{uid}')
async def delete(uid: UUID):
    try:
        _, inter, *_ = conversations.pop(uid)
    except KeyError:
        raise HTTPException(404)

    inter.terminate()


@app.websocket('/chat/{uid}/trace')
async def ws_trace(websocket: WebSocket, uid: UUID):
    try:
        _, inter, *_ = conversations[uid]
    except KeyError:
        raise HTTPException(404)

    await websocket.accept()

    queue = asyncio.Queue()

    async def cb_output(q, k, v):
        s = '{}:{}'.format(k, v)
        await q.put(s)

    try:
        inter.on_output = partial(cb_output, queue)
        while not iter.terminated:
            task = asyncio.create_task(queue.get())
            try:
                txt = await asyncio.wait_for(task, timeout=1)
            except asyncio.TimeoutError:
                pass
            await websocket.send_text(txt)
    finally:
        inter.on_output = None
