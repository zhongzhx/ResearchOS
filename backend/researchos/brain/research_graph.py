from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .brain_page import brain_root, read_brain_page

RELATION_TYPES = {"supports", "contradicts", "measured_by", "tested_in", "uses_model", "uses_assay", "derived_from", "contains_compound", "has_marker", "targets_pathway", "generated_by", "compared_with", "cites", "replicates", "fails_because", "depends_on", "belongs_to_project", "produces_dataset", "validates_claim", "requires_protocol", "mentions", "similar_to"}


def graph_path() -> Path:
    path = brain_root() / "research_graph_edges.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_edges() -> list[dict[str, Any]]:
    path = graph_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_edges(edges: list[dict[str, Any]]) -> None:
    graph_path().write_text("\n".join(json.dumps(edge, ensure_ascii=False, sort_keys=True) for edge in edges) + ("\n" if edges else ""), encoding="utf-8")


def extract_research_links_from_page(slug: str) -> list[dict[str, Any]]:
    page = read_brain_page(slug)
    text = page["compiled_truth"]
    edges = []
    for source_id in page["frontmatter"].get("source_ids") or []:
        edges.append({"source_slug": slug, "target_slug": str(source_id), "relation_type": "derived_from", "confidence": page["frontmatter"].get("confidence", "medium"), "extraction_method": "frontmatter_source_ids", "project_id": page["frontmatter"].get("project_id", "")})
    for relation in sorted(RELATION_TYPES):
        for match in re.finditer(rf"{relation}\s+([A-Za-z0-9_.:-]+)", text, flags=re.I):
            edges.append({"source_slug": slug, "target_slug": match.group(1), "relation_type": relation, "confidence": "medium", "extraction_method": "deterministic_text_rule", "project_id": page["frontmatter"].get("project_id", "")})
    return edges


def upsert_research_edge(edge: dict[str, Any]) -> dict[str, Any]:
    if edge.get("relation_type") not in RELATION_TYPES:
        raise ValueError("unsupported relation_type")
    edge = {**edge, "confidence": edge.get("confidence") or "medium", "extraction_method": edge.get("extraction_method") or "manual"}
    edges = _read_edges()
    key = (edge.get("source_slug"), edge.get("target_slug"), edge.get("relation_type"))
    edges = [item for item in edges if (item.get("source_slug"), item.get("target_slug"), item.get("relation_type")) != key]
    edges.append(edge)
    _write_edges(edges)
    return edge


def remove_stale_edges_for_page(slug: str) -> dict[str, Any]:
    edges = _read_edges()
    kept = [edge for edge in edges if edge.get("source_slug") != slug]
    _write_edges(kept)
    return {"removed": len(edges) - len(kept)}


def graph_neighbors(slug: str, relation_type: str | None = None, depth: int = 1) -> list[dict[str, Any]]:
    edges = _read_edges()
    result = []
    frontier = {slug}
    for _ in range(max(depth, 1)):
        next_frontier = set()
        for edge in edges:
            if relation_type and edge.get("relation_type") != relation_type:
                continue
            if edge.get("source_slug") in frontier or edge.get("target_slug") in frontier:
                result.append(edge)
                next_frontier.add(edge.get("source_slug"))
                next_frontier.add(edge.get("target_slug"))
        frontier = next_frontier - frontier
    return result


def graph_query(start_slug: str, relation_type: str | None = None, direction: str = "both", depth: int = 2) -> list[dict[str, Any]]:
    edges = graph_neighbors(start_slug, relation_type=relation_type, depth=depth)
    if direction == "out":
        return [edge for edge in edges if edge.get("source_slug") == start_slug]
    if direction == "in":
        return [edge for edge in edges if edge.get("target_slug") == start_slug]
    return edges


def rebuild_graph(project_id: str | None = None) -> dict[str, Any]:
    existing = _read_edges()
    kept = [edge for edge in existing if project_id and edge.get("project_id") != project_id]
    new_edges = []
    for path in brain_root().rglob("*.md"):
        page = read_brain_page(path.stem)
        if project_id and page["frontmatter"].get("project_id") != project_id:
            continue
        new_edges.extend(extract_research_links_from_page(path.stem))
    _write_edges(kept + new_edges)
    return {"edge_count": len(kept + new_edges), "rebuilt_count": len(new_edges)}
