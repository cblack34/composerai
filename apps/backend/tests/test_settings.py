from pathlib import Path

import pytest
from pydantic import ValidationError

from composerai_backend import _run
from composerai_backend.settings import DEFAULT_MODEL, DEFAULT_PROJECT, Settings


def test_settings_use_defaults_when_only_the_root_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")

    settings = Settings()

    assert settings.model == DEFAULT_MODEL
    assert settings.project_name == DEFAULT_PROJECT
    assert settings.project_root == Path("/projects")


def test_settings_read_the_process_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COMPOSERAI_MODEL", "xai:grok-4")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "other")
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(tmp_path))

    settings = Settings()

    assert settings.model == "xai:grok-4"
    assert settings.project_name == "other"
    assert settings.project_root == tmp_path


@pytest.mark.parametrize("name", ["COMPOSERAI_MODEL", "COMPOSERAI_PROJECT_NAME"])
def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    monkeypatch.setenv(name, "")

    settings = Settings()

    assert settings.model == DEFAULT_MODEL
    assert settings.project_name == DEFAULT_PROJECT


def test_settings_reject_a_project_name_that_is_not_one_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", ".")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_require_a_project_root() -> None:
    with pytest.raises(ValidationError):
        Settings()


async def test_probe_writes_the_mount_file_for_the_configured_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "demo")
    served = False

    async def serve() -> None:
        nonlocal served
        served = True
        assert (tmp_path / "demo" / "verse-1" / "mounted.txt").read_bytes() == b"mounted\n"

    monkeypatch.setattr("composerai_backend._serve", serve)

    await _run()

    assert served


async def test_probe_does_not_write_when_the_project_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", ".")

    with pytest.raises(ValidationError):
        await _run()

    assert list(tmp_path.iterdir()) == []
