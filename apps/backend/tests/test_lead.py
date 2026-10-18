from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.native_tools import WebSearchTool

from composerai_backend.lead import LeadDeps, _main, agent, run_lead, search_agent
from composerai_backend.settings import DEFAULT_SEARCH_MODEL
from composerai_midi import MidiModel
from composerai_store import FileContent, PathRejected, ProjectEntry, ProjectStore


def _script(tool_name: str, args: Mapping[str, object]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name, dict(args))])
        return ModelResponse(parts=[TextPart(content="done")])

    return FunctionModel(respond)


class _UnusedMidi:
    async def generate(self, section: str) -> bytes:
        raise AssertionError(section)


class _RecordingStore:
    def __init__(self, inner: ProjectStore) -> None:
        self.inner = inner
        self.writes: list[str] = []

    async def list(self, path: str) -> list[ProjectEntry]:
        return await self.inner.list(path)

    async def read(self, path: str) -> FileContent:
        return await self.inner.read(path)

    async def write(self, path: str, data: bytes) -> FileContent:
        self.writes.append(path)
        return await self.inner.write(path, data)


async def test_save_section_midi_writes_standard_midi(
    deps: LeadDeps,
    store: ProjectStore,
) -> None:
    with agent.override(model=_script("save_section_midi", {"section": "verse-1", "file": "sketch"})):
        result = await run_lead("Save a verse.", deps)

    assert result == "done"
    saved = await store.read("demo/verse-1/sketch.mid")
    assert saved.path == "demo/verse-1/sketch.mid"
    assert saved.data.startswith(b"MThd")


async def test_save_section_midi_honors_an_explicit_project(
    deps: LeadDeps,
    store: ProjectStore,
) -> None:
    with agent.override(
        model=_script(
            "save_section_midi",
            {"section": "chorus", "file": "hook", "project": "other"},
        )
    ):
        await run_lead("Save a chorus.", deps)

    saved = await store.read("other/chorus/hook.mid")
    assert saved.path == "other/chorus/hook.mid"
    assert saved.data.startswith(b"MThd")


@pytest.mark.parametrize("section", ["..", "", "bad/name"])
async def test_bad_section_does_not_create_a_file_at_the_mount_root(
    store: ProjectStore,
    project_root: Path,
    section: str,
) -> None:
    recording = _RecordingStore(store)
    deps = LeadDeps(store=recording, midi=_UnusedMidi(), project="demo")
    with pytest.raises(PathRejected):
        with agent.override(model=_script("save_section_midi", {"section": section, "file": "sketch"})):
            await run_lead("Save a verse.", deps)

    assert recording.writes == []
    assert list(project_root.iterdir()) == []


async def test_write_without_a_project_is_rejected(
    store: ProjectStore,
    project_root: Path,
    midi: MidiModel,
) -> None:
    recording = _RecordingStore(store)
    deps = LeadDeps(store=recording, midi=midi, project="demo")
    with pytest.raises(PathRejected):
        with agent.override(model=_script("write_file", {"path": "notes.txt", "content": "nope"})):
            await run_lead("Write a note.", deps)

    assert recording.writes == []
    assert list(project_root.iterdir()) == []


async def test_write_and_read_round_trip(deps: LeadDeps, store: ProjectStore) -> None:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(
                parts=[ToolCallPart("write_file", {"path": "demo/verse-1/notes.txt", "content": "hello"})]
            )
        if len(messages) == 3:
            return ModelResponse(parts=[ToolCallPart("read_file", {"path": "demo/verse-1/notes.txt"})])
        part = messages[-1].parts[-1]
        assert isinstance(part, ToolReturnPart)
        assert part.content == "hello"
        return ModelResponse(parts=[TextPart(content="read")])

    with agent.override(model=FunctionModel(respond)):
        result = await run_lead("Write notes and read them back.", deps)

    assert result == "read"
    saved = await store.read("demo/verse-1/notes.txt")
    assert saved.data == b"hello"


