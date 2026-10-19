import traceback
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, field_validator

DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 0.98
DEFAULT_MAX_TOKENS = 2046


class MidiGenerator(Protocol):
    def __call__(self, prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes: ...


class Service:
    def __init__(self) -> None:
        self._generator: MidiGenerator | None = None

    @property
    def ready(self) -> bool:
        return self._generator is not None

    def mark_ready(self, generator: MidiGenerator) -> None:
        self._generator = generator

    def generate(self, prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        generator = self._generator
        if generator is None:
            raise RuntimeError("model is not loaded")
        return generator(prompt, temperature, top_p, max_tokens)


class GenerateBody(BaseModel):
    prompt: str
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    max_tokens: int = DEFAULT_MAX_TOKENS

    @field_validator("prompt")
    @classmethod
    def _prompt_has_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank prompt")
        return value


def create_app(service: Service) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> Response:
        if not service.ready:
            raise HTTPException(status_code=503, detail="loading")
        return Response(content=b"ok", media_type="text/plain")

    @app.post("/generate")
    def generate(body: GenerateBody) -> Response:
        if not service.ready:
            raise HTTPException(status_code=503, detail="loading")
        try:
            data = service.generate(body.prompt, body.temperature, body.top_p, body.max_tokens)
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="generation failed") from exc
        return Response(content=data, media_type="audio/midi")

    return app
