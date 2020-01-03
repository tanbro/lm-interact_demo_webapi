from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .routers import chat, qa
from .settings import settings

app = FastAPI(
    title="LM Demo",
    description="Language Model Demo WebService"
)  # pylint:disable=invalid-name

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins.split(),
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(chat.router, prefix='/chat', tags=['chat'])
app.include_router(qa.router, prefix='/qa', tags=['qa'])
