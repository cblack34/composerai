import asyncio
import sys
from collections.abc import Sequence
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SkipValidation, field_validator
from pydantic_ai import Agent, ModelMessage, RunContext, ToolReturnPart
from pydantic_ai.capabilities import WebSearch
from pydantic_ai.messages import TextContent, UserContent

from composerai_midi import MidiModel, Music21MidiModel
from composerai_store import LocalProjectStore, ProjectStore

from composerai_backend.feedback import FeedbackLibrary, FileFeedbackLibrary, GenerationNotFound
from composerai_backend.paths import path_component, project_write_path, section_midi_path
from composerai_backend.settings import Settings


class LeadDeps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    store: Annotated[ProjectStore, SkipValidation]
    midi: Annotated[MidiModel, SkipValidation]
    library: Annotated[FeedbackLibrary, SkipValidation]
    project: str
    search_model: str

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
        "save_section_midi writes <project>/<section>/<file>.mid from a musical prompt. "
        "Section and file are single path components. "
        "When the user praises or rejects a section, call log_feedback with the generation id the save returned. "
        "Do not invent a thumb. No thumb means neutral. "
        "The archive is not part of the project folder. "
        "list_files, read_file, and write_file use the project store. "
        "A write path must start with a project folder, never a file at the mount root. "
        "web_search answers a query from the web and does not write a file."
    ),
)


search_agent: Agent[None, str] = Agent(
    name="search",
    deps_type=type(None),
    defer_model_check=True,
    capabilities=[WebSearch()],
    instructions="Answer the query using web search.",
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


def _user_intent(prompt: str | Sequence[UserContent] | None) -> str:
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    texts: list[str] = []
    for part in prompt:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, TextContent):
            texts.append(part.content)
    return "".join(texts)


@agent.tool
async def save_section_midi(
    ctx: RunContext[LeadDeps],
    section: str,
    file: str,
    prompt: str,
    project: str | None = None,
) -> dict[str, str] | str:
    """Generate MIDI for one section and save <project>/<section>/<file>.mid.

    prompt is the musical prompt given to the MIDI model. A blank prompt writes nothing.
    file is the stem with no suffix. project defaults to the current project.
    """
    text = prompt.strip()
    if not text:
        return "The prompt is blank."
    chosen = ctx.deps.project if project is None else project
    path = section_midi_path(chosen, section, file)
    result = await ctx.deps.midi.generate(section, text)
    record = await ctx.deps.library.record_generation(
        project_name=chosen,
        section_name=section,
        project_path=path,
        user_intent=_user_intent(ctx.prompt),
        prompt=text,
        midi=result,
        lead_model_id=ctx.model.model_id,
    )
    saved = await ctx.deps.store.write(path, result.data)
    return {
        "generation_id": str(record.id),
        "project_id": str(record.project_id),
        "path": saved.path,
    }


@agent.tool
async def log_feedback(
    ctx: RunContext[LeadDeps],
    generation_id: UUID,
    value: Literal["up", "down"],
) -> str:
    """Attach up or down to a generation id from save_section_midi.

    An unknown id writes nothing. A later call records another thumb.
    """
    try:
        await ctx.deps.library.add_thumb(generation_id, value)
    except GenerationNotFound:
        return "No generation was found. Nothing was written."
    return f"Logged {value}."


@agent.tool
async def web_search(ctx: RunContext[LeadDeps], query: str) -> str:
    """Search the web for a query and return the answer."""
    text = query.strip()
    if not text:
        return "The query is blank."
    result = await search_agent.run(text, model=ctx.deps.search_model, usage=ctx.usage)
    return result.output


def _saved_generations(messages: Sequence[ModelMessage]) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for message in messages:
        for part in message.parts:
            if not isinstance(part, ToolReturnPart) or part.tool_name != "save_section_midi":
                continue
            content = part.content
            if not isinstance(content, dict):
                continue
            generation_id = content.get("generation_id")
            if not isinstance(generation_id, str) or generation_id in seen:
                continue
            seen.add(generation_id)
            path = content.get("path")
            found.append((generation_id, path if isinstance(path, str) and path else None))
    return found


def _reply_with_generation_ids(output: str, messages: Sequence[ModelMessage]) -> str:
    missing = [
        f"generation_id: {generation_id}"
        if path is None
        else f"generation_id: {generation_id} ({path})"
        for generation_id, path in _saved_generations(messages)
        if f"generation_id: {generation_id}" not in output
    ]
    if not missing:
        return output
    trailer = "\n".join(missing)
    if output.strip():
        return f"{output.rstrip()}\n\n{trailer}"
    return trailer


async def run_lead(
    prompt: str,
    deps: LeadDeps,
    *,
    model: str | None = None,
    message_history: Sequence[ModelMessage] | None = None,
) -> str:
    result = await agent.run(
        prompt,
        deps=deps,
        model=model,
        message_history=message_history,
    )
    return _reply_with_generation_ids(result.output, result.new_messages())


async def _main(prompt: str) -> None:
    settings = Settings()
    deps = LeadDeps(
        store=LocalProjectStore(settings.project_root),
        midi=Music21MidiModel(),
        library=FileFeedbackLibrary(settings.archive_root),
        project=settings.project_name,
        search_model=settings.search_model,
    )
    print(await run_lead(prompt, deps, model=settings.model))


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        raise SystemExit("usage: composerai-lead PROMPT")
    asyncio.run(_main(prompt))
