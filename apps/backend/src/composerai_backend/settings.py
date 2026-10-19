from pathlib import Path
from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from composerai_backend.paths import path_component

DEFAULT_MODEL = "xai:grok-4.7"
DEFAULT_SEARCH_MODEL = "xai:grok-4.7"
DEFAULT_PROJECT = "demo"
DEFAULT_MIDI_LLM_URL = "http://127.0.0.1:8001"


class Settings(BaseSettings):
    """Process configuration. Runners export these variables before startup."""

    model_config = SettingsConfigDict(
        env_prefix="COMPOSERAI_",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    model: str = DEFAULT_MODEL
    search_model: str = DEFAULT_SEARCH_MODEL
    project_root: Path
    archive_root: Path
    project_name: str = DEFAULT_PROJECT
    midi_llm_url: str = DEFAULT_MIDI_LLM_URL

    @field_validator("project_name")
    @classmethod
    def _project_name(cls, value: str) -> str:
        return path_component(value)

    @model_validator(mode="after")
    def _roots_are_disjoint(self) -> Self:
        project = self.project_root.resolve()
        archive = self.archive_root.resolve()
        if archive.is_relative_to(project) or project.is_relative_to(archive):
            raise ValueError("archive root and project root must not contain each other")
        return self
