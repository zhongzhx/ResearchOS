from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .brain_page import brain_root


VALID_STATUSES = {"draft", "pending_review", "active", "rejected", "deprecated", "needs_more_evidence"}


def registry_path() -> Path:
    path = brain_root() / "generated_skills" / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}", encoding="utf-8")
    return path


def _load() -> dict[str, Any]:
    return json.loads(registry_path().read_text(encoding="utf-8"))


def _save(registry: dict[str, Any]) -> None:
    registry_path().write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def register_pending_skill(skill_dir: str) -> dict[str, Any]:
    manifest = json.loads((Path(skill_dir) / "skill.json").read_text(encoding="utf-8"))
    name = manifest["name"]
    row = {**manifest, "skill_dir": str(Path(skill_dir).resolve()), "status": "pending_review", "updated_at": datetime.now().isoformat(timespec="seconds")}
    registry = _load()
    registry[name] = row
    _save(registry)
    return row


def get_skill_status(skill_name: str) -> dict[str, Any]:
    return _load().get(skill_name, {"name": skill_name, "status": "missing"})


def list_pending_skills() -> list[dict[str, Any]]:
    return [row for row in _load().values() if row.get("status") == "pending_review"]


def _set_status(skill_name: str, status: str, reason: str = "") -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError("unsupported skill status")
    registry = _load()
    if skill_name not in registry:
        raise KeyError("skill not found")
    if status == "active" and registry[skill_name].get("status") != "pending_review":
        raise ValueError("only pending_review skills can be activated")
    registry[skill_name]["status"] = status
    registry[skill_name]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if reason:
        key = "rejection_reason" if status == "rejected" else "status_reason"
        registry[skill_name][key] = reason
    _save(registry)
    return registry[skill_name]


def activate_skill(skill_name: str) -> dict[str, Any]:
    return _set_status(skill_name, "active")


def reject_skill(skill_name: str, reason: str) -> dict[str, Any]:
    return _set_status(skill_name, "rejected", reason)


def deprecate_skill(skill_name: str, reason: str) -> dict[str, Any]:
    return _set_status(skill_name, "deprecated", reason)
