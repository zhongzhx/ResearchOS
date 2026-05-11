from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .brain_page import append_timeline_event, brain_root, read_brain_page, update_compiled_truth


def evidence_path() -> Path:
    path = brain_root() / "evidence_items.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def claim_links_path() -> Path:
    path = brain_root() / "claim_evidence_links.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def create_evidence_item(source_id: str, evidence_type: str, claim_text: str, confidence: str, metadata: dict[str, Any]) -> dict[str, Any]:
    evidence = {"evidence_id": f"ev_{abs(hash((source_id, claim_text))) & 0xffffffff:x}", "source_id": source_id, "evidence_type": evidence_type, "claim_text": claim_text, "confidence": confidence, "metadata": metadata or {}}
    _append_jsonl(evidence_path(), evidence)
    return evidence


def link_evidence_to_claim(evidence_id: str, claim_slug: str) -> dict[str, Any]:
    link = {"evidence_id": evidence_id, "claim_slug": claim_slug}
    _append_jsonl(claim_links_path(), link)
    append_timeline_event(claim_slug, {"evidence_type": "evidence_link", "confidence": "medium", "source_ids": [evidence_id], "event": f"Linked evidence {evidence_id}", "impact": "Evidence linked to claim."})
    return link


def mark_claim_as_hypothesis(claim_slug: str, reason: str) -> dict[str, Any]:
    page = read_brain_page(claim_slug)
    truth = page["compiled_truth"]
    if "hypothesis" not in truth.lower() and "假设" not in truth:
        truth = f"Hypothesis: {truth}"
    return update_compiled_truth(claim_slug, truth, reason, page["frontmatter"].get("source_ids") or [], "low")


def promote_claim_confidence(claim_slug: str, reason: str, source_ids: list[str]) -> dict[str, Any]:
    if not source_ids:
        raise ValueError("source_ids are required to promote claim confidence")
    page = read_brain_page(claim_slug)
    return update_compiled_truth(claim_slug, page["compiled_truth"], reason, source_ids, "high")


def downgrade_claim_confidence(claim_slug: str, reason: str, source_ids: list[str]) -> dict[str, Any]:
    page = read_brain_page(claim_slug)
    return update_compiled_truth(claim_slug, page["compiled_truth"], reason, source_ids, "low")


def find_claims_without_evidence(project_id: str) -> list[dict[str, Any]]:
    links = _read_jsonl(claim_links_path())
    linked = {row["claim_slug"] for row in links}
    claims = []
    for path in (brain_root() / "claims").glob("*.md"):
        page = read_brain_page(path.stem)
        if page["frontmatter"].get("project_id") == project_id and not page["frontmatter"].get("source_ids") and path.stem not in linked:
            claims.append({"slug": path.stem, "title": page["frontmatter"].get("title")})
    return claims
