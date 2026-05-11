from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FORBIDDEN_AUTO_STATUSES = {"pending_review", "draft", "rejected", "deprecated", "needs_more_evidence"}


@dataclass
class ResearchPipeline:
    pipeline_name: str
    intent: str
    trigger_phrases: list[str] = field(default_factory=list)
    planner_agent: str = "brain_agent"
    executor_agent: str = "execution_agent"
    execution_skills: list[str] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    validation_rules: list[str] = field(default_factory=list)
    promotion_targets: list[str] = field(default_factory=list)
    auto_crystallize_candidate: bool = True
    requires_user_authorization: bool = False
    risk_level: str = "medium"
    allowed_tools: list[str] = field(default_factory=list)
    brain_responsibilities: list[str] = field(default_factory=list)
    execution_responsibilities: list[str] = field(default_factory=list)
    control_skills: dict[str, list[str]] = field(default_factory=lambda: {
        "pre_dispatch": ["skill-router-orchestrator", "context-compiler-maintenance"],
        "post_execution": ["skill-output-validator", "evidence-promotion"],
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "intent": self.intent,
            "trigger_phrases": self.trigger_phrases,
            "planner_agent": self.planner_agent,
            "executor_agent": self.executor_agent,
            "execution_skills": self.execution_skills,
            "required_inputs": self.required_inputs,
            "expected_outputs": self.expected_outputs,
            "validation_rules": self.validation_rules,
            "promotion_targets": self.promotion_targets,
            "auto_crystallize_candidate": self.auto_crystallize_candidate,
            "requires_user_authorization": self.requires_user_authorization,
            "risk_level": self.risk_level,
            "allowed_tools": self.allowed_tools,
            "brain_responsibilities": self.brain_responsibilities,
            "execution_responsibilities": self.execution_responsibilities,
            "control_skills": self.control_skills,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def skill_library_root() -> Path:
    return repo_root() / "skills" / "researchos_skill_library"


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_skill_catalog() -> dict[str, dict[str, Any]]:
    data = _json(skill_library_root() / "skill_catalog.json")
    catalog: dict[str, dict[str, Any]] = {}
    for item in data.get("skills", []):
        skill_id = str(item.get("skill_id") or "")
        if skill_id:
            catalog[skill_id] = item
    return catalog


def load_legacy_skill_path_map() -> dict[str, str]:
    data = _json(skill_library_root() / "legacy_skill_path_map.json")
    return {str(key).replace("\\", "/"): str(value).replace("\\", "/") for key, value in data.items()}


def resolve_skill_path(path_or_skill_id: str) -> str:
    value = str(path_or_skill_id or "").replace("\\", "/").strip()
    legacy = load_legacy_skill_path_map()
    if value in legacy:
        return legacy[value]
    catalog = load_skill_catalog()
    if value in catalog:
        return str(catalog[value].get("canonical_path") or "")
    if value.endswith("/SKILL.md"):
        return value
    return str(catalog.get(value, {}).get("canonical_path") or value)


def load_pipeline_registry() -> dict[str, dict[str, Any]]:
    data = _json(skill_library_root() / "pipeline_registry.json")
    pipelines: dict[str, dict[str, Any]] = {}
    for raw in data.get("pipelines", []):
        pipeline = ResearchPipeline(**raw).to_dict()
        pipelines[pipeline["pipeline_name"]] = pipeline
        pipelines[pipeline["intent"]] = pipeline
    return pipelines


def list_pipelines() -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows = []
    for pipeline in load_pipeline_registry().values():
        name = pipeline["pipeline_name"]
        if name not in seen:
            rows.append(pipeline)
            seen.add(name)
    return rows


def get_pipeline_for_intent(intent: str) -> dict[str, Any]:
    registry = load_pipeline_registry()
    if intent in registry:
        return registry[intent]
    return {
        "pipeline_name": "generic_skill_task",
        "intent": intent or "unknown",
        "trigger_phrases": [],
        "planner_agent": "brain_agent",
        "executor_agent": "execution_agent",
        "execution_skills": [],
        "required_inputs": [],
        "expected_outputs": ["structured_output"],
        "validation_rules": ["Only use supplied execution context."],
        "promotion_targets": [],
        "auto_crystallize_candidate": False,
        "requires_user_authorization": False,
        "risk_level": "low",
        "allowed_tools": [],
        "control_skills": {
            "pre_dispatch": ["skill-router-orchestrator", "context-compiler-maintenance"],
            "post_execution": ["skill-output-validator", "evidence-promotion"],
        },
    }


def route_query_to_pipeline(user_query: str) -> dict[str, Any]:
    query = str(user_query or "").lower()
    direct_routes = [
        ("nature_figure_generation", ["nature figure", "publication figure", "scientific figure", "manuscript figure", "publication plot", "\u79d1\u7814\u4f5c\u56fe", "\u8bba\u6587\u56fe", "\u9ad8\u6c34\u5e73\u671f\u520a\u56fe\u7247"]),
        ("nature_citation_support", ["nature citation", "cns citation", "supporting references", "text citation", "endnote", "ris", "zotero", "\u8865\u5f15\u7528", "\u652f\u6491\u6587\u732e"]),
        ("nature_data_availability", ["data availability", "fair metadata", "repository plan", "\u6570\u636e\u53ef\u7528\u6027", "\u6570\u636e\u5171\u4eab", "\u6570\u636e\u4ed3\u5e93"]),
        ("nature_reviewer_response", ["response to reviewers", "rebuttal letter", "major revision", "minor revision", "reviewer comments", "\u5ba1\u7a3f\u610f\u89c1\u56de\u590d", "\u8fd4\u4fee\u56de\u590d"]),
        ("nature_paper_to_ppt", ["paper ppt", "paper to slides", "paper presentation", "journal club", "pptx", "\u6587\u732e\u6c47\u62a5", "\u7ec4\u4f1appt", "\u8bba\u6587ppt"]),
        ("nature_academic_polishing", ["nature style", "academic polishing", "polish manuscript", "polish abstract", "\u6da6\u8272", "\u8bba\u6587\u6da6\u8272", "\u5b66\u672f\u82f1\u8bed"]),
        ("literature_harvest", ["\u4e0b\u8f7d", "\u6587\u732e", "\u8bba\u6587", "literature", "paper", "keyword harvest"]),
        ("browser_research_learning", ["\u6d4f\u89c8\u5668", "\u7f51\u9875", "browser"]),
        ("protocol_to_sop", ["sop", "methods \u8f6c", "protocol to"]),
        ("data_analysis_to_narrative", ["csv", "\u7ed3\u679c\u6bb5", "data analysis"]),
        ("writing_review", ["\u5ba1\u7a3f", "peer review"]),
        ("failure_recovery", ["\u5931\u8d25", "failure"]),
        ("research_route_planning", ["\u89c4\u5212", "\u8def\u7ebf", "research route"]),
    ]
    for intent, triggers in direct_routes:
        if any(term.lower() in query for term in triggers):
            return get_pipeline_for_intent(intent)
    best: dict[str, Any] | None = None
    best_score = 0
    for pipeline in list_pipelines():
        score = 0
        for trigger in pipeline.get("trigger_phrases", []):
            trigger_l = str(trigger).lower()
            if trigger_l and trigger_l in query:
                score += max(2, len(trigger_l.split()))
        if score > best_score:
            best = pipeline
            best_score = score
    return best or get_pipeline_for_intent("generic_skill_task")

def validate_pipeline_permissions(pipeline: dict[str, Any]) -> dict[str, Any]:
    catalog = load_skill_catalog()
    errors = []
    for skill_id in pipeline.get("execution_skills", []):
        row = catalog.get(skill_id)
        if not row:
            errors.append(f"missing skill in catalog: {skill_id}")
            continue
        if row.get("status") in FORBIDDEN_AUTO_STATUSES:
            errors.append(f"skill is not active: {skill_id}")
    requires_auth = bool(pipeline.get("requires_user_authorization"))
    return {
        "valid": not errors,
        "errors": errors,
        "auto_executable_without_user_authorization": not requires_auth and not errors,
        "requires_user_authorization": requires_auth,
    }
