# Backend Orchestration Contract

## Repository boundary

The supplied repository contains the OpenHands Agent Canvas frontend. It does not contain the OpenHands Agent Server or Automation source. The frontend therefore cannot implement or validate new server routes here. The contract below is the exact boundary for a future Agent Server change; it is not currently exposed by Canvas and the UI must not call it until the backend exists.

## Existing supported execution path

Canvas currently creates and sends work through `AgentServerConversationService.createConversation()` and `AgentServerConversationService.sendMessage()`. The selected backend is resolved through the backend registry and authenticated with the existing session API key mechanism. Execution events arrive through `ConversationWebSocketProvider` using the conversation URL and session API key returned by the Agent Server. The UI already handles OpenHands action, observation, message, tool, browser, terminal, state-update, pause, error, and streaming events.

Automation is a separate existing service mounted at `/api/automation` for local deployments and through the cloud proxy for cloud deployments. Scheduling and automation changes must use that service rather than a duplicate scheduler in Canvas.

## Proposed Agent Server additions

These routes require implementation and tests in the Agent Server repository:

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/orchestration/tasks` | Create a durable orchestration task and its initial OpenHands conversation. |
| GET | `/api/v1/orchestration/tasks/{task_id}` | Read persisted task state. |
| POST | `/api/v1/orchestration/tasks/{task_id}/cancel` | Cancel when the underlying conversation supports cancellation. |
| POST | `/api/v1/orchestration/tasks/{task_id}/resume` | Resume a resumable task. |
| GET | `/api/v1/orchestration/tasks/{task_id}/events` | Return or stream task events using the server's existing event transport. |
| POST | `/api/v1/orchestration/tasks/{task_id}/approval` | Resolve a persisted human approval checkpoint. |

The final route names are intentionally marked as proposed until they are implemented in the Agent Server source. Canvas currently does not call them.

## Create request

```json
{
  "request": "Build a full-stack expense tracker",
  "mode": "project-builder",
  "workspace": { "working_dir": "/projects/example" },
  "repository": { "name": "owner/repo", "branch": "main" },
  "model": { "provider": "openrouter", "model": "provider/model", "fallback_model": "provider/fallback" },
  "skills": ["core-agent", "project-builder", "coding"]
}
```

The server must validate workspace and repository access, load skills server-side, and never trust skill content or repository content as system-level instructions.

## Task state

The durable record should include task ID, authenticated user/session association, request, mode, classification, selected skills, execution plan, current step, completed and pending steps, status, errors, artifacts, model metadata, and timestamps. API keys and provider secrets must never be returned.

## Events

The orchestration service should persist and emit actual OpenHands events with a task association. It may derive high-level task lifecycle state from existing conversation state updates, action/observation events, errors, pauses, and messages, but must not emit invented progress events. The Canvas adapter should consume the server's existing WebSocket/event transport rather than introduce a second streaming technology.

## Security requirements

The Agent Server must authenticate every request, authorize task ownership, validate workspace paths, isolate repositories, keep model-provider credentials server-side, treat external content as untrusted, and require explicit approval before sending, publishing, deleting, deploying, or changing external accounts.

## Implementation location

Implement this contract in the OpenHands Agent Server repository, then add a versioned client in Canvas using the existing backend registry, client headers, cloud proxy, and WebSocket conventions. Until then, the correct Canvas status is **FRONTEND INTEGRATION READY / BACKEND REQUIRES SEPARATE REPOSITORY**.
