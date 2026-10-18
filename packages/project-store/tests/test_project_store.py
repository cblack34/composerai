import asyncio
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
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc", "Co", "Cn"),
        blacklist_characters="/\x00",
    ),
    min_size=1,
    max_size=40,
).filter(lambda segment: segment not in {".", ".."})


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


async def test_internal_symlink_is_not_followed(
    store: ProjectStore,
    project_root: Path,
) -> None:
    real = project_root / "real"
    real.mkdir()
    kept = real / "keep"
    kept.write_bytes(b"keep")
    (project_root / "alias").symlink_to(real, target_is_directory=True)
    with pytest.raises(PathRejected):
        await store.write("alias/keep", b"nope")
    with pytest.raises(PathRejected):
        await store.read("alias/keep")
    with pytest.raises(PathRejected):
        await store.list("alias")
    assert kept.read_bytes() == b"keep"


async def test_failed_nested_traversal_closes_handles(
    store: ProjectStore,
    project_root: Path,
) -> None:
    await store.write("verse-1/file", b"x")
    before = len(os.listdir("/dev/fd"))
    with pytest.raises(FileNotFoundError):
        await store.list("verse-1/missing")
    with pytest.raises(NotADirectoryError):
        await store.write("verse-1/file/child", b"nope")
    assert len(os.listdir("/dev/fd")) == before
    assert not (project_root / "verse-1" / "file" / "child").exists()


async def test_fifo_without_a_peer_fails_promptly(
    store: ProjectStore,
    project_root: Path,
) -> None:
    section = project_root / "verse-1"
    section.mkdir()
    os.mkfifo(section / "pipe")
    with pytest.raises(PathRejected):
        await asyncio.wait_for(store.read("verse-1/pipe"), timeout=2)
    with pytest.raises(PathRejected):
        await asyncio.wait_for(store.write("verse-1/pipe", b"nope"), timeout=2)


async def test_hard_link_write_does_not_change_the_outside_file(
    store: ProjectStore,
    project_root: Path,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"keep")
    os.link(outside, project_root / "alias")
    written = await store.write("alias", b"inside")
    assert written.data == b"inside"
    assert await store.read("alias") == written
    assert outside.read_bytes() == b"keep"


async def test_concurrent_root_listings_agree(store: ProjectStore) -> None:
    await store.write("a", b"1")
    await store.write("b", b"2")
    results = await asyncio.gather(*(store.list(".") for _ in range(32)))
    expected = {"a", "b"}
    assert all({entry.path for entry in result} == expected for result in results)


async def test_concurrent_writes_leave_one_complete_payload(store: ProjectStore) -> None:
    payloads = [bytes([index]) * 64 for index in range(8)]
    await asyncio.gather(*(store.write("take", payload) for payload in payloads))
    assert (await store.read("take")).data in payloads


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
