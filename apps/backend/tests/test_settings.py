from pathlib import Path

import pytest
from pydantic import ValidationError

from composerai_backend import _run
from composerai_backend.settings import (
    DEFAULT_MIDI_LLM_URL,
    DEFAULT_MODEL,
    DEFAULT_PROJECT,
    DEFAULT_SEARCH_MODEL,
    Settings,
)


def test_settings_use_defaults_when_only_the_roots_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", "/archive")

    settings = Settings()

    assert settings.model == DEFAULT_MODEL
    assert settings.search_model == DEFAULT_SEARCH_MODEL
    assert settings.project_name == DEFAULT_PROJECT
    assert settings.midi_llm_url == DEFAULT_MIDI_LLM_URL
    assert settings.project_root == Path("/projects")
    assert settings.archive_root == Path("/archive")


def test_settings_read_the_process_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects"
    archive = tmp_path / "archive"
    monkeypatch.setenv("COMPOSERAI_MODEL", "xai:grok-4")
    monkeypatch.setenv("COMPOSERAI_SEARCH_MODEL", "xai:grok-3")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "other")
    monkeypatch.setenv("COMPOSERAI_MIDI_LLM_URL", "http://midi-llm:8000")
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(archive))

    settings = Settings()

    assert settings.model == "xai:grok-4"
    assert settings.search_model == "xai:grok-3"
    assert settings.project_name == "other"
    assert settings.midi_llm_url == "http://midi-llm:8000"
    assert settings.project_root == project
    assert settings.archive_root == archive


@pytest.mark.parametrize(
    "name",
    [
        "COMPOSERAI_MODEL",
        "COMPOSERAI_SEARCH_MODEL",
        "COMPOSERAI_PROJECT_NAME",
        "COMPOSERAI_MIDI_LLM_URL",
    ],
)
def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", "/archive")
    monkeypatch.setenv(name, "")

    settings = Settings()

    assert settings.model == DEFAULT_MODEL
    assert settings.search_model == DEFAULT_SEARCH_MODEL
    assert settings.project_name == DEFAULT_PROJECT
    assert settings.midi_llm_url == DEFAULT_MIDI_LLM_URL


def test_settings_reject_a_project_name_that_is_not_one_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", "/archive")
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", ".")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_require_a_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", "/archive")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("value", [None, ""])
def test_settings_require_an_archive_root(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "/projects")
    if value is not None:
        monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", value)

    with pytest.raises(ValidationError):
        Settings()

    assert Settings.model_fields["archive_root"].is_required()


async def test_probe_writes_the_mount_file_for_the_configured_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects"
    project.mkdir()
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(tmp_path / "archive"))
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", "demo")
    served = False

    async def serve() -> None:
        nonlocal served
        served = True
        assert (project / "demo" / "verse-1" / "mounted.txt").read_bytes() == b"mounted\n"

    monkeypatch.setattr("composerai_backend._serve", serve)

    await _run()

    assert served


async def test_probe_does_not_write_when_the_project_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects"
    project.mkdir()
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(tmp_path / "archive"))
    monkeypatch.setenv("COMPOSERAI_PROJECT_NAME", ".")

    with pytest.raises(ValidationError):
        await _run()

    assert list(project.iterdir()) == []


@pytest.mark.parametrize(
    "kind",
    ["equal", "child", "symlink", "relative", "parent", "parent-symlink"],
)
def test_settings_reject_nested_project_and_archive_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
) -> None:
    project = tmp_path / "projects"
    project.mkdir()
    if kind == "equal":
        archive: Path = project
    elif kind == "child":
        archive = project / "demo" / "archive"
    elif kind == "symlink":
        target = project / "demo" / "archive"
        target.mkdir(parents=True)
        archive = tmp_path / "link"
        archive.symlink_to(target, target_is_directory=True)
    elif kind == "parent":
        archive = tmp_path / "archive"
        project = archive / "generations"
        project.mkdir(parents=True)
    elif kind == "parent-symlink":
        archive = tmp_path / "archive"
        target = archive / "generations"
        target.mkdir(parents=True)
        project = tmp_path / "project-link"
        project.symlink_to(target, target_is_directory=True)
    else:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", "projects")
        monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", "projects/demo/../archive")
        with pytest.raises(ValidationError):
            Settings()
        return

    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(archive))
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("project_name", "archive_name"),
    [("projects", "projects-archive"), ("archive-projects", "archive")],
)
def test_settings_allow_roots_whose_names_share_a_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_name: str,
    archive_name: str,
) -> None:
    project = tmp_path / project_name
    archive = tmp_path / archive_name
    project.mkdir()
    monkeypatch.setenv("COMPOSERAI_PROJECT_ROOT", str(project))
    monkeypatch.setenv("COMPOSERAI_ARCHIVE_ROOT", str(archive))

    settings = Settings()

    assert settings.project_root == project
    assert settings.archive_root == archive
