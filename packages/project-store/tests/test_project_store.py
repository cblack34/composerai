import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from composerai_store import (
    FileContent,
    LocalProjectStore,
    PathRejected,
    ProjectEntry,
    ProjectStore,
)

_INSIDE_ABSOLUTE = "inside-absolute"
_SEGMENT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=12,
)


def _snapshot(root: Path) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            items.append((relative, f"link:{os.readlink(path)}"))
        elif path.is_dir():
            items.append((relative, "dir"))
        else:
            items.append((relative, path.read_bytes().hex()))
    return items


async def _call(store: ProjectStore, operation: str, path: str) -> None:
    if operation == "list":
        await store.list(path)
    elif operation == "read":
        await store.read(path)
    elif operation == "write":
        await store.write(path, b"nope")
    else:
        raise AssertionError(operation)


@pytest.mark.parametrize("operation", ["list", "read", "write"])
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("", id="empty"),
        pytest.param("..", id="parent"),
        pytest.param("../outside", id="parent-child"),
        pytest.param("foo/../../outside", id="nested-parent"),
        pytest.param("verse-1/../../escaped", id="section-escape"),
        pytest.param("/escaped", id="absolute"),
        pytest.param("//escaped", id="double-slash-absolute"),
        pytest.param(_INSIDE_ABSOLUTE, id="absolute-inside-root"),
    ],
)
async def test_illegal_paths_are_rejected_and_create_nothing(
    store: ProjectStore,
    project_root: Path,
    tmp_path: Path,
    operation: str,
    path: str,
) -> None:
    if path == _INSIDE_ABSOLUTE:
        path = str(project_root / "verse-1" / "name")
    before = _snapshot(tmp_path)
    with pytest.raises(PathRejected):
        await _call(store, operation, path)
    assert _snapshot(tmp_path) == before


async def test_section_path_round_trip(store: ProjectStore, project_root: Path) -> None:
    written = await store.write("verse-1/name", b"lyric")
    assert written == FileContent(path="verse-1/name", data=b"lyric")
    target = project_root / "verse-1" / "name"
    assert target.is_file()
    assert target.read_bytes() == b"lyric"
    assert target.resolve().is_relative_to(project_root.resolve())
    assert await store.read("verse-1/name") == written
    assert await store.write("./verse-1/name", b"lyric") == written
    await store.write("verse-1/other", b"more")
    assert await store.list("verse-1/") == [
        ProjectEntry(path="verse-1/name", is_directory=False),
        ProjectEntry(path="verse-1/other", is_directory=False),
    ]
    assert await store.list(".") == [
        ProjectEntry(path="verse-1", is_directory=True),
    ]


async def test_symlink_escape_is_rejected(
    store: ProjectStore,
    project_root: Path,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "linked-outside"
    outside.mkdir()
    (project_root / "escape").symlink_to(outside)
    before = _snapshot(tmp_path)
    with pytest.raises(PathRejected):
        await store.write("escape/secret", b"nope")
    with pytest.raises(PathRejected):
        await store.read("escape/secret")
    with pytest.raises(PathRejected):
        await store.list("escape")
    assert _snapshot(tmp_path) == before
    assert not (outside / "secret").exists()


@settings(deadline=None, database=None)
@given(
    segments=st.lists(_SEGMENT, min_size=1, max_size=4),
    payload=st.binary(max_size=4096),
)
async def test_generated_relative_paths_round_trip_under_root(
    segments: list[str],
    payload: bytes,
) -> None:
    relative = "/".join(segments)
    with TemporaryDirectory() as raw:
        root = Path(raw)
        store: ProjectStore = LocalProjectStore(root)
        written = await store.write(relative, payload)
        assert written.path == relative
        assert written.data == payload
        loaded = await store.read(relative)
        assert loaded == written
        location = (root / written.path).resolve()
        assert location.is_file()
        assert location.is_relative_to(root.resolve())
        assert location != root.resolve()
        assert location.read_bytes() == payload
