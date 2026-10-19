# Slice plan — web search

## Strategic source

- **Active build pack:** [`docs/build-brief.md`](../../build-brief.md), [`docs/vision.md`](../../vision.md) (context only), [`docs/engineering/code-quality.md`](../../engineering/code-quality.md), [`docs/engineering/workflow.md`](../../engineering/workflow.md), [`docs/engineering/dependencies.md`](../../engineering/dependencies.md)
- **Human approval:** 2026-10-18. One `web_search` tool runs a short Grok agent with xAI native web search. The lead model stays configurable.
- **Final acceptance advanced:** The lead's tools include web search, as named in the build brief. Chat and MIDI save stay as they are.

## Outcome

The lead calls `web_search` with a query. The tool runs a short agent on `COMPOSERAI_SEARCH_MODEL` (default `xai:grok-4.7`) that has xAI native web search, and returns that agent's answer. The lead model remains `COMPOSERAI_MODEL`.

## Why this slice is next

Chat and MIDI save are on `main` (`bcee340`). Web search and feedback logging are the brief's remaining tools. Web search is this slice because the lead model is expected to change, and search stays on Grok's built-in tool rather than on whichever model is leading.

## Scope

### In scope

- A `web_search` tool on the lead. It takes a query and returns the search agent's text.
- The search agent has native web search only. It does not receive the project store, the MIDI model, or the lead's other tools.
- `COMPOSERAI_SEARCH_MODEL` through the existing settings model, default `xai:grok-4.7`. Compose and `.env.example` carry it. `XAI_API_KEY` stays in the process environment.
- Pytest with `FunctionModel` and no network call. One live chat confirms a real search.

### Out of scope

- Native web search on the lead model itself.
- DuckDuckGo, Moonshot, OpenRouter engine selection, X search, code execution, and file search.
- A new package or a new provider key.
- Feedback logging, UI changes, streaming, and any change to `POST /api/chat`.
- The roadmap in `docs/vision.md`.

## Strategic traceability

| Strategic requirement or criterion | How this slice advances it |
| --- | --- |
| The lead's tools include web search | The lead gains `web_search`. |
| The agent acts only through tools | Search runs inside that tool. The search agent has no store or MIDI access. |
| `ProjectStore` is the only filesystem seam | The search agent does not receive a store. |
| The user can chat with the lead | `POST /api/chat` is unchanged. A chat can still call the new tool. |

## Gates and dependencies

### Hard gates

- The lead, settings, and chat endpoint on `main`.
- The live search check needs `XAI_API_KEY` in the local environment. Offline tests do not read it.

### Sequencing recommendations

- None. This slice is one issue.

## Architecture and contracts

- **Affected seams:** the lead's tools and process settings. The chat HTTP contract, `ProjectStore`, and the MIDI protocol stay.
- **Public contracts:** `POST /api/chat` is unchanged. `COMPOSERAI_SEARCH_MODEL` is a new optional environment variable.
- **Data and migration considerations:** Search results are not written to the project folder by this tool. An empty `COMPOSERAI_SEARCH_MODEL` keeps the default.

## High-level approach

Add the search model to settings. Register `web_search` on the lead. The tool runs a separate agent whose only capability is xAI native web search, using the configured search model, and returns that agent's text. The chat handler and the CLI pass the setting in. Tests replace both models with `FunctionModel`.

## Verification

- `uv run pytest` from the repo root on Python 3.14. Those tests do not call xAI.
- One live chat through the running stack asks for a current fact. The reply shows that web search ran.
- A chat can still save a MIDI file. The search tool does not write one.

## Risks and stop conditions

- Stop if native web search on the search agent requires a new dependency.
- Stop if the search agent can read or write the project folder.
- Stop if `grok-4.7` rejects the native web search tool.
- Do not put `XAI_API_KEY` in the image, the repo, an issue, or an agent prompt.

## Execution issues

GitHub issues are the WIP tracker and source of task-level detail.

| Issue | Purpose | Dependencies |
| --- | --- | --- |
| [#13](https://github.com/cblack34/composerai/issues/13) — Add the web search tool | The tool, the search model setting, and the offline tests. | None |

## Delivery shape

- **Topology:** Direct pull request to `main`.
- **Branch or spine:** `slice/web-search`
- **Final PR:** Opened when #13 is complete.
- **Human merge gate:** Only the human may physically merge the final PR to `main`. Agents must stop when it is ready.

## Amendments

None.

## Delivery record

- **Outcome:** The lead has `web_search`. The tool runs a short agent on `COMPOSERAI_SEARCH_MODEL` with xAI native web search and returns that text. `POST /api/chat` is unchanged.
- **Verification:** `uv run pytest` on CPython 3.14, 82 passed. A live chat through `http://127.0.0.1:5173/api/chat` returned 200. The reply reported web results for an invented phrase and did not save a file. Evidence is on #13.
- **Deviations:** None. A blank query returns "The query is blank." and does not call the search agent.
- **Unresolved gates or risks:** No CI. Feedback logging remains out of this slice.
- **Final PR:** https://github.com/cblack34/composerai/pull/14
- **Merge state:** In review. Agents do not merge to `main`.
