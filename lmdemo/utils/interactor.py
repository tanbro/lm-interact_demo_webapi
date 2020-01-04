import asyncio.subprocess
import logging
import os
import random
import warnings
from inspect import isawaitable
from locale import getpreferredencoding
from types import SimpleNamespace
from typing import (Any, Awaitable, Callable, Coroutine, List, Optional,
                    TypeVar, Union)

from fastapi import HTTPException

# 同步或者异步的回调类型
Callback = TypeVar('Callback',
                   Callable[..., Any],
                   Callable[..., Awaitable[Any]],
                   )


OnStartedCallback = TypeVar('OnStartedCallback',
                            Callable[[], None],
                            Callable[[], Awaitable[None]],
                            )

StartedConditionCallback = TypeVar('StartedConditionCallback',
                                   Callable[[str, str], bool],
                                   Callable[[str, str], Awaitable[bool]],
                                   )

OnOutputCallback = TypeVar('OnOutputCallback',
                           Callable[[str, str], None],
                           Callable[[str, str], Awaitable[None]],
                           )


class Interactor:
    def __init__(self,
                 proc_program: str,
                 proc_args: Optional[List[str]] = None,
                 proc_cwd: str = '',
                 started_condition: Optional[StartedConditionCallback] = None,
                 on_started: Optional[OnStartedCallback] = None,
                 on_output: Optional[OnOutputCallback] = None,
                 on_terminated: Optional[Callback] = None,
                 ):
        self._logger = logging.getLogger(self.__class__.__qualname__)
        self._proc_program = proc_program
        self._proc_cwd = proc_cwd
        self._proc_args = proc_args or []
        self._proc = None
        self._proc_started = False
        self._proc_terminated = False
        self._started_condition: Optional[StartedConditionCallback] = None
        if started_condition is None:
            self._started_condition = lambda x, y: True
        else:
            self._started_condition = started_condition
        self._on_started: Optional[OnStartedCallback] = on_started
        self._on_output: Optional[OnOutputCallback] = on_output
        self._on_terminated: Optional[Callback] = on_terminated
        self._cb_stdout: Optional[Callable[[str], None]] = None
        self._cb_stderr: Optional[Callable[[str], None]] = None
        self._input_lock = asyncio.Lock()

    async def startup(self):
        logger = self._logger
        try:
            try:
                self._proc = await asyncio.create_subprocess_exec(
                    self._proc_program,
                    *self._proc_args,
                    cwd=self._proc_cwd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                logger.info('%s: pending', self._proc)
                asyncio.ensure_future(self.monitor())
            except NotImplementedError:
                warnings.warn(
                    "Current asyncio event loop does not support subprocesses. "
                    "A dummy subprocess will be used. It's ONLY for DEVELOPMENT!",
                )
                self._proc = DummySubprocess()
                self._proc_started = True
                func = self._on_started
                if isawaitable(func):
                    await func
                elif callable(func):
                    ret_val = func()
                    if isawaitable(ret_val):
                        await ret_val
            return self._proc
        except Exception as err:
            logger.exception('startup: %s', err)
            raise

    async def read_line(self, stream, tag=None):
        line = await stream.readline()
        return line, tag

    async def monitor(self, read_timeout=1, encoding=None):
        logger = self._logger
        proc = self._proc
        try:
            encoding = encoding or getpreferredencoding()
            at_eof = False
            while not at_eof:
                aws = [
                    asyncio.ensure_future(self.read_line(stream, name_tag))
                    for name_tag, stream in [('stdout', proc.stdout), ('stderr', proc.stderr)]
                ]
                done, pending = await asyncio.wait(aws, timeout=read_timeout, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                for task in done:
                    result = task.result()
                    data, name = result
                    at_eof = data == b''
                    if at_eof:
                        break
                    line = data.decode(encoding).strip()
                    logger.debug('%s: %s: %s', proc, name, line)
                    if not self._proc_started:
                        func = self._started_condition
                        if callable(func):
                            ret_val = func(name, line)
                            if isawaitable(ret_val):
                                ret_val = await ret_val
                            self._proc_started = bool(ret_val)
                        if self._proc_started:
                            logger.info('%s: started', proc)
                            func = self._on_started
                            if isawaitable(func):
                                await func
                            elif callable(func):
                                ret_val = func()
                                if isawaitable(ret_val):
                                    await ret_val
                    # 启动的回调函数
                    if self._proc_started:
                        func = None
                        if name == 'stdout':
                            func = self._cb_stdout
                        elif name == 'stderr':
                            func = self._cb_stderr
                        if callable(func):
                            ret_val = func(line)
                            if isawaitable(ret_val):
                                await ret_val
                    # onOutput 无论是否启动成功
                    func = self._on_output
                    if callable(func):
                        ret_val = func(name, line)
                        if isawaitable(ret_val):
                            await ret_val
            # end of while

            self._proc_terminated = True
            logger.warning('%s: terminated(returncode=%s)', proc, proc.returncode)

            func = self._on_terminated
            if isawaitable(func):
                await func
            elif callable(func):
                ret_val = func()
                if isawaitable(ret_val):
                    await ret_val

        except Exception as err:
            logger.exception('%s: monitor: %s', proc, err)
            raise

    async def interact(self, input_text: str, timeout=30, encoding=None) -> str:
        proc = self._proc
        logger = self._logger
        lock = self._input_lock
        result = ''

        if not self.started:
            raise HTTPException(
                status_code=409, detail='Process {} started condition not matched'.format(proc))
        if lock.locked():
            raise HTTPException(status_code=409)

        try:
            logger.debug('%s: interact: input: %s', proc, input_text)

            async with lock:
                if isinstance(self._proc, asyncio.subprocess.Process):
                    encoding = encoding or getpreferredencoding()
                    input_data = f'{input_text.strip()}{os.linesep}'.encode(encoding)
                    fut = asyncio.get_event_loop().create_future()
                    self._cb_stdout = lambda x: fut.set_result(x.strip())
                    try:
                        proc.stdin.write(input_data)
                        aws = [
                            asyncio.ensure_future(m)
                            for m in (proc.stdin.drain(), fut)
                        ]
                        _, pending = await asyncio.wait(aws, timeout=timeout)
                        if pending:
                            for task in pending:
                                task.cancel()
                            raise RuntimeError(
                                'Following streaming i/o tasks can not be done in %s seconds: %s',
                                timeout, pending
                            )
                    finally:
                        self._cb_stdout = None
                    result = fut.result()

                elif isinstance(self._proc, DummySubprocess):
                    await asyncio.sleep(1)
                    result = f'Your input: {input_text.strip()}'

                else:
                    raise RuntimeError('Un-support asyncio subprocess %r', self._proc)

        except Exception as err:
            logger.exception('%s: interact: %s', proc, err)
            raise

        logger.debug('%s: interact: output: %s', proc, result)
        return result

    def terminate(self):
        self._proc.terminate()

    async def signal(self, sig):
        async with self._input_lock:
            os.kill(self._proc.pid, sig)

    @property
    def proc(self):
        return self._proc

    @property
    def started(self):
        return self._proc_started

    @property
    def terminated(self):
        return self._proc_terminated

    @property
    def on_output(self, value):
        return self._on_output

    @on_output.setter
    def on_output(self, value):
        self._on_output = value


class DummySubprocess:
    def __init__(self):
        self._pid = random.choice(range(32768, 65536))

    @property
    def pid(self):
        return self._pid

    @property
    def returncode(self):
        return 0

    def terminate(self):
        pass
