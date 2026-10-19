from pathlib import Path

import pytest
from music21 import converter

from composerai_midi import MidiModel


@pytest.mark.parametrize("section", ["verse-1", "chorus", "bridge"])
async def test_generate_returns_standard_midi(model: MidiModel, section: str) -> None:
    result = await model.generate(section, "a short verse")
    assert result.model_id == "music21-stub"
    assert result.metadata == {}
    assert result.data.startswith(b"MThd")
    notes = list(converter.parseData(result.data, format="midi").flatten().notes)
    assert [(item.nameWithOctave, item.quarterLength) for item in notes] == [("C4", 1.0)]


async def test_generate_writes_no_files(
    model: MidiModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = await model.generate("verse-1", "a short verse")
    assert result.data.startswith(b"MThd")
    assert list(tmp_path.iterdir()) == []
