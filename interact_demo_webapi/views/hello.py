from sanic import response


def hello(request):
    return response.text("hello! it works!")
