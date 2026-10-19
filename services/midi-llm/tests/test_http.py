import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from midi_llm_http.server import Service, create_app

MIDI = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"


@pytest.fixture
def service() -> Service:
    return Service()


@pytest.fixture
def client(service: Service) -> TestClient:
    return TestClient(create_app(service))


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
    [{}, {"prompt": 1}, {"prompt": ""}, {"prompt": "   "}, {"prompt": "a waltz", "max_tokens": 1.5}],
)
def test_bad_prompt_is_rejected_and_does_not_run_the_model(
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
