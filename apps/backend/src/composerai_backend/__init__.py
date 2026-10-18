import asyncio
import os
import signal
from pathlib import Path

from composerai_store import LocalProjectStore

_PAYLOAD = b"mounted\n"


async def _run() -> None:
    root = Path(os.environ["COMPOSERAI_PROJECT_ROOT"])
    project = os.environ.get("COMPOSERAI_PROJECT_NAME") or "demo"
    store = LocalProjectStore(root)
    await store.write(f"{project}/verse-1/mounted.txt", _PAYLOAD)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    loop.add_signal_handler(signal.SIGINT, stop.set)
    await stop.wait()


def main() -> None:
    asyncio.run(_run())
