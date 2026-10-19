# Slice plan — MIDI-LLM container

## Strategic source

- **Active build pack:** [docs/build-brief.md](../../build-brief.md). [docs/vision.md](../../vision.md) stays out of seed scope.
- **Human approval:** 2026-10-19. The maintainer approved this CPU container and the Llama 3.2 Community License for this local container.
- **Final acceptance advanced:** `docker compose up` can start a MIDI model service, and the lead can cause a MIDI file to be written into a section folder through that service and ProjectStore.

## Outcome

One local MIDI-LLM container answers a text prompt with MIDI bytes. The lead can call it through one tool, save the file through ProjectStore, and archive the generation the same way `save_section_midi` already does. The music21 stub stays.

## Why this slice is next

The seed brief names a Dockerized MIDI model. The in-process music21 stub already satisfies the folder write, and the maintainer asked for the real model plus the lead tool in this slice. The checkpoint is public. No hosted inference API serves it. Docker on this Mac cannot see the M4 GPU, so the container runs on CPU.

## Scope

### In scope

- One Compose service for `slseanwu/MIDI-LLM_Llama-3.2-1B`, transformers on CPU, MIDI bytes only.
- Weights download on first start into a named Docker volume. Weights stay out of git and out of the image.
- HTTP: a text prompt and optional generation parameters in, one MIDI body out.
- Lead tool `generate_midi_from_text`. The model id defaults to `midi-llm`. An unknown id writes nothing.
- The tool saves `<project>/<section>/<file>.mid` through ProjectStore and records a generation so a later thumb still has an id.
- The chat reply names that generation the same way it names a `save_section_midi` save.
- A note of the license approval in `docs/engineering/dependencies.md`.

### Out of scope

- GPU, MPS, vLLM, FP8, and audio synthesis.
- `continue_midi` and `infill_midi`. One line here is the whole deferral: a later slice can add them when a container supports them.
- A second real MIDI container, training, retrieval, ranking, comments, and frontend access to the model.
- Replacing or moving `save_section_midi`.
- Changing `POST /api/chat`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| Build brief: Docker Compose includes a MIDI model container | Adds one service beside the backend. |
| Build brief: the backend calls the Dockerized model and saves via ProjectStore | The new tool is the only lead path to this container. |
| Build brief: a MIDI file appears in a section folder | The tool writes that file. The music21 path still can too. |
| Vision: several MIDI models, retrieval, and fine-tuning stay deferred | One checkpoint and one id. Unknown ids write nothing. |

## Gates and dependencies

### Hard gates

- The Llama 3.2 Community License is accepted for this local container. That acceptance does not cover editing upstream files or committing weights.
- The HTTP contract exists before the lead tool calls it.
- A blank prompt, an unknown model id, a down container, or a body that is not MIDI writes nothing and does not archive a generation.

### Sequencing recommendations

- Build the image and the service contract first. Wire the tool second. The live generation check needs both.

## Architecture and contracts

- **Affected seams:** a new Compose service; the lead's tool list; Settings for the service URL; the reply trailer that names generation ids. ProjectStore remains the only writer of the project folder. The archive root stays outside the song folder.
- **Public contracts:** `POST /api/chat` stays `{prompt, messages}` in and `{reply}` out. `save_section_midi` and `log_feedback` stay. The new tool returns the same generation id, project id, and path shape on success.
- **Data and migration considerations:** none for existing projects. New generations use the same archive keys. The stable MIDI model id is `midi-llm`.

## High-level approach

The service listens on the Compose network and is also published on loopback port 8001 so a host can call it directly. The backend process keeps using port 8000. Inside the network the backend calls `http://midi-llm:8000`. Chat startup does not wait for the model to finish loading. A down service fails the new tool closed.

The image uses Python 3.14 and a CPU torch wheel. FastAPI validates the generate body. It does not install the upstream CUDA and vLLM lockfile. It clones the model code so the upstream license file stays in the image, and it does not edit those files. Anticipation (Apache-2.0) decodes tokens to MIDI. There is no FluidSynth and no MP3.

Defaults match the checkpoint card: temperature 1.0, top_p 0.98, max tokens 2046, one sequence. The live check uses a short token cap.

Disk: the named volume holds the Hugging Face cache. Removing that volume and the service image reclaims the weights. `docker compose down` leaves the volume in place.

## Verification

- `uv run pytest` passes without downloading weights. Tool tests use a fake server or a fake client.
- After the image is built, one short host request to the published port returns a body that starts with `MThd`. The weight file is in the volume and not in the image or the git tree.
- Repository definition of done remains `docker compose up --build` and a MIDI file in the mounted project folder. The live generation check is the evidence for this service. The music21 path is unchanged.

## Risks and stop conditions

- CPU generation of a full 2046-token piece will be slow. The live check stays short. Stop if the process is killed for memory. Do not resize Docker Desktop without asking.
- If bfloat16 will not run on CPU, float32 is allowed. Record that on the issue. Do not switch checkpoints.
- If the download fails because a file is gated, stop. Do not put a Hugging Face token in the repo, the image, or an issue.
- Do not install the upstream `requirements.txt`. It is a CUDA and vLLM lock.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#18](https://github.com/cblack34/composerai/issues/18) — Add the MIDI-LLM container | Image, Compose service, and the license note | None |
| [#19](https://github.com/cblack34/composerai/issues/19) — Call MIDI-LLM from the lead | The text-to-MIDI tool, the archive write, and the live MIDI check | #18 |

## Delivery shape

- **Topology:** direct PR to `main`
- **Branch or spine:** `slice/midi-llm-container`
- **Final PR:** https://github.com/cblack34/composerai/pull/20
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

### 2026-10-19 — Python 3.14 and FastAPI

- Previous assumption or plan statement: the image used Python 3.11 and a stdlib HTTP server. A rejected generate body was HTTP 400.
- New evidence: torch 2.14.1 publishes a CPU wheel for CPython 3.14 on linux/arm64. The maintainer asked for FastAPI so request validation can grow.
- Human-approved change: the image uses Python 3.14 and FastAPI. An invalid generate body is HTTP 422 and does not run the model. A blank prompt is that validation error.
- Affected issues: #18

## Delivery record

- **Outcome:** The `midi-llm` service returns one MIDI body for a text prompt. `generate_midi_from_text` archives that generation and writes the section file through ProjectStore. The music21 tool still works.
- **Verification:** `uv run pytest`, 145 passed, after the Python 3.14 and FastAPI amendment. The running container is CPython 3.14.8. `GET /health` returned 200 body `ok`. A blank prompt returned 422. `POST` to `127.0.0.1:8001/generate` with `max_tokens` 64 returned 167 bytes starting with `MThd`. bfloat16 loaded on CPU. The weight file is in the `midi-llm-weights` volume and not in the image or the git tree. Issues [#18](https://github.com/cblack34/composerai/issues/18) and [#19](https://github.com/cblack34/composerai/issues/19).
- **Deviations:** None. The client sends the prompt only. Sampling defaults stay on the service. bfloat16 loaded on CPU.
- **Unresolved gates or risks:** A full generation uses 2046 tokens and will be slow on CPU. Docker cannot use the M4 GPU. Continue and infill stay deferred.
- **Final PR:** https://github.com/cblack34/composerai/pull/20
- **Merge state:** Ready for the human to merge. Agents do not merge to `main`.
