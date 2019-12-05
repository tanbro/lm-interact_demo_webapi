from sanic.response import text

async def hello(request):
  return text("hello! it works!")
