import asyncio
import sys
from typing import Annotated

from pydantic import BaseModel, ConfigDict, SkipValidation, field_validator
from pydantic_ai import Agent, RunContext

from composerai_midi import MidiModel, Music21MidiModel
from composerai_store import LocalProjectStore, ProjectStore

from composerai_backend.paths import path_component, project_write_path, section_midi_path
from composerai_backend.settings import Settings


class LeadDeps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    store: Annotated[ProjectStore, SkipValidation]
    midi: Annotated[MidiModel, SkipValidation]
    project: str

    @field_validator("project")
    @classmethod
    def _project(cls, value: str) -> str:
        return path_component(value)


agent: Agent[LeadDeps, str] = Agent(
    name="lead",
    deps_type=LeadDeps,
    defer_model_check=True,
    instructions=(
        "You are the songwriting lead. Plan one section at a time and save it as MIDI. "
        "Act only through tools. "
        "save_section_midi writes <project>/<section>/<file>.mid. "
        "Section and file are single path components. "
        "list_files, read_file, and write_file use the project store. "
        "A write path must start with a project folder, never a file at the mount root."
    ),
)


@agent.instructions
def _default_project(ctx: RunContext[LeadDeps]) -> str:
    return f"The default project is {ctx.deps.project}."


@agent.tool
async def list_files(ctx: RunContext[LeadDeps], path: str) -> list[dict[str, str | bool]]:
    """List files and directories at a path in the project store."""
    entries = await ctx.deps.store.list(path)
    return [{"path": entry.path, "is_directory": entry.is_directory} for entry in entries]


@agent.tool
async def read_file(ctx: RunContext[LeadDeps], path: str) -> str:
    """Read a UTF-8 text file from the project store."""
    content = await ctx.deps.store.read(path)
    return content.data.decode()


@agent.tool
async def write_file(ctx: RunContext[LeadDeps], path: str, content: str) -> str:
    """Write UTF-8 text inside a project folder. The first path component is the project."""
    checked = project_write_path(path)
    saved = await ctx.deps.store.write(checked, content.encode())
    return saved.path


@agent.tool
async def save_section_midi(
    ctx: RunContext[LeadDeps],
    section: str,
    file: str,
    project: str | None = None,
) -> str:
    """Generate MIDI for one section and save <project>/<section>/<file>.mid.

    file is the stem with no suffix. project defaults to the current project.
    """
    chosen = ctx.deps.project if project is None else project
    path = section_midi_path(chosen, section, file)
    data = await ctx.deps.midi.generate(section)
    saved = await ctx.deps.store.write(path, data)
    return saved.path


async def run_lead(prompt: str, deps: LeadDeps, *, model: str | None = None) -> str:
    result = await agent.run(prompt, deps=deps, model=model)
    return result.output


async def _main(prompt: str) -> None:
    settings = Settings()
    deps = LeadDeps(
        store=LocalProjectStore(settings.project_root),
        midi=Music21MidiModel(),
        project=settings.project_name,
    )
    print(await run_lead(prompt, deps, model=settings.model))


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        raise SystemExit("usage: composerai-lead PROMPT")
    asyncio.run(_main(prompt))
