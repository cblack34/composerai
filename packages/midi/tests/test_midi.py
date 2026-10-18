from pathlib import Path

import pytest

from composerai_midi import MidiModel


@pytest.mark.parametrize("section", ["verse-1", "chorus", "bridge"])
async def test_generate_returns_standard_midi(model: MidiModel, section: str) -> None:
    data = await model.generate(section)
    assert isinstance(data, bytes)
    assert data.startswith(b"MThd")


async def test_generate_writes_no_files(
    model: MidiModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    data = await model.generate("verse-1")
    assert data.startswith(b"MThd")
    assert list(tmp_path.iterdir()) == []
