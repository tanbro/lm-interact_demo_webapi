"""
transformer-learning-conv-ai 的 web chat demo
"""

import argparse
import os
import sys

from .app import app


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    # web
    group = parser.add_argument_group('Web 服务器参数')
    group.add_argument('--debug', '-d', action='store_true',
                       help='输出 Web 框架的 Debug 信息 (default=%(default)s)')
    group.add_argument('--http-host', '-s', type=str, default='*',
                       help='HTTP 服务地址 (default=%(default)s)')
    group.add_argument('--http-port', '-p', type=int, default=8888,
                       help='HTTP 服务端口 (default=%(default)s)')
    group.add_argument('--allow-origins', type=str, nargs='*',
                       help='Access-Control-Allow-Origin 响应头中允许的域的列表 (default=%(default)s)')
    # interact
    group = parser.add_argument_group(
        'transformer-learning-conv-ai 交互演示命令行执行程序的相关运行参数')
    group.add_argument("--interact-cmd", type=str, default=sys.executable,
                       help="交互对话程序的启动命令. (default=%(default)s)")
    group.add_argument("--interact-args", type=str, default='interact.py',
                       help="交互对话程序的命令参数. (default=%(default)s)")
    group.add_argument("--interact-pwd", type=str, default=os.getcwd(),
                       help="交互对话程序的工作目录. (default=%(default)s)")
    args = parser.parse_args()
    # return
    return args


def main(args: argparse.Namespace):
    app.config.update(vars(args))
    from . import middlewares
    from . import routes
    app.run(debug=args.debug, host=args.http_host, port=args.http_port)


if __name__ == "__main__":
    args = parse_args()
    code = main(args)
    exit(code)
