import asyncio
from typing import Protocol

from music21 import note, stream
from music21.midi.translate import streamToMidiFile


class MidiModel(Protocol):
    async def generate(self, section: str) -> bytes: ...


class Music21MidiModel(MidiModel):
    async def generate(self, section: str) -> bytes:
        return await asyncio.to_thread(self._generate, section)

    def _generate(self, section: str) -> bytes:
        part = stream.Part()
        part.id = section
        part.append(note.Note("C4", quarterLength=1))
        return streamToMidiFile(part).writestr()
