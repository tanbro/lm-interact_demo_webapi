from .app import app


@app.middleware('response')
def setup_cors_headers(request, response):
    origin = app.config.allow_origin.strip()
    response.headers.update({
        'Access-Control-Allow-Origin': origin
    })
    if origin == '*':
        response.headers.update({
            'Vary': 'Origin'
        })
