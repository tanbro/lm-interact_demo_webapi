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
        if proc:
            d = {'id': proc.pid}
            d.update(proc_info)
            return response.json([d])
        return response.json([])

    async def post(self, request):
        global proc, proc_info

        program = app.config.qa_prog
        _args = app.config.qa_args
        args = shlex.split(_args)
        cwd = app.config.qa_pwd

        async def stream_from_interact(res):
            global proc_info
            started = False
            response_aws = []
            # 读 interact 进程输出
            streams = proc.stdout, proc.stderr
            async with AioStreamsLineReader(streams) as reader:
                async for line_pair in reader:
                    for name, line in zip(('STDOUT', 'STDERR'), line_pair):
                        if line is not None:
                            logger.info('%s %s: %s', proc, name, line)
                            # stdout, stderr 发送到浏览器
                            response_aws.append(asyncio.create_task(
                                res.write(line + os.linesep)
                            ))
                            if line == 'Started':
                                started = True
                    if started:
                        break
                if reader.at_eof:
                    logger.error('%s: interact 进程已退出', proc)
                    await terminate_proc()
                    abort(500)
            proc_info.update({'started': True})
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
                'program': program,
                'cwd': cwd,
                'args': _args,
                'started': False,
            }
            # 等待启动
            logger.info('持续读取 %s 进程输出，等待其启动完毕 ..', proc)
            # Streaming 读取 stdout, stderr ...
            return response.stream(stream_from_interact, headers={'X-PROCID': proc.pid})


class Input(HTTPMethodView):
    def options(self, request, id_):
        return response.raw(b'')

    async def post(self, request, id_):
        if lock.locked():
            return response.text('', 409)
        # 用户输入
        title = request.json['title'].strip()
        text = request.json['text'].strip()
        if (not title) and (not text):
            return response.text('', 400)
        # interact 进程交互
        async with lock:
            if not proc:
                return response.text('', 404)
            if proc.pid != id_:
                return response.text('', 404)
            if not proc_info.get('started'):
                return response.text('', 409)
            logger.info('intput: %s\n\t%s', title, text)
            # 传到 interact 进程
            context_string = f'{title}<sep>{text}<sep><sep><|endoftext|>'
            data = (context_string + os.linesep).encode()
            proc.stdin.write(data)
            await proc.stdin.drain()
            # 读取 interact 进程 的 stdout/stderr 输出
            answer = None
            streams = proc.stdout, proc.stderr
            async with AioStreamsLineReader(streams) as reader:
                async for line_pair in reader:
                    for name, line in zip(('STDOUT', 'STDERR'), line_pair):
                        if line is not None:
                            logger.info('%s %s: %s', proc, name, line)
                            if name == 'STDOUT':
                                answer = line
                    if answer is not None:
                        break
                if reader.at_eof:
                    logger.error('%s: interact 进程已退出', proc)
                    await terminate_proc()
                    abort(500)
            # response
            answer = answer.lstrip('>').lstrip()
            return response.json({
                'answer': answer,
            })


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
