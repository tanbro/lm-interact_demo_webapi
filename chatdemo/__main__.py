"""
transformer-learning-conv-ai 的 web chat demo
"""

import argparse
import os.path
import sys

from sanic import Sanic
from sanic.response import json

from .app import app
from .route import setup_routings


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transformers-example-dir', '-e', type=str, default='transformers/example',
                        help='pytorch-transformer （改） 的 examples 目录 (default=%(default)s)')
    parser.add_argument('--src-dir', '-c', type=str, default='transformer-learning-conv-ai',
                        help='transformer-learning-conv-ai （改） 源代码所在目录 (default=%(default)s)')
    parser.add_argument('--http-host', '-s', type=str, default='localhost',
                        help='Host of serving http address (default=%(default)s)')
    parser.add_argument('--http-port', '-p', type=int, default=8888,
                        help='Port of serving http address (default=%(default)s)')
    args = parser.parse_args()
    return args


def main(args: argparse.Namespace):
    sys.path.append(args.transformers_example_dir)
    sys.path.append(args.src_dir)
    setup_routings()
    app.run(host=args.http_host, port=args.http_port)


if __name__ == "__main__":
    args = parse_args()
    code = main(args)
    exit(code)
