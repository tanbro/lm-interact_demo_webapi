from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .settings import settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins.split(),
    allow_methods=['*'],
    allow_headers=['*'],
)
