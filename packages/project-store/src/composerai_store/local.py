from __future__ import annotations

import asyncio
from pathlib import Path

from composerai_store.store import FileContent, PathRejected, ProjectEntry, ProjectStore


def _confine(root: Path, path: str, *, allow_root: bool) -> Path:
    if path == "":
        raise PathRejected(path)
    candidate = Path(path)
    if candidate.is_absolute():
        raise PathRejected(path)
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root) or (resolved == root and not allow_root):
        raise PathRejected(path)
    return resolved


class LocalProjectStore(ProjectStore):
    def __init__(self, root: Path) -> None:
        resolved = Path(root).resolve()
        if not resolved.is_dir():
            raise NotADirectoryError(resolved)
        self._root = resolved

    async def list(self, path: str) -> list[ProjectEntry]:
        return await asyncio.to_thread(self._list, path)

    async def read(self, path: str) -> FileContent:
        return await asyncio.to_thread(self._read, path)

    async def write(self, path: str, data: bytes) -> FileContent:
        return await asyncio.to_thread(self._write, path, data)

    def _list(self, path: str) -> list[ProjectEntry]:
        directory = _confine(self._root, path, allow_root=True)
        if not directory.exists():
            raise FileNotFoundError(path)
        if not directory.is_dir():
            raise NotADirectoryError(path)
        entries = [
            ProjectEntry(
                path=child.relative_to(self._root).as_posix(),
                is_directory=child.is_dir(),
            )
            for child in directory.iterdir()
        ]
        entries.sort(key=lambda entry: entry.path)
        return entries

    def _read(self, path: str) -> FileContent:
        target = _confine(self._root, path, allow_root=False)
        return FileContent(
            path=target.relative_to(self._root).as_posix(),
            data=target.read_bytes(),
        )

    def _write(self, path: str, data: bytes) -> FileContent:
        target = _confine(self._root, path, allow_root=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return FileContent(
            path=target.relative_to(self._root).as_posix(),
            data=data,
        )
