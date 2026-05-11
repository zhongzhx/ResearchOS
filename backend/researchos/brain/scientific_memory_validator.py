from __future__ import annotations

from typing import Any

MECHANISM_TERMS = ["mechanism", "pathway", "activate", "inhibit", "regulate", "mediated", "机制", "通路", "激活", "抑制", "调控", "介导"]
HIDDEN_TERMS = ["system prompt", "hidden policies", "internal tool instructions", "developer message", "tool trace", "prompt_router"]


def detect_hidden_prompt_leak(text: str) -> dict[str, Any]:
    lowered = str(text or "").lower()
    found = [term for term in HIDDEN_TERMS if term in lowered]
    return {"valid": not found, "risk_level": "high" if found else "low", "issues": [f"hidden/internal prompt leak: {term}" for term in found], "recommendations": ["Remove internal prompt/tool policy text."] if found else []}


def detect_unsourced_mechanism_claim(text: str, source_ids: list[str]) -> dict[str, Any]:
    lowered = str(text or "").lower()
    has_mechanism = any(term in lowered or term in text for term in MECHANISM_TERMS)
    is_hypothesis = "hypothesis" in lowered or "假设" in text
    invalid = has_mechanism and not source_ids and not is_hypothesis
    return {"valid": not invalid, "risk_level": "high" if invalid else "low", "issues": ["unsourced mechanism claim"] if invalid else [], "recommendations": ["Add source_ids or mark as hypothesis."] if invalid else []}


def validate_memory_write(memory_item: dict[str, Any]) -> dict[str, Any]:
    text = str(memory_item.get("text") or memory_item.get("compiled_truth") or "")
    source_ids = list(memory_item.get("source_ids") or [])
    confidence = str(memory_item.get("confidence") or "")
    issues: list[str] = []
    recommendations: list[str] = []
    hidden = detect_hidden_prompt_leak(text)
    mechanism = detect_unsourced_mechanism_claim(text, source_ids)
    issues.extend(hidden["issues"])
    issues.extend(mechanism["issues"])
    if not confidence:
        issues.append("missing confidence")
    if not source_ids and memory_item.get("type") not in {"failure", "decision"}:
        issues.append("missing source_ids")
    if "hypothesis" in text.lower() and confidence == "high":
        issues.append("hypothesis cannot be written as high confidence conclusion")
        recommendations.append("Downgrade confidence or add direct evidence.")
    risk = "high" if hidden["issues"] or mechanism["issues"] else ("medium" if issues else "low")
    return {"valid": not issues, "risk_level": risk, "issues": issues, "recommendations": recommendations + hidden["recommendations"] + mechanism["recommendations"]}


def validate_brain_page(page_obj: dict[str, Any]) -> dict[str, Any]:
    fm = page_obj.get("frontmatter") or {}
    item = {"type": fm.get("type"), "text": page_obj.get("compiled_truth"), "source_ids": fm.get("source_ids") or [], "confidence": fm.get("confidence")}
    result = validate_memory_write(item)
    if not page_obj.get("timeline_entries"):
        result["issues"].append("missing Evidence Timeline")
    result["valid"] = not result["issues"]
    result["risk_level"] = "high" if any("hidden" in issue or "unsourced" in issue for issue in result["issues"]) else ("medium" if result["issues"] else "low")
    return result


def validate_claim_page(page_obj: dict[str, Any]) -> dict[str, Any]:
    result = validate_brain_page(page_obj)
    if (page_obj.get("frontmatter") or {}).get("type") != "claim":
        result["issues"].append("not a claim page")
    result["valid"] = not result["issues"]
    return result