async def test_list_files_returns_store_entries(deps: LeadDeps, store: ProjectStore) -> None:
    await store.write("demo/verse-1/notes.txt", b"hello")

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("list_files", {"path": "demo/verse-1"})])
        part = messages[-1].parts[-1]
        assert isinstance(part, ToolReturnPart)
        assert part.content == [{"path": "demo/verse-1/notes.txt", "is_directory": False}]
        return ModelResponse(parts=[TextPart(content="listed")])

    with agent.override(model=FunctionModel(respond)):
        result = await run_lead("List the verse.", deps)

    assert result == "listed"


def _native_web_search(info: AgentInfo) -> bool:
    return any(isinstance(tool, WebSearchTool) for tool in info.model_request_parameters.native_tools)


async def test_web_search_returns_the_search_text_and_skips_a_blank_query(deps: LeadDeps) -> None:
    calls: list[str] = []

    def search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        names = {tool.name for tool in info.function_tools}
        assert names.isdisjoint({"list_files", "read_file", "write_file", "save_section_midi", "web_search"})
        assert _native_web_search(info)
        part = messages[-1].parts[-1]
        assert isinstance(part, UserPromptPart)
        content = part.content
        assert isinstance(content, str)
        calls.append(content)
        return ModelResponse(parts=[TextPart(content="from the web")])

    async def ask(query: str) -> str:
        def lead(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            assert not _native_web_search(info)
            if len(messages) == 1:
                return ModelResponse(parts=[ToolCallPart("web_search", {"query": query})])
            part = messages[-1].parts[-1]
            assert isinstance(part, ToolReturnPart)
            return ModelResponse(parts=[TextPart(content=part.content)])

        with agent.override(model=FunctionModel(lead)), search_agent.override(model=FunctionModel(search)):
            return await run_lead("Look something up.", deps)

    assert await ask("") == "The query is blank."
    assert await ask("  ") == "The query is blank."
    assert calls == []
    assert await ask("current chart") == "from the web"
    assert calls == ["current chart"]


async def test_lead_can_call_web_search_and_surface_the_text(deps: LeadDeps) -> None:
    def search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="the chart is at 1")])

    def lead(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("web_search", {"query": "top song"})])
        part = messages[-1].parts[-1]
        assert isinstance(part, ToolReturnPart)
        assert part.content == "the chart is at 1"
        return ModelResponse(parts=[TextPart(content=f"Search said: {part.content}")])

    with agent.override(model=FunctionModel(lead)), search_agent.override(model=FunctionModel(search)):
        result = await run_lead("What is the top song?", deps)

    assert result == "Search said: the chart is at 1"


def test_lead_deps_default_the_search_model(deps: LeadDeps) -> None:
    assert deps.search_model == DEFAULT_SEARCH_MODEL


def test_lead_deps_reject_a_project_that_is_not_one_component() -> None:
    with pytest.raises(ValidationError):
        LeadDeps(store=object(), midi=object(), project="..")


async def test_main_builds_the_lead_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COMPOSERAI_MODEL", "xai:grok-4")
    monkeypatch.setenv("COMPOSERAI_SEARCH_MODEL", "xai:grok-3")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "demo")
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(tmp_path))
    seen: dict[str, object] = {}

    async def fake(prompt: str, deps: LeadDeps, *, model: str | None = None) -> str:
        seen["prompt"] = prompt
        seen["model"] = model
        seen["project"] = deps.project
        seen["search_model"] = deps.search_model
        await deps.store.write("demo/verse-1/notes.txt", b"ok")
        return "saved"

    monkeypatch.setattr("composerai_backend.lead.run_lead", fake)

    await _main("write a verse")

    assert seen == {
        "prompt": "write a verse",
        "model": "xai:grok-4",
        "project": "demo",
        "search_model": "xai:grok-3",
    }
    assert (tmp_path / "demo" / "verse-1" / "notes.txt").read_bytes() == b"ok"
