from typing import Protocol

from pydantic import BaseModel, ConfigDict


class FileContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    data: bytes


class ProjectEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    is_directory: bool


class PathRejected(ValueError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"rejected path: {path!r}")


class ProjectStore(Protocol):
    async def list(self, path: str) -> list[ProjectEntry]: ...

    async def read(self, path: str) -> FileContent: ...

    async def write(self, path: str, data: bytes) -> FileContent: ...
