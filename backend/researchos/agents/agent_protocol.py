from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


Priority = Literal["low", "normal", "high"]
ExecutionStatus = Literal["success", "partial_success", "failed"]
DecisionType = Literal["accept", "revise", "retry", "ask_user", "write_memory", "crystallize_skill", "stop"]
AgentName = Literal["brain_agent", "execution_agent"]
ContextScope = Literal["brain_full", "execution_minimal", "validation_only", "memory_write"]

DEFAULT_FORBIDDEN_CONTEXT_TYPES = [
    "full_agent_memory",
    "full_research_brain_repo",
    "full_project_history",
    "full_user_profile",
    "all_claims_evidence",
    "all_failure_records",
    "all_previous_skillruns",
    "brain_internal_planning",
    "system_prompts",
    "hidden_policies",
    "unrelated_project_files",
    "unrelated_rag_chunks",
    "compiled_context",
]

EXECUTION_ALLOWED_CONTEXT_FIELDS = {
    "task_brief",
    "project_short_summary",
    "relevant_sources",
    "relevant_chunks",
    "required_output_schema",
    "validation_rules",
    "known_constraints",
    "active_skill_instructions",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


@dataclass
class TaskSpec:
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    project_id: str | None = None
    user_query: str = ""
    intent: str = "research_advice"
    task_type: str = "general_research_task"
    priority: Priority = "normal"
    required_skills: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    input_files: list[str] = field(default_factory=list)
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_outputs: list[str] = field(default_factory=list)
    output_format: str = "json"
    source_requirements: dict[str, Any] = field(default_factory=dict)
    validation_rules: list[str] = field(default_factory=list)
    safety_constraints: list[str] = field(default_factory=list)
    context_package: dict[str, Any] = field(default_factory=dict)
    context_scope: str = "execution_minimal"
    max_context_tokens: int = 2000
    allowed_context_types: list[str] = field(default_factory=lambda: sorted(EXECUTION_ALLOWED_CONTEXT_FIELDS))
    forbidden_context_types: list[str] = field(default_factory=lambda: list(DEFAULT_FORBIDDEN_CONTEXT_TYPES))
    context_source_ids: list[str] = field(default_factory=list)
    context_redaction_report: dict[str, Any] = field(default_factory=dict)
    created_by: str = "brain_agent"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.created_by != "brain_agent":
            raise ValueError("TaskSpec.created_by must be brain_agent")
        if self.context_scope != "execution_minimal":
            raise ValueError("TaskSpec.context_scope must default to execution_minimal for execution tasks")
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        self.required_skills = [str(item) for item in _as_list(self.required_skills)]
        self.allowed_tools = [str(item) for item in _as_list(self.allowed_tools)]
        self.forbidden_tools = [str(item) for item in _as_list(self.forbidden_tools)]
        self.input_files = [str(item) for item in _as_list(self.input_files)]
        self.expected_outputs = [str(item) for item in _as_list(self.expected_outputs)]
        self.validation_rules = [str(item) for item in _as_list(self.validation_rules)]
        self.safety_constraints = [str(item) for item in _as_list(self.safety_constraints)]
        self.allowed_context_types = [str(item) for item in _as_list(self.allowed_context_types)]
        self.forbidden_context_types = [str(item) for item in _as_list(self.forbidden_context_types)]
        self.context_source_ids = [str(item) for item in _as_list(self.context_source_ids)]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ExecutionResult:
    task_id: str
    skillrun_id: str | None = None
    status: ExecutionStatus = "success"
    summary: str = ""
    output_files: list[str] = field(default_factory=list)
    structured_outputs: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)
    validation_report: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat()
        return data


@dataclass
class BrainDecision:
    decision_type: DecisionType
    reason: str
    next_task_spec: TaskSpec | None = None
    memory_actions: list[dict[str, Any]] = field(default_factory=list)
    skill_actions: list[dict[str, Any]] = field(default_factory=list)
    user_facing_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.next_task_spec:
            data["next_task_spec"] = self.next_task_spec.to_dict()
        return data


