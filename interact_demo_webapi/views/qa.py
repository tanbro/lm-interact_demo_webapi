import asyncio
import os
import shlex
import signal
from datetime import datetime

from sanic import Sanic, response
from sanic.exceptions import abort
from sanic.log import logger
from sanic.views import HTTPMethodView

from ..app import app
from ..helpers.aiostreamslinereader import AioStreamsLineReader

proc: asyncio.subprocess.Process = None
lock = asyncio.Lock()
proc_info = {}


class Index(HTTPMethodView):

    def options(self, request):
        return response.raw(b'')

    def get(self, request):
        # List
        pass

    async def post(self, request):
        global proc, proc_info

        program = app.config.qa_prog
        args = shlex.split(app.config.qa_args)
        cwd = app.config.qa_pwd

        async def stream_from_interact(res):
            global proc_info
            personality = ''
            response_aws = []
            # 读 interact 进程输出
            streams = proc.stdout, proc.stderr
            async with AioStreamsLineReader(streams) as reader:
                async for stdout_line, stderr_line in reader:
                    if stdout_line is not None:
                        # 收到第一个 stdout 认为启动成功！输出内容当作 personality
                        logger.info('%s STDOUT: %s', proc, stdout_line)
                        personality = stdout_line
                        # 发送到浏览器
                        response_aws.append(asyncio.create_task(
                            res.write(stderr_line + os.linesep)
                        ))
                    elif stderr_line is not None:
                        logger.info('%s STDERR: %s', proc, stderr_line)
                        # 发送到浏览器
                        response_aws.append(asyncio.create_task(
                            res.write(stderr_line + os.linesep)
                        ))
                if reader.at_eof:
                    logger.error('%s: interact 进程已退出', proc)
                    await terminate_proc()
                    abort(500)
            logger.info(
                '%s 启动成功',
                proc
            )

            # 等待到浏览器发送完毕
            if response_aws:
                _, pending = await asyncio.wait(response_aws, timeout=15)
                for task in pending:
                    task.cancel()
            # stream coroutine 结束

        if lock.locked():
            return response.text('', 409)

        async with lock:
            # 首先关闭
            await terminate_proc()

            # 然后新建
            logger.info(
                'create subprocess: program=%s, args=%s, cwd=%s',
                program, args, cwd
            )
            proc = await asyncio.create_subprocess_exec(
                program,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            logger.info('subprocess created: %s', proc)
            proc_info = {
                'personality': '',
                'started': False,
                'history': [],
            }
            # 等待启动
            logger.info('持续读取 %s 进程输出，等待其启动完毕 ..', proc)
            # Streaming 读取 stdout, stderr ...
            return response.stream(stream_from_interact, headers={'X-PROCID': proc.pid})


async def terminate_proc():
    global proc
    if proc:
        logger.info('terminate: %s', proc)
        try:
            proc.terminate()
        except ProcessLookupError as e:
            proc = None
            logger.error(
                'ProcessLookupError when terminating %s: %s', proc, e)
        else:
            logger.info('terminate %s: waiting...', proc)
            await proc.wait()
            logger.info('terminate %s: ok. returncode=%s',
                        proc, proc.returncode)
            proc = None
            proc_info = {}
