from collections.abc import Sequence
from pathlib import Path

import httpx2
import pytest
from pydantic_ai import ModelMessage
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from composerai_backend.api import app
from composerai_backend.lead import LeadDeps, agent
from composerai_midi import Music21MidiModel
from composerai_store import LocalProjectStore


@pytest.fixture(autouse=True)
def chat_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "demo")
    monkeypatch.setenv("COMPOSERAI_MODEL", "xai:grok-4")
    return tmp_path


async def _post(payload: dict[str, object]) -> httpx2.Response:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/chat", json=payload)


def _text(messages: Sequence[ModelMessage]) -> list[str]:
    seen: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, UserPromptPart | TextPart):
                content = part.content
                assert isinstance(content, str)
                seen.append(content)
    return seen


async def test_chat_returns_the_lead_reply() -> None:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert _text(messages) == ["Save a verse."]
        return ModelResponse(parts=[TextPart(content="done")])

    with agent.override(model=FunctionModel(respond)):
        response = await _post({"prompt": "Save a verse.", "messages": []})

    assert response.status_code == 200
    assert response.json() == {"reply": "done"}


async def test_chat_forwards_prior_messages() -> None:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert _text(messages) == ["Write a verse.", "Saved verse-1.", "Now a chorus."]
        return ModelResponse(parts=[TextPart(content="chorus")])

    with agent.override(model=FunctionModel(respond)):
        response = await _post(
            {
                "prompt": "Now a chorus.",
                "messages": [
                    {"role": "user", "content": "Write a verse."},
                    {"role": "assistant", "content": "Saved verse-1."},
                ],
            }
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "chorus"}


@pytest.mark.parametrize("prompt", ["", " ", "\n\t"])
async def test_blank_prompt_does_not_call_the_lead(prompt: str) -> None:
    calls = 0

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[TextPart(content="nope")])

    with agent.override(model=FunctionModel(respond)):
        response = await _post({"prompt": prompt, "messages": [{"role": "user", "content": "Hi."}]})

    assert response.status_code == 400
    assert calls == 0


async def test_chat_builds_the_lead_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    chat_env: Path,
) -> None:
    monkeypatch.setenv("COMPOSERAI_SEARCH_MODEL", "xai:grok-3")
    seen: dict[str, object] = {}

    async def fake(
        prompt: str,
        deps: LeadDeps,
        *,
        model: str | None = None,
        message_history: Sequence[ModelMessage] | None = None,
    ) -> str:
        seen["prompt"] = prompt
        seen["model"] = model
        seen["project"] = deps.project
        seen["search_model"] = deps.search_model
        seen["store"] = deps.store
        seen["midi"] = deps.midi
        seen["history"] = message_history
        return "ok"

    monkeypatch.setattr("composerai_backend.api.run_lead", fake)

    response = await _post(
        {
            "prompt": "Save a verse.",
            "messages": [
                {"role": "user", "content": "Hi."},
                {"role": "assistant", "content": "Hello."},
            ],
        }
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "ok"}
    assert seen["prompt"] == "Save a verse."
    assert seen["model"] == "xai:grok-4"
    assert seen["search_model"] == "xai:grok-3"
    assert seen["project"] == "demo"
    store = seen["store"]
    midi = seen["midi"]
    assert isinstance(store, LocalProjectStore)
    await store.write("demo/verse-1/notes.txt", b"ok")
    assert (chat_env / "demo" / "verse-1" / "notes.txt").read_bytes() == b"ok"
    assert isinstance(midi, Music21MidiModel)
    history = seen["history"]
    assert isinstance(history, list)
    assert _text(history) == ["Hi.", "Hello."]
