import pytest

from composerai_backend.paths import path_component, project_write_path, section_midi_path
from composerai_store import PathRejected


def test_section_midi_path() -> None:
    assert section_midi_path("demo", "verse-1", "sketch") == "demo/verse-1/sketch.mid"


@pytest.mark.parametrize("name", ["", ".", "..", "a/b"])
def test_path_component_rejects(name: str) -> None:
    with pytest.raises(PathRejected):
        path_component(name)


def test_project_write_path_keeps_a_project_folder() -> None:
    assert project_write_path("demo/verse-1/notes.txt") == "demo/verse-1/notes.txt"


@pytest.mark.parametrize(
    "path",
    ["notes.txt", "", "..", "demo/../outside", "/notes.txt", "demo/", "demo/./notes.txt"],
)
def test_project_write_path_rejects_before_a_store_would(path: str) -> None:
    with pytest.raises(PathRejected):
        project_write_path(path)
