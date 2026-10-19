import asyncio
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 0.98
DEFAULT_MAX_TOKENS = 2046


class MidiGenerator(Protocol):
    def __call__(self, prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes: ...


@dataclass
class _Job:
    prompt: str
    temperature: float
    top_p: float
    max_tokens: int
    future: asyncio.Future[bytes]


class Service:
    def __init__(self) -> None:
        self._generator: MidiGenerator | None = None
        self._jobs: asyncio.Queue[_Job | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    @property
    def ready(self) -> bool:
        return self._generator is not None

    def mark_ready(self, generator: MidiGenerator) -> None:
        self._generator = generator

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        worker = self._worker
        if worker is None:
            return
        self._worker = None
        await self._jobs.put(None)
        await worker

    async def generate(self, prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        if self._worker is None:
            raise RuntimeError("service is not started")
        generator = self._generator
        if generator is None:
            raise RuntimeError("model is not loaded")
        job = _Job(
            prompt,
            temperature,
            top_p,
            max_tokens,
            asyncio.get_running_loop().create_future(),
        )
        await self._jobs.put(job)
        return await job.future

    async def _run(self) -> None:
        while True:
            job = await self._jobs.get()
            if job is None:
                return
            if job.future.done():
                continue
            try:
                generator = self._generator
                if generator is None:
                    raise RuntimeError("model is not loaded")
                data = await asyncio.to_thread(
                    generator,
                    job.prompt,
                    job.temperature,
                    job.top_p,
                    job.max_tokens,
                )
            except Exception as exc:
                if job.future.done():
                    traceback.print_exc()
                else:
                    job.future.set_exception(exc)
            else:
                if not job.future.done():
                    job.future.set_result(data)


class GenerateBody(BaseModel):
    prompt: str
    temperature: float = Field(default=DEFAULT_TEMPERATURE, gt=0, allow_inf_nan=False)
    top_p: float = Field(default=DEFAULT_TOP_P, ge=0, le=1, allow_inf_nan=False)
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=3)

    @field_validator("prompt")
    @classmethod
    def _prompt_has_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank prompt")
        return value


def create_app(service: Service) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await service.start()
        yield
        await service.stop()

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health() -> Response:
        if not service.ready:
            raise HTTPException(status_code=503, detail="loading")
        return Response(content=b"ok", media_type="text/plain")

    @app.post("/generate")
    async def generate(body: GenerateBody) -> Response:
        if not service.ready:
            raise HTTPException(status_code=503, detail="loading")
        try:
            data = await service.generate(body.prompt, body.temperature, body.top_p, body.max_tokens)
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="generation failed") from exc
        return Response(content=data, media_type="audio/midi")

    return app
