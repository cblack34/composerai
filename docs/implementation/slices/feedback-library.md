# Slice plan — feedback library

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. Every MIDI call records a generation outside the song folder, keyed by a UUID v7. A separate tool attaches a thumb to that id. No thumb means neutral.
- **Final acceptance advanced:** The lead's tools include feedback logging, as named in the build brief. Chat and the working MIDI copy in the project folder stay as they are.

## Outcome

`save_section_midi` writes an immutable generation to an archive the song folder cannot delete, then writes the working MIDI copy into the project. The generation id is a UUID v7. `log_feedback` attaches `up` or `down` to that id. The newest thumb wins. No thumb means neutral.

## Why this slice is next

Web search, chat, and the music21 stub are on `main` (`b440601`). Feedback logging is the last tool the build brief names. The library is the seed's preference record. Retrieval, ranking, comments, and a training run stay later.

## Scope

### In scope

- A `FeedbackLibrary` protocol and one file-backed adapter. Records go through a second `ProjectStore` rooted at `COMPOSERAI_ARCHIVE_ROOT`.
- UUID v7 for each MIDI call. One stable `project_id` per project name, reused, stored in the archive.
- `session_id` and `section_id` on the record, null in this seed. An empty `refs` object for later ids.
- The generation stores the current user message, the prompt passed to the MIDI model, the MIDI model id, the archived MIDI bytes, the project name, the section name, and the project path.
- `MidiModel.generate(section, prompt)` returns the bytes, a model id, and metadata. The music21 stub still returns one C4.
- `log_feedback(generation_id, up|down)`. Unknown generation writes nothing.
- Pytest with `FunctionModel` and no network call. One live chat saves a section and a thumb, and the archive survives deletion of the project file.

### Out of scope

- A retrieval tool, a ranking UI, comments, and any feedback kind other than `thumb`.
- A training job, a session system, and the MIDI model container.
- A change to `POST /api/chat`.
- Renaming project folders to UUIDs. The path stays `<project>/<section>/<file>.mid`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| The lead's tools include feedback logging | `save_section_midi` records the generation. `log_feedback` attaches the thumb. |
| The agent acts only through tools | The archive is written inside those tools. |
| `ProjectStore` is the only filesystem seam for the project folder | The working copy still goes through the project store. The archive is a second store outside that mount. |
| The user can open the MIDI file on the host | The working copy is unchanged. The archive keeps its own bytes. |

## Gates and dependencies

### Hard gates

- The lead, the music21 stub, and `POST /api/chat` on `main`.
- The live check needs `XAI_API_KEY` in the local environment. Offline tests do not read it.

### Sequencing recommendations

- The library and the `generate` result land before the lead tools record generations.

## Architecture and contracts

- **Affected seams:** `MidiModel`, lead tools, `Settings`, Compose, a new archive mount.
- **Public contracts:** `POST /api/chat` stays `{prompt, messages}` in and `{reply}` out. `generate` gains a prompt and returns a result object instead of bare bytes. Project paths stay `<project>/<section>/<file>.<ext>`.
- **Data and migration considerations:** `archive/` is gitignored local data, like `projects/`. Deleting a project file does not delete a generation. The library has no delete.

## High-level approach

The backend owns a `FeedbackLibrary` protocol. The file adapter stores generation JSON, MIDI bytes, thumb JSON, and the project-name to `project_id` mapping under the archive root. `save_section_midi` calls `generate` with the lead's prompt, records the generation, then writes the working copy. `log_feedback` only appends a thumb. Later feedback kinds are new `kind` values. This seed writes `thumb` only, and a reader keeps an unrecognized kind.

## Verification

- `uv run pytest` from the repo root on Python 3.14.
- A save stores a new generation UUID, a stable `project_id`, a null session id, the prompt, and the MIDI bytes. A second save of the same project reuses `project_id`.
- Up, then down, leaves the latest as down. No thumb reads as neutral. Deleting the project MIDI leaves the archive.
- One live chat through the rebuilt stack saves a section and a thumb. The host has the project file and `archive/`. Removing the project file leaves the archive.

## Risks and stop conditions

- Stop if a generation or thumb is written through the project mount, or if deleting a project file removes a generation.
- Stop if the slice adds a dependency, a retrieval tool, or a change to `POST /api/chat`.
- Stop if a new interface is an abstract base class. Protocols are the default.
- Do not put `XAI_API_KEY` in the archive, the image, the repo, or an issue.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#15](https://github.com/cblack34/composerai/issues/15) — Add the feedback library and MIDI result | The library, the project UUID, and `generate` returning a model id. | None |
| [#16](https://github.com/cblack34/composerai/issues/16) — Record generations and log thumbs | Archive on save, the thumb tool, and the archive mount. | #15 |

## Delivery shape

- **Topology:** Direct pull request to `main`.
- **Branch or spine:** `slice/feedback-library`
- **Final PR:** Opened when the issues are complete.
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

Complete once when the final PR is ready for human merge. Do not use this section for WIP status.

- **Outcome:** `save_section_midi` records a UUID v7 generation in the archive, then writes the working MIDI copy. `log_feedback` attaches `up` or `down`. No thumb means neutral. The newest thumb wins.
- **Verification:** `uv run pytest` on CPython 3.14.7, 106 passed. A live chat through `http://127.0.0.1:5173/api/chat` returned 200, saved `projects/demo/verse-1/live-thumb.mid`, and wrote the generation, the thumb, and the project id under `archive/`. Deleting that project file left the archive. Evidence is on #15 and #16.
- **Deviations:** `composerai-midi` declares `pydantic` because `MidiResult` is a Pydantic model. `refs` values are UUIDs.
- **Unresolved gates or risks:** No CI. Retrieval, ranking, comments, sessions, a training run, and the MIDI model container stay out of this slice.
- **Final PR:**
- **Merge state:** In review. Agents do not merge to `main`.
