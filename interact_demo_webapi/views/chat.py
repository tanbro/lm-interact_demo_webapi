import asyncio.subprocess
import logging
import shlex
from datetime import datetime
from functools import partial
from typing import Dict, List, Tuple, Union
from uuid import UUID, uuid1

from fastapi import HTTPException

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
    return [i[0] for i in conversations]


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
    else:
        logger.info('%s: proc=%s', uid, inter.proc)
        obj.pid = inter.proc.pid
        return obj


@app.get('/chat/{uid}', response_model=Conversation)
def get(uid: UUID):
    try:
        obj, _ = conversations[uid]
    except KeyError:
        raise HTTPException(404)
    else:
        return obj


@app.post('/chat/{uid}')
async def interact(uid: UUID, msg: TextMessage, timeout: float = 15):
    try:
        _, inter = conversations[uid]
    except KeyError:
        raise HTTPException(404)
    else:
        output_line = await inter.interact(msg.text, timeout=timeout)
        msg = output_line.lstrip('>').lstrip().lstrip('▁').lstrip()
        return {
            'msg': msg,
            'time': datetime.now()
        }


@app.delete('/chat/{uid}')
async def delete(uid: UUID):
    try:
        _, inter = conversations.pop(uid)
    except KeyError:
        raise HTTPException(404)
    else:
        inter.terminate()


@app.get('/chat/{uid}/{name}')
def get_attr(uid: UUID, name: str = None):
    try:
        obj, _ = conversations[uid]
    except KeyError:
        raise HTTPException(404)
    else:
        if name:
            return obj['attr']
        return getattr(obj, name)
