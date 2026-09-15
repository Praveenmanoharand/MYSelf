from pathlib import Path

import pytest

from openhands.agent_server.orchestration_models import (
    CreateTaskRequest,
    OrchestrationStatus,
    classify_request,
    validate_workspace,
)
from openhands.agent_server.orchestration_service import OrchestrationService
from openhands.agent_server.orchestration_store import OrchestrationStore


def test_classification_routes_modes_and_language():
    assert classify_request("Build a full-stack expense tracker", "general") == "coding"
    assert classify_request("Create a proposal and quotation", "general") == "proposal"
    assert (
        classify_request("research sources and compare them", "general") == "research"
    )
    assert classify_request("anything", "document") == "document"


def test_workspace_isolation(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    assert validate_workspace(None, root) == str(root.resolve())
    assert validate_workspace(str(root / "project"), root).startswith(
        str(root.resolve())
    )
    with pytest.raises(ValueError, match="inside"):
        validate_workspace(str(tmp_path / "outside"), root)


@pytest.mark.asyncio
async def test_store_round_trip_and_event_pagination(tmp_path: Path):
    store = OrchestrationStore(tmp_path)
    from openhands.agent_server.orchestration_models import (
        OrchestrationEvent,
        OrchestrationTask,
    )

    task = OrchestrationTask(
        session_id="session", request="test", workspace=str(tmp_path)
    )
    await store.save_task(task)
    assert (await store.get_task(task.id)).status == OrchestrationStatus.QUEUED
    await store.append_event(OrchestrationEvent(task_id=task.id, kind="one"))
    await store.append_event(OrchestrationEvent(task_id=task.id, kind="two"))
    events = await store.get_events(task.id, limit=1)
    assert len(events) == 1
    assert (await store.get_events(task.id, page_id=str(events[0].id)))[0].payload == {}


def test_artifact_scan_only_reports_existing_files(tmp_path: Path):
    artifact = tmp_path / "proposal.md"
    artifact.write_text("real", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored").write_text("no", encoding="utf-8")
    found = OrchestrationService._scan_artifacts(str(tmp_path))
    assert len(found) == 1
    assert found[0]["path"] == "proposal.md"
    assert found[0]["exists"] is True


def test_task_request_does_not_store_api_keys():
    payload = CreateTaskRequest(request="run", model="openai/test")
    assert "api_key" not in payload.model_dump()
