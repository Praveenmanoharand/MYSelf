from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from openhands.agent_server.dependencies import get_conversation_service
from openhands.agent_server.orchestration_models import (
    ApprovalRequest,
    CreateTaskRequest,
    ResumeTaskRequest,
    TaskEventsResponse,
    TaskResponse,
)
from openhands.agent_server.orchestration_service import OrchestrationService


orchestration_router = APIRouter(
    prefix="/v1/orchestration/tasks", tags=["Orchestration"]
)


def get_service(request: Request) -> OrchestrationService:
    service = getattr(request.app.state, "orchestration_service", None)
    if service is None:
        service = OrchestrationService(
            get_conversation_service(request),
            request.app.state.config.conversations_path,
            request.app.state.config.workspace_path,
        )
        request.app.state.orchestration_service = service
    return service


def session_key(request: Request) -> str | None:
    return request.headers.get("X-Session-API-Key")


async def owned_task(service: OrchestrationService, task_id: UUID, request: Request):
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.session_id != service._session_id(session_key(request)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@orchestration_router.post(
    "", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create_task(payload: CreateTaskRequest, request: Request) -> TaskResponse:
    try:
        task = await get_service(request).create_task(payload, session_key(request))
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return TaskResponse(task=task)


@orchestration_router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, request: Request) -> TaskResponse:
    task = await owned_task(get_service(request), task_id, request)
    return TaskResponse(task=task)


@orchestration_router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: UUID, request: Request) -> TaskResponse:
    service = get_service(request)
    await owned_task(service, task_id, request)
    try:
        return TaskResponse(task=await service.cancel_task(task_id))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@orchestration_router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(
    task_id: UUID, payload: ResumeTaskRequest, request: Request
) -> TaskResponse:
    service = get_service(request)
    await owned_task(service, task_id, request)
    try:
        return TaskResponse(task=await service.resume_task(task_id, payload.message))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@orchestration_router.post("/{task_id}/approval", response_model=TaskResponse)
async def approve_task(
    task_id: UUID, payload: ApprovalRequest, request: Request
) -> TaskResponse:
    service = get_service(request)
    task = await owned_task(service, task_id, request)
    if task.status.value != "waiting_for_user":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Task is not waiting for user approval"
        )
    if not payload.approved:
        task.status = "cancelled"
        task.errors.append(payload.reason or "Approval rejected")
        await service.store.save_task(task)
        await service._emit(task, "approval_rejected", {"reason": payload.reason})
        return TaskResponse(task=task)
    return TaskResponse(task=await service.resume_task(task_id, payload.reason or None))


@orchestration_router.get("/{task_id}/events", response_model=TaskEventsResponse)
async def get_task_events(
    task_id: UUID, request: Request, page_id: str | None = None, limit: int = 100
) -> TaskEventsResponse:
    service = get_service(request)
    await owned_task(service, task_id, request)
    items = await service.store.get_events(task_id, min(max(limit, 1), 100), page_id)
    return TaskEventsResponse(
        items=items,
        next_page_id=str(items[-1].id)
        if len(items) == min(max(limit, 1), 100)
        else None,
    )


@orchestration_router.websocket("/{task_id}/events/ws")
async def stream_task_events(websocket: WebSocket, task_id: str):
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        await websocket.accept()
        await websocket.send_json({"kind": "error", "detail": "Invalid task id"})
        await websocket.close(code=4400)
        return
    app = websocket.scope["app"]
    config = app.state.config
    key = websocket.headers.get("X-Session-API-Key")
    if config.session_api_keys and key not in config.session_api_keys:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    service = getattr(app.state, "orchestration_service", None)
    if service is None:
        service = OrchestrationService(
            app.state.conversation_service,
            config.conversations_path,
            config.workspace_path,
        )
        app.state.orchestration_service = service
    page_id: str | None = None
    try:
        task = await service.get_task(task_uuid)
        if task is None or task.session_id != service._session_id(key):
            await websocket.send_json({"kind": "error", "detail": "Task not found"})
            await websocket.close(code=4404)
            return
        while True:
            events = await service.store.get_events(
                task_uuid, limit=100, page_id=page_id
            )
            for event in events:
                await websocket.send_json(event.model_dump(mode="json"))
                page_id = str(event.id)
            latest = await service.get_task(task_uuid)
            if latest is None or latest.status.value in {
                "completed",
                "failed",
                "cancelled",
            }:
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"kind": "error", "detail": str(exc)})
        await websocket.close(code=1011)
