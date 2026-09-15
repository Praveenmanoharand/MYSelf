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


def test_openrouter_environment_config_is_selected_without_logging_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-for-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("FALLBACK_MODEL", "openai/gpt-4o-mini")
    service = OrchestrationService(object(), tmp_path, tmp_path)

    model, provider, fallback, api_key = service._model_config(
        CreateTaskRequest(request="run")
    )

    assert model == "openai/gpt-4o-mini"
    assert provider == "openrouter"
    assert fallback == "openai/gpt-4o-mini"
    assert api_key == "secret-for-test"
