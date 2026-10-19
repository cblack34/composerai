import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from composerai_backend.feedback import (
    FeedbackLibrary,
    FileFeedbackLibrary,
    GenerationNotFound,
    GenerationRecord,
)
from composerai_midi import MidiResult
from composerai_store import LocalProjectStore, PathRejected


def test_file_library_creates_a_missing_archive_root(tmp_path: Path) -> None:
    root = tmp_path / "missing" / "archive"
    FileFeedbackLibrary(root)
    FileFeedbackLibrary(root)
    assert root.is_dir()


async def _record(
    library: FeedbackLibrary,
    *,
    project_name: str = "demo",
    section_name: str = "verse-1",
    project_path: str = "demo/verse-1/sketch.mid",
    user_intent: str = "a sad verse",
    prompt: str = "write a sad verse",
    midi: bytes = b"MThd-seed",
    metadata: dict[str, object] | None = None,
    lead_model_id: str | None = None,
    session_id: UUID | None = None,
    section_id: UUID | None = None,
    refs: dict[str, UUID] | None = None,
) -> GenerationRecord:
    return await library.record_generation(
        project_name=project_name,
        section_name=section_name,
        project_path=project_path,
        user_intent=user_intent,
        prompt=prompt,
        midi=MidiResult(
            data=midi,
            model_id="music21-stub",
            metadata={} if metadata is None else metadata,
        ),
        lead_model_id=lead_model_id,
        session_id=session_id,
        section_id=section_id,
        refs=refs,
    )


async def test_record_generation_reuses_project_id_and_stores_prompt_and_midi(
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    first = await _record(library, metadata={"take": 1})
    archive = LocalProjectStore(archive_root)
    json_path = f"generations/{first.id}.json"
    stored_json = await archive.read(json_path)
    stored = json.loads(stored_json.data)
    midi = await archive.read(first.artifact_path)

    assert first.id.version == 7
    assert first.project_id.version == 7
    assert first.created_at.utcoffset() == timedelta(0)
    assert first.session_id is None
    assert first.section_id is None
    assert first.refs == {}
    assert first.lead_model_id is None
    assert stored == first.model_dump(mode="json")
    assert stored["session_id"] is None
    assert stored["prompt"] == "write a sad verse"
    assert stored["user_intent"] == "a sad verse"
    assert stored["midi_model_id"] == "music21-stub"
    assert stored["output_metadata"] == {"take": 1}
    assert stored["artifact_path"] == f"generations/{first.id}.mid"
    assert midi.data == b"MThd-seed"
    assert b"MThd-seed" not in stored_json.data
    mapping = await archive.read("project-names/demo")
    assert mapping.data.decode() == str(first.project_id)

    second = await _record(
        library,
        section_name="chorus",
        project_path="demo/chorus/hook.mid",
        prompt="write a chorus",
        midi=b"MThd-second",
    )
    assert second.id != first.id
    assert second.id.version == 7
    assert second.project_id == first.project_id
    assert second.session_id is None
    assert (await archive.read("project-names/demo")).data == mapping.data
    assert (await archive.read(f"generations/{first.id}.mid")).data == b"MThd-seed"
    assert (await archive.read(f"generations/{second.id}.mid")).data == b"MThd-second"

    session_id = uuid.uuid7()
    section_id = uuid.uuid7()
    take = uuid.uuid7()
    explicit = await _record(
        library,
        section_name="bridge",
        session_id=session_id,
        section_id=section_id,
        refs={"take": take},
        lead_model_id="xai:grok-4.7",
    )
    assert explicit.project_id == first.project_id
    assert explicit.session_id == session_id
    assert explicit.section_id == section_id
    assert explicit.refs == {"take": take}
    assert explicit.lead_model_id == "xai:grok-4.7"
    stored_explicit = json.loads((await archive.read(f"generations/{explicit.id}.json")).data)
    assert stored_explicit["refs"] == {"take": str(take)}

    with pytest.raises(ValidationError):
        await _record(library, refs=cast(dict[str, UUID], {"take": "later"}))


async def test_up_then_down_leaves_down(
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    record = await _record(library)
    up = await library.add_thumb(record.id, "up")
    down = await library.add_thumb(record.id, "down")

    assert up.id != down.id
    assert up.id.version == 7
    assert down.id.version == 7
    assert up.kind == "thumb"
    assert down.kind == "thumb"
    assert await library.latest_thumb(record.id) == "down"

    archive = LocalProjectStore(archive_root)
    stored_up = json.loads((await archive.read(f"feedback/{up.id}.json")).data)
    stored_down = json.loads((await archive.read(f"feedback/{down.id}.json")).data)
    assert stored_up["kind"] == "thumb"
    assert stored_up["value"] == "up"
    assert stored_up["generation_id"] == str(record.id)
    assert stored_down["kind"] == "thumb"
    assert stored_down["value"] == "down"


async def test_no_thumb_is_neutral(library: FeedbackLibrary) -> None:
    record = await _record(library)
    assert await library.latest_thumb(record.id) is None


async def test_unknown_feedback_kind_keeps_extra_fields(
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    record = await _record(library)
    await library.add_thumb(record.id, "up")
    feedback_id = uuid.uuid7()
    payload = {
        "id": str(feedback_id),
        "generation_id": str(record.id),
        "kind": "comment",
        "created_at": "2099-01-01T00:00:00Z",
        "value": "down",
        "note": "keep me",
        "score": 2,
    }
    archive = LocalProjectStore(archive_root)
    await archive.write(f"feedback/{feedback_id}.json", json.dumps(payload).encode())

    loaded = await library.read_feedback(feedback_id)
    assert loaded.kind == "comment"
    assert loaded.model_dump(mode="json") == payload
    assert await library.latest_thumb(record.id) == "up"


async def test_missing_generation_writes_nothing(
    library: FeedbackLibrary,
    archive_root: Path,
) -> None:
    archive = LocalProjectStore(archive_root)
    missing = uuid.uuid7()
    before = await archive.list(".")
    with pytest.raises(GenerationNotFound) as raised:
        await library.add_thumb(missing, "down")
    assert raised.value.generation_id == missing
    assert await archive.list(".") == before


@pytest.mark.parametrize("project_name", ["", ".", "..", "bad/name"])
async def test_project_name_must_be_one_path_component(
    library: FeedbackLibrary,
    archive_root: Path,
    project_name: str,
) -> None:
    with pytest.raises(PathRejected):
        await _record(library, project_name=project_name)
    archive = LocalProjectStore(archive_root)
    assert await archive.list(".") == []


async def test_deleting_a_project_store_file_leaves_the_archive(
    library: FeedbackLibrary,
    archive_root: Path,
    tmp_path: Path,
) -> None:
    midi = b"MThd-archive-bytes"
    record = await _record(library, midi=midi)
    project_root = tmp_path / "projects"
    project_root.mkdir()
    assert not archive_root.resolve().is_relative_to(project_root.resolve())
    project_store = LocalProjectStore(project_root)
    await project_store.write("demo/verse-1/sketch.mid", b"working-copy")
    (project_root / "demo" / "verse-1" / "sketch.mid").unlink()

    archive_store = LocalProjectStore(archive_root)
    assert (await archive_store.read(record.artifact_path)).data == midi
    assert (await archive_store.read(f"generations/{record.id}.json")).data
    with pytest.raises(FileNotFoundError):
        await project_store.read("demo/verse-1/sketch.mid")
    with pytest.raises(FileNotFoundError):
        await project_store.read(record.artifact_path)
