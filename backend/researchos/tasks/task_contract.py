from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec


@dataclass
class TaskContract:
    required_skills: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    input_files: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    validation_rules: list[str] = field(default_factory=list)
    source_requirements: dict[str, Any] = field(default_factory=dict)
    safety_constraints: list[str] = field(default_factory=list)
    authorization_requirements: dict[str, Any] = field(default_factory=dict)
    memory_commit_policy: dict[str, Any] = field(default_factory=dict)
    handoff_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_contract_from_task_spec(task_spec: TaskSpec) -> dict[str, Any]:
    requires_authorization = "requires_user_authorization" in set(task_spec.safety_constraints or [])
    authorized = bool((task_spec.input_data or {}).get("authorized", not requires_authorization))
    contract = TaskContract(
        required_skills=list(task_spec.required_skills or []),
        allowed_tools=list(task_spec.allowed_tools or []),
        forbidden_tools=list(task_spec.forbidden_tools or []),
        input_files=list(task_spec.input_files or []),
        expected_outputs=list(task_spec.expected_outputs or []),
        validation_rules=list(task_spec.validation_rules or []),
        source_requirements=dict(task_spec.source_requirements or {}),
        safety_constraints=list(task_spec.safety_constraints or []),
        authorization_requirements={
            "requires_user_authorization": requires_authorization,
            "authorized": authorized,
            "blocked_if_missing": requires_authorization and not authorized,
        },
        memory_commit_policy={
            "direct_execution_memory_write_allowed": False,
            "requires_evidence_promotion": True,
            "write_failure_memory_on_failed_task": True,
            "reject_secret_leakage": True,
        },
        handoff_requirements=[
            "what_was_completed",
            "generated_files",
            "key_findings_and_confidence",
            "overinterpretation_limits",
            "unresolved_items",
            "next_steps",
            "reusable_workflow_candidates",
        ],
    )
    return contract.to_dict()
