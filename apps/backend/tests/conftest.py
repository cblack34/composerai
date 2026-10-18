from pathlib import Path

import pydantic_ai.models as models
import pytest

from composerai_backend.lead import LeadDeps
from composerai_midi import MidiModel, Music21MidiModel
from composerai_store import LocalProjectStore, ProjectStore

models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture(autouse=True)
def _hide_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    root.mkdir()
    return root


@pytest.fixture
def store(project_root: Path) -> ProjectStore:
    return LocalProjectStore(project_root)


@pytest.fixture
def midi() -> MidiModel:
    return Music21MidiModel()


@pytest.fixture
def deps(store: ProjectStore, midi: MidiModel) -> LeadDeps:
    return LeadDeps(store=store, midi=midi, project="demo")
