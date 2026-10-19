import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from midi_llm_http.server import Service, make_server

MIDI = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"


@pytest.fixture
def service() -> Service:
    return Service()


@pytest.fixture
def base_url(service: Service):
    server = make_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(url: str, payload: dict[str, object] | None = None) -> tuple[int, str, bytes]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {} if data is None else {"Content-Type": "application/json"}
    method = "GET" if data is None else "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def test_importing_the_http_module_does_not_import_torch() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import midi_llm_http.server, sys; "
            "raise SystemExit('torch' in sys.modules or 'midi_llm_http.model' in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr


def test_health_is_503_until_the_model_is_loaded(service: Service, base_url: str) -> None:
    status, _, _ = _request(f"{base_url}/health")
    assert status == 503

    service.mark_ready(lambda prompt, temperature, top_p, max_tokens: MIDI)
    status, _, body = _request(f"{base_url}/health")
    assert status == 200
    assert body == b"ok"


def test_generate_before_load_is_503(base_url: str) -> None:
    status, _, _ = _request(f"{base_url}/generate", payload={"prompt": "a waltz"})
    assert status == 503


@pytest.mark.parametrize(
    "payload",
    [{}, {"prompt": 1}, {"prompt": ""}, {"prompt": "   "}, {"prompt": "a waltz", "max_tokens": 1.5}],
)
def test_bad_prompt_is_400_and_does_not_run_the_model(
    service: Service,
    base_url: str,
    payload: dict[str, object],
) -> None:
    called = False

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        nonlocal called
        called = True
        return MIDI

    service.mark_ready(generate)
    status, _, _ = _request(f"{base_url}/generate", payload=payload)
    assert status == 400
    assert called is False


def test_generate_returns_one_midi_body_with_checkpoint_defaults(service: Service, base_url: str) -> None:
    seen: list[tuple[str, float, float, int]] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        seen.append((prompt, temperature, top_p, max_tokens))
        return MIDI

    service.mark_ready(generate)
    status, content_type, body = _request(f"{base_url}/generate", payload={"prompt": "a waltz"})
    assert status == 200
    assert content_type == "audio/midi"
    assert body == MIDI
    assert seen == [("a waltz", 1.0, 0.98, 2046)]


def test_generate_forwards_sampling_parameters(service: Service, base_url: str) -> None:
    seen: list[tuple[str, float, float, int]] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        seen.append((prompt, temperature, top_p, max_tokens))
        return MIDI

    service.mark_ready(generate)
    status, content_type, body = _request(
        f"{base_url}/generate",
        payload={"prompt": "a waltz", "temperature": 0.5, "top_p": 0.9, "max_tokens": 8},
    )
    assert status == 200
    assert content_type == "audio/midi"
    assert body == MIDI
    assert seen == [("a waltz", 0.5, 0.9, 8)]
