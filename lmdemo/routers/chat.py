import asyncio.subprocess
import logging
import os
import random
import shlex
import signal
import sys
from string import Template
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from time import time
from typing import Any, Dict, List, Tuple, Union
from uuid import UUID, uuid1

import yaml
from dateutil.tz import tzlocal
from fastapi import APIRouter, HTTPException
from starlette.responses import Response, StreamingResponse
from transitions import Machine

from ..models.backend import BackendState
from ..models.chat import (AllMessages, BaseMessage, ChatBackend, Counselor,
                           IncomingMessages, MessageDirection,
                           OutgoingMessages, PromptMessage, PromptMessageBody,
                           PromptResultMessage, PromptResultMessageBody,
                           PromptResultValue, SuggestMessage,
                           SuggestMessageBody, TextMessage)
from ..settings import settings
from ..statemachines.chat import FINALS, StateModel, create_machine
from ..utils.interactor import Interactor

MAX_BACKENDS = 1

router = APIRouter()


@dataclass
class BackendData:
    uid: UUID = None
    backend: ChatBackend = None
    interactor: Interactor = None
    lock: asyncio.Lock = None
    machine: Machine = None


backends_lock = asyncio.Lock()
backends: Dict[str, BackendData] = {}


@router.get('/', response_model=List[ChatBackend])
def list_():
    return [bo.backend for bo in backends.values()]


@router.post('/', status_code=201, response_model=ChatBackend)
async def create():

    logger = logging.getLogger(__name__)

    async def coro_started_condition(uid, name, line):
        if name.strip().lower() == 'stdout':
            # 固定一个假的 personality:
            personality = '您好，我是心理咨询师小媒，有什么可以帮到您？'
            async with backends_lock:
                bo = backends[uid]
            async with bo.lock:
                bo.backend.personality = personality
            return True
        return False

    async def coro_on_started(uid):
        async with backends_lock:
            bo = backends[uid]
        async with bo.lock:
            bo.backend.state = BackendState.started

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
                        MAX_BACKENDS
                    )
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

            interactor = Interactor(
                backend.program, shlex.split(backend.args), backend.cwd,
                started_condition=partial(coro_started_condition, uid),
                on_started=coro_on_started(uid),
                on_terminated=coro_on_terminated(uid),
            )
            backends[uid] = BackendData(
                uid=uid,
                backend=backend,
                interactor=interactor,
                lock=asyncio.Lock(),
                machine=create_machine(StateModel())
            )

        try:
            await interactor.startup()
        except:
            async with backends_lock:
                del backends[uid]
            raise
        else:
            backend.pid = interactor.proc.pid
            logger.info('Backend create ok: %s', interactor.proc)

        return backend
    except Exception as err:
        logger.exception('An un-caught error occurred when create: %s', err)
        raise


@router.get('/{uid}', response_model=ChatBackend)
async def get(uid: UUID):
    async with backends_lock:
        try:
            bo = backends[uid]
        except KeyError:
            raise HTTPException(404)
        else:
            return bo.backend


PUNCTUATION_MAP = [
    (',', '，'),
    ('!', '！'),
    ('?', '？'),
    (':', '：'),
    ('▁', '，'),
]


async def predict(interactor, txt, timeout=None):
    txt = txt.strip()
    if not txt:
        raise ValueError('input text can not be empty')
    output_text = await interactor.interact(txt, timeout=timeout)
    # 清除 > ▁ 的开头的符号
    output_text = output_text.lstrip('>').lstrip().lstrip('▁').lstrip()
    # 特殊的规定：半角标点转为全角标点，还有就是 ▁ 换为逗号:
    for old, new in PUNCTUATION_MAP:
        output_text = output_text.replace(old, new)
    return TextMessage(
        direction=MessageDirection.outgoing,
        message=output_text,
        time=datetime.now(tzlocal()),
    )


def get_counselors():
    with open('data/counselors.yml', encoding='utf8') as fp:
        ds = yaml.load(fp, Loader=yaml.SafeLoader)
    for i in range(len(ds)):
        ds[i]['id'] = i
    return [Counselor(**d) for d in ds]


