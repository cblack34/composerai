# Slice plan — chat UI

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. The chat panel and the HTTP endpoint that runs the existing lead are this slice.
- **Final acceptance advanced:** `docker compose up` starts the stack, and the user can chat with the lead. A chat can still write a MIDI file into a mounted section folder.

## Outcome

A browser chat sends a prompt to the backend. The backend runs the existing lead and returns the reply. The lead can still save MIDI through `ProjectStore`. The user opens that file on the host.

## Why this slice is next

The store, the mount, and the lead are on `main` (`a9cf849`). The seed definition of done still requires a person to chat. There is no HTTP API and no frontend.

## Scope

### In scope

- One HTTP endpoint that accepts the new prompt and the prior messages, runs the existing lead, and returns the reply.
- The browser holds the transcript. The endpoint builds `Settings`, `LocalProjectStore`, and `Music21MidiModel` at the edge.
- Compose serves that API instead of the idle probe. Startup still writes `projects/<project>/verse-1/mounted.txt`.
- A React, TypeScript, and Vite chat panel in `apps/web`. It is not a uv workspace member.
- Compose starts the panel and proxies API calls to the backend. The user opens the web port.
- FastAPI, if its resolved license is permissive.
- Pytest for the endpoint with `FunctionModel`, and one live Compose check that a chat saves a `.mid` file.

### Out of scope

- Streaming, server-side sessions, and chat history on disk.
- Web search and feedback logging.
- A project explorer, piano roll, file download API, auth, and another MIDI container.
- The roadmap in `docs/vision.md`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| The user can chat with the lead | The panel sends prompts to the backend and shows replies. |
| The frontend talks only to the backend API | The browser calls the chat endpoint. It does not touch the filesystem or a model provider. |
| The lead acts only through tools | The endpoint calls the existing lead. |
| A MIDI file appears in a mounted section folder | The same save tool remains available during a chat. |
| `ProjectStore` is the only filesystem seam | The endpoint constructs the local adapter and passes it in. |

## Gates and dependencies

### Hard gates

- The lead and `ProjectStore` on `main`.
- The live chat check needs `XAI_API_KEY` in the local environment. Offline tests do not read it.

### Sequencing recommendations

- The endpoint lands before the panel, because the panel consumes its contract.

## Architecture and contracts

- **Affected seams:** backend process, Compose services, a new web app. The lead tools and `ProjectStore` stay.
- **Public contracts:** `POST /api/chat` with `prompt` and prior `messages` (`role` of `user` or `assistant`, and `content`). The response is `reply`. A blank prompt is rejected. Prior messages do not include the new prompt.
- **Data and migration considerations:** Chat transcripts are not stored. Project files stay at `<project>/<section>/<file>.<ext>` inside the mount.

## High-level approach

Extend the existing lead run so prior messages reach Pydantic AI. Serve one endpoint from the backend process that already owns settings and the store. Replace the idle Compose command with that server, and keep the mount probe write at startup. Add a Vite panel that posts to the endpoint through the Compose network.

## Verification

- `uv run pytest` from the repo root on Python 3.14. The endpoint tests use `FunctionModel` and do not call xAI.
- `docker compose up --build` serves the panel. Startup still writes `projects/demo/verse-1/mounted.txt`.
- One live chat asks the lead to save a section. The host file is `projects/demo/<section>/<file>.mid`.
- The implementation lead exercises the panel in a browser.

## Risks and stop conditions

- Stop if FastAPI resolves to a non-permissive license.
- Stop if the panel or the endpoint reads the project folder outside `ProjectStore`, or if the panel calls a model provider.
- Stop if a new interface is an abstract base class. Protocols are the default.
- Do not put `XAI_API_KEY` in the image, the repo, an issue, or an agent prompt.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#10](https://github.com/cblack34/composerai/issues/10) — Add the chat HTTP endpoint | The endpoint, message history, and the Compose command. | None |
| [#11](https://github.com/cblack34/composerai/issues/11) — Add the Vite chat panel | The panel and the Compose web service. | #10 |

## Delivery shape

- **Topology:** Direct pull request to `main`.
- **Branch or spine:** `slice/chat-ui`
- **Final PR:** Opened when both issues are complete.
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

- **Outcome:** The browser chat posts to `POST /api/chat`. The endpoint runs the existing lead. A live chat saved `projects/demo/verse-1/chat.mid`.
- **Verification:** `uv run pytest` on CPython 3.14.7, 79 passed. `npm test` in `apps/web`, 2 passed. Compose wrote `mounted\n`. Headless Chrome rendered the prompt, the textarea, and Send. A blank prompt through `http://127.0.0.1:5173/api/chat` returned 400. One live prompt returned a reply and wrote a 72-byte file whose header is `MThd`. Evidence is on #10 and #11.
- **Deviations:** None. FastAPI 0.146.0 is MIT. The web image is `node:24.22.0-trixie-slim`. Vite 8's unmodified `lightningcss` 1.33.0 dependency stays under MPL-2.0.
- **Unresolved gates or risks:** No CI. Web search and feedback logging remain out of this slice.
- **Final PR:** https://github.com/cblack34/composerai/pull/12
- **Merge state:** Ready for the human to merge. Agents do not merge to `main`.
