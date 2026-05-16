from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime_paths import prompt_root

PROMPT_ROOT = prompt_root()
PROMPT_PATH = PROMPT_ROOT / "researchos_agent_system_prompt.md"
ZH_PROMPT_ROOT = PROMPT_ROOT / "zh"

ZH_POLICY_FILES: dict[str, str] = {
    "base_identity": "base_identity_zh.md",
    "evidence": "evidence_policy_zh.md",
    "citation": "citation_policy_zh.md",
    "memory": "memory_policy_zh.md",
    "claim": "claim_policy_zh.md",
    "natural_language_task": "natural_language_task_policy_zh.md",
    "literature_rag": "literature_rag_policy_zh.md",
    "experiment_log": "experiment_log_policy_zh.md",
    "protocol_extraction": "protocol_extraction_policy_zh.md",
    "writing_assistant": "writing_assistant_policy_zh.md",
    "weekly_digest": "weekly_digest_policy_zh.md",
    "weekly_research_report": "weekly_digest_policy_zh.md",
    "weekly_research_digest": "weekly_digest_policy_zh.md",
    "project_retrospective": "project_retrospective_policy_zh.md",
    "project_gap_analysis": "project_retrospective_policy_zh.md",
    "peer_review": "peer_review_policy_zh.md",
    "literature_mining_to_kb": "literature_rag_policy_zh.md",
    "memory_update": "memory_policy_zh.md",
    "conflict_detection": "project_retrospective_policy_zh.md",
    "workflow_planning": "natural_language_task_policy_zh.md",
    "scientific_writing": "writing_assistant_policy_zh.md",
    "result_narrative": "writing_assistant_policy_zh.md",
    "claim_generation": "claim_policy_zh.md",
    "claim_evidence_review": "claim_policy_zh.md",
    "result_analysis": "claim_policy_zh.md",
    "data_contextualization": "experiment_log_policy_zh.md",
    "data_qc": "experiment_log_policy_zh.md",
    "lcms_data_analysis": "experiment_log_policy_zh.md",
    "qpcr_analysis": "experiment_log_policy_zh.md",
    "elisa_analysis": "experiment_log_policy_zh.md",
    "sop_generation": "protocol_extraction_policy_zh.md",
    "reagent_calculation": "protocol_extraction_policy_zh.md",
    "plate_layout": "protocol_extraction_policy_zh.md",
    "backend_llm_guardrails": "backend_llm_guardrails_zh.md",
    "prompt_composition": "prompt_composition_zh.md",
}

PROMPT_POLICY_ALIASES: dict[str, str] = {
    "rag": "literature_rag",
    "literature": "literature_rag",
    "literature_mining": "literature_rag",
    "research_route_planning": "literature_rag",
    "paper_writing": "writing_assistant",
    "writing": "writing_assistant",
    "result_narrative": "result_narrative",
    "experiment_log_ingestion": "experiment_log",
    "log_ingestion": "experiment_log",
    "structured_protocol": "protocol_extraction",
    "protocol": "protocol_extraction",
    "paper_to_protocol": "protocol_extraction",
    "kit_manual": "protocol_extraction",
    "weekly_report": "weekly_digest",
    "weekly_papers": "weekly_digest",
    "retrospective": "project_retrospective",
    "gap_analysis": "project_retrospective",
    "project_gap_analysis": "project_gap_analysis",
    "review": "peer_review",
}

PROMPT_POLICY_STACKS: dict[str, list[str]] = {
    "natural_language_task": ["base_identity", "natural_language_task"],
    "literature_rag": ["base_identity", "evidence", "citation", "literature_rag"],
    "writing_assistant": ["base_identity", "evidence", "citation", "claim", "writing_assistant"],
    "experiment_log": ["base_identity", "memory", "claim", "experiment_log"],
    "protocol_extraction": ["base_identity", "evidence", "protocol_extraction"],
    "weekly_digest": ["base_identity", "evidence", "citation", "weekly_digest"],
    "weekly_research_report": ["base_identity", "evidence", "citation", "claim", "weekly_research_report"],
    "weekly_research_digest": ["base_identity", "evidence", "citation", "weekly_research_digest"],
    "project_retrospective": ["base_identity", "evidence", "memory", "claim", "project_retrospective"],
    "project_gap_analysis": ["base_identity", "evidence", "memory", "claim", "project_gap_analysis"],
    "peer_review": ["base_identity", "evidence", "citation", "claim", "peer_review"],
    "literature_mining_to_kb": ["base_identity", "evidence", "citation", "literature_mining_to_kb"],
    "memory_update": ["base_identity", "memory", "claim", "memory_update"],
    "conflict_detection": ["base_identity", "evidence", "memory", "claim", "conflict_detection"],
    "workflow_planning": ["base_identity", "natural_language_task", "workflow_planning"],
    "scientific_writing": ["base_identity", "evidence", "citation", "claim", "scientific_writing"],
    "result_narrative": ["base_identity", "evidence", "citation", "claim", "result_narrative"],
    "claim_generation": ["base_identity", "evidence", "claim", "claim_generation"],
    "claim_evidence_review": ["base_identity", "evidence", "citation", "claim", "claim_evidence_review"],
    "result_analysis": ["base_identity", "evidence", "claim", "result_analysis"],
    "data_contextualization": ["base_identity", "memory", "data_contextualization"],
    "data_qc": ["base_identity", "evidence", "data_qc"],
    "lcms_data_analysis": ["base_identity", "evidence", "data_contextualization", "lcms_data_analysis"],
    "qpcr_analysis": ["base_identity", "evidence", "data_contextualization", "qpcr_analysis"],
    "elisa_analysis": ["base_identity", "evidence", "data_contextualization", "elisa_analysis"],
    "sop_generation": ["base_identity", "evidence", "protocol_extraction", "sop_generation"],
    "reagent_calculation": ["base_identity", "protocol_extraction", "reagent_calculation"],
    "plate_layout": ["base_identity", "protocol_extraction", "plate_layout"],
    "backend_llm_guardrails": ["base_identity", "backend_llm_guardrails"],
}


