from pathlib import Path

import pydantic_ai.models as models
import pytest

from composerai_backend.feedback import FeedbackLibrary, FileFeedbackLibrary
from composerai_backend.lead import LeadDeps
from composerai_midi import MidiModel, Music21MidiModel
from composerai_store import LocalProjectStore, ProjectStore

models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture(autouse=True)
def _hide_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    for name in (
        "COMPOSERAI_MODEL",
        "COMPOSERAI_SEARCH_MODEL",
        "COMPOSERAI_PROJECT_ROOT",
        "COMPOSERAI_PROJECT_NAME",
        "COMPOSERAI_ARCHIVE_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)


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
def archive_root(tmp_path: Path) -> Path:
    return tmp_path / "archive"


@pytest.fixture
def library(archive_root: Path) -> FeedbackLibrary:
    return FileFeedbackLibrary(archive_root)


@pytest.fixture
def deps(store: ProjectStore, midi: MidiModel, library: FeedbackLibrary) -> LeadDeps:
    return LeadDeps(
        store=store,
        midi=midi,
        library=library,
        project="demo",
        search_model="xai:grok-4.7",
    )
