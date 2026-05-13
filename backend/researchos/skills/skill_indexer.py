from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SECTION_ALIASES = {
    "input_schema": "inputs",
    "inputs": "inputs",
    "input": "inputs",
    "output_schema": "outputs",
    "outputs": "outputs",
    "output": "outputs",
    "procedure": "procedure",
    "workflow": "procedure",
    "run function": "procedure",
    "usage": "procedure",
    "validation": "validation",
    "validation rules": "validation",
    "system_instruction": "validation",
    "safety": "safety_rules",
    "safety rules": "safety_rules",
    "guardrails": "safety_rules",
}
SAFE_SECTION_KEYS = ["purpose", "inputs", "outputs", "procedure", "validation", "safety_rules"]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw = parts[1]
    frontmatter: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"')
    return frontmatter, parts[2]


def _extract_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "purpose"
    sections[current] = []
    for line in body.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            raw_name = heading.group(1).strip().casefold()
            current = SECTION_ALIASES.get(raw_name, raw_name.replace(" ", "_"))
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _truncate(text: str, max_chars: int = 1200) -> str:
    cleaned = "\n".join(line.rstrip() for line in str(text or "").splitlines()).strip()
    return cleaned[:max_chars]


def _script_paths(text: str) -> list[str]:
    matches = re.findall(r"(?i)(?:\.?[\\/])?scripts[\\/][A-Za-z0-9_.-]+", text)
    normalized = []
    for match in matches:
        value = match.replace("\\", "/").lstrip("./")
        if value not in normalized:
            normalized.append(value)
        basename = Path(value).name
        if basename not in normalized:
            normalized.append(basename)
    return normalized


def scan_skill_library(skill_root: str | Path) -> list[Path]:
    root = Path(skill_root)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("SKILL.md") if path.is_file() and ".git" not in path.parts)


def extract_skill_summary_from_md(skill_md_path: str | Path) -> dict[str, Any]:
    path = Path(skill_md_path)
    text = path.read_text(encoding="utf-8-sig")
    frontmatter, body = _parse_frontmatter(text)
    sections = _extract_sections(body)
    title_match = re.search(r"(?m)^#\s+(.+)$", body)
    skill_id = frontmatter.get("name") or path.parent.name
    description = frontmatter.get("description") or ""
    purpose_parts = [part for part in [description, title_match.group(1).strip() if title_match else "", sections.get("purpose", "")] if part]
    summary = {
        "skill_id": skill_id,
        "name": frontmatter.get("name") or skill_id,
        "title": title_match.group(1).strip() if title_match else skill_id,
        "description": description,
        "canonical_path": str(path).replace("\\", "/"),
        "purpose": _truncate("\n".join(purpose_parts)),
        "inputs": _truncate(sections.get("inputs", "")),
        "outputs": _truncate(sections.get("outputs", "")),
        "procedure": _truncate(sections.get("procedure", "")),
        "validation": _truncate(sections.get("validation", "")),
        "safety_rules": _truncate(sections.get("safety_rules", "")),
        "script_paths": _script_paths(text),
    }
    summary["summary_text"] = " ".join(str(summary.get(key) or "") for key in SAFE_SECTION_KEYS)
    return summary


def build_skill_index(skill_root: str | Path) -> dict[str, Any]:
    skills = [extract_skill_summary_from_md(path) for path in scan_skill_library(skill_root)]
    return {"version": "1.0", "skills": skills}


def write_skill_catalog(catalog: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
