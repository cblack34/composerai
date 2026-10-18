# Slice plan — store protocol

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. Change `ProjectStore` from an abstract base class to a protocol, and remove the leftover annotation future-import, before the lead slice.
- **Final acceptance advanced:** `ProjectStore` remains the only filesystem seam. Callers keep depending on that interface. The public methods stay `list`, `read`, and `write`.

## Outcome

`ProjectStore` is a `typing.Protocol`. `LocalProjectStore` is still the only filesystem adapter. The annotation future-import is gone. Store behavior is unchanged.

## Why this slice is next

The lead slice will add a second interface and will copy this seam. The current `ABC` is the pattern that would be copied. Python 3.14 is already the workspace pin, and one `from __future__ import annotations` remains from the earlier pin. No research gate blocks this slice.

## Scope

### In scope

- `ProjectStore` as a protocol with the same three async methods.
- Removal of `from __future__ import annotations` in the local adapter.
- The existing store tests, still passing on Python 3.14.

### Out of scope

- The Pydantic AI lead, music21, and MIDI generation.
- The `projects/<project>/<section>/<file>` layout and the Compose probe path.
- `.env.example`, new dependencies, the React app, and any HTTP API.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| `ProjectStore` is the only filesystem seam | The seam stays one interface plus the local adapter. The interface becomes a protocol. |
| Depend on interfaces at boundaries | Callers keep using `ProjectStore`, not the filesystem. |
| Python 3.14 | The leftover annotation future-import is removed. Deferred annotation evaluation is the language default. |

## Gates and dependencies

### Hard gates

- None. Python 3.14 is already merged on `main`.

### Sequencing recommendations

- Land this before the lead and MIDI stub. That slice should declare its MIDI interface as a protocol.

## Architecture and contracts

- **Affected seams:** `ProjectStore` and `LocalProjectStore`.
- **Public contracts:** Method names, arguments, and result models stay. The interface is structural rather than an abstract base class. No `isinstance` checks exist today.
- **Data and migration considerations:** None. No on-disk format changes.

## High-level approach

Replace the abstract base class with a protocol in the store package. Keep the local adapter as the implementation. Delete the future-import. Do not restyle the adapter or change path confinement.

## Verification

- `uv run pytest` from the repo root on Python 3.14. The existing store suite is the evidence that behavior held.

## Risks and stop conditions

- Stop if the protocol change requires a new dependency or changes which paths the store accepts.
- Stop if a caller was relying on abstract-base-class registration. None does today.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#5](https://github.com/cblack34/composerai/issues/5) — Make ProjectStore a Protocol | Switch the seam to a protocol and drop the annotation future-import. | None |

## Delivery shape

- **Topology:** One direct pull request to `main`.
- **Branch or spine:** `slice/store-protocol`
- **Final PR:** https://github.com/cblack34/composerai/pull/6
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

Complete once when the final PR is ready for human merge. Do not use this section for WIP status.

- **Outcome:** `ProjectStore` is a `typing.Protocol` with `list`, `read`, and `write`. `LocalProjectStore` still implements it. `from __future__ import annotations` is gone from the local adapter. Store behavior is unchanged.
- **Verification:** `uv run pytest` on CPython 3.14.7, 35 passed. Evidence is on #5.
- **Deviations:** None.
- **Unresolved gates or risks:** No CI. Copilot review is requested on the final head. The lead slice is next.
- **Final PR:** https://github.com/cblack34/composerai/pull/6
- **Merge state:** Waiting on review of the final head. Agents do not merge to `main`.
