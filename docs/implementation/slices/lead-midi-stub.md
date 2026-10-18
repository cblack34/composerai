# Slice plan — lead and MIDI stub

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. The lead and a music21 MIDI stub are this slice. Interfaces are protocols. Project files live at `projects/<project>/<section>/<file>.<ext>`.
- **Final acceptance advanced:** The lead can cause a MIDI file to be written into a section folder in the mounted project directory. The user can open that file on the host. Chat UI remains the following slice.

## Outcome

A Pydantic AI lead, configured for `xai:grok-4.7`, can plan a section and save MIDI bytes through `ProjectStore`. music21 builds those bytes behind a protocol. The file lands at `projects/<project>/<section>/<file>.mid`. The Compose mount still works, and the startup probe uses that layout.

## Why this slice is next

The store, the mount, Python 3.14, and the `ProjectStore` protocol are on `main`. The chat UI needs this lead and this MIDI boundary first. `XAI_API_KEY` is present in the local `.env`. No research gate blocks the interfaces.

## Scope

### In scope

- An async MIDI protocol and one music21 stub that returns bytes.
- A lead in `apps/backend` whose only actions are tools: `ProjectStore` list, read, and write, plus one tool that calls the MIDI protocol and writes the bytes into a section file.
- The path layout `projects/<project>/<section>/<file>.<ext>`. The default project name is `demo`.
- Environment configuration: `XAI_API_KEY`, `COMPOSERAI_MODEL`, `COMPOSERAI_PROJECT_ROOT`, `COMPOSERAI_PROJECT_NAME`. `.env.example` is committed. `.env` stays gitignored.
- Pytest, including a `FunctionModel` run that does not call xAI.
- One live lead run that writes a `.mid` file on the host.

### Out of scope

- React, Vite, and any HTTP API.
- Web search and feedback logging.
- A real MIDI model or a second Compose service.
- music21's bundled scores. This slice uses the library only.
- Another `ProjectStore` adapter, auth, and the roadmap in `docs/vision.md`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| The lead acts only through tools | Store operations and MIDI invocation are tools. |
| MIDI models sit behind a narrow interface | A protocol returns bytes. music21 is the stub behind it. |
| `ProjectStore` is the only filesystem seam | The MIDI package returns bytes. The tool writes them through the store. |
| A MIDI file appears in a mounted section folder | The tool writes `<project>/<section>/<file>.mid`. Compose keeps the bind mount. |
| Pydantic for structured data | Store models stay Pydantic. The lead is Pydantic AI. |
| Permissive dependencies | `pydantic-ai` with the `xai` extra (`xai-sdk`, Apache-2.0) and music21 (BSD-3-Clause). |

## Gates and dependencies

### Hard gates

- The live acceptance run needs `XAI_API_KEY`. It is set locally. Offline tests do not read it.

### Sequencing recommendations

- The MIDI package lands before the lead tools.
- The HTTP API and the React chat panel follow this slice. The real MIDI model can stay a stub for the rest of the seed.

## Architecture and contracts

- **Affected seams:** MIDI protocol, lead tools, `ProjectStore`, Compose environment, the startup probe path.
- **Public contracts:** `ProjectStore` methods stay. New MIDI protocol. No HTTP contract. Project files are `<project>/<section>/<file>.<ext>` inside the mount.
- **Data and migration considerations:** The old probe path `projects/verse-1/mounted.txt` is replaced by `projects/<project>/verse-1/mounted.txt`. `projects/` is gitignored local data.

## High-level approach

Add a workspace package for the MIDI protocol and the music21 stub. Depend on it from `apps/backend`. The save tool takes a project and a section, calls the protocol, and writes the bytes through `ProjectStore`. Tests construct the lead with `FunctionModel`. Configuration comes from the environment. The key is never written into the image or the repo. Compose still starts the backend and bind-mounts `projects/`.

## Verification

- `uv run pytest` from the repo root on Python 3.14.
- `docker compose up --build`, then the host file `projects/demo/verse-1/mounted.txt`.
- With `XAI_API_KEY` set, one live lead run writes a `.mid` file under `projects/demo/<section>/`.

## Risks and stop conditions

- Stop if `pydantic-ai`, `xai-sdk`, or music21 resolves to a non-permissive license.
- Stop if the stub, a tool, or the lead writes the project folder without `ProjectStore`.
- Stop if a new interface is an abstract base class. Protocols are the default.
- Stop if `grok-4.7` is rejected by the installed provider. Use the current id from docs.x.ai.
- Pytest does not call xAI. The live call is one manual check.
- The backend image still runs as root so the bind mount is writable.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#7](https://github.com/cblack34/composerai/issues/7) — Add a music21 MIDI interface | The protocol and the byte-producing stub. | None |
| [#8](https://github.com/cblack34/composerai/issues/8) — Add the lead and section MIDI tool | The lead, the tools, the path layout, and the probe. | #7 |

## Delivery shape

- **Topology:** One direct pull request to `main`.
- **Branch or spine:** `slice/lead-midi-stub`
- **Final PR:** https://github.com/cblack34/composerai/pull/9
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

Complete once when the final PR is ready for human merge. Do not use this section for WIP status.

- **Outcome:** A Pydantic AI lead saves MIDI through `ProjectStore` at `projects/<project>/<section>/<file>.mid`. music21 builds the bytes behind `MidiModel`. The Compose probe writes `projects/demo/verse-1/mounted.txt`.
- **Verification:** `uv run pytest` on CPython 3.14.7, 73 passed. Compose host file was `mounted\n`. One live prompt wrote `projects/demo/verse-1/sketch.mid` (72 bytes, header `MThd`). Those two runtime checks ran before the path fix; the accepted paths are unchanged. Evidence is on #7 and #8.
- **Deviations:** music21 is pinned at 10.5.0 in the MIDI package. The image deletes music21's bundled score files after install and keeps the corpus Python modules. `XAI_API_KEY` stays in the process environment for the xAI SDK.
- **Unresolved gates or risks:** No CI. The chat UI is the next slice.
- **Final PR:** https://github.com/cblack34/composerai/pull/9
- **Merge state:** Ready for the human to merge. Agents do not merge to `main`.
