import asyncio.subprocess
import logging
import os
import random
import shlex
import signal
import sys
from datetime import datetime
from functools import partial
from time import time
from typing import Any, Dict, List, Tuple, Union
from uuid import UUID, uuid1

import yaml
from dateutil.tz import tzlocal
from fastapi import APIRouter, HTTPException
from starlette.responses import Response, StreamingResponse

from ..models.backend import BackendState
from ..models.chat import (BaseMessage, ChatBackend, Counselor,
                           MessageDirection, SuggestCounselorMessage,
                           SuggestCounselorMessageBody, TextMessage,
                           UnionMessageTypes)
from ..settings import settings
from ..utils.interactor import Interactor

MAX_BACKENDS = 1

router = APIRouter()

backends_lock = asyncio.Lock()

backends: Dict[
    str,
    Tuple[ChatBackend, Interactor, asyncio.Lock, List[BaseMessage], Dict[str, Any]]
] = {}


@router.get('/', response_model=List[ChatBackend])
def list_():
    return [v[0] for v in backends.values()]


@router.post('/', status_code=201, response_model=ChatBackend)
async def create():

    logger = logging.getLogger(__name__)

    async def coro_started_condition(uid, name, line):
        if name.strip().lower() == 'stdout':
            personality = '您好，我是心理咨询师小媒，有什么可以帮到您？'
            # 固定一个假的 personality
            # (
            #     line
            #     .lstrip('>').lstrip()
            #     .lstrip('▁').lstrip()
            # )
            async with backends_lock:
                backend, _, lock, *_ = backends[uid]
            async with lock:
                backend.personality = personality
            return True
        return False

    async def coro_on_started(uid):
        async with backends_lock:
            backend, _, lock, *_ = backends[uid]
        async with lock:
            backend.state = BackendState.started

    async def coro_on_terminated(uid):
        async with backends_lock:
            try:
                del backends[backend.uid]
            except KeyError:
                pass

    try:
        async with backends_lock:
            if len(backends) >= MAX_BACKENDS:
                raise HTTPException(
                    status_code=403,
                    detail='Max length of backends reached: {}'.format(
                        MAX_BACKENDS)
                )

            # 新建聊天进程
            uid = uuid1()
            backend = ChatBackend(
                uid=uid,
                program=settings.chat_program,
                args=settings.chat_args,
                cwd=settings.chat_cwd
            )
            logger.info('create Chat backend: %s', backend)

            inter = Interactor(
                backend.program, shlex.split(backend.args), backend.cwd,
                started_condition=partial(coro_started_condition, uid),
                on_started=coro_on_started(uid),
                on_terminated=coro_on_terminated(uid),
            )
            lock = asyncio.Lock()
            backends[uid] = (backend, inter, lock, [], {})

        try:
            await inter.startup()
        except:
            async with backends_lock:
                del backends[uid]
            raise
        else:
            backend.pid = inter.proc.pid
            logger.info('Backend create ok: %s', inter.proc)

        return backend
    except Exception as err:
        logger.exception('An un-caught error occurred when create: %s', err)
        raise


@router.get('/{uid}', response_model=ChatBackend)
async def get(uid: UUID):
    async with backends_lock:
        try:
            obj, *_ = backends[uid]
        except KeyError:
            raise HTTPException(404)

    return obj


