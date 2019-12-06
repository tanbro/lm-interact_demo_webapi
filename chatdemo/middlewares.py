from .app import app


@app.middleware('response')
def setup_cors_headers(request, response):
    origin = app.config.allow_origin.strip()
    if origin:
        response.headers.update({
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Accept, Accept-Encoding, Content-Type',
        })
        if origin != '*':
            response.headers.update({
                'Vary': 'Accept-Encoding, Origin',
            })
