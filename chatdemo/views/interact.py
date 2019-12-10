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

    def get(self, request, id_=None):
        # List
        if id_ is None:
            if proc:
                d = {'id': proc.pid}
                d.update(proc_info)
                d.pop('history')
                return response.json([d])
            return response.json([])
        # Detail
        if not proc:
            return response.text('', 404)
        if id_ != proc.pid:
            return response.text('', 404)
        d = {'id': proc.pid}
        d.update(proc_info)
        return response.json(d)

    async def post(self, request):
        global proc, proc_info

        program = app.config.interact_prog
        args = shlex.split(app.config.interact_args)
        cwd = app.config.interact_pwd

        async def stream_from_interact(res):
            global proc_info
            personality = ''
            response_aws = []
            # 读 interact 进程输出
            streams = proc.stdout, proc.stderr
            async with AioStreamsLineReader(streams) as reader:
                async for stdout_line, stderr_line in reader:
                    if stdout_line:
                        # 收到第一个 stdout 认为启动成功！输出内容当作 personality
                        logger.info('%s STDOUT: %s', proc, stdout_line)
                        personality = stdout_line
                        # 发送到浏览器
                        response_aws.append(asyncio.create_task(
                            res.write(stderr_line + os.linesep)
                        ))
                        break
                    elif stderr_line:
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
                '%s 启动成功. personality: %s',
                proc, personality
            )
            proc_info.update({
                'personality': personality.lstrip('>').lstrip().lstrip('▁').lstrip(),
                'started': True,
            })
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
            return response.stream(stream_from_interact, headers={'X-INTERACT-ID': proc.pid})


class Input(HTTPMethodView):
    def options(self, request, id_):
        return response.raw(b'')

    async def post(self, request, id_):
        if lock.locked():
            return response.text('', 409)
        # 用户输入
        msg = request.json['msg'].strip()
        if not msg:
            return response.text('', 400)
        # interact 进程交互
        async with lock:
            if not proc:
                return response.text('', 404)
            if proc.pid != id_:
                return response.text('', 404)
            if not proc_info.get('started'):
                return response.text('', 409)
            logger.info('intput: %s', msg)
            proc_info['history'].append({
                'dir': 'input',
                'msg': msg,
                'time': datetime.now().isoformat(),
            })
            # 传到 interact 进程
            data = (msg.strip() + os.linesep).encode()
            proc.stdin.write(data)
            await proc.stdin.drain()
            # 读取 interact 进程 的 stdout/stderr 输出
            msg = ''
            streams = proc.stdout, proc.stderr
            async with AioStreamsLineReader(streams) as reader:
                async for stdout_line, stderr_line in reader:
                    if stdout_line:
                        # 得到了返回消息
                        logger.info('%s STDOUT: %s', proc, stdout_line)
                        msg = stdout_line
                        break
                    elif stderr_line:
                        logger.info('%s STDERR: %s', proc, stderr_line)
                if reader.at_eof:
                    logger.error('%s: interact 进程已退出', proc)
                    await terminate_proc()
                    abort(500)
            # 处理返回消息
            msg = msg.lstrip('>').lstrip().lstrip('▁').lstrip()
            # 更新 interact 对话历史
            proc_info['history'].append({
                'dir': 'output',
                'msg': msg,
                'time': datetime.now().isoformat(),
            })
            # response
            return response.json(dict(
                msg=msg
            ))


class Clear(HTTPMethodView):
    def options(self, request, id_):
        return response.raw(b'')

    async def post(self, request, id_):
        if lock.locked():
            return response.text('', 409)
        # interact 进程交互
        async with lock:
            if not proc:
                return response.text('', 404)
            if proc.pid != id_:
                return response.text('', 404)
            if not proc_info.get('started'):
                return response.text('', 409)
            # 发送 HUP
            os.kill(proc.pid, signal.SIGHUP)
        # response
        return response.text('')


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