@dataclass
class ContextEnvelope:
    agent_name: AgentName
    scope: ContextScope
    project_id: str | None = None
    user_query: str = ""
    allowed_context_types: list[str] = field(default_factory=list)
    forbidden_context_types: list[str] = field(default_factory=lambda: list(DEFAULT_FORBIDDEN_CONTEXT_TYPES))
    included_sources: list[dict[str, Any]] = field(default_factory=list)
    excluded_sources: list[dict[str, Any]] = field(default_factory=list)
    context_package: dict[str, Any] = field(default_factory=dict)
    max_context_tokens: int = 2000
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def build_brain_context_envelope(user_query: str, project_id: str | None, intent: str) -> ContextEnvelope:
    return ContextEnvelope(
        agent_name="brain_agent",
        scope="brain_full",
        project_id=project_id,
        user_query=user_query,
        allowed_context_types=[
            "project_summary",
            "project_memory",
            "rag_chunks",
            "references",
            "claims",
            "tasks",
            "skill_runs",
        ],
        context_package={"intent": intent, "user_query": user_query},
        max_context_tokens=4000,
    )


def redact_forbidden_context(context_package: dict[str, Any], forbidden_context_types: list[str]) -> dict[str, Any]:
    forbidden = set(forbidden_context_types or [])
    redacted: list[str] = []
    cleaned: dict[str, Any] = {}
    for key, value in (context_package or {}).items():
        if key in forbidden:
            redacted.append(key)
            continue
        cleaned[key] = value
    return {"context_package": cleaned, "redacted": redacted}


def _token_limited_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    return text[:max_chars]


def sanitize_context_for_execution(compiled_context: dict[str, Any], task_spec: TaskSpec) -> dict[str, Any]:
    compiled = compiled_context or {}
    max_chars = max(int(task_spec.max_context_tokens * 4), 500)
    relevant_chunks = compiled.get("relevant_chunks") or compiled.get("context_items") or compiled.get("chunks") or []
    relevant_sources = compiled.get("sources") or compiled.get("references") or []
    package = {
        "task_brief": _token_limited_text(task_spec.user_query or compiled.get("user_query"), 800),
        "project_short_summary": _token_limited_text(compiled.get("project_summary") or compiled.get("project_state_summary"), 1200),
        "relevant_sources": relevant_sources[:10] if isinstance(relevant_sources, list) else [],
        "relevant_chunks": relevant_chunks[:10] if isinstance(relevant_chunks, list) else [],
        "required_output_schema": task_spec.input_data.get("output_schema", {}) if isinstance(task_spec.input_data, dict) else {},
        "validation_rules": list(task_spec.validation_rules),
        "known_constraints": list(task_spec.safety_constraints),
        "active_skill_instructions": compiled.get("active_skill_instructions", [])[:5] if isinstance(compiled.get("active_skill_instructions", []), list) else [],
    }
    redacted = redact_forbidden_context(package, task_spec.forbidden_context_types)
    return redacted["context_package"]


def build_execution_context_package(task_spec: TaskSpec, compiled_context: dict[str, Any]) -> dict[str, Any]:
    package = sanitize_context_for_execution(compiled_context, task_spec)
    return {key: value for key, value in package.items() if key in EXECUTION_ALLOWED_CONTEXT_FIELDS}


def validate_context_isolation(task_spec: TaskSpec) -> dict[str, Any]:
    context = task_spec.context_package or {}
    forbidden = set(task_spec.forbidden_context_types or DEFAULT_FORBIDDEN_CONTEXT_TYPES)
    forbidden_found = sorted(key for key in context if key in forbidden)
    unknown_fields = sorted(key for key in context if key not in EXECUTION_ALLOWED_CONTEXT_FIELDS)
    oversized = len(str(context)) > max(task_spec.max_context_tokens * 8, 1000)
    valid = not forbidden_found and not unknown_fields and not oversized and task_spec.context_scope == "execution_minimal"
    errors: list[str] = []
    if forbidden_found:
        errors.append(f"Forbidden context types present: {', '.join(forbidden_found)}")
    if unknown_fields:
        errors.append(f"Execution context contains unsupported fields: {', '.join(unknown_fields)}")
    if oversized:
        errors.append("Execution context exceeds max_context_tokens budget")
    if task_spec.context_scope != "execution_minimal":
        errors.append("Execution Agent requires context_scope=execution_minimal")
    return {
        "valid": valid,
        "forbidden_found": forbidden_found,
        "unsupported_fields": unknown_fields,
        "oversized": oversized,
        "errors": errors,
        "max_context_tokens": task_spec.max_context_tokens,
    }


def build_execution_context_package_from_compiled(task_spec: TaskSpec, compiled_context: dict[str, Any]) -> dict[str, Any]:
    return build_execution_context_package(task_spec, compiled_context)
