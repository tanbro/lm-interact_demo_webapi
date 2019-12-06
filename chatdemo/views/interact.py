import asyncio
import os
import shlex

from sanic import Sanic
from sanic.exceptions import abort
from sanic.log import logger
from sanic.response import json
from sanic.views import HTTPMethodView

from ..app import app

PERSONALITY_PREFIX = 'INFO:interact.py:Selected personality:'

proc: asyncio.subprocess.Process = None
lock = asyncio.Lock()


class Index(HTTPMethodView):

    def get(self, request, id_):
        if not proc:
            abort(404)
        if proc.pid != id_:
            abort(404)
        return json({'id': proc.pid})


class Reset(HTTPMethodView):
    async def post(self, request):
        global proc

        program = app.config.interact_cmd
        args = shlex.split(app.config.interact_args)
        cwd = app.config.interact_pwd

        if lock.locked():
            abort(409)
        async with lock:
            # 首先关闭
            if proc:
                logger.info('terminate: %s', proc)
                try:
                    proc.terminate()
                except ProcessLookupError as e:
                    logger.error('ProcessLookupError when terminating %s: %s', proc, e)
                else:
                    logger.info('wait: %s', proc)
                    await proc.wait()
                    logger.info('terminated: %s', proc)
                proc = None

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
            logger.info(
                'subprocess created: %s',
                proc
            )

            # 等待启动
            personality = ''
            reader_name = 'STDERR'
            reader = proc.stderr
            while True:
                line = await reader.readline()
                line = line.decode().strip()
                logger.info('%s %s: %s', proc, reader_name, line)
                if line.startswith(PERSONALITY_PREFIX):
                    personality = line[len(PERSONALITY_PREFIX):].strip().lstrip('▁').lstrip()
                    break
            return json(dict(
                id=proc.pid,
                personality=personality,
            ))


class Input(HTTPMethodView):
    async def post(self, request, id_):
        if lock.locked():
            abort(409)
        async with lock:
            if not proc:
                abort(404)
            if proc.pid != id_:
                abort(404)
            # 用户输入
            msg = request.json['msg'].strip()
            logger.info('intput: %s', msg)
            # 传到 interact 进程
            data = (msg.strip() + os.linesep).encode()
            proc.stdin.write(data)
            await proc.stdin.drain()
            # 读取 interact 进程 的 stdout 输出
            data = await proc.stdout.readline()
            msg = data.decode().strip()
            logger.info('output: %s', msg)
            msg = msg.lstrip('>').lstrip().lstrip('▁').lstrip()
            # 尝试读取 interact 进程 的 stderr 输出，一直尝试读取，直到超时
            while True:
                try:
                    data = await asyncio.wait_for(proc.stderr.readline(), timeout=1)
                except asyncio.TimeoutError:
                    break
                else:
                    txt = data.decode().strip()
                    logger.info('%s STDERR: %s', proc, txt)
            # 返回
            return json(dict(
                msg=msg
            ))
