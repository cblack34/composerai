import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from composerai_midi import MidiResult
from composerai_store import LocalProjectStore, ProjectStore

from composerai_backend.paths import path_component


class GenerationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    project_id: UUID
    session_id: UUID | None = None
    section_id: UUID | None = None
    refs: dict[str, UUID] = {}
    project_name: str
    section_name: str
    project_path: str
    user_intent: str
    prompt: str
    midi_model_id: str
    output_metadata: dict[str, JsonValue] = {}
    lead_model_id: str | None = None
    created_at: datetime
    artifact_path: str


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID
    generation_id: UUID
    kind: str
    created_at: datetime


class GenerationNotFound(LookupError):
    def __init__(self, generation_id: UUID) -> None:
        self.generation_id = generation_id
        super().__init__(f"generation not found: {generation_id}")


class FeedbackLibrary(Protocol):
    async def record_generation(
        self,
        *,
        project_name: str,
        section_name: str,
        project_path: str,
        user_intent: str,
        prompt: str,
        midi: MidiResult,
        lead_model_id: str | None = None,
        session_id: UUID | None = None,
        section_id: UUID | None = None,
        refs: Mapping[str, UUID] | None = None,
    ) -> GenerationRecord: ...

    async def add_thumb(
        self,
        generation_id: UUID,
        value: Literal["up", "down"],
    ) -> FeedbackRecord: ...

    async def latest_thumb(self, generation_id: UUID) -> Literal["up", "down"] | None: ...

    async def read_feedback(self, feedback_id: UUID) -> FeedbackRecord: ...


def _generation_json(generation_id: UUID) -> str:
    return f"generations/{generation_id}.json"


def _generation_midi(generation_id: UUID) -> str:
    return f"generations/{generation_id}.mid"


def _feedback_json(feedback_id: UUID) -> str:
    return f"feedback/{feedback_id}.json"


def _thumb_value(record: FeedbackRecord) -> Literal["up", "down"] | None:
    extra = record.model_extra or {}
    value = extra.get("value")
    if value == "up" or value == "down":
        return value
    return None


class FileFeedbackLibrary(FeedbackLibrary):
    def __init__(self, root: Path) -> None:
        directory = Path(root)
        directory.mkdir(parents=True, exist_ok=True)
        self._store: ProjectStore = LocalProjectStore(directory)

    async def record_generation(
        self,
        *,
        project_name: str,
        section_name: str,
        project_path: str,
        user_intent: str,
        prompt: str,
        midi: MidiResult,
        lead_model_id: str | None = None,
        session_id: UUID | None = None,
        section_id: UUID | None = None,
        refs: Mapping[str, UUID] | None = None,
    ) -> GenerationRecord:
        project_name = path_component(project_name)
        project_id = await self._project_id(project_name)
        generation_id = uuid.uuid7()
        record = GenerationRecord(
            id=generation_id,
            project_id=project_id,
            session_id=session_id,
            section_id=section_id,
            refs={} if refs is None else dict(refs),
            project_name=project_name,
            section_name=section_name,
            project_path=project_path,
            user_intent=user_intent,
            prompt=prompt,
            midi_model_id=midi.model_id,
            output_metadata=dict(midi.metadata),
            lead_model_id=lead_model_id,
            created_at=datetime.now(UTC),
            artifact_path=_generation_midi(generation_id),
        )
        await self._write_once(record.artifact_path, midi.data)
        await self._write_once(_generation_json(generation_id), record.model_dump_json().encode())
        return record

    async def add_thumb(
        self,
        generation_id: UUID,
        value: Literal["up", "down"],
    ) -> FeedbackRecord:
        await self._require_generation(generation_id)
        record = FeedbackRecord(
            id=uuid.uuid7(),
            generation_id=generation_id,
            kind="thumb",
            created_at=datetime.now(UTC),
            value=value,
        )
        await self._write_once(_feedback_json(record.id), record.model_dump_json().encode())
        return record

    async def latest_thumb(self, generation_id: UUID) -> Literal["up", "down"] | None:
        chosen: FeedbackRecord | None = None
        chosen_value: Literal["up", "down"] | None = None
        for record in await self._feedback_records():
            if record.generation_id != generation_id or record.kind != "thumb":
                continue
            value = _thumb_value(record)
            if value is None:
                continue
            if chosen is None or (record.created_at, record.id) > (chosen.created_at, chosen.id):
                chosen = record
                chosen_value = value
        return chosen_value

    async def read_feedback(self, feedback_id: UUID) -> FeedbackRecord:
        content = await self._store.read(_feedback_json(feedback_id))
        return FeedbackRecord.model_validate_json(content.data)

    async def _project_id(self, project_name: str) -> UUID:
        path = f"project-names/{path_component(project_name)}"
        try:
            existing = await self._store.read(path)
        except FileNotFoundError:
            created = uuid.uuid7()
            await self._store.write(path, str(created).encode())
            return created
        return UUID(existing.data.decode())

    async def _require_generation(self, generation_id: UUID) -> None:
        try:
            await self._store.read(_generation_json(generation_id))
        except FileNotFoundError as exc:
            raise GenerationNotFound(generation_id) from exc

    async def _feedback_records(self) -> list[FeedbackRecord]:
        try:
            entries = await self._store.list("feedback")
        except FileNotFoundError:
            return []
        records: list[FeedbackRecord] = []
        for entry in entries:
            if entry.is_directory or not entry.path.endswith(".json"):
                continue
            content = await self._store.read(entry.path)
            records.append(FeedbackRecord.model_validate_json(content.data))
        return records

    async def _write_once(self, path: str, data: bytes) -> None:
        try:
            await self._store.read(path)
        except FileNotFoundError:
            await self._store.write(path, data)
            return
        raise FileExistsError(path)
