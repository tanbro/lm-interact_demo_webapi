from uuid import uuid1
import asyncio
import logging

from starlette.exceptions import HTTPException
from starlette.responses import Response

from ..app import app
from ..models.backend import Backend, BackendState
from ..models.qa import Answer, Question
from ..settings import settings
from ..utils.interactor import Interactor
import shlex

MAX_BACKENDS = 1

backends: Dict[
    str,
    Tuple[Backend, Interactor, asyncio.Lock]
] = {}

backends_lock = asyncio.Lock()


@app.get('/qa', response_model=List[Backend])
def list_():
    return [v[0] for v in backends.values()]


@app.post('/qa', status_code=201, response_model=Backend)
async def create(wait: float = 0):
    logger = logging.getLogger(__name__)

    def fn_con_started(output_file: str, output_text: str) -> bool:
        return output_text.strip().lower().startswith('ready')

    async def fn_on_terminate(uid):
        logger = logging.getLogger(__name__)
        logger.warning('QA backend terminated')
        async with backends_lock:
            try:
                del backends[uid]
            except KeyError:
                pass

    async with backends_lock:
        if len(backends) >= MAX_BACKENDS:
            raise HTTPException(
                status_code=403,
                detail='Max length of backends reached: {}'.format(
                    MAX_BACKENDS)
            )
        uid = uuid1()
        backend = Backend(
            uid=uid,
            program=settings.qa_program,
            args=settings.qa_args,
            cwd=settings.qa_cwd
        )
        logger.info('create QA backend: %s', backend)

        interactor = Interactor(
            backend.program, shlex.split(backend.args), backend.cwd,
            started_condition=fn_con_started,
            on_terminated=lambda: fn_on_terminate(uid),
        )
        lock = asyncio.Lock()
        backends[uid] = (backend, interactor, lock)
        await interactor.startup()

    return Response()


@app.get('/qa/{uid}', response_model=Backend)
def get(uid: UUID):
    try:
        obj, *_ = backends[uid]
    except KeyError:
        raise HTTPException(403)
    return obj


@app.post('/qa/{uid}', response_model=Answer)
async def interact(uid: UUID, item: Question, timeout: float = 15):
    try:
        _, interactor, lock, *_ = backends[uid]
    except KeyError:
        raise HTTPException(404)

    in_txt = '{title}<sep>{text}<sep><sep><|endoftext|>'.format(item.dict())

    async with lock:
        out_txt = await interactor.interact(in_txt, timeout=timeout)

    out_txt = out_txt.lstrip('>').lstrip().lstrip('▁').lstrip()
    answer = Answer(text=out_txt)

    return answer
