from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PAGE_DIRS = {
    "project": "projects",
    "experiment": "experiments",
    "paper": "papers",
    "dataset": "datasets",
    "protocol": "protocols",
    "claim": "claims",
    "compound": "compounds",
    "sample": "samples",
    "organism": "organisms",
    "method": "methods",
    "failure": "failures",
    "decision": "decisions",
    "report": "reports",
    "workflow": "workflows",
    "generated_skill": "generated_skills",
}
HIDDEN_PATTERNS = ["system prompt", "hidden polic", "internal tool instruction", "developer message", "prompt_router"]


def brain_root() -> Path:
    agent_data_dir = os.environ.get("RESEARCHOS_AGENT_DATA_DIR")
    return Path(os.environ.get("RESEARCH_BRAIN_ROOT") or (Path(agent_data_dir) / "research_brain" if agent_data_dir else Path.cwd() / "data" / "research_brain"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", str(value or "").strip(), flags=re.UNICODE).strip("-").lower()
    return text or f"page-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def page_dir(page_type: str) -> Path:
    directory = PAGE_DIRS.get(page_type, f"{page_type}s")
    path = brain_root() / directory
    path.mkdir(parents=True, exist_ok=True)
    return path


def page_path(page_type: str, slug: str) -> Path:
    return page_dir(page_type) / f"{slugify(slug)}.md"


def find_page_path(slug: str) -> Path:
    normalized = f"{slugify(slug)}.md"
    for path in brain_root().rglob(normalized):
        if path.is_file():
            return path
    raise FileNotFoundError(f"brain page not found: {slug}")


def _safe_text(text: Any) -> str:
    value = str(text or "")
    lowered = value.lower()
    if any(pattern in lowered for pattern in HIDDEN_PATTERNS):
        raise ValueError("brain page content contains hidden/internal prompt text")
    return value.strip()


def _frontmatter_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _parse_frontmatter_value(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def render_timeline_entry(event: dict[str, Any]) -> str:
    timestamp = str(event.get("timestamp") or now_iso())
    evidence_type = str(event.get("evidence_type") or "evidence")
    confidence = str(event.get("confidence") or "low")
    source_ids = event.get("source_ids") or []
    source_lines = "\n".join(f"- {source_id}" for source_id in source_ids) or "- none"
    return "\n".join(
        [
            f"## {timestamp} | {evidence_type} | {confidence}",
            "",
            "Source IDs:",
            source_lines,
            "",
            "Event:",
            str(event.get("event") or "").strip(),
            "",
            "Impact:",
            str(event.get("impact") or "").strip(),
            "",
        ]
    )


def parse_timeline(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    parts = re.split(r"(?m)^## ", text.strip())
    for part in parts:
        if not part.strip():
            continue
        lines = part.splitlines()
        header = lines[0].strip()
        header_parts = [item.strip() for item in header.split("|")]
        body = "\n".join(lines[1:])
        sources_match = re.search(r"Source IDs:\s*(.*?)(?:\n\nEvent:|\Z)", body, flags=re.S)
        event_match = re.search(r"Event:\s*(.*?)(?:\n\nImpact:|\Z)", body, flags=re.S)
        impact_match = re.search(r"Impact:\s*(.*)", body, flags=re.S)
        source_ids = []
        if sources_match:
            for line in sources_match.group(1).splitlines():
                value = line.strip().lstrip("-").strip()
                if value and value != "none":
                    source_ids.append(value)
        entries.append(
            {
                "timestamp": header_parts[0] if header_parts else "",
                "evidence_type": header_parts[1] if len(header_parts) > 1 else "",
                "confidence": header_parts[2] if len(header_parts) > 2 else "",
                "source_ids": source_ids,
                "event": event_match.group(1).strip() if event_match else "",
                "impact": impact_match.group(1).strip() if impact_match else "",
            }
        )
    return entries


def render_brain_page(page_obj: dict[str, Any]) -> str:
    frontmatter = dict(page_obj.get("frontmatter") or {})
    frontmatter["updated_at"] = frontmatter.get("updated_at") or now_iso()
    lines = ["---"]
    for key in [
        "type",
        "title",
        "slug",
        "project_id",
        "status",
        "confidence",
        "created_at",
        "updated_at",
        "source_ids",
        "tags",
    ]:
        lines.append(f"{key}: {_frontmatter_value(frontmatter.get(key, [] if key in {'source_ids', 'tags'} else ''))}")
    lines.extend(["---", "", "# Compiled Truth", "", _safe_text(page_obj.get("compiled_truth")), "", "# Evidence Timeline", ""])
    for event in page_obj.get("timeline_entries") or []:
        lines.append(render_timeline_entry(event))
    return "\n".join(lines).rstrip() + "\n"


def parse_brain_page(markdown_text: str) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", markdown_text, flags=re.S)
    if not match:
        raise ValueError("brain page missing frontmatter")
    fm_text, body = match.groups()
    frontmatter: dict[str, Any] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = _parse_frontmatter_value(value)
    compiled_match = re.search(r"# Compiled Truth\s*(.*?)(?:\n# Evidence Timeline|\Z)", body, flags=re.S)
    timeline_match = re.search(r"# Evidence Timeline\s*(.*)$", body, flags=re.S)
    return {
        "frontmatter": frontmatter,
        "compiled_truth": (compiled_match.group(1).strip() if compiled_match else ""),
        "timeline_entries": parse_timeline(timeline_match.group(1) if timeline_match else ""),
    }


def create_brain_page(page_type: str, slug: str, frontmatter: dict[str, Any], compiled_truth: str, timeline_entries: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = now_iso()
    normalized_slug = slugify(slug)
    fm = {
        "type": page_type,
        "title": frontmatter.get("title") or normalized_slug,
        "slug": normalized_slug,
        "project_id": frontmatter.get("project_id") or "",
        "status": frontmatter.get("status") or "draft",
        "confidence": frontmatter.get("confidence") or "low",
        "created_at": frontmatter.get("created_at") or timestamp,
        "updated_at": timestamp,
        "source_ids": frontmatter.get("source_ids") or [],
        "tags": frontmatter.get("tags") or [],
    }
    page = {"frontmatter": fm, "compiled_truth": _safe_text(compiled_truth), "timeline_entries": timeline_entries or []}
    path = page_path(page_type, normalized_slug)
    path.write_text(render_brain_page(page), encoding="utf-8")
    return {**page, "path": str(path)}


def read_brain_page(slug: str) -> dict[str, Any]:
    path = find_page_path(slug)
    page = parse_brain_page(path.read_text(encoding="utf-8"))
    page["path"] = str(path)
    return page


def update_compiled_truth(slug: str, new_truth: str, reason: str, source_ids: list[str], confidence: str) -> dict[str, Any]:
    path = find_page_path(slug)
    page = parse_brain_page(path.read_text(encoding="utf-8"))
    page["compiled_truth"] = _safe_text(new_truth)
    page["frontmatter"]["updated_at"] = now_iso()
    page["frontmatter"]["confidence"] = confidence or page["frontmatter"].get("confidence", "low")
    existing_sources = list(page["frontmatter"].get("source_ids") or [])
    page["frontmatter"]["source_ids"] = sorted(set(existing_sources + list(source_ids or [])))
    page["timeline_entries"].append({"evidence_type": "compiled_truth_update", "confidence": confidence, "source_ids": source_ids or [], "event": reason, "impact": "Compiled Truth updated."})
    path.write_text(render_brain_page(page), encoding="utf-8")
    page["path"] = str(path)
    return page


def append_timeline_event(slug: str, event: dict[str, Any]) -> dict[str, Any]:
    path = find_page_path(slug)
    page = parse_brain_page(path.read_text(encoding="utf-8"))
    event = dict(event)
    event.setdefault("timestamp", now_iso())
    page["timeline_entries"].append(event)
    page["frontmatter"]["updated_at"] = now_iso()
    source_ids = list(page["frontmatter"].get("source_ids") or [])
    source_ids.extend(event.get("source_ids") or [])
    page["frontmatter"]["source_ids"] = sorted(set(source_ids))
    path.write_text(render_brain_page(page), encoding="utf-8")
    page["path"] = str(path)
    return page


def archive_brain_page(slug: str, reason: str) -> dict[str, Any]:
    page = append_timeline_event(slug, {"evidence_type": "archive", "confidence": "medium", "source_ids": [], "event": reason, "impact": "Page archived."})
    page["frontmatter"]["status"] = "archived"
    page["frontmatter"]["updated_at"] = now_iso()
    Path(page["path"]).write_text(render_brain_page(page), encoding="utf-8")
    return page
