from __future__ import annotations

from pathlib import Path
from typing import Any

from .research_task import ResearchTask


def _list_or_none(items: list[str], fallback: str = "None recorded.") -> str:
    clean = [str(item) for item in items if str(item)]
    if not clean:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean)


def _artifact_lines(artifacts: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in artifacts or []:
        path = str(item.get("path") or "")
        label = Path(path).name if path else str(item.get("artifact_id") or "artifact")
        lines.append(f"{label}: {path}")
    return lines


def compose_handoff(task: ResearchTask) -> str:
    execution = task.execution or {}
    validation = task.validation or {}
    memory_commit = task.memory_commit or {}
    artifacts = task.artifacts or []
    completed = execution.get("status") in {"success", "partial_success"}
    summary = str((execution.get("structured_outputs") or {}).get("summary") or execution.get("summary") or "")
    if not summary:
        summary = "Task execution completed." if completed else "Task execution did not complete successfully."
    confidence = "medium"
    if validation.get("safe_to_promote") and validation.get("safe_to_return"):
        confidence = "medium-high"
    if validation.get("required_human_review") or execution.get("status") == "failed":
        confidence = "low"
    unresolved = list(execution.get("unresolved_items") or [])
    unresolved.extend(str(error) for error in execution.get("errors") or [])
    rejected = memory_commit.get("rejected_items") or []
    if rejected:
        unresolved.extend(str(item.get("reason") or item) for item in rejected if isinstance(item, dict))
    promoted_pages = memory_commit.get("promoted_pages") or []
    reusable = []
    pipeline = (task.contract or {}).get("required_skills") or []
    if pipeline:
        reusable.append(f"Reuse required skills: {', '.join(str(item) for item in pipeline)}")
    return "\n".join(
        [
            f"# Research Task Handoff: {task.task_id}",
            "",
            "## 完成了什么",
            f"- {summary}",
            f"- Final task status: {task.status}",
            "",
            "## 生成了哪些文件",
            _list_or_none(_artifact_lines(artifacts)),
            "",
            "## 关键结论和置信度",
            f"- Confidence: {confidence}",
            f"- Safe to return: {bool(validation.get('safe_to_return'))}",
            f"- Safe to promote: {bool(validation.get('safe_to_promote'))}",
            "",
            "## 哪些内容不能过度解释",
            "- Treat outputs without source IDs, statistical evidence, or explicit validation as provisional.",
            "- Do not treat failure memory or low-confidence notes as confirmed scientific claims.",
            "",
            "## 未解决项",
            _list_or_none(unresolved),
            "",
            "## 下一步建议",
            "- Review validation issues before using outputs in a manuscript, dataset, or long-term claim.",
            "- Re-run the task with narrower scope if unresolved items remain.",
            "",
            "## 可复用流程候选",
            _list_or_none(reusable),
            "",
            "## 记忆提交",
            f"- Promoted pages: {len(promoted_pages)}",
            f"- Required human review: {bool(memory_commit.get('required_human_review'))}",
            "",
        ]
    )
