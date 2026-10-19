import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from composerai_backend.midi_llm import HttpMidiLlmClient, MidiLlmError


class _Handler(BaseHTTPRequestHandler):
    status = 200
    seen: list[tuple[str, str | None, bytes]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        _Handler.seen.append((self.path, self.headers.get("Content-Type"), self.rfile.read(length)))
        body = b"MThd\x00" if self.status == 200 else b"loading"
        content_type = "audio/midi" if self.status == 200 else "text/plain"
        self.send_response(self.status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def midi_llm_url() -> Iterator[str]:
    _Handler.status = 200
    _Handler.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def test_http_client_posts_the_prompt_and_returns_the_body(midi_llm_url: str) -> None:
    client = HttpMidiLlmClient(midi_llm_url)
    assert await client.generate("a waltz") == b"MThd\x00"
    path, content_type, raw = _Handler.seen[0]
    assert path == "/generate"
    assert content_type == "application/json"
    assert json.loads(raw) == {"prompt": "a waltz"}


async def test_http_client_raises_on_an_http_error(midi_llm_url: str) -> None:
    _Handler.status = 503
    client = HttpMidiLlmClient(midi_llm_url)
    with pytest.raises(MidiLlmError):
        await client.generate("a waltz")


async def test_http_client_raises_when_nothing_is_listening() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    host, port = server.server_address
    server.server_close()
    client = HttpMidiLlmClient(f"http://{host}:{port}")
    with pytest.raises(MidiLlmError):
        await client.generate("a waltz")


class _DropHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.connection.shutdown(socket.SHUT_RDWR)
        self.connection.close()

    def log_message(self, format: str, *args: object) -> None:
        return


async def test_http_client_raises_when_the_service_drops_the_connection() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DropHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        client = HttpMidiLlmClient(f"http://{host}:{port}")
        with pytest.raises(MidiLlmError):
            await client.generate("a waltz")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _truncated_response_url() -> tuple[str, threading.Thread]:
    ready = threading.Event()
    port: dict[str, int] = {}

    def run() -> None:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port["value"] = listener.getsockname()[1]
        ready.set()
        conn, _ = listener.accept()
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        conn.sendall(
            b"HTTP/1.0 200 OK\r\nContent-Type: audio/midi\r\nContent-Length: 100\r\n\r\nMThd"
        )
        conn.shutdown(socket.SHUT_WR)
        try:
            while conn.recv(1024):
                pass
        except OSError:
            pass
        conn.close()
        listener.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    return f"http://127.0.0.1:{port['value']}", thread


async def test_http_client_raises_when_the_response_is_truncated() -> None:
    url, thread = _truncated_response_url()
    try:
        client = HttpMidiLlmClient(url)
        with pytest.raises(MidiLlmError):
            await client.generate("a waltz")
    finally:
        thread.join(timeout=5)
