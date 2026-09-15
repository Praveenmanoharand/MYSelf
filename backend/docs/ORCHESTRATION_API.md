# Agent Canvas Orchestration API

The Agent Server exposes the orchestration layer under the existing authenticated API group:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/orchestration/tasks` | Create a task and queue real OpenHands execution |
| GET | `/api/v1/orchestration/tasks/{id}` | Read persistent task state |
| POST | `/api/v1/orchestration/tasks/{id}/cancel` | Interrupt the underlying conversation and cancel the task |
| POST | `/api/v1/orchestration/tasks/{id}/resume` | Resume a paused task, optionally with a user message |
| POST | `/api/v1/orchestration/tasks/{id}/approval` | Approve or reject a waiting task |
| GET | `/api/v1/orchestration/tasks/{id}/events` | Read durable normalized and OpenHands events |
| WebSocket | `/api/v1/orchestration/tasks/{id}/events/ws` | Stream durable events until terminal state |

Requests are authenticated by the existing `X-Session-API-Key` dependency. Task ownership is scoped to a hash of that session key; the raw key is never persisted or returned.

## Execution

Task creation validates that the workspace is inside the configured Agent Server workspace root. The server loads user and project skills through the SDK skill loader and merges the bundled server `SKILL.md` definitions. It creates a real `StartConversationRequest`, `Agent`, `LLM`, and `LocalWorkspace`, starts the existing `ConversationService`, subscribes to the existing `EventService`, and sends the user request through the real agent loop.

`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `FALLBACK_MODEL`, `MODEL_TIMEOUT_SECONDS`, and `MODEL_MAX_RETRIES` are server-only environment variables. The task response exposes model names and provider metadata, never credentials. If the primary execution setup fails and a fallback model is configured, the task enters `retrying` and starts a second real conversation using the fallback model.

Task records and JSONL event histories are stored under the configured conversations path in an owner-only `orchestration` directory. Completed tasks scan the workspace and record only files that actually exist, excluding `.git` content.

## Honest limitations

The WebSocket stream polls the durable JSONL event log at a bounded interval, so it does not introduce an independent in-memory event bus. The first implementation does not fabricate PDF/DOCX generation: document artifacts are only reported when an OpenHands tool actually creates them in the workspace.
