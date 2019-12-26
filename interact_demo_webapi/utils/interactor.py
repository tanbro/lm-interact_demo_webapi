import asyncio.subprocess
import logging
import os
from locale import getpreferredencoding
from typing import Callable, Coroutine, List, Optional, Union

from fastapi import HTTPException


class Interactor:
    def __init__(self,
                 proc_program: str,
                 proc_args: Optional[List[str]] = None,
                 proc_cwd: str = '',
                 started_condition=None,
                 on_started=None,
                 on_output=None,
                 on_terminated=None,
                 ):
        self._logger = logging.getLogger(self.__class__.__qualname__)
        self._proc_program = proc_program
        self._proc_cwd = proc_cwd
        self._proc_args = proc_args or []
        self._proc = None
        self._proc_started = False
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
        logger.info('%s: pending', self._proc.pid)
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
        encoding = encoding or getpreferredencoding()

        proc = self._proc
        logger = self._logger

        while True:
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
                if data == b'':  # EOF!
                    break
                line = data.decode(encoding).strip()
                logger.debug('%s: %s: %s', self._proc, name, line)
                if not self._proc_started:
                    started = False
                    func = self._started_condition
                    if asyncio.iscoroutinefunction(func):
                        started = await func(name, line)
                    elif callable(func):
                        started = func(name, line)
                    self._proc_started = bool(started)
                    if started:
                        logger.info('%s: started', self._proc)
                        func = self._on_started
                        if asyncio.iscoroutinefunction(func):
                            asyncio.create_task(func())
                        elif callable(func):
                            asyncio.get_event_loop().call_soon(func)

                if self._proc_started:
                    if callable(self._stdout_callback):
                        self._stdout_callback(line)

                func = self._on_output
                if asyncio.iscoroutinefunction(func):
                    asyncio.create_task(func(name, line))
                elif callable(func):
                    asyncio.get_event_loop().call_soon(func, name, line)

        logger.warning('%s: terminated')
        func = self._on_terminated
        if asyncio.iscoroutinefunction(func):
            asyncio.create_task(func())
        elif callable(func):
            asyncio.get_event_loop().call_soon(func)

    async def interact(self, s: str, timeout=30, encoding=None) -> str:
        proc = self._proc
        logger = self._logger

        if not self._proc_started:
            raise RuntimeError(
                'Process %s started condition not matched',
                proc
            )
        if self._input_lock.locked:
            raise HTTPException(status_code=409)

        logger.info('%s: input: %s', proc, s)

        encoding = encoding or getpreferredencoding()
        data = (s.strip() + os.linesep).encode(encoding)
        fut = asyncio.Future()

        def cb_stdout(_line):
            fut.set_result(_line.strip())

        async with self._input_lock:
            self._stdout_callback = cb_stdout
            try:
                proc.stdin.write(data)
                await proc.stdin.drain()
                await asyncio.wait_for(fut, timeout)
            finally:
                self._stdout_callback = None
        return fut.result()

    def terminate(self):
        self._proc.terminate()

    @property
    def proc(self):
        return self._proc

    @property
    def started(self):
        return self._proc_started
