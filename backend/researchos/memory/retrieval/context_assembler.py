from __future__ import annotations

from typing import Any

from backend.researchos.brain.context_indexer import load_project_context_index
from backend.researchos.memory.compression.cognitive_state import summarize_cognitive_state_for_context
from backend.researchos.memory.episodic.episodic_memory_store import search_episodes
from backend.researchos.memory.memory_config import redact_payload, redact_text
from backend.researchos.memory.retrieval.memory_retriever import retrieve_memories
from backend.researchos.memory.retrieval.retrieval_audit import context_hash, write_retrieval_audit


def select_context_sources(project_id: str, query: str, intent: str | None = None) -> list[dict[str, Any]]:
    return retrieve_memories(project_id, query, top_k=20)


def assemble_brain_context(project_id: str, user_query: str, intent: str | None = None, max_tokens: int = 12000) -> dict[str, Any]:
    cognitive = summarize_cognitive_state_for_context(project_id, max_items=20)
    try:
        index = load_project_context_index(project_id)
    except Exception:
        index = {"project_id": project_id, "available_assets": {}, "recommended_context_for_intents": {}}
    selected = select_context_sources(project_id, user_query, intent=intent)
    episodes = search_episodes(project_id, user_query, limit=5)
    claims = [item for item in selected if item.get("memory_type") == "claim"]
    failures = [item for item in selected if item.get("memory_type") == "failure"]
    package = {
        "project_id": project_id,
        "intent": intent,
        "user_query": redact_text(user_query, max_chars=1000),
        "cognitive_state": cognitive,
        "project_context_index": {
            "project_id": index.get("project_id"),
            "available_assets": index.get("available_assets"),
            "recommended_context_for_intents": index.get("recommended_context_for_intents"),
        },
        "selected_semantic_memories": selected,
        "selected_episodes": episodes,
        "selected_failures": failures,
        "selected_claims": claims,
        "selected_skill_summaries": [],
    }
    h = context_hash(package)
    audit = write_retrieval_audit(project_id, h, selected)
    package["retrieval_audit"] = audit
    return redact_payload(package, max_chars=max_tokens * 4)


def assemble_execution_context(task_spec: Any, brain_context: dict[str, Any], max_tokens: int = 6000) -> dict[str, Any]:
    selected = list((brain_context or {}).get("selected_semantic_memories") or [])[:8]
    project_summary = (brain_context or {}).get("cognitive_state", {}).get("current_goal") or ""
    package = {
        "task_brief": redact_text(getattr(task_spec, "user_query", ""), max_chars=800),
        "project_short_summary": redact_text(project_summary, max_chars=1000),
        "selected_sources": [
            {
                "source_id": item.get("source_id"),
                "memory_id": item.get("memory_id"),
                "title": item.get("title"),
                "confidence": item.get("confidence"),
                "summary": redact_text(item.get("summary"), max_chars=500),
            }
            for item in selected
        ],
        "validation_rules": list(getattr(task_spec, "validation_rules", []) or []),
        "known_constraints": list(getattr(task_spec, "safety_constraints", []) or []),
        "required_output_schema": getattr(task_spec, "input_data", {}).get("output_schema", {}) if isinstance(getattr(task_spec, "input_data", {}), dict) else {},
        "selected_skill_instructions": list((brain_context or {}).get("selected_skill_summaries") or [])[:5],
        "context_audit": (brain_context or {}).get("retrieval_audit", {}),
    }
    return redact_payload(package, max_chars=max_tokens * 4)

