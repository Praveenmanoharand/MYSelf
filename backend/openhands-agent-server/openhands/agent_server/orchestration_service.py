from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from openhands.agent_server.conversation_service import ConversationService
from openhands.agent_server.models import StartConversationRequest
from openhands.agent_server.orchestration_models import (
    CreateTaskRequest,
    OrchestrationEvent,
    OrchestrationStatus,
    OrchestrationTask,
    classify_request,
    validate_workspace,
)
from openhands.agent_server.orchestration_store import OrchestrationStore
from openhands.agent_server.pub_sub import Subscriber
from openhands.agent_server.skills_service import load_all_skills
from openhands.sdk import LLM, Agent, AgentContext, Message, TextContent
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.event import Event
from openhands.sdk.event.conversation_state import ConversationStateUpdateEvent
from openhands.sdk.skills.skill import load_skills_from_dir
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.preset.default import get_default_tools


class _TaskSubscriber(Subscriber[Event]):
    def __init__(self, service: OrchestrationService, task_id: UUID):
        self.service = service
        self.task_id = task_id

    async def __call__(self, event: Event):
        await self.service.record_event(self.task_id, event)


class OrchestrationService:
    def __init__(
        self,
        conversation_service: ConversationService,
        persistence_dir: Path,
        workspace_root: Path,
    ):
        self.conversation_service = conversation_service
        self.store = OrchestrationStore(persistence_dir)
        self.workspace_root = workspace_root
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._subscribers: dict[UUID, tuple[Any, UUID]] = {}

    @staticmethod
    def _session_id(session_key: str | None) -> str:
        return hashlib.sha256((session_key or "anonymous").encode()).hexdigest()[:32]

    def _model_config(
        self, request: CreateTaskRequest
    ) -> tuple[str, str, str | None, str | None]:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        model = (
            request.model
            or os.getenv("DEFAULT_MODEL")
            or os.getenv("OPENROUTER_MODEL")
            or "openai/gpt-4o-mini"
        )
        fallback = request.fallback_model or os.getenv("FALLBACK_MODEL")
        api_key = openrouter_key or os.getenv("OPENAI_API_KEY")
        base_url = (
            openrouter_base_url if openrouter_key else os.getenv("OPENAI_API_BASE")
        )
        provider = "openrouter" if openrouter_key else "configured"
        return model, provider, fallback, api_key if base_url else None

    def _selected_skills(
        self, request_text: str, workspace: str
    ) -> tuple[list[str], str]:
        result = load_all_skills(
            load_public=False, load_user=True, load_project=True, project_dir=workspace
        )
        skills = {skill.name: skill for skill in result.skills}
        bundled_dir = Path(__file__).resolve().parents[2] / "skills"
        if bundled_dir.exists():
            bundled, knowledge, agent_skills = load_skills_from_dir(bundled_dir)
            skills.update(bundled)
            skills.update(knowledge)
            skills.update(agent_skills)
        category = classify_request(request_text, "general")
        names = {"core-agent", category}
        if category == "coding":
            names.update({"project-builder", "coding"})
        if category == "proposal":
            names.update({"freelancer", "proposal-generator", "document-generator"})
        if category == "document":
            names.update({"document-generator", "content-writer"})
        if category == "research":
            names.update({"research", "data-analysis"})
        selected = [skills[name] for name in names if name in skills]
        context = "\n\n".join(f"## {skill.name}\n{skill.content}" for skill in selected)
        return [skill.name for skill in selected], context

    async def create_task(
        self, request: CreateTaskRequest, session_key: str | None
    ) -> OrchestrationTask:
        workspace = validate_workspace(request.workspace, self.workspace_root)
        selected_skills, skill_context = self._selected_skills(
            request.request, workspace
        )
        model, provider, fallback, api_key = self._model_config(request)
        plan = [
            "Understand request",
            "Select skills and configure agent",
            "Execute through OpenHands",
            "Validate result",
            "Record artifacts",
        ]
        task = OrchestrationTask(
            session_id=self._session_id(session_key),
            request=request.request,
            mode=request.mode,
            workspace=workspace,
            repository=request.repository,
            classification=classify_request(request.request, request.mode),
            selected_skills=selected_skills,
            execution_plan=plan,
            pending_steps=list(range(len(plan))),
            model=model,
            provider=provider,
            fallback_model=fallback,
        )
        await self.store.save_task(task)
        await self._emit(task, "task_created", {"selected_skills": selected_skills})
        task.status = OrchestrationStatus.PLANNING
        await self.store.save_task(task)
        await self._emit(task, "planning_started", {"plan": plan})
        self._tasks[task.id] = asyncio.create_task(
            self._execute(task, skill_context, api_key)
        )
        return task

    async def _execute(
        self,
        task: OrchestrationTask,
        skill_context: str,
        api_key: str | None,
        allow_fallback: bool = True,
    ) -> None:
        event_service = None
        subscription_id = None
        try:
            llm = LLM(
                model=task.model or "openai/gpt-4o-mini",
                api_key=SecretStr(api_key) if api_key else None,
                base_url=(
                    os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                    if api_key and os.getenv("OPENROUTER_API_KEY")
                    else os.getenv("OPENAI_API_BASE")
                ),
                timeout=int(os.getenv("MODEL_TIMEOUT_SECONDS", "120")),
                num_retries=int(os.getenv("MODEL_MAX_RETRIES", "2")),
            )
            agent = Agent(
                llm=llm,
                tools=get_default_tools(enable_browser=True),
                agent_context=AgentContext(system_message_suffix=skill_context or None),
            )
            start_request = StartConversationRequest(
                workspace=LocalWorkspace(working_dir=task.workspace),
                agent=agent,
                initial_message=None,
                tags={"orchestrationtask": str(task.id)},
            )
            start = await self.conversation_service.start_conversation(start_request)
            task.conversation_id = start[0].id
            task.status = OrchestrationStatus.RUNNING
            task.current_step = 2
            task.completed_steps = [0, 1]
            task.pending_steps = [2, 3, 4]
            await self.store.save_task(task)
            event_service = await self.conversation_service.get_event_service(
                task.conversation_id
            )
            if event_service is None:
                raise RuntimeError("Conversation event service unavailable")
            subscriber = _TaskSubscriber(self, task.id)
            subscription_id = await event_service.subscribe_to_events(subscriber)
            self._subscribers[task.id] = (event_service, subscription_id)
            await event_service.send_message(
                Message(role="user", content=[TextContent(text=task.request)]), run=True
            )
            deadline = time.monotonic() + max(
                300, int(os.getenv("MODEL_TIMEOUT_SECONDS", "120")) + 30
            )
            execution_status = ConversationExecutionStatus.IDLE
            while time.monotonic() < deadline:
                state = await event_service.get_state()
                execution_status = state.execution_status
                if execution_status in (
                    ConversationExecutionStatus.PAUSED,
                    ConversationExecutionStatus.WAITING_FOR_CONFIRMATION,
                    ConversationExecutionStatus.FINISHED,
                    ConversationExecutionStatus.ERROR,
                    ConversationExecutionStatus.STUCK,
                ):
                    break
                await asyncio.sleep(0.5)
            else:
                raise TimeoutError("OpenHands execution did not reach a terminal state")
            if (
                execution_status == ConversationExecutionStatus.PAUSED
                or execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                task.status = OrchestrationStatus.WAITING_FOR_USER
            elif execution_status in (
                ConversationExecutionStatus.FINISHED,
                ConversationExecutionStatus.ERROR,
                ConversationExecutionStatus.STUCK,
            ):
                task.status = (
                    OrchestrationStatus.COMPLETED
                    if execution_status == ConversationExecutionStatus.FINISHED
                    else OrchestrationStatus.FAILED
                )
                task.current_step = 4
                task.completed_steps = [0, 1, 2, 3, 4]
                task.pending_steps = []
                task.artifacts = self._scan_artifacts(task.workspace)
            await self.store.save_task(task)
            await self._emit(
                task,
                "task_completed"
                if task.status == OrchestrationStatus.COMPLETED
                else "task_state_changed",
                {
                    "conversation_id": str(task.conversation_id),
                    "execution_status": str(execution_status),
                },
            )
        except asyncio.CancelledError:
            task.status = OrchestrationStatus.CANCELLED
            await self.store.save_task(task)
            await self._emit(task, "task_cancelled")
            raise
        except Exception as exc:
            if (
                allow_fallback
                and task.fallback_model
                and task.model != task.fallback_model
            ):
                task.status = OrchestrationStatus.RETRYING
                task.errors.append(f"Primary model failed: {type(exc).__name__}: {exc}")
                await self.store.save_task(task)
                await self._emit(
                    task, "retrying", {"fallback_model": task.fallback_model}
                )
                task.model = task.fallback_model
                await self._execute(task, skill_context, api_key, allow_fallback=False)
                return
            task.status = OrchestrationStatus.FAILED
            task.errors.append(f"{type(exc).__name__}: {exc}")
            await self.store.save_task(task)
            await self._emit(task, "error", {"message": str(exc)})
        finally:
            if event_service is not None and subscription_id is not None:
                await event_service.unsubscribe_from_events(subscription_id)
            self._subscribers.pop(task.id, None)

    @staticmethod
    def _scan_artifacts(workspace: str) -> list[dict[str, Any]]:
        root = Path(workspace)
        artifacts: list[dict[str, Any]] = []
        if not root.exists():
            return artifacts
        for path in root.rglob("*"):
            if len(artifacts) >= 500 or not path.is_file() or ".git" in path.parts:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            artifacts.append(
                {
                    "path": str(path.relative_to(root)),
                    "absolute_path": str(path),
                    "size": stat.st_size,
                    "exists": path.exists(),
                }
            )
        return artifacts

    async def record_event(self, task_id: UUID, event: Event) -> None:
        payload = (
            event.model_dump(mode="json")
            if hasattr(event, "model_dump")
            else {"value": str(event)}
        )
        kind = event.__class__.__name__
        await self._emit_by_id(task_id, kind, payload)
        if isinstance(event, ConversationStateUpdateEvent):
            task = await self.store.get_task(task_id)
            if task is not None:
                status = str(event.value).lower()
                if "paused" in status or "confirmation" in status:
                    task.status = OrchestrationStatus.WAITING_FOR_USER
                elif "running" in status:
                    task.status = OrchestrationStatus.RUNNING
                await self.store.save_task(task)

    async def _emit(
        self, task: OrchestrationTask, kind: str, payload: dict[str, Any] | None = None
    ) -> None:
        await self._emit_by_id(task.id, kind, payload or {})

    async def _emit_by_id(
        self, task_id: UUID, kind: str, payload: dict[str, Any]
    ) -> None:
        await self.store.append_event(
            OrchestrationEvent(task_id=task_id, kind=kind, payload=payload)
        )

    async def get_task(self, task_id: UUID) -> OrchestrationTask | None:
        return await self.store.get_task(task_id)

    async def cancel_task(self, task_id: UUID) -> OrchestrationTask:
        task = await self._require(task_id)
        if task.conversation_id:
            await self.conversation_service.interrupt_conversation(task.conversation_id)
        running = self._tasks.get(task_id)
        if running:
            running.cancel()
        task.status = OrchestrationStatus.CANCELLED
        await self.store.save_task(task)
        await self._emit(task, "task_cancelled")
        return task

    async def resume_task(
        self, task_id: UUID, message: str | None = None
    ) -> OrchestrationTask:
        task = await self._require(task_id)
        if not task.conversation_id:
            raise ValueError("task has no conversation")
        event_service = await self.conversation_service.get_event_service(
            task.conversation_id
        )
        if event_service is None:
            raise ValueError("conversation event service unavailable")
        if message:
            await event_service.send_message(
                Message(role="user", content=[TextContent(text=message)]), run=False
            )
        task.status = OrchestrationStatus.RUNNING
        await self.store.save_task(task)
        await self._emit(task, "task_resumed")
        await event_service.run()
        return task

    async def _require(self, task_id: UUID) -> OrchestrationTask:
        task = await self.store.get_task(task_id)
        if task is None:
            raise KeyError(str(task_id))
        return task
