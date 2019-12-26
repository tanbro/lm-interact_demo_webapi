from .app import app


@app.middleware('response')
def setup_cors_headers(request, response):
    allow_origins = app.config.allow_origins
    if allow_origins:
        all_allowed = allowed = '*' in allow_origins
        if all_allowed:
            origin = '*'
        else:
            origin = request.headers.get('origin')
            allowed = origin in allow_origins
        if allowed:
            response.headers.update({
                'Access-Control-Allow-Origin': origin,
                'Access-Control-Allow-Methods': 'OPTIONS, GET, POST',
                'Access-Control-Allow-Headers': 'Content-Type',
            })
            if not all_allowed:
                response.headers.update({
                    'Vary': 'Origin',
                })
