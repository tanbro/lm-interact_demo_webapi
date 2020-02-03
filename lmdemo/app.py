from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

from .routers import chat, qa
from .settings import settings

# pylint:disable=invalid-name
app = FastAPI(
    title='LM Demo',
    description='Language Model Demo WebService',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins.split(),  # pylint:disable=no-member
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(chat.router, prefix='/chat', tags=['chat'])
app.include_router(qa.router, prefix='/qa', tags=['qa'])


@app.get('/')
def root():
    return PlainTextResponse('It works!')
