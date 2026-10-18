import pytest

from composerai_midi import MidiModel, Music21MidiModel


@pytest.fixture
def model() -> MidiModel:
    return Music21MidiModel()
