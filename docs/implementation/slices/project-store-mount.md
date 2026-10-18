# Slice plan — project-store mount

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. The project-folder seam is the slice. It uses a uv workspace, async code, and pytest with fixtures, parametrize, and Hypothesis.
- **Final acceptance advanced:** A file written through `ProjectStore` is visible on the host in the mounted project directory. Compose starts the backend that owns that mount.

## Outcome

The repo is a uv workspace with one lockfile and one `.venv` at the root. An async `ProjectStore` is the only filesystem seam. The backend workspace member runs under Docker Compose with `projects/` bind-mounted, and a write through the store appears on the host under a section folder.

## Why this slice is next

The seed has no application code. The lead, the MIDI call, and the chat UI all have to go through `ProjectStore`, and the host mount is what makes a generated file openable outside the container. No research gate blocks this slice. The LLM provider and the MIDI model stay later.

## Scope

### In scope

- A uv workspace rooted at the repo, with one shared `.venv` and `uv.lock`. Python packages are added with `uv`, not pip.
- Async `ProjectStore` interface, Pydantic result models, and one local adapter.
- Section-relative writes such as `verse-1/`, confined to the project root.
- A backend workspace member that depends on the store and is the Compose service.
- Pytest, with shared fixtures, parametrize, and Hypothesis for generated paths and payloads.

### Out of scope

- The Pydantic AI lead, web search, feedback logging, and the LLM provider.
- The MIDI model container and MIDI generation.
- The React app and any HTTP API.
- Further `ProjectStore` adapters, auth, and the roadmap in `docs/vision.md`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| Docker Compose with a backend and a project-folder volume | Compose runs the backend with `projects/` bind-mounted. |
| `ProjectStore` is the only filesystem seam | The interface and the local adapter are the seam. The backend calls the interface. |
| Section-folder convention | Writes target a section path under the project root. |
| A file in the mounted project directory is visible on the host | The container write is checked on the host under `projects/<section>/`. |
| Pydantic for structured data | Store results are Pydantic models. |
| Permissive dependency policy | Runtime dependency is Pydantic. Dev dependencies are pytest, pytest-asyncio, and Hypothesis. |

## Gates and dependencies

### Hard gates

- None. The workspace, the store, and the mount can be built without an LLM key or a MIDI model.

### Sequencing recommendations

- After this slice merges, the next slice is the lead agent and a stub MIDI writer that saves through `ProjectStore`. That slice needs an xAI API key and model choice before it starts.
- The chat UI follows the agent. The real MIDI model can stay a stub for the rest of the seed.

## Architecture and contracts

- **Affected seams:** `ProjectStore` and the Compose mount. The backend depends on the store package. Nothing else reads or writes the project folder.
- **Public contracts:** No HTTP API. The store interface is internal and async.
- **Data and migration considerations:** None. `projects/` is gitignored and holds local project data.

Workspace shape, so later packages join this environment instead of creating another one:

- The root is a virtual uv project (`package = false`). It owns the shared `dev` dependency group and the single `uv.lock`. `uv sync --all-packages` installs every member into the root `.venv`.
- `packages/project-store` is the store library.
- `apps/backend` is the application image. It depends on the store with a workspace source. Its member path is explicit, not `apps/*`, so the future Node app at `apps/web` is not a uv member.
- A future Python MIDI service joins as its own workspace member. It is not created in this slice.
- One `requires-python` covers the whole workspace: 3.12 or newer.

## High-level approach

Create the workspace with uv. The store package exposes an async interface and a local adapter that confines every path to an injected root, using the standard library for filesystem IO. Tests use a `conftest` fixture for that root, parametrize the known escaping paths, and use Hypothesis to generate further relative paths and payloads. The backend package is a second workspace member with a small async entrypoint. Compose builds it with uv and bind-mounts `projects/`.

Hypothesis is MPL-2.0. It is an unmodified dev dependency, and using it does not relicense this repository.

## Verification

- `uv sync --all-packages` from the repo root, then both workspace members import from that `.venv`.
- `uv run pytest` from the repo root.
- `docker compose up --build`, then a store write from inside the backend, then the file present on the host under `projects/<section>/`.
- No CI workflow exists yet. This evidence is local.

## Risks and stop conditions

- Stop if a second filesystem API, a new external service, or a runtime dependency other than Pydantic appears necessary.
- Stop if a path can resolve outside the project root. Fix the adapter.
- Stop if the host cannot see the mounted write. Fix the Compose mount.
- The workspace uses one `requires-python` for every member. Do not pin a member to a narrower interpreter.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#1](https://github.com/cblack34/composerai/issues/1) — Add the uv workspace and async ProjectStore | Shared workspace, async store, and tests | None |
| [#2](https://github.com/cblack34/composerai/issues/2) — Mount the project folder through the backend workspace member | Backend member, Compose mount, host-visible write | #1 |

## Delivery shape

- **Topology:** One pull request to `main`. Conventional Commits title. A human merges.
- **Branch or spine:** `slice/project-store-mount`
- **Final PR:** https://github.com/cblack34/composerai/pull/3
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

- **Outcome:** The repo is a uv workspace with one root `.venv`. An async `ProjectStore` is the only filesystem seam. Compose runs `apps/backend` with `projects/` bind-mounted, and a startup write appears on the host at `projects/verse-1/mounted.txt`.
- **Verification:** `uv sync --all-packages`, `uv run pytest` (27 passed), and `docker compose up --build -d` followed by the host file check and `docker compose down`. Evidence is on #1 and #2.
- **Deviations:** Generated filename tests skip unassigned, control, and private-use characters because this filesystem rejects some of them. The backend image runs as root so the bind mount is writable.
- **Unresolved gates or risks:** No CI workflow. The lead, MIDI model, and chat UI remain later slices. The next slice needs an xAI API key and model choice.
- **Final PR:** https://github.com/cblack34/composerai/pull/3
- **Merge state:** Pull request is open. Agents do not merge to `main`.
