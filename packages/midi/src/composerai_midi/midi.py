import asyncio
from typing import Protocol

from music21 import note, stream
from music21.midi.translate import streamToMidiFile
from pydantic import BaseModel, ConfigDict, JsonValue

_MUSIC21_MODEL_ID = "music21-stub"


class MidiResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: bytes
    model_id: str
    metadata: dict[str, JsonValue] = {}


class MidiModel(Protocol):
    async def generate(self, section: str, prompt: str) -> MidiResult: ...


class Music21MidiModel(MidiModel):
    async def generate(self, section: str, prompt: str) -> MidiResult:
        data = await asyncio.to_thread(self._generate, section)
        return MidiResult(data=data, model_id=_MUSIC21_MODEL_ID)

    def _generate(self, section: str) -> bytes:
        part = stream.Part()
        part.id = section
        part.append(note.Note("C4", quarterLength=1))
        return streamToMidiFile(part).writestr()
