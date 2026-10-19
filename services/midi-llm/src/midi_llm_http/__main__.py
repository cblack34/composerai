import asyncio
import contextlib
import traceback

import uvicorn

from midi_llm_http.server import MidiGenerator, Service, create_app


def _checkpoint() -> MidiGenerator:
    from midi_llm_http.model import CheckpointGenerator

    return CheckpointGenerator()


async def _load(service: Service) -> None:
    try:
        service.mark_ready(await asyncio.to_thread(_checkpoint))
    except Exception:
        traceback.print_exc()


async def _serve() -> None:
    service = Service()
    config = uvicorn.Config(create_app(service), host="0.0.0.0", port=8000)
    loader = asyncio.create_task(_load(service))
    try:
        await uvicorn.Server(config).serve()
    finally:
        if not loader.done():
            loader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loader


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
