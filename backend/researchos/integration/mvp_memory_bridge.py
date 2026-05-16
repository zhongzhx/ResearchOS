from __future__ import annotations

from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain
from backend.researchos.memory.memory_config import redact_payload


def promote_execution_result_for_new_feature(
    result: ExecutionResult,
    task_spec: TaskSpec,
    pipeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = promote_skill_outputs_to_brain(result, task_spec, pipeline or {})
    return redact_payload(decision)


def memory_commit_not_connected(reason: str) -> dict[str, Any]:
    return {
        "status": "not_connected",
        "promoted_pages": [],
        "promoted_claims": [],
        "promoted_datasets": [],
        "promoted_decisions": [],
        "failure_memory": [],
        "rejected_items": [{"target": "memory", "reason": reason}],
        "required_human_review": True,
    }
