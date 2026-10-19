import json
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Protocol

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


def _float_field(payload: dict[str, object], key: str, default: float) -> float | None:
    if key not in payload:
        return default
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _int_field(payload: dict[str, object], key: str, default: int) -> int | None:
    if key not in payload:
        return default
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def make_server(service: Service, host: str, port: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/health":
                self._send(404, b"not found", "text/plain")
                return
            if service.ready:
                self._send(200, b"ok", "text/plain")
                return
            self._send(503, b"loading", "text/plain")

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/generate":
                self._send(404, b"not found", "text/plain")
                return
            payload = self._payload()
            if payload is None:
                self._send(400, b"invalid json", "text/plain")
                return
            prompt = payload.get("prompt")
            if not isinstance(prompt, str):
                self._send(400, b"invalid prompt", "text/plain")
                return
            if not prompt.strip():
                self._send(400, b"blank prompt", "text/plain")
                return
            temperature = _float_field(payload, "temperature", DEFAULT_TEMPERATURE)
            top_p = _float_field(payload, "top_p", DEFAULT_TOP_P)
            max_tokens = _int_field(payload, "max_tokens", DEFAULT_MAX_TOKENS)
            if temperature is None or top_p is None or max_tokens is None:
                self._send(400, b"invalid generation parameters", "text/plain")
                return
            if not service.ready:
                self._send(503, b"loading", "text/plain")
                return
            try:
                body = service.generate(prompt, temperature, top_p, max_tokens)
            except Exception:
                traceback.print_exc()
                self._send(500, b"generation failed", "text/plain")
                return
            self._send(200, body, "audio/midi")

        def _payload(self) -> dict[str, object] | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None
            try:
                length = int(raw_length)
            except ValueError:
                return None
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None
            return payload

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HTTPServer((host, port), Handler)


def serve(service: Service, host: str = "0.0.0.0", port: int = 8000) -> None:
    make_server(service, host, port).serve_forever()
