from sanic.exceptions import abort

from .app import app


@app.middleware('response')
def setup_cors_headers(request, response):
    origin = app.config.allow_origin.strip()   
    if origin:
        response.headers.update({
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'OPTIONS, GET, POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Vary': 'Accept-Encoding',
        })
        if not '*' in origin:
            response.headers.update({
                'Vary': 'Accept-Encoding, Origin',
            })
