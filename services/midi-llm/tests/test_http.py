import asyncio
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from midi_llm_http.server import Service, create_app

MIDI = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"


@pytest.fixture
def service() -> Service:
    return Service()


@pytest.fixture
def client(service: Service) -> Iterator[TestClient]:
    with TestClient(create_app(service)) as test_client:
        yield test_client


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


def test_health_is_503_until_the_model_is_loaded(service: Service, client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 503

    service.mark_ready(lambda prompt, temperature, top_p, max_tokens: MIDI)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_generate_before_load_is_503(client: TestClient) -> None:
    response = client.post("/generate", json={"prompt": "a waltz"})
    assert response.status_code == 503


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"prompt": 1},
        {"prompt": ""},
        {"prompt": "   "},
        {"prompt": "a waltz", "max_tokens": 1.5},
        {"prompt": "a waltz", "temperature": 0},
        {"prompt": "a waltz", "temperature": -1},
        {"prompt": "a waltz", "top_p": -0.1},
        {"prompt": "a waltz", "top_p": 1.1},
        {"prompt": "a waltz", "max_tokens": 0},
        {"prompt": "a waltz", "max_tokens": 2},
    ],
)
def test_invalid_generate_body_is_rejected_and_does_not_run_the_model(
    service: Service,
    client: TestClient,
    payload: dict[str, object],
) -> None:
    called = False

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        nonlocal called
        called = True
        return MIDI

    service.mark_ready(generate)
    response = client.post("/generate", json=payload)
    assert response.status_code == 422
    assert called is False


def test_generate_returns_one_midi_body_with_checkpoint_defaults(
    service: Service, client: TestClient
) -> None:
    seen: list[tuple[str, float, float, int]] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        seen.append((prompt, temperature, top_p, max_tokens))
        return MIDI

    service.mark_ready(generate)
    response = client.post("/generate", json={"prompt": "a waltz"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/midi"
    assert response.content == MIDI
    assert seen == [("a waltz", 1.0, 0.98, 2046)]


def test_generate_forwards_sampling_parameters(service: Service, client: TestClient) -> None:
    seen: list[tuple[str, float, float, int]] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        seen.append((prompt, temperature, top_p, max_tokens))
        return MIDI

    service.mark_ready(generate)
    response = client.post(
        "/generate",
        json={"prompt": "a waltz", "temperature": 0.5, "top_p": 0.9, "max_tokens": 8},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/midi"
    assert response.content == MIDI
    assert seen == [("a waltz", 0.5, 0.9, 8)]


@pytest.mark.parametrize(
    ("temperature", "top_p", "max_tokens"),
    [(0.1, 0.0, 3), (1.0, 1.0, 3)],
)
def test_sampling_bounds_are_forwarded(
    service: Service,
    client: TestClient,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> None:
    seen: list[tuple[float, float, int]] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        seen.append((temperature, top_p, max_tokens))
        return MIDI

    service.mark_ready(generate)
    response = client.post(
        "/generate",
        json={
            "prompt": "a waltz",
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        },
    )
    assert response.status_code == 200
    assert seen == [(temperature, top_p, max_tokens)]


def test_health_responds_while_generation_runs(service: Service) -> None:
    started = threading.Event()
    release = threading.Event()
    posted: list[object] = []

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        started.set()
        assert release.wait(timeout=5)
        return MIDI

    service.mark_ready(generate)
    with TestClient(create_app(service)) as client:

        def post() -> None:
            try:
                posted.append(client.post("/generate", json={"prompt": "a waltz", "max_tokens": 8}))
            except Exception as exc:
                posted.append(exc)

        thread = threading.Thread(target=post)
        thread.start()
        try:
            assert started.wait(timeout=2)
            health = client.get("/health")
            assert health.status_code == 200
            assert health.content == b"ok"
        finally:
            release.set()
            thread.join(timeout=5)

    assert thread.is_alive() is False
    assert len(posted) == 1
    response = posted[0]
    assert not isinstance(response, Exception)
    assert response.status_code == 200
    assert response.content == MIDI


async def test_a_cancelled_request_does_not_overlap_the_next_generation(service: Service) -> None:
    started = threading.Event()
    release = threading.Event()
    second = threading.Event()
    calls = 0

    def generate(prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            assert release.wait(timeout=5)
        else:
            second.set()
        return MIDI

    service.mark_ready(generate)
    await service.start()
    try:
        first = asyncio.create_task(service.generate("a waltz", 1.0, 0.98, 8))
        assert await asyncio.to_thread(started.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert second.is_set() is False
        follow = asyncio.create_task(service.generate("a waltz", 1.0, 0.98, 8))
        await asyncio.sleep(0.05)
        assert second.is_set() is False
        release.set()
        assert await follow == MIDI
        assert calls == 2
    finally:
        release.set()
        await service.stop()
