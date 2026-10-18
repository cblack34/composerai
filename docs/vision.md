# Vision / Roadmap

Captured during seed planning. Not in scope for the seed. See `docs/build-brief.md` for what to build now.

## Core idea

A local, VS Code-inspired songwriting workspace. A lead agent helps compose by section. MIDI is the primary artifact. The user and agent share a project folder. Feedback is logged for later improvement.

## Deferred

### UI
- Real project explorer with section folders.
- Piano roll / sheet music view.
- Ranking sidebar with play buttons and drag-to-rank.
- Persistent controls (section, BPM, key, time signature) packaged as cache-friendly context JSON.
- Lite DAW tab.
- Flexible chat placement.

### Agent capabilities
- MIDI → AI-readable conversion tool.
- Retrieval of past prompts/outputs.
- Lyrics parsing for note durations.
- Multiple MIDI models with lead selection.
- Preference data for later fine-tuning.

### Architecture
- File API backed by ProjectStore.
- Additional ProjectStore adapters (e.g. S3) for hosting.
- Single-user now; model ready for multi-user later.
