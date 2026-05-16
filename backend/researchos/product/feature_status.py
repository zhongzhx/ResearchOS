from __future__ import annotations

from typing import Any

from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, load_skill_catalog

from .feature_contracts import ProductFeatureContract, FeatureStatus


def skill_statuses(skill_ids: list[str]) -> dict[str, str]:
    catalog = load_skill_catalog()
    return {skill_id: str((catalog.get(skill_id) or {}).get("status") or "missing") for skill_id in skill_ids}


def missing_or_inactive_skills(skill_ids: list[str]) -> list[str]:
    statuses = skill_statuses(skill_ids)
    return [skill_id for skill_id, status in statuses.items() if status not in {"active", "enabled"}]


def pipeline_connected(pipeline_name: str) -> bool:
    return get_pipeline_for_intent(pipeline_name).get("pipeline_name") == pipeline_name


def resolve_feature_status(contract: ProductFeatureContract) -> FeatureStatus:
    if not pipeline_connected(contract.preferred_pipeline):
        return "not_connected"
    missing = missing_or_inactive_skills(contract.required_skills)
    if missing:
        return "partial" if contract.demo_available else "not_connected"
    if contract.not_connected_dependencies:
        return "partial"
    return contract.status


def feature_status_detail(contract: ProductFeatureContract) -> dict[str, Any]:
    missing = missing_or_inactive_skills(contract.required_skills)
    return {
        "status": resolve_feature_status(contract),
        "pipeline_connected": pipeline_connected(contract.preferred_pipeline),
        "skill_statuses": skill_statuses(contract.required_skills),
        "missing_skills": missing,
        "not_connected_dependencies": list(contract.not_connected_dependencies),
    }
