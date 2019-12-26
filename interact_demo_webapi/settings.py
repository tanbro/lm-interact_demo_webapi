from sys import executable

from pydantic import BaseSettings, Field

ENV_PREFIX = 'LMDEMO'


def env(s: str) -> str:
    return '{0}_{1}'.format(
        ENV_PREFIX,
        s.strip().strip('_').upper()
    )


class Settings(BaseSettings):
    chat_program: str = Field(executable, env=env('chat_program'))
    chat_args: str = Field('', env=env('chat_args'))
    chat_cwd: str = Field('.', env=env('chat_cwd'))


settings = Settings()
