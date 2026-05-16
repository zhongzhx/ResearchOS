from __future__ import annotations

from typing import Any

from backend.researchos.product.feature_flows import (
    get_product_feature as _get_product_feature,
    list_product_features as _list_product_features,
    run_product_feature as _run_product_feature,
    run_product_feature_demo as _run_product_feature_demo,
)
from backend.researchos.settings.secret_store import redact_secrets_in_obj

from .mvp_task_bridge import persist_product_feature_lifecycle


def list_product_features() -> list[dict[str, Any]]:
    return redact_secrets_in_obj(_list_product_features())


def get_product_feature(feature_id: str) -> dict[str, Any]:
    return redact_secrets_in_obj(_get_product_feature(feature_id))


def run_product_feature(feature_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    result = _run_product_feature(feature_id, payload)
    if result.get("ok") and result.get("status") != "disabled":
        lifecycle = persist_product_feature_lifecycle(feature_id, payload, result)
        result.setdefault("task_id", lifecycle.get("research_task_id"))
        result["research_task_id"] = lifecycle.get("research_task_id")
        result["research_task_dir"] = lifecycle.get("research_task_dir")
    return redact_secrets_in_obj(result)


def run_product_feature_demo(feature_id: str, project_id: str = "demo_project") -> dict[str, Any]:
    return run_product_feature(feature_id, {"project_id": project_id, "mode": "demo"})
