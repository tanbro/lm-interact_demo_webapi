import logging
from os import getcwd
from pprint import pformat
from sys import executable

from pydantic import BaseSettings, Field

ENV_PREFIX = 'WEBAPP'


def e(name: str) -> str:
    return '_'.join((ENV_PREFIX, name.strip().strip('_').upper()))


class Settings(BaseSettings):
    allow_origins: str = Field('*', env=e('allow_origins'))

    chat_program: str = Field(executable, env=e('chat_program'))
    chat_args: str = Field('', env=e('chat_args'))
    chat_cwd: str = Field(getcwd(), env=e('chat_cwd'))

    qa_program: str = Field(executable, env=e('qa_program'))
    qa_args: str = Field('', env=e('qa_args'))
    qa_cwd: str = Field(getcwd(), env=e('qa_cwd'))


settings = Settings()

logging.getLogger(__name__).info('settings:\n%s', pformat(settings.dict()))
