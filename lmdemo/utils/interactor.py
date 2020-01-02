import asyncio.subprocess
import logging
import os
from locale import getpreferredencoding
from typing import (Any, Awaitable, Callable, Coroutine, List, Optional,
                    TypeVar, Union)

from fastapi import HTTPException

# 同步或者异步的回调类型
Callback = TypeVar('Callback',
                   Callable[..., Any],
                   Callable[..., Awaitable[Any]],
                   None)


OnStartedCallback = TypeVar('OnStartedCallback',
                            Callable[[], None],
                            Callable[[], Awaitable[None]],
                            None)

StartedConditionCallback = TypeVar('StartedConditionCallback',
                                   Callable[[str, str], bool],
                                   Callable[[str, str], Awaitable[bool]],
                                   None)

OnOutputCallback = TypeVar('OnOutputCallback',
                           Callable[[str, str], None],
                           Callable[[str, str], Awaitable[None]],
                           None)


class Interactor:
    def __init__(self,
                 proc_program: str,
                 proc_args: Optional[List[str]] = None,
                 proc_cwd: str = '',
                 started_condition: StartedConditionCallback = None,
                 on_started: OnStartedCallback = None,
                 on_output: OnOutputCallback = None,
                 on_terminated: Callback = None,
                 ):
        self._logger = logging.getLogger(self.__class__.__qualname__)
        self._proc_program = proc_program
        self._proc_cwd = proc_cwd
        self._proc_args = proc_args or []
        self._proc = None
        self._proc_started = False
        self._proc_terminated = False
        self._started_condition = started_condition
        self._on_started = on_started
        self._on_output = on_output
        self._on_terminated = on_terminated
        self._stdout_callback = None
        self._stderr_callback = None
        self._input_lock = asyncio.Lock()

    async def startup(self):
        logger = self._logger
        self._proc = await asyncio.create_subprocess_exec(
            self._proc_program,
            *self._proc_args,
            cwd=self._proc_cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info('%s: pending', self._proc)
        if not self._started_condition:
            self._proc_started = True
            func = self._on_started
            if asyncio.iscoroutinefunction(func):
                await func()
            elif callable(func):
                func()
        asyncio.create_task(self.monitor())
        return self._proc

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
                aws = {
                    asyncio.create_task(self.read_line(stream, name_tag))
                    for name_tag, stream in [('stdout', proc.stdout), ('stderr', proc.stderr)]
                }
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
                            started = func(name, line)
                            if asyncio.iscoroutine(started):
                                started = await started
                            self._proc_started = bool(started)
                        if self._proc_started:
                            logger.info('%s: started', proc)
                            func = self._on_started
                            if asyncio.iscoroutine(func):
                                await func
                            elif callable(func):
                                ret_val = func()
                                if asyncio.iscoroutine(ret_val):
                                    await ret_val
                    # 启动的回调函数
                    if self._proc_started:
                        if name == 'stdout':
                            func = self._stdout_callback
                            if asyncio.iscoroutine(func):
                                await func
                            elif callable(func):
                                ret_val = func()
                                if asyncio.iscoroutine(ret_val):
                                    await ret_val
                    # onOutput 无论是否启动成功
                    func = self._on_output
                    if asyncio.iscoroutine(func):
                        await func
                    elif callable(func):
                        ret_val = func()
                        if asyncio.iscoroutine(ret_val):
                            await ret_val
                    if func:
                        if callable(func):
                            ret_val = func(name, line)
                            if asyncio.iscoroutine(ret_val):
                                await ret_val
            # end of while

            self._proc_terminated = True
            logger.warning('%s: terminated(returncode=%s)', proc, proc.returncode)

            func = self._on_terminated
            if asyncio.iscoroutine(func):
                await func
            elif callable(func):
                ret_val = func()
                if asyncio.iscoroutine(ret_val):
                    await ret_val

        except Exception as err:
            logger.exception('%s: monitor: %s', proc, err)
            raise

    async def interact(self, input_text: str, timeout=30, encoding=None) -> str:
        proc = self._proc
        logger = self._logger
        lock = self._input_lock

        if not self.started:
            raise HTTPException(
                status_code=409, detail='Process {} started condition not matched'.format(proc))
        if lock.locked():
            raise HTTPException(status_code=409)

        logger.debug('%s: interact: input: %s', proc, input_text)
        encoding = encoding or getpreferredencoding()
        input_data = '{0}{1}'.format(
            input_text.strip(), os.linesep).encode(encoding)

        try:
            async with lock:
                output_future = asyncio.get_event_loop().create_future()
                self._stdout_callback = lambda x: (
                    output_future.set_result(x.strip())
                )
                try:
                    proc.stdin.write(input_data)
                    aws = (
                        proc.stdin.drain(),
                        output_future
                    )
                    _, pending = await asyncio.wait(aws, timeout=timeout)
                    if pending:
                        for task in pending:
                            task.cancel()
                        raise RuntimeError(
                            'streaming i/o tasks can not be done: %r', pending)
                finally:
                    self._stdout_callback = None

            output_text = output_future.result()
        except Exception as err:
            logger.exception('%s: interact: %s', proc, err)
            raise

        logger.debug('%s: interact: output: %s', proc, output_text)
        return output_text

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