@router.post('/{uid}', response_model=Union[UnionMessageTypes, List[UnionMessageTypes]])
async def interact(uid: UUID, msg: TextMessage, timeout: float = 15):
    logger = logging.getLogger(__name__)
    try:
        async with backends_lock:
            try:
                _, inter, lock, msg_list, state, *_ = backends[uid]
            except KeyError:
                raise HTTPException(404)

        msg.direction = MessageDirection.incoming
        msg_list.append(msg)

        # 如果超过 2 轮对话，每隔 1 轮就推荐咨询师
        suggest_state = state.get('suggest')
        n_turn = sum(1 for m in msg_list if m.direction == MessageDirection.incoming)
        if not suggest_state:
            if (
                state.get('turn_since_latest_suggest') == 1
                or (
                    'turn_since_latest_suggest' not in state
                    and (n_turn > 0 and n_turn % 2 == 0)
                )
            ):
                # 进入推荐状态 - 询问
                with open('data/fallbacks.txt', encoding='utf8') as fp:
                    ss = [s for s in fp.readlines() if s.strip()]
                s = random.choice(ss)
                out_msg = TextMessage(
                    direction=MessageDirection.outgoing,
                    message=s,
                    time=datetime.now(tzlocal())
                )
                msg_list.append(out_msg)
                state.update({
                    'suggest': 'prompting',
                    'turn_since_latest_suggest': 0
                })
                return out_msg
        elif suggest_state == 'prompting':
            with open('data/counselors.yml', encoding='utf8') as fp:
                ds = yaml.load(fp, Loader=yaml.SafeLoader)
            ds = random.sample(ds, k=2)
            counselors = [Counselor(**d) for d in ds]
            out_msg = SuggestCounselorMessage(
                direction=MessageDirection.outgoing,
                message=SuggestCounselorMessageBody(
                    text='为您智能推荐以下{}位适合的咨询师：'.format(len(counselors)),
                    counselors=counselors
                ),
                time=datetime.now(tzlocal())
            )
            msg_list.append(out_msg)
            state.update({'suggest': 'prompted'})
            return out_msg
        elif suggest_state == 'prompted':
            state.update({
                'turn_since_latest_suggest': state.get('turn_since_latest_suggest', 0) + 1
            })
            logger.debug('prompted: state: %s', state)

        # 通过 pipe 调用 model 文本生成
        async with lock:
            out_txt = await inter.interact(msg.message, timeout=timeout)
        out_txt = out_txt.lstrip('>').lstrip().lstrip('▁').lstrip()
        # 特殊的规定：半角标点转为全角标点，还有就是 ``'▁'`` 换为逗号:
        out_text = out_text.strip().lstrip('▁').lstrip()
        for old, new in PUNCTUATION_MAP:
            out_text = out_text.replace(old, new)
        out_msg = TextMessage(
            direction=MessageDirection.outgoing,
            message=out_txt,
            time=datetime.now(tzlocal())
        )
        msg_list.append(out_msg)
        if suggest_state:
            state.update({'suggest': None})
        return out_msg

    except Exception as err:
        logger.exception('An un-caught error occurred when interact: %s', err)
        raise


@router.delete('/{uid}')
async def delete(uid: UUID):
    async with backends_lock:
        try:
            _, inter, lock, *_ = backends.pop(uid)
        except KeyError:
            raise HTTPException(404)

    async with lock:
        inter.terminate()


@router.get('/{uid}/history', response_model=List[UnionMessageTypes])
async def get_history(uid: UUID):
    async with backends_lock:
        try:
            _, _, _, msg_list, *_ = backends[uid]
        except KeyError:
            raise HTTPException(404)

    return msg_list


@router.delete('/{uid}/history')
async def delete_history(uid: UUID):
    async with backends_lock:
        try:
            _, inter, lock, msg_list, *_ = backends[uid]
        except KeyError:
            raise HTTPException(404)

    async with lock:
        inter.signal(signal.SIGHUP)
        while msg_list:
            del msg_list[0]


@router.get('/{uid}/trace')
async def trace(uid: UUID, timeout: float = 15):
    """trace before started
    """
    async with backends_lock:
        try:
            _, inter, *_ = backends[uid]
        except KeyError:
            raise HTTPException(404)

    if inter.started:
        return Response(status_code=204)
    if inter.terminated:
        raise HTTPException(403, detail='backend process terminated')

    async def streaming(inter, max_alive=15, wait_timeout=1):
        try:
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
        except Exception as err:
            logging.getLogger(__name__).exception(
                'An un-caught error occurred when tracing backend starting output: %s',
                err
            )
            raise

    gen = streaming(inter, timeout)
    response = StreamingResponse(gen, status_code=206, media_type="text/plain")
    return response

PUNCTUATION_MAP = [
    (',', '，'),
    ('!', '！'),
    ('?', '？'),
    (':', '：'),
    ('▁', '，'),
]
