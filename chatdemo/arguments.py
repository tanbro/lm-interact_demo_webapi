import argparse
import os
import sys


def get_args(description: str = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    add_web_args(parser)
    add_interact_args(parser)
    return parser.parse_args()


def add_web_args(parser):
    group = parser.add_argument_group('Web 服务器参数。')
    group.add_argument('--debug', '-d', action='store_true',
                       help='输出 Web 框架的 Debug 信息。 (default=%(default)s)')
    group.add_argument('--http-host', '-s', type=str, default='*',
                       help='HTTP 服务地址。 (default=%(default)s)')
    group.add_argument('--http-port', '-p', type=int, default=8888,
                       help='HTTP 服务端口。 (default=%(default)s)')
    group.add_argument('--allow-origins', type=str, nargs='*',
                       help='Access-Control-Allow-Origin 响应头中允许 CORS 的域列表。'
                       '"*" 表示允许所有的域, None 表示禁止 CORS。 (default=%(default)s)')


def add_interact_args(parser):
    group = parser.add_argument_group(
        'transformer-learning-conv-ai 交互演示命令行执行程序的相关运行参数')
    group.add_argument("--interact-prog", type=str, default=sys.executable,
                       help="交互对话程序的启动命令。 (default=%(default)s)")
    group.add_argument("--interact-args", type=str, default='interact2.py',
                       help="交互对话程序的命令参数。 (default=%(default)s)")
    group.add_argument("--interact-pwd", type=str, default=os.getcwd(),
                       help="交互对话程序的工作目录。 (default=%(default)s)")
