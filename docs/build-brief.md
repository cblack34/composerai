# Build Brief — Seed

_Read this first. This defines the minimal seed. The broader vision lives in `docs/vision.md` and is out of scope for the seed._

## Product outcome

A runnable local loop: the user chats with a lead agent; the agent can plan a section, call a MIDI model, and save the resulting MIDI (and notes) into a project folder on disk. The user opens the MIDI externally.

## In scope

- Docker Compose with backend, MIDI model container, and a volume mount for the project folder.
- `ProjectStore` interface + local filesystem adapter.
- Pydantic AI agent with tools: ProjectStore operations (list/read/write), MIDI model invocation, web search, feedback logging.
- Minimal React + TypeScript + Vite frontend with a chat panel (explorer optional/dummy).
- Simple section-folder convention (e.g. `verse-1/`, `chorus/`).
- Vision/roadmap file already present for later work.

## Out of scope

- Real project explorer, piano roll, ranking UI, lite DAW.
- File API for the frontend (open files externally for now).
- Structured section/BPM/key controls and context JSON.
- MIDI-to-AI-readable conversion tool.
- Multiple model adapters beyond a single invocation path.
- Auth, multi-user, or non-local storage.

## Architecture boundaries and contracts

1. **ProjectStore** — sole filesystem interface. Agent tools call it; nothing else touches the project folder.
2. **Agent tools** — the only way the lead acts. Includes ProjectStore ops, MIDI invoke, web search, feedback log.
3. **Frontend ↔ Backend** — React talks only to the backend API.
4. **MIDI model invocation** — narrow interface. Backend calls the Dockerized model and saves results via ProjectStore.

## Suggested implementation approach

1. Docker Compose skeleton + volume mount.
2. `ProjectStore` interface + local adapter.
3. Pydantic AI agent + tools.
4. Minimal chat frontend.
5. Wire MIDI model invocation (or a stub that writes a fixed MIDI) and confirm a file appears in the project folder.

## Definition of done

- `docker compose up` starts the stack.
- User can chat with the lead.
- Lead can cause a MIDI file to be written into a section folder in the mounted project directory.
- User can open that MIDI file from the host filesystem.
