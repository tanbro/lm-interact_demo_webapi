from sanic import Sanic
from sanic.views import HTTPMethodView
from sanic.response import text, json


class HelloRootView(HTTPMethodView):

    async def get(self, request):
        return json({"hello": "world"})
