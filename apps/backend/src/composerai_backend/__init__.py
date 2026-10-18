import asyncio
import signal

from composerai_backend.paths import probe_path
from composerai_backend.settings import Settings
from composerai_store import LocalProjectStore

_PAYLOAD = b"mounted\n"


async def _run() -> None:
    settings = Settings()
    store = LocalProjectStore(settings.project_root)
    await store.write(probe_path(settings.project_name), _PAYLOAD)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    loop.add_signal_handler(signal.SIGINT, stop.set)
    await stop.wait()


def main() -> None:
    asyncio.run(_run())
