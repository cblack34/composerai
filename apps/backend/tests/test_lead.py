import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.messages import CachePoint, TextContent
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.native_tools import WebSearchTool

from composerai_backend.feedback import FeedbackLibrary, FileFeedbackLibrary
from composerai_backend.lead import LeadDeps, _main, agent, run_lead, search_agent
from composerai_midi import MidiModel, MidiResult, Music21MidiModel
from composerai_store import FileContent, LocalProjectStore, PathRejected, ProjectEntry, ProjectStore


def _script(tool_name: str, args: Mapping[str, object]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name, dict(args))])
        return ModelResponse(parts=[TextPart(content="done")])

    return FunctionModel(respond)


class _UnusedMidi:
    async def generate(self, section: str, prompt: str) -> MidiResult:
        raise AssertionError((section, prompt))


class _RecordingMidi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._inner = Music21MidiModel()

    async def generate(self, section: str, prompt: str) -> MidiResult:
        self.calls.append((section, prompt))
        return await self._inner.generate(section, prompt)


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


async def _save(
    deps: LeadDeps,
    *,
    prompt: str = "a short verse",
    section: str = "verse-1",
    file: str = "sketch",
    user: str = "Save a verse.",
    model_name: str = "grok-test",
) -> object:
    seen: list[object] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "save_section_midi",
                        {"section": section, "file": file, "prompt": prompt},
                    )
                ]
            )
        part = messages[-1].parts[-1]
        assert isinstance(part, ToolReturnPart)
        seen.append(part.content)
        return ModelResponse(parts=[TextPart(content="done")])

    with agent.override(model=FunctionModel(respond, model_name=model_name)):
        assert await run_lead(user, deps) == "done"
    assert len(seen) == 1
    return seen[0]


