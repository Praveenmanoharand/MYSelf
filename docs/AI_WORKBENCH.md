# AI Workbench Architecture

The AI Workbench extends OpenHands Agent Canvas without replacing its execution layer. The home command center creates a persisted local task record, classifies the request, selects skills, stores the prompt draft, and launches the existing OpenHands conversation flow. OpenHands remains responsible for actual file operations, commands, tool calls, agent execution, and backend communication.

## Phase-one modules

| Module | Responsibility |
|---|---|
| `src/lib/agent-orchestrator/skills.ts` | Discovers bundled `skills/*/SKILL.md` files, parses YAML front matter, classifies requests, and builds skill context. |
| `task-state.ts` | Creates and persists task plans, selected skills, statuses, steps, errors, and artifact IDs in browser storage. |
| `model-router.ts` | Reads optional environment-driven primary, task-specific, and fallback model metadata without exposing credentials. |
| `quotation.ts` | Performs deterministic line-item, tax, discount, total, and milestone calculations. |
| `workflow.ts` | Enforces workflow dependencies and explicit step state transitions. |
| `artifacts.ts` | Defines artifact metadata and requires an existence check before marking an artifact verified. |

## Skills

Add a directory under `skills/` with a `SKILL.md` file containing YAML front matter:

```md
---
name: my-skill
description: What this skill does
---

Instructions passed to the orchestrator.
```

The Vite build bundles these files through `import.meta.glob`, so adding a skill does not require changing the orchestrator source.

## Optional model configuration

The existing OpenHands backend remains the default execution path. Optional route metadata can be configured with:

- `VITE_MODEL_PROVIDER`
- `VITE_PRIMARY_MODEL`
- `VITE_FALLBACK_MODEL`
- `VITE_MODEL_TIMEOUT_MS`
- `VITE_MODEL_MAX_RETRIES`
- `VITE_OPENROUTER_MODEL`
- `VITE_<TASK_TYPE>_MODEL`, such as `VITE_RESEARCH_MODEL`

API keys must remain server-side or in the existing backend configuration. Do not put provider secrets in Vite-exposed variables.

## Validation

Run:

```sh
npm run typecheck
npm run build:app
npx vitest run src/lib/agent-orchestrator
```

## Current limitations

This phase does not claim a standalone server-side orchestrator, direct web-search API, PDF/DOCX generator, external messaging connector, or workflow scheduler. Those capabilities need backend/API ownership and should be implemented in later phases through the existing OpenHands and automation services. The current modes route real work through OpenHands and do not simulate those unavailable integrations.
