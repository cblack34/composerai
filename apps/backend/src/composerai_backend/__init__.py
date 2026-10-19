import asyncio

import uvicorn

from composerai_store import LocalProjectStore

from composerai_backend.api import app
from composerai_backend.lead import agent, search_agent
from composerai_backend.paths import probe_path
from composerai_backend.settings import Settings

_PAYLOAD = b"mounted\n"
# A published container port reaches 0.0.0.0, not the loopback interface.
_HOST = "0.0.0.0"
_PORT = 8000


async def _serve() -> None:
    config = uvicorn.Config(app, host=_HOST, port=_PORT)
    async with agent, search_agent:
        await uvicorn.Server(config).serve()


async def _run() -> None:
    settings = Settings()
    store = LocalProjectStore(settings.project_root)
    await store.write(probe_path(settings.project_name), _PAYLOAD)
    await _serve()


def main() -> None:
    asyncio.run(_run())
