from abc import ABC, abstractmethod

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


class ProjectStore(ABC):
    @abstractmethod
    async def list(self, path: str) -> list[ProjectEntry]: ...

    @abstractmethod
    async def read(self, path: str) -> FileContent: ...

    @abstractmethod
    async def write(self, path: str, data: bytes) -> FileContent: ...
