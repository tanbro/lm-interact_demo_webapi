import asyncio
from locale import getpreferredencoding
from typing import List, Optional


class AioStreamsLineReader:
    EOF = -1

    def __init__(self,
                 streams: List[asyncio.StreamReader] = [],
                 encoding: Optional[str] = None,
                 timeout: float = 1
                 ):
        if not streams:
            raise ValueError('streams cannot be empty.')
        self._streams = streams
        self._encoding = encoding
        self._timeout = float(timeout)
        self._at_eof = False
        self._exit_flag = False
        self._exit_lock = asyncio.Lock()

    async def readline(self):

        async def _read(stream, tag=None):
            line = await stream.readline()
            return line, tag

        encoding = self._encoding or getpreferredencoding()
        lines = [None for _ in range(len(self._streams))]
        aws = {
            asyncio.create_task(_read(stream, i))
            for i, stream in enumerate(self._streams)
        }
        done, pending = await asyncio.wait(aws, timeout=self._timeout, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            output_bytes, index = task.result()
            if output_bytes == b'':  # EOF!
                self._at_eof = True
                lines[index] = self.EOF
            else:
                self._at_eof = False
                line = output_bytes.decode(encoding).strip()
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
        if self._at_eof:
            raise StopAsyncIteration()
        return lines

    @property
    def encoding(self):
        return self._encoding

    @property
    def timeout(self):
        return self._timeout

    @property
    def at_eof(self):
        return self._at_eof
