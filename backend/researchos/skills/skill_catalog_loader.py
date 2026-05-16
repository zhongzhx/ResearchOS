from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ACTIVE_STATUSES = {"active", "enabled"}
FORBIDDEN_AUTO_STATUSES = {"pending_review", "draft", "rejected", "deprecated", "needs_more_evidence", "disabled", "broken", "duplicate"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def skill_library_root() -> Path:
    return repo_root() / "skills" / "researchos_skill_library"


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_path(value: str | Path) -> str:
    return str(value or "").replace("\\", "/").strip()


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
    return {_normalize_path(key): _normalize_path(value) for key, value in data.items()}


def get_skill_by_id(skill_id: str) -> dict[str, Any]:
    catalog = load_skill_catalog()
    key = str(skill_id or "").strip()
    if key in catalog:
        return catalog[key]
    resolved = resolve_skill_path(key)
    for row in catalog.values():
        if _normalize_path(row.get("canonical_path", "")) == resolved:
            return row
    raise KeyError(f"skill not found: {skill_id}")


def resolve_skill_path(skill_id_or_legacy_path: str) -> str:
    value = _normalize_path(skill_id_or_legacy_path)
    legacy = load_legacy_skill_path_map()
    if value in legacy:
        return legacy[value]

    catalog = load_skill_catalog()
    if value in catalog:
        return _normalize_path(catalog[value].get("canonical_path") or "")

    for row in catalog.values():
        canonical = _normalize_path(row.get("canonical_path") or "")
        if value == canonical:
            return canonical
        if value in {_normalize_path(path) for path in row.get("legacy_paths", [])}:
            return canonical

    if value.endswith("/SKILL.md"):
        return value
    return _normalize_path(catalog.get(value, {}).get("canonical_path") or value)


def list_active_skills() -> list[dict[str, Any]]:
    return [row for row in load_skill_catalog().values() if str(row.get("status") or "") in ACTIVE_STATUSES]


def list_pending_skills() -> list[dict[str, Any]]:
    return [row for row in load_skill_catalog().values() if str(row.get("status") or "") in FORBIDDEN_AUTO_STATUSES]


def validate_skill_status(skill_id: str, require_active: bool = True) -> dict[str, Any]:
    try:
        row = get_skill_by_id(skill_id)
    except KeyError as exc:
        return {"valid": False, "skill_id": skill_id, "status": "missing", "errors": [str(exc)]}

    status = str(row.get("status") or "").strip()
    errors: list[str] = []
    if status in FORBIDDEN_AUTO_STATUSES:
        errors.append(f"skill is not active: {row.get('skill_id')}")
    elif require_active and status not in ACTIVE_STATUSES:
        errors.append(f"skill status is not active: {row.get('skill_id')} status={status or 'unknown'}")

    return {
        "valid": not errors,
        "skill_id": row.get("skill_id"),
        "status": status,
        "errors": errors,
        "requires_user_authorization": bool(row.get("requires_user_authorization")),
        "allowed_auto_call": bool(row.get("allowed_auto_call")),
        "canonical_path": _normalize_path(row.get("canonical_path") or ""),
    }