def load_researchos_system_prompt() -> str:
    """Load the backend system prompt used for ResearchOS Agent LLM calls."""
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"ResearchOS system prompt not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def normalize_prompt_policy(prompt_policy: str | None) -> str:
    policy = (prompt_policy or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not policy:
        return "backend_llm_guardrails"
    return PROMPT_POLICY_ALIASES.get(policy, policy)


def load_prompt_fragment(policy_name: str, prompt_language: str = "zh") -> tuple[str, str]:
    """Load a single prompt fragment and return content plus file path."""
    language = (prompt_language or "zh").strip().lower()
    policy = normalize_prompt_policy(policy_name)
    if language == "zh":
        filename = ZH_POLICY_FILES.get(policy)
        if filename:
            path = ZH_PROMPT_ROOT / filename
            if path.exists():
                return path.read_text(encoding="utf-8").strip(), str(path)
    return load_researchos_system_prompt(), str(PROMPT_PATH)


def prompt_stack_for_policy(prompt_policy: str | None) -> list[str]:
    policy = normalize_prompt_policy(prompt_policy)
    return PROMPT_POLICY_STACKS.get(policy, ["base_identity", "evidence", "citation", policy])


def compose_researchos_prompt(
    prompt_language: str = "zh",
    prompt_policy: str | None = "backend_llm_guardrails",
    *,
    include_backend_guardrails: bool = False,
) -> dict[str, Any]:
    """Compose a ResearchOS policy prompt with zh support and English fallback."""
    language = (prompt_language or "zh").strip().lower()
    policy = normalize_prompt_policy(prompt_policy)
    if language != "zh":
        prompt = load_researchos_system_prompt()
        return {
            "prompt": prompt,
            "prompt_language": "en",
            "prompt_policy": policy,
            "prompt_files": [str(PROMPT_PATH)],
            "fallback_used": False,
        }

    stack = list(prompt_stack_for_policy(policy))
    if include_backend_guardrails and "backend_llm_guardrails" not in stack:
        stack.append("backend_llm_guardrails")

    fragments: list[str] = []
    files: list[str] = []
    fallback_used = False
    for item in stack:
        content, file_path = load_prompt_fragment(item, "zh")
        fragments.append(content)
        files.append(file_path)
        if Path(file_path) == PROMPT_PATH:
            fallback_used = True

    prompt = "\n\n---\n\n".join(fragment for fragment in fragments if fragment).strip()
    return {
        "prompt": prompt,
        "prompt_language": "zh",
        "prompt_policy": policy,
        "prompt_files": files,
        "fallback_used": fallback_used,
    }


def researchos_prompt_info(
    include_prompt: bool = False,
    prompt_language: str = "en",
    prompt_policy: str | None = None,
) -> dict[str, Any]:
    if (prompt_language or "").lower() == "zh" or prompt_policy:
        composed = compose_researchos_prompt(prompt_language or "zh", prompt_policy or "backend_llm_guardrails")
        prompt = composed["prompt"]
        prompt_files = composed["prompt_files"]
        language = composed["prompt_language"]
        policy = composed["prompt_policy"]
    else:
        prompt = load_researchos_system_prompt()
        prompt_files = [str(PROMPT_PATH)]
        language = "en"
        policy = "base_identity"
    info: dict[str, Any] = {
        "agent_name": "ResearchOS Agent",
        "prompt_path": prompt_files[0],
        "prompt_files": prompt_files,
        "prompt_language": language,
        "prompt_policy": policy,
        "character_count": len(prompt),
        "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    if include_prompt:
        info["system_prompt"] = prompt
    return info


def _format_context_block(context: Any) -> str:
    if context is None or context == "":
        return ""
    if isinstance(context, str):
        return context.strip()
    return json.dumps(context, ensure_ascii=False, indent=2)


def build_researchos_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Build OpenAI-compatible chat messages with the ResearchOS system prompt."""
    user_message = (
        payload.get("user_message")
        or payload.get("message")
        or payload.get("input")
        or payload.get("question")
    )
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("user_message is required")

    prompt_language = payload.get("prompt_language") or payload.get("language") or "zh"
    prompt_policy = payload.get("prompt_policy") or payload.get("task_type") or "backend_llm_guardrails"
    system_prompt = compose_researchos_prompt(str(prompt_language), str(prompt_policy))["prompt"]
    extra_system_instruction = payload.get("extra_system_instruction")
    if isinstance(extra_system_instruction, str) and extra_system_instruction.strip():
        system_prompt = f"{system_prompt}\n\nAdditional backend instruction:\n{extra_system_instruction.strip()}"

    messages = [{"role": "system", "content": system_prompt}]
    context_block = _format_context_block(payload.get("context") or payload.get("local_context"))
    if context_block:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Local context retrieved for this task. Use it only when relevant, "
                    "cite it when making knowledge-base claims, and do not treat it as complete if evidence is missing.\n\n"
                    f"{context_block}"
                ),
            }
        )
    messages.append({"role": "user", "content": user_message.strip()})
    return messages
