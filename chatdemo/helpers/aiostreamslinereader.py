import asyncio
from locale import getpreferredencoding
from typing import List, Optional


class AioStreamsLineReader:

    EOF = -1

    def __init__(self,
                 streams: List[asyncio.StreamReader] = [],
                 encoding: Optional[str] = None,
                 raise_on_eof: bool = False,
                 raise_on_timeout: bool = False,
                 timeout: float = 1
                 ):
        if not streams:
            raise ValueError('streams cannot be empty.')
        self._streams = streams
        self._encoding = encoding
        self._raise_on_eof = bool(raise_on_eof)
        self._raise_on_timeout = bool(raise_on_timeout)
        self._timeout = float(timeout)
        self._at_eof = False
        self._exit_flag = False
        self._exit_lock = asyncio.Lock()

    async def readline(self):

        async def _read(stream, tag=None):
            line = await stream.readline()
            return line, tag

        lines = [None for _ in range(len(self._streams))]
        aws = {
            asyncio.create_task(_read(stream, i))
            for i, stream in enumerate(self._streams)
        }
        try:
            done, pending = await asyncio.wait(aws, timeout=self._timeout, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError:
            if self._raise_on_timeout:
                raise
        else:
            for task in pending:
                task.cancel()
            for task in done:
                output_bytes, index = task.result()
                if output_bytes == b'':  # EOF!
                    self._at_eof = True
                    if self._raise_on_eof:
                        raise EOFError()
                    lines[index] = self.EOF
                else:
                    line = output_bytes.decode(
                        self._encoding or getpreferredencoding()).strip()
                    lines[index] = line
        return tuple(lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        async with self._exit_lock:
            self._exit_flag = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        async with self._exit_lock:
            exit_flag = self._exit_flag
        if exit_flag:
            raise GeneratorExit()
        lines = await self.readline()
        if self.is_eof(lines):
            raise StopAsyncIteration()
        return lines

    def is_eof(self, lines):
        return any(line == self.EOF for line in lines)

    @property
    def encoding(self):
        return self._encoding

    @property
    def raise_on_eof(self):
        return self._raise_on_eof

    @property
    def raise_on_timeout(self):
        return self._raise_on_timeout

    @property
    def timeout(self):
        return self._timeout

    @property
    def at_eof(self):
        return self._at_eof