@router.post('/{uid}', response_model=Union[OutgoingMessages, List[OutgoingMessages]])
async def interact(uid: UUID, msg: IncomingMessages, timeout: float = 15, stateless: bool = False):
    logger = logging.getLogger(__name__)
    try:
        async with backends_lock:
            try:
                bo = backends[uid]
            except KeyError:
                raise HTTPException(404)

        msg.direction = MessageDirection.incoming
        bo.machine.model.history.append(msg)
        out_msg = None

        async with bo.lock:
            if stateless:
                # 无状态的交互
                logger.debug('%s interact stateless', bo.interactor)
                out_msg = await predict(bo.interactor, msg.message, timeout=timeout)
                bo.machine.model.history.append(out_msg)
            else:
                # 按照状态机进行交互
                old_state = bo.machine.model.state
                msg_body = msg.message
                # 状态转移！
                trigger_name = msg.type
                try:
                    trigger_value = getattr(msg_body, 'value')
                except AttributeError:
                    bo.machine.model.trigger(trigger_name)
                else:
                    bo.machine.model.trigger(trigger_name, trigger_value)
                logger.debug('%s interact: trigger(%s)[%s==>%s]', bo.interactor.proc,
                             trigger_name, old_state, bo.machine.model.state)
                # 输入输出逻辑
                while not out_msg:
                    if bo.machine.model.state == 'dialog':
                        # 通过 ML 模型进行预测
                        out_msg = await predict(bo.interactor, msg.message, timeout=timeout)
                    elif bo.machine.model.state == 'suggest.ask':
                        # 询问是否要推荐咨询老师，从设置文件读取用于回复的语句
                        with open(os.path.join('data', 'sentences.yml'), encoding='utf8') as fp:
                            txt_list = yaml.load(fp, Loader=yaml.SafeLoader)[bo.machine.model.state]
                        txt = random.choice(txt_list)
                        out_msg = PromptMessage(message=PromptMessageBody(
                            text=txt, yes_label='可以', no_label='不用'
                        ))
                    elif bo.machine.model.state == 'suggest.yes':
                        # 展示推荐的咨询老师
                        counselors = random.sample(get_counselors(), k=2)
                        out_msg = SuggestMessage(
                            direction=MessageDirection.outgoing,
                            message=SuggestMessageBody(
                                text='为您推荐以下{}位咨询师：'.format(len(counselors)),
                                counselors=counselors
                            ),
                            time=datetime.now(tzlocal())
                        )
                    elif bo.machine.model.state == 'suggest.no':
                        # 拒绝推荐咨询老师
                        bo.machine.model.trigger('')
                    elif bo.machine.model.state == 'booked':
                        # 选中了一个咨询老师，回复一个确认信息：从设置文件读取用于回复的语句，返回纯文本消息
                        with open(os.path.join('data', 'sentences.yml'), encoding='utf8') as fp:
                            txt_list = yaml.load(fp, Loader=yaml.SafeLoader)[bo.machine.model.state]
                        txt = random.choice(txt_list)
                        tpl = Template(txt)
                        counselor = get_counselors()[trigger_value]
                        txt = tpl.substitute(**counselor.dict())
                        out_msg = TextMessage(
                            direction=MessageDirection.outgoing,
                            message=txt,
                            time=datetime.now(tzlocal())
                        )
                    else:
                        # 其它，从设置文件读取用于回复的语句，返回纯文本消息
                        with open(os.path.join('data', 'sentences.yml'), encoding='utf8') as fp:
                            txt_list = yaml.load(fp, Loader=yaml.SafeLoader)[bo.machine.model.state]
                        txt = random.choice(txt_list)
                        out_msg = TextMessage(
                            message=txt,
                            direction=MessageDirection.outgoing,
                            time=datetime.now(tzlocal())
                        )
                # end-while
                # 结束了？
                if bo.machine.model.state in FINALS:
                    logger.info('%s interact: final state: %s', bo.interactor.proc, bo.machine.model.state)
                    await bo.interactor.signal(signal.SIGHUP)
                    bo.machine = create_machine(StateModel())
                else:
                    bo.machine.model.history.append(out_msg)

        return out_msg

    except Exception as err:
        logger.exception('An un-caught error occurred in interact: %s', err)
        raise


@router.delete('/{uid}')
async def delete(uid: UUID):
    async with backends_lock:
        try:
            bo = backends.pop(uid)
        except KeyError:
            raise HTTPException(404)

    async with bo.lock:
        bo.interactor.terminate()


@router.get('/{uid}/history', response_model=List[AllMessages])
async def get_history(uid: UUID):
    logger = logging.getLogger(__name__)
    try:
        async with backends_lock:
            try:
                bo = backends[uid]
            except KeyError:
                raise HTTPException(404)

        async with bo.lock:
            return bo.machine.model.history
    except Exception as err:
        logger.exception('An un-caught error occurred in get_history: %s', err)
        raise


@router.delete('/{uid}/history')
async def delete_history(uid: UUID):
    async with backends_lock:
        try:
            bo = backends[uid]
        except KeyError:
            raise HTTPException(404)

    async with bo.lock:
        await bo.interactor.signal(signal.SIGHUP)
        bo.machine = create_machine(StateModel())


@router.get('/{uid}/trace')
async def trace(uid: UUID, timeout: float = 15):
    """trace before started
    """
    async with backends_lock:
        try:
            bo = backends[uid]
        except KeyError:
            raise HTTPException(404)

    if bo.interactor.started:
        return Response(status_code=204)
    if bo.interactor.terminated:
        raise HTTPException(403, detail='backend process terminated')

    async def streaming(interactor, max_alive=15, wait_timeout=1):
        try:
            ts = time()
            queue = asyncio.Queue()
            interactor.on_output = lambda k, v: queue.put_nowait((k, v))
            try:
                while (
                    time()-ts < max_alive
                    and not interactor.started
                    and not interactor.terminated
                ):
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                    except asyncio.TimeoutError:
                        pass
                    else:
                        name, txt = data
                        yield '{}:{}{}'.format(name, txt, os.linesep)
            finally:
                interactor.on_output = None
        except Exception as err:
            logging.getLogger(__name__).exception(
                'An un-caught error occurred when tracing backend starting output: %s',
                err
            )
            raise

    gen = streaming(bo.interactor, timeout)
    response = StreamingResponse(gen, status_code=206, media_type="text/plain")
    return response
