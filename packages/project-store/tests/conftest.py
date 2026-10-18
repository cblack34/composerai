from pathlib import Path

import pytest

from composerai_store import LocalProjectStore, ProjectStore


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


@pytest.fixture
def store(project_root: Path) -> ProjectStore:
    return LocalProjectStore(project_root)
