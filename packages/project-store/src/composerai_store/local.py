from __future__ import annotations

import asyncio
import errno
import os
import stat
import weakref
from pathlib import Path

from composerai_store.store import FileContent, PathRejected, ProjectEntry, ProjectStore

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_READ_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_WRITE_FLAGS = (
    os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
)


def _components(path: str) -> tuple[str, ...]:
    if path == "":
        raise PathRejected(path)
    candidate = Path(path)
    if candidate.is_absolute():
        raise PathRejected(path)
    parts = tuple(part for part in candidate.parts if part != ".")
    if any(part == ".." for part in parts):
        raise PathRejected(path)
    return parts


def _relative(parts: tuple[str, ...]) -> str:
    return "/".join(parts)


def _reject_if_symlink(parent_fd: int, name: str, path: str, exc: OSError) -> None:
    if exc.errno == errno.ELOOP:
        raise PathRejected(path) from exc
    if exc.errno != errno.ENOTDIR:
        return
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise PathRejected(path) from exc


def _open_dir(parent_fd: int, name: str, path: str) -> int:
    try:
        return os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        _reject_if_symlink(parent_fd, name, path, exc)
        if isinstance(exc, NotADirectoryError):
            raise NotADirectoryError(path) from exc
        raise


def _ensure_dir(parent_fd: int, name: str, path: str) -> int:
    try:
        return _open_dir(parent_fd, name, path)
    except FileNotFoundError:
        try:
            os.mkdir(name, dir_fd=parent_fd)
        except FileExistsError:
            pass
        return _open_dir(parent_fd, name, path)


class LocalProjectStore(ProjectStore):
    def __init__(self, root: Path) -> None:
        resolved = Path(root).resolve()
        if not resolved.is_dir():
            raise NotADirectoryError(resolved)
        self._root_fd = os.open(resolved, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self._closed = weakref.finalize(self, os.close, self._root_fd)

    async def list(self, path: str) -> list[ProjectEntry]:
        return await asyncio.to_thread(self._list, path)

    async def read(self, path: str) -> FileContent:
        return await asyncio.to_thread(self._read, path)

    async def write(self, path: str, data: bytes) -> FileContent:
        return await asyncio.to_thread(self._write, path, data)

    def _list(self, path: str) -> list[ProjectEntry]:
        parts = _components(path)
        directory, opened = self._descend(parts, path=path, create=False)
        try:
            entries = []
            for name in os.listdir(directory):
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                entries.append(
                    ProjectEntry(
                        path=_relative((*parts, name)),
                        is_directory=stat.S_ISDIR(info.st_mode),
                    )
                )
        finally:
            self._close_opened(opened)
        entries.sort(key=lambda entry: entry.path)
        return entries

    def _read(self, path: str) -> FileContent:
        parts = _components(path)
        if not parts:
            raise PathRejected(path)
        parent, opened = self._descend(parts[:-1], path=path, create=False)
        try:
            fd = self._open_file(parent, parts[-1], path, write=False)
            with os.fdopen(fd, "rb") as handle:
                data = handle.read()
        finally:
            self._close_opened(opened)
        return FileContent(path=_relative(parts), data=data)

    def _write(self, path: str, data: bytes) -> FileContent:
        parts = _components(path)
        if not parts:
            raise PathRejected(path)
        parent, opened = self._descend(parts[:-1], path=path, create=True)
        try:
            fd = self._open_file(parent, parts[-1], path, write=True)
            try:
                view = memoryview(data)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
            finally:
                os.close(fd)
        finally:
            self._close_opened(opened)
        return FileContent(path=_relative(parts), data=data)

    def _descend(
        self,
        parts: tuple[str, ...],
        *,
        path: str,
        create: bool,
    ) -> tuple[int, list[int]]:
        current = self._root_fd
        opened: list[int] = []
        try:
            for name in parts:
                current = (
                    _ensure_dir(current, name, path) if create else _open_dir(current, name, path)
                )
                opened.append(current)
        except BaseException:
            self._close_opened(opened)
            raise
        return current, opened

    def _open_file(self, parent_fd: int, name: str, path: str, *, write: bool) -> int:
        flags = _FILE_WRITE_FLAGS if write else _FILE_READ_FLAGS
        try:
            fd = os.open(name, flags, 0o644, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.ENXIO:
                raise PathRejected(path) from exc
            _reject_if_symlink(parent_fd, name, path, exc)
            raise
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(fd)
            if stat.S_ISDIR(info.st_mode):
                raise IsADirectoryError(path)
            raise PathRejected(path)
        return fd

    @staticmethod
    def _close_opened(opened: list[int]) -> None:
        for fd in reversed(opened):
            os.close(fd)
