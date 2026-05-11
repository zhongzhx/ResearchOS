from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.researchos.brain.skill_registry_review import get_skill_status
from backend.researchos.brain.skill_crystallizer import skills_root
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp, repo_root
from backend.researchos.skills.pipeline_registry import (
    load_legacy_skill_path_map,
    load_skill_catalog,
    list_pipelines,
    resolve_skill_path,
    route_query_to_pipeline,
)


def resolver_path() -> Path:
    return repo_root() / "skills" / "RESOLVER.md"


def load_skill_resolver() -> dict[str, Any]:
    path = resolver_path()
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)
    resolver: dict[str, Any] = {}
    for section in sections[1:]:
        lines = section.splitlines()
        intent = lines[0].strip()
        body = "\n".join(lines[1:])
        triggers = re.findall(r"(?m)^- (.+)$", body.split("Skill path:")[0])
        skill_path_match = re.search(r"Skill path:\s*\n?(.+)", body)
        fallback_match = re.search(r"Fallback:\s*\n?(.+)", body)
        resolver[intent] = {
            "triggers": [trigger.strip() for trigger in triggers],
            "skill_path": skill_path_match.group(1).strip() if skill_path_match else "",
            "fallback": fallback_match.group(1).strip() if fallback_match else "",
        }
    return resolver


def list_registered_skills() -> list[dict[str, Any]]:
    ros = import_research_os_mvp()
    try:
        return ros.list_skills(default_agent_root(), include_disabled=True)
    except Exception:
        return []


def check_unreachable_skills() -> list[dict[str, Any]]:
    resolver_text = str(load_skill_resolver())
    unreachable = []
    for skill in list_registered_skills():
        skill_id = skill.get("skill_id", "")
        name = skill.get("skill_name", "")
        if str(skill_id).startswith("core_") and skill_id not in resolver_text and name not in resolver_text:
            unreachable.append({"skill_id": skill_id, "skill_name": name})
    return unreachable


def check_duplicate_triggers() -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    duplicates = []
    for intent, config in load_skill_resolver().items():
        for trigger in config.get("triggers", []):
            key = trigger.lower()
            if key in seen:
                duplicates.append({"trigger": trigger, "first_intent": seen[key], "second_intent": intent})
            seen[key] = intent
    return duplicates


def _generated_active_routes() -> list[dict[str, Any]]:
    routes = []
    registry_root = skills_root() / "generated"
    if not registry_root.exists():
        return routes
    for manifest in registry_root.glob("*/skill.json"):
        import json

        row = json.loads(manifest.read_text(encoding="utf-8"))
        status = get_skill_status(row.get("name", "")).get("status") or row.get("status")
        if status == "active":
            routes.append({"skill_name": row["name"], "skill_path": str(manifest.parent / "SKILL.md"), "triggers": [row["name"], row.get("type", "")]})
    return routes


def route_intent_to_skill(user_query: str) -> dict[str, Any]:
    query = user_query.lower()
    for generated in _generated_active_routes():
        if any(trigger and trigger.lower() in query for trigger in generated.get("triggers", [])):
            return {**generated, "source": "generated_registry"}
    for intent, config in load_skill_resolver().items():
        if any(trigger.lower() in query for trigger in config.get("triggers", [])):
            pipeline = route_query_to_pipeline(user_query)
            return {"intent": intent, "skill_path": resolve_skill_path(config.get("skill_path", "")), "fallback": resolve_skill_path(config.get("fallback", "")), "pipeline": pipeline.get("pipeline_name"), "source": "resolver"}
    pipeline = route_query_to_pipeline(user_query)
    if pipeline.get("pipeline_name"):
        return {"intent": pipeline.get("intent"), "pipeline": pipeline.get("pipeline_name"), "execution_skills": pipeline.get("execution_skills"), "source": "pipeline_registry"}
    return {"intent": "unknown", "source": "resolver", "warning": "no route matched"}


def check_missing_canonical_paths() -> list[dict[str, Any]]:
    missing = []
    root = repo_root()
    for skill_id, row in load_skill_catalog().items():
        path = str(row.get("canonical_path") or "")
        if "{skill_name}" in path:
            continue
        if not (root / path).exists():
            missing.append({"skill_id": skill_id, "canonical_path": path})
    return missing


def check_legacy_map_errors() -> list[dict[str, Any]]:
    errors = []
    root = repo_root()
    for legacy, canonical in load_legacy_skill_path_map().items():
        if not legacy.endswith("/SKILL.md"):
            errors.append({"legacy_path": legacy, "error": "legacy path must point to SKILL.md"})
        if not (root / canonical).exists():
            errors.append({"legacy_path": legacy, "canonical_path": canonical, "error": "canonical path missing"})
    return errors


def _pipelines_missing(field: str) -> list[str]:
    return [pipeline["pipeline_name"] for pipeline in list_pipelines() if not pipeline.get(field)]


def run_resolver_smoke_tests() -> dict[str, Any]:
    resolver = load_skill_resolver()
    pipelines = list_pipelines()
    browser = next((item for item in pipelines if item.get("pipeline_name") == "browser_research_learning"), {})
    return {
        "ok": bool(resolver) and bool(pipelines) and not check_missing_canonical_paths() and not check_legacy_map_errors(),
        "resolver_entries": len(resolver),
        "pipeline_entries": len(pipelines),
        "duplicate_triggers": check_duplicate_triggers(),
        "unreachable_skills": check_unreachable_skills(),
        "missing_canonical_paths": check_missing_canonical_paths(),
        "legacy_map_errors": check_legacy_map_errors(),
        "pipelines_missing_planner_agent": _pipelines_missing("planner_agent"),
        "pipelines_missing_executor_agent": _pipelines_missing("executor_agent"),
        "pipelines_missing_execution_skills": _pipelines_missing("execution_skills"),
        "pipelines_missing_validation_rules": _pipelines_missing("validation_rules"),
        "pipelines_missing_promotion_targets": _pipelines_missing("promotion_targets"),
        "browser_pipeline_requires_authorization": bool(browser.get("requires_user_authorization")),
        "warnings": ["resolver file missing"] if not resolver else [],
    }
