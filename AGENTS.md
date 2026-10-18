# AGENTS.md — composerai

Instructions for the AI agent that plans and builds this project. This file is the source of truth for **how** to work; the active strategic pack listed below defines **what** must be true.

**Code, types, schemas, commands, and file layouts in strategic docs are illustrative guidance, not mandates.** Described behavior, architecture contracts, non-negotiables, and final acceptance are authoritative.

## What this is

A local AI songwriting workspace. A lead agent helps compose by section and writes MIDI into a project folder. The seed proves the core loop: chat → lead plans a section → MIDI model generates → result saved to disk.

Stack: Python (Pydantic AI) backend, React + TypeScript + Vite frontend, Docker Compose, local project folder via volume mount.

## Prime directive

**Cold-read the active pack and current repository, then propose only the single best next implementation slice before coding.** Preserve the complete strategic outcome and stop when final acceptance passes.

The human approves scope changes, architecture boundary changes, and merges to `main`.

## Definition of done

```bash
# Seed verification (to be filled as the project grows)
docker compose up --build
# Confirm agent can write a MIDI file into the mounted project folder
```

## Non-negotiables

1. **ProjectStore is the only filesystem seam.** Nothing else reads or writes the project folder directly.
2. **The agent acts only through explicit tools.** No reaching around tools.
3. **Frontend talks only to the backend API.** No direct filesystem or model access.
4. **MIDI models are invoked through a narrow interface.** The rest of the system does not depend on a specific model.

## Dependencies

Follow [`docs/engineering/dependencies.md`](docs/engineering/dependencies.md).

## Always / Ask first / Never

- **Always:** follow `docs/engineering/workflow.md` and `docs/engineering/code-quality.md`; depend on interfaces at boundaries.
- **Ask first:** changing a non-negotiable, adding a new external service, expanding beyond the current seed scope, or adding a dependency whose license or maintenance status is unclear.
- **Never:** implement deferred roadmap items in the seed; bypass ProjectStore; merge to `main`.

## Active build pack

1. [`docs/build-brief.md`](docs/build-brief.md) — seed scope and boundaries (read first)
2. [`docs/vision.md`](docs/vision.md) — broader roadmap (context only; not in scope for seed)
3. [`docs/engineering/code-quality.md`](docs/engineering/code-quality.md)
4. [`docs/engineering/workflow.md`](docs/engineering/workflow.md)
5. [`docs/engineering/dependencies.md`](docs/engineering/dependencies.md)