async def test_save_section_midi_writes_standard_midi(
    store: ProjectStore,
    library: FeedbackLibrary,
) -> None:
    recording = _RecordingStore(store)
    midi = _RecordingMidi()
    deps = LeadDeps(
        store=recording,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
    with agent.override(
        model=_script(
            "save_section_midi",
            {"section": "verse-1", "file": "sketch", "prompt": "a short verse"},
        )
    ):
        result = await run_lead("Save a verse.", deps)

    assert result == "done"
    assert midi.calls == [("verse-1", "a short verse")]
    assert recording.writes == ["demo/verse-1/sketch.mid"]
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
            {"section": "chorus", "file": "hook", "project": "other", "prompt": "a chorus hook"},
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
    library: FeedbackLibrary,
    archive_root: Path,
    section: str,
) -> None:
    recording = _RecordingStore(store)
    deps = LeadDeps(
        store=recording,
        midi=_UnusedMidi(),
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
    with pytest.raises(PathRejected):
        with agent.override(
            model=_script(
                "save_section_midi",
                {"section": section, "file": "sketch", "prompt": "a short verse"},
            )
        ):
            await run_lead("Save a verse.", deps)

    assert recording.writes == []
    assert list(project_root.iterdir()) == []
    assert await LocalProjectStore(archive_root).list(".") == []


async def test_write_without_a_project_is_rejected(
    store: ProjectStore,
    project_root: Path,
    midi: MidiModel,
    library: FeedbackLibrary,
) -> None:
    recording = _RecordingStore(store)
    deps = LeadDeps(
        store=recording,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
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
        assert names.isdisjoint(
            {"list_files", "read_file", "write_file", "save_section_midi", "log_feedback", "web_search"}
        )
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


async def test_web_search_runs_on_the_deps_search_model(
    store: ProjectStore,
    midi: MidiModel,
    library: FeedbackLibrary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = LeadDeps(
        store=store,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-3",
    )
    seen: dict[str, object] = {}

    async def run(prompt: str, **kwargs: object) -> SimpleNamespace:
        seen["prompt"] = prompt
        seen.update(kwargs)
        return SimpleNamespace(output="ok")

    monkeypatch.setattr(search_agent, "run", run)

    with agent.override(model=_script("web_search", {"query": "top song"})):
        await run_lead("Look something up.", deps)

    assert seen["prompt"] == "top song"
    assert seen["model"] == "xai:grok-3"
    assert seen["usage"] is not None


def test_lead_deps_reject_a_project_that_is_not_one_component() -> None:
    with pytest.raises(ValidationError):
        LeadDeps(
            store=object(),
            midi=object(),
            library=object(),
            project="..",
            search_model="xai:grok-4.7",
        )


async def test_main_builds_the_lead_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects"
    project.mkdir()
    archive = tmp_path / "archive"
    monkeypatch.setenv("COMPOSERAI_MODEL", "xai:grok-4")
    monkeypatch.setenv("COMPOSERAI_SEARCH_MODEL", "xai:grok-3")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "demo")
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(archive))
    seen: dict[str, object] = {}

    async def fake(prompt: str, deps: LeadDeps, *, model: str | None = None) -> str:
        seen["prompt"] = prompt
        seen["model"] = model
        seen["project"] = deps.project
        seen["search_model"] = deps.search_model
        seen["library"] = deps.library
        await deps.store.write("demo/verse-1/notes.txt", b"ok")
        return "saved"

    monkeypatch.setattr("composerai_backend.lead.run_lead", fake)

    await _main("write a verse")

    library = seen.pop("library")
    assert seen == {
        "prompt": "write a verse",
        "model": "xai:grok-4",
        "project": "demo",
        "search_model": "xai:grok-3",
    }
    assert isinstance(library, FileFeedbackLibrary)
    assert archive.is_dir()
    assert (project / "demo" / "verse-1" / "notes.txt").read_bytes() == b"ok"


def _canonical(value: object) -> str:
    assert isinstance(value, str)
    parsed = UUID(value)
    assert str(parsed) == value
    return value


async def _stored(archive_root: Path, generation_id: str) -> dict[str, object]:
    content = await LocalProjectStore(archive_root).read(f"generations/{generation_id}.json")
    stored = json.loads(content.data)
    assert isinstance(stored, dict)
    return stored


async def _log(deps: LeadDeps, generation_id: str, value: str, user: str) -> str:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(
                parts=[ToolCallPart("log_feedback", {"generation_id": generation_id, "value": value})]
            )
        part = messages[-1].parts[-1]
        assert isinstance(part, ToolReturnPart)
        assert isinstance(part.content, str)
        return ModelResponse(parts=[TextPart(content=part.content)])

    with agent.override(model=FunctionModel(respond)):
        return await run_lead(user, deps)


async def test_save_archives_the_prompt_and_reuses_project_id(
    store: ProjectStore,
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    midi = _RecordingMidi()
    deps = LeadDeps(
        store=store,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
    first = await _save(deps, prompt="  a short verse  ", user="Save a verse.")
    second = await _save(
        deps,
        section="chorus",
        file="hook",
        prompt="a chorus",
        user="Save a chorus.",
    )
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first_id = _canonical(first["generation_id"])
    second_id = _canonical(second["generation_id"])
    project_id = _canonical(first["project_id"])
    assert first_id != second_id
    assert _canonical(second["project_id"]) == project_id
    assert UUID(first_id).version == 7
    assert UUID(project_id).version == 7
    assert first["path"] == "demo/verse-1/sketch.mid"
    assert midi.calls == [("verse-1", "a short verse"), ("chorus", "a chorus")]

    stored = await _stored(archive_root, first_id)
    assert stored["prompt"] == "a short verse"
    assert stored["user_intent"] == "Save a verse."
    assert stored["session_id"] is None
    assert stored["section_id"] is None
    assert stored["refs"] == {}
    assert stored["project_id"] == project_id
    assert stored["midi_model_id"] == "music21-stub"
    assert stored["output_metadata"] == {}
    assert stored["lead_model_id"] == "grok-test"
    assert stored["project_path"] == "demo/verse-1/sketch.mid"
    project_bytes = (await store.read("demo/verse-1/sketch.mid")).data
    archive = LocalProjectStore(archive_root)
    assert (await archive.read(f"generations/{first_id}.mid")).data == project_bytes
    assert await library.latest_thumb(UUID(first_id)) is None

    second_stored = await _stored(archive_root, second_id)
    assert second_stored["project_id"] == project_id
    assert second_stored["session_id"] is None


async def test_log_feedback_up_then_down_leaves_down(
    deps: LeadDeps,
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    saved = await _save(deps)
    assert isinstance(saved, dict)
    generation_id = _canonical(saved["generation_id"])
    assert await library.latest_thumb(UUID(generation_id)) is None

    assert await _log(deps, generation_id, "up", "That verse works.") == "Logged up."
    assert await library.latest_thumb(UUID(generation_id)) == "up"
    assert await _log(deps, generation_id, "down", "That verse does not work.") == "Logged down."
    assert await library.latest_thumb(UUID(generation_id)) == "down"

    feedback = await LocalProjectStore(archive_root).list("feedback")
    assert len([entry for entry in feedback if entry.path.endswith(".json")]) == 2


async def test_unknown_generation_writes_nothing(
    deps: LeadDeps,
    archive_root: Path,
) -> None:
    missing = str(UUID(int=1))
    assert await _log(deps, missing, "down", "No such section.") == (
        "No generation was found. Nothing was written."
    )
    assert await LocalProjectStore(archive_root).list(".") == []


async def test_deleting_the_project_midi_leaves_the_archive(
    deps: LeadDeps,
    store: ProjectStore,
    project_root: Path,
    archive_root: Path,
) -> None:
    saved = await _save(deps)
    assert isinstance(saved, dict)
    generation_id = _canonical(saved["generation_id"])
    path = project_root / "demo" / "verse-1" / "sketch.mid"
    project_bytes = path.read_bytes()
    path.unlink()

    archive = LocalProjectStore(archive_root)
    assert (await archive.read(f"generations/{generation_id}.mid")).data == project_bytes
    with pytest.raises(FileNotFoundError):
        await store.read("demo/verse-1/sketch.mid")


@pytest.mark.parametrize("prompt", ["", " ", "\n\t"])
async def test_blank_midi_prompt_writes_neither_copy(
    store: ProjectStore,
    library: FeedbackLibrary,
    project_root: Path,
    archive_root: Path,
    prompt: str,
) -> None:
    midi = _RecordingMidi()
    deps = LeadDeps(
        store=store,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
    assert await _save(deps, prompt=prompt) == "The prompt is blank."
    assert midi.calls == []
    assert list(project_root.iterdir()) == []
    assert await LocalProjectStore(archive_root).list(".") == []


async def test_a_failed_project_write_keeps_the_generation(
    store: ProjectStore,
    library: FeedbackLibrary,
    project_root: Path,
    archive_root: Path,
) -> None:
    class _FailingStore:
        async def list(self, path: str) -> list[ProjectEntry]:
            return await store.list(path)

        async def read(self, path: str) -> FileContent:
            return await store.read(path)

        async def write(self, path: str, data: bytes) -> FileContent:
            raise OSError(path)

    midi = _RecordingMidi()
    deps = LeadDeps(
        store=_FailingStore(),
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
    with pytest.raises(OSError):
        with agent.override(
            model=_script(
                "save_section_midi",
                {"section": "verse-1", "file": "sketch", "prompt": "a short verse"},
            )
        ):
            await run_lead("Save a verse.", deps)

    assert midi.calls == [("verse-1", "a short verse")]
    assert list(project_root.iterdir()) == []
    archive = LocalProjectStore(archive_root)
    entries = await archive.list("generations")
    midi_entries = [entry for entry in entries if entry.path.endswith(".mid")]
    assert len(midi_entries) == 1
    assert (await archive.read(midi_entries[0].path)).data.startswith(b"MThd")


async def test_user_intent_keeps_text_parts(
    deps: LeadDeps,
    archive_root: Path,
) -> None:
    async def run(prompt: str | list[object] | None, file: str) -> str:
        seen: list[object] = []

        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "save_section_midi",
                            {"section": "verse-1", "file": file, "prompt": "a short verse"},
                        )
                    ]
                )
            part = messages[-1].parts[-1]
            assert isinstance(part, ToolReturnPart)
            seen.append(part.content)
            return ModelResponse(parts=[TextPart(content="done")])

        with agent.override(model=FunctionModel(respond, model_name="grok-test")):
            result = await agent.run(prompt, deps=deps)
        assert result.output == "done"
        content = seen[0]
        assert isinstance(content, dict)
        return _canonical(content["generation_id"])

    sequence_id = await run(["Save ", TextContent(content="a verse."), CachePoint()], "sketch")
    empty_id = await run(None, "empty")
    assert (await _stored(archive_root, sequence_id))["user_intent"] == "Save a verse."
    assert (await _stored(archive_root, empty_id))["user_intent"] == ""
