"""
transformer-learning-conv-ai 的 web chat demo
"""

from .app import app
from .arguments import get_args


def main(args):
    app.config.update(vars(args))
    from . import middlewares
    from . import routes
    app.run(host=args.http_host, port=args.http_port, debug=args.debug)


if __name__ == '__main__':
    args = get_args(__doc__)
    code = main(args)
    exit(code)
