from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.skills.skill_catalog_loader import get_skill_by_id, repo_root, resolve_skill_path, validate_skill_status
from backend.researchos.skills.skill_indexer import extract_skill_summary_from_md


BLOCKED_FILE_NAMES = {".env", ".env.local", ".env.production", "secrets.json", "credentials.json"}
RUNTIME_FILE_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".toml"}


def _safe_text(text: str) -> str:
    safe_lines = []
    for line in str(text or "").splitlines():
        lowered = line.casefold()
        if any(secret in lowered for secret in ["api_key", "apikey", "secret", "token=", "password", "bearer "]):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _skill_doc_path(skill_id: str) -> tuple[str, Path]:
    validation = validate_skill_status(skill_id, require_active=True)
    if validation.get("status") == "missing":
        raise KeyError(f"skill not found in catalog: {skill_id}")
    if not validation["valid"]:
        raise PermissionError("; ".join(validation["errors"]))
    row = get_skill_by_id(skill_id)
    canonical_id = str(row.get("skill_id") or skill_id)
    resolved = resolve_skill_path(skill_id)
    path = repo_root() / resolved
    if not path.exists():
        raise FileNotFoundError(f"skill doc not found: {resolved}")
    if path.name != "SKILL.md":
        raise ValueError(f"resolved skill path must point to SKILL.md: {resolved}")
    return canonical_id, path


def load_selected_skill_docs(required_skills: list[str]) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for skill in required_skills or []:
        skill_id, path = _skill_doc_path(skill)
        summary = extract_skill_summary_from_md(path)
        docs[skill_id] = {
            "skill_id": skill_id,
            "canonical_path": str(path).replace("\\", "/"),
            "sections": {
                "Purpose": _safe_text(summary.get("purpose", "")),
                "Inputs": _safe_text(summary.get("inputs", "")),
                "Outputs": _safe_text(summary.get("outputs", "")),
                "Procedure": _safe_text(summary.get("procedure", "")),
                "Validation": _safe_text(summary.get("validation", "")),
                "Safety Rules": _safe_text(summary.get("safety_rules", "")),
                "script path": ", ".join(summary.get("script_paths") or []),
            },
        }
    return docs


def _is_safe_runtime_file(path: Path) -> bool:
    lowered = path.name.casefold()
    if lowered in BLOCKED_FILE_NAMES or lowered.endswith(".log"):
        return False
    if any(part.casefold() in {"__pycache__", ".git", "logs", "skillruns"} for part in path.parts):
        return False
    return path.suffix.casefold() in RUNTIME_FILE_SUFFIXES


def load_skill_runtime_files(skill_id: str) -> list[str]:
    _, skill_doc = _skill_doc_path(skill_id)
    skill_dir = skill_doc.parent.resolve()
    files = []
    for path in skill_dir.rglob("*"):
        if not path.is_file() or not _is_safe_runtime_file(path):
            continue
        resolved = path.resolve()
        if skill_dir not in resolved.parents and resolved != skill_dir:
            continue
        files.append(str(resolved))
    return sorted(files)


def build_execution_skill_context(required_skills: list[str], max_tokens: int = 6000) -> str:
    docs = load_selected_skill_docs(required_skills)
    max_chars = max(int(max_tokens * 4), 1000)
    blocks = []
    for skill_id, doc in docs.items():
        lines = [f"## {skill_id}"]
        for section_name in ["Purpose", "Inputs", "Outputs", "Procedure", "Validation", "Safety Rules", "script path"]:
            content = str(doc.get("sections", {}).get(section_name) or "").strip()
            if content:
                lines.append(f"{section_name}:")
                lines.append(content)
        blocks.append("\n".join(lines))
    return _safe_text("\n\n".join(blocks))[:max_chars]
