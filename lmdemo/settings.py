from os import getcwd
from sys import executable

from pydantic import BaseSettings, Field

ENV_PREFIX = 'APP'


def env(s: str) -> str:
    return '{0}_{1}'.format(
        ENV_PREFIX,
        s.strip().strip('_').upper()
    )


class Settings(BaseSettings):
    allow_origins: str = Field('*', env=env('allow_origins'))
    chat_program: str = Field(executable, env=env('chat_program'))
    chat_args: str = Field('', env=env('chat_args'))
    chat_cwd: str = Field(getcwd(), env=env('chat_cwd'))


settings = Settings()
