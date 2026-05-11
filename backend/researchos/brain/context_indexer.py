from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .brain_page import brain_root, read_brain_page


def _index_path(project_id: str) -> Path:
    path = brain_root() / "projects" / project_id / "project_context_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _pages(project_id: str) -> list[dict[str, Any]]:
    pages = []
    for path in brain_root().rglob("*.md"):
        page = read_brain_page(path.stem)
        if page["frontmatter"].get("project_id") == project_id:
            pages.append(page)
    return pages


def build_project_context_index(project_id: str) -> dict[str, Any]:
    pages = _pages(project_id)
    counts = {"papers": 0, "experiments": 0, "datasets": 0, "protocols": 0, "claims": 0, "skills": 0, "failures": 0}
    active_claims = []
    hypotheses = []
    failures = []
    for page in pages:
        page_type = page["frontmatter"].get("type")
        if page_type == "paper":
            counts["papers"] += 1
        elif page_type == "experiment":
            counts["experiments"] += 1
        elif page_type == "dataset":
            counts["datasets"] += 1
        elif page_type == "protocol":
            counts["protocols"] += 1
        elif page_type == "claim":
            counts["claims"] += 1
            item = {"slug": page["frontmatter"]["slug"], "title": page["frontmatter"].get("title"), "confidence": page["frontmatter"].get("confidence"), "source_ids": page["frontmatter"].get("source_ids") or []}
            if "hypothesis" in page["compiled_truth"].lower():
                hypotheses.append(item)
            else:
                active_claims.append(item)
        elif page_type == "generated_skill":
            counts["skills"] += 1
        elif page_type == "failure":
            counts["failures"] += 1
            failures.append({"slug": page["frontmatter"]["slug"], "title": page["frontmatter"].get("title")})
    index = {
        "project_id": project_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "available_assets": counts,
        "active_claims": active_claims,
        "hypotheses": hypotheses,
        "key_experiments": [{"slug": p["frontmatter"]["slug"], "title": p["frontmatter"].get("title")} for p in pages if p["frontmatter"].get("type") == "experiment"][:20],
        "key_datasets": [{"slug": p["frontmatter"]["slug"], "title": p["frontmatter"].get("title")} for p in pages if p["frontmatter"].get("type") == "dataset"][:20],
        "active_skills": [],
        "pending_skills": [],
        "recent_skillruns": [],
        "unresolved_failures": failures,
        "recommended_context_for_intents": {
            "experiment_design": active_claims[:5],
            "literature_review": active_claims[:5] + hypotheses[:5],
            "data_analysis": failures[:5],
            "mechanism_reasoning": active_claims[:5] + hypotheses[:5],
            "sop_generation": [],
            "report_writing": active_claims[:5] + failures[:5],
        },
    }
    _index_path(project_id).write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return index


def update_project_context_index(project_id: str) -> dict[str, Any]:
    return build_project_context_index(project_id)


def load_project_context_index(project_id: str) -> dict[str, Any]:
    path = _index_path(project_id)
    if not path.exists():
        return build_project_context_index(project_id)
    return json.loads(path.read_text(encoding="utf-8"))


def select_high_value_context(project_id: str, intent: str, user_query: str) -> dict[str, Any]:
    index = load_project_context_index(project_id)
    mapped = index.get("recommended_context_for_intents", {}).get(intent) or []
    if not mapped and "mechanism" in user_query.lower():
        mapped = index.get("recommended_context_for_intents", {}).get("mechanism_reasoning") or []
    return {"project_id": project_id, "intent": intent, "selected": mapped[:10], "index_updated_at": index.get("updated_at")}
