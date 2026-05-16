from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.researchos.execution.runtime_adapter import repo_root

from .research_task import ResearchTask


def default_task_root() -> Path:
    if os.environ.get("RESEARCHOS_TASKS_ROOT"):
        return Path(os.environ["RESEARCHOS_TASKS_ROOT"])
    try:
        from backend.researchos.config.paths import get_research_tasks_dir

        return get_research_tasks_dir()
    except Exception:
        return repo_root() / "data" / "research_tasks"


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


class ResearchTaskStateStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else default_task_root()

    def task_dir(self, task_id: str) -> Path:
        return self.base_dir / task_id

    def create_task(self, project_id: str | None, user_query: str, task_id: str | None = None) -> ResearchTask:
        task = ResearchTask(task_id=task_id, project_id=project_id, user_query=user_query) if task_id else ResearchTask(project_id=project_id, user_query=user_query)
        self.task_dir(task.task_id).mkdir(parents=True, exist_ok=True)
        self._write_json(task.task_id, "task.json", task.to_dict())
        self.append_event(task.task_id, "task_created", {"project_id": project_id, "user_query": user_query})
        return task

    def load_task(self, task_id: str) -> ResearchTask:
        payload = self._read_json(task_id, "task.json")
        return ResearchTask.from_dict(payload)

    def save_task(self, task: ResearchTask) -> None:
        task.touch()
        self.task_dir(task.task_id).mkdir(parents=True, exist_ok=True)
        self._write_json(task.task_id, "task.json", task.to_dict())

    def mark_running(self, task: ResearchTask) -> None:
        task.status = "running"
        self.save_task(task)
        self.append_event(task.task_id, "task_running", {})

    def write_goal(self, task: ResearchTask, goal: dict[str, Any]) -> None:
        task.goal = goal
        self._write_json(task.task_id, "goal.json", goal)
        self.save_task(task)
        self.append_event(task.task_id, "goal_written", {"file": "goal.json"})

    def write_plan(self, task: ResearchTask, plan_markdown: str) -> None:
        task.plan = plan_markdown
        task.status = "planned"
        self._write_text(task.task_id, "plan.md", plan_markdown)
        self.save_task(task)
        self.append_event(task.task_id, "plan_written", {"file": "plan.md"})

    def write_contract(self, task: ResearchTask, contract: dict[str, Any]) -> None:
        task.contract = contract
        task.status = "contracted"
        self._write_json(task.task_id, "contract.json", contract)
        self.save_task(task)
        self.append_event(task.task_id, "contract_written", {"file": "contract.json"})

    def write_execution(self, task: ResearchTask, execution: dict[str, Any]) -> None:
        task.execution = execution
        task.status = "failed" if execution.get("status") == "failed" else "completed"
        self._write_json(task.task_id, "execution_result.json", execution)
        self.save_task(task)
        self.append_event(task.task_id, "execution_written", {"file": "execution_result.json", "status": execution.get("status")})

    def write_artifacts(self, task: ResearchTask, artifacts: list[dict[str, Any]]) -> None:
        task.artifacts = artifacts
        self._write_json(task.task_id, "artifacts.json", artifacts)
        self.save_task(task)
        self.append_event(task.task_id, "artifacts_written", {"file": "artifacts.json", "count": len(artifacts)})

    def write_validation(self, task: ResearchTask, validation: dict[str, Any]) -> None:
        task.validation = validation
        if task.status != "failed":
            task.status = "validated"
        self._write_json(task.task_id, "validation_report.json", validation)
        self.save_task(task)
        self.append_event(task.task_id, "validation_written", {"file": "validation_report.json", "safe_to_return": validation.get("safe_to_return")})

    def write_handoff(self, task: ResearchTask, handoff: str) -> None:
        task.handoff = handoff
        if task.status != "committed":
            task.status = "handed_off"
        self._write_text(task.task_id, "handoff.md", handoff)
        self.save_task(task)
        self.append_event(task.task_id, "handoff_written", {"file": "handoff.md"})

    def write_memory_commit(self, task: ResearchTask, memory_commit: dict[str, Any]) -> None:
        task.memory_commit = memory_commit
        task.status = "committed"
        self._write_json(task.task_id, "memory_commit.json", memory_commit)
        self.save_task(task)
        self.append_event(task.task_id, "memory_commit_written", {"file": "memory_commit.json"})

    def append_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.task_dir(task_id).mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": _json_safe(payload),
        }
        with (self.task_dir(task_id) / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _write_json(self, task_id: str, filename: str, payload: Any) -> None:
        self.task_dir(task_id).mkdir(parents=True, exist_ok=True)
        with (self.task_dir(task_id) / filename).open("w", encoding="utf-8") as handle:
            json.dump(_json_safe(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)

    def _read_json(self, task_id: str, filename: str) -> dict[str, Any]:
        with (self.task_dir(task_id) / filename).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_text(self, task_id: str, filename: str, content: str) -> None:
        self.task_dir(task_id).mkdir(parents=True, exist_ok=True)
        (self.task_dir(task_id) / filename).write_text(content, encoding="utf-8")
