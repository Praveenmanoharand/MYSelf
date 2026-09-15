from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path
from typing import Any
from uuid import UUID

from openhands.agent_server.orchestration_models import (
    OrchestrationEvent,
    OrchestrationTask,
)


class OrchestrationStore:
    def __init__(self, root: Path):
        self.root = root / "orchestration"
        self.root.mkdir(parents=True, exist_ok=True, mode=stat.S_IRWXU)
        self._lock = asyncio.Lock()

    def _task_path(self, task_id: UUID) -> Path:
        return self.root / f"{task_id}.json"

    def _events_path(self, task_id: UUID) -> Path:
        return self.root / f"{task_id}.events.jsonl"

    def _write_json(self, path: Path, value: Any) -> None:
        temporary = path.with_suffix(f".tmp.{os.getpid()}")
        temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        temporary.replace(path)

    async def save_task(self, task: OrchestrationTask) -> OrchestrationTask:
        async with self._lock:
            self._write_json(self._task_path(task.id), task.model_dump(mode="json"))
        return task

    async def get_task(self, task_id: UUID) -> OrchestrationTask | None:
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            return OrchestrationTask.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None

    async def append_event(self, event: OrchestrationEvent) -> None:
        async with self._lock:
            path = self._events_path(event.task_id)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    async def get_events(
        self, task_id: UUID, limit: int = 100, page_id: str | None = None
    ) -> list[OrchestrationEvent]:
        path = self._events_path(task_id)
        if not path.exists():
            return []
        events: list[OrchestrationEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(OrchestrationEvent.model_validate_json(line))
            except ValueError:
                continue
        if page_id:
            try:
                index = (
                    next(
                        i for i, event in enumerate(events) if str(event.id) == page_id
                    )
                    + 1
                )
                events = events[index:]
            except StopIteration:
                pass
        return events[:limit]
