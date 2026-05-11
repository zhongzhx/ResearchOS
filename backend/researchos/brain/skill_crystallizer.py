from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .post_task_reflector import reflect_on_completed_skillrun
from .scientific_memory_validator import detect_hidden_prompt_leak


def skills_root() -> Path:
    return Path(os.environ.get("RESEARCHOS_SKILLS_ROOT") or Path.cwd() / "skills")


def safe_skill_dir_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-").lower()
    return value or "generated-skill"


def crystallize_skill_from_skillrun(skillrun_id: str) -> dict[str, Any]:
    return crystallize_skill_from_reflection(reflect_on_completed_skillrun(skillrun_id))


def crystallize_skill_from_reflection(reflection: dict[str, Any]) -> dict[str, Any]:
    if not reflection.get("should_crystallize_skill", True) and reflection.get("reuse_score", 0) < 0.7:
        raise ValueError("reflection is not suitable for skill crystallization")
    candidate = {
        "name": reflection.get("candidate_skill_name") or f"Generated {reflection.get('candidate_skill_type', 'Research Skill')}",
        "version": "0.1.0",
        "status": "pending_review",
        "created_from_skillrun_id": reflection.get("skillrun_id"),
        "type": reflection.get("candidate_skill_type") or "generic_skill_task",
        "purpose": reflection.get("task_summary") or "Reusable ResearchOS workflow distilled from a completed SkillRun.",
        "inputs": ["project_id", "task_input"],
        "outputs": ["structured_outputs", "sources", "artifacts"],
        "requires_human_review": True,
        "risk_level": reflection.get("risk_level") or "medium",
        "provenance": {"reflection": reflection},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    skill_dir = create_generated_skill_directory(candidate)
    validation = validate_candidate_before_register(skill_dir)
    return {"candidate": candidate, "skill_dir": skill_dir, "validation": validation}


def generate_skill_manifest(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": candidate["name"],
        "version": "0.1.0",
        "status": "pending_review",
        "created_from_skillrun_id": candidate.get("created_from_skillrun_id"),
        "type": candidate.get("type"),
        "inputs": candidate.get("inputs") or [],
        "outputs": candidate.get("outputs") or [],
        "requires_human_review": True,
        "validation_policy": {"require_sources": True, "allow_unsourced_claims": False, "mark_low_confidence": True},
        "created_at": candidate.get("created_at") or datetime.now().isoformat(timespec="seconds"),
    }


def generate_skill_markdown(candidate: dict[str, Any]) -> str:
    text = "\n".join(
        [
            f"# {candidate['name']}",
            "",
            "# Purpose",
            candidate.get("purpose") or "Reusable ResearchOS workflow.",
            "",
            "# When to Use",
            f"Use when task_type is `{candidate.get('type')}` and the user has approved this generated skill.",
            "",
            "# Inputs",
            "- project_id",
            "- task_input",
            "- source_ids when evidence is required",
            "",
            "# Outputs",
            "- structured_outputs",
            "- sources",
            "- artifacts",
            "",
            "# Procedure",
            "1. Read only the task-specific inputs.",
            "2. Execute the approved procedure.",
            "3. Return structured outputs with provenance.",
            "",
            "# Validation",
            "- Require sources for evidence-backed claims.",
            "- Mark low-confidence or unsupported claims clearly.",
            "",
            "# Failure Modes",
            "- Missing inputs.",
            "- Missing evidence.",
            "- Output validation failure.",
            "",
            "# Human Review Requirements",
            "- This generated skill is pending_review by default.",
            "- Human review is required before activation.",
            "",
            "# Provenance",
            f"- created_from_skillrun_id: {candidate.get('created_from_skillrun_id')}",
            f"- risk_level: {candidate.get('risk_level')}",
        ]
    )
    leak = detect_hidden_prompt_leak(text)
    if not leak["valid"]:
        raise ValueError("generated skill markdown contains internal prompt text")
    return text + "\n"


def create_generated_skill_directory(candidate: dict[str, Any]) -> str:
    root = skills_root() / "generated" / safe_skill_dir_name(candidate["name"])
    (root / "examples").mkdir(parents=True, exist_ok=True)
    (root / "validators").mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(generate_skill_markdown(candidate), encoding="utf-8")
    (root / "skill.json").write_text(json.dumps(generate_skill_manifest(candidate), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (root / "examples" / "example_input.json").write_text(json.dumps({"project_id": "example", "task_input": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "examples" / "example_output.md").write_text("# Example Output\n\nPending human review.\n", encoding="utf-8")
    (root / "validators" / "validate_output.py").write_text("def validate(output):\n    return {'valid': bool(output), 'issues': []}\n", encoding="utf-8")
    return str(root)


def validate_candidate_before_register(skill_dir: str) -> dict[str, Any]:
    root = Path(skill_dir)
    issues = []
    for rel in ["SKILL.md", "skill.json", "examples/example_input.json", "examples/example_output.md", "validators/validate_output.py"]:
        if not (root / rel).exists():
            issues.append(f"missing {rel}")
    if (root / "skill.json").exists():
        manifest = json.loads((root / "skill.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "pending_review":
            issues.append("generated skill must default to pending_review")
    markdown = (root / "SKILL.md").read_text(encoding="utf-8") if (root / "SKILL.md").exists() else ""
    for heading in ["# Purpose", "# When to Use", "# Inputs", "# Outputs", "# Procedure", "# Validation", "# Failure Modes", "# Human Review Requirements", "# Provenance"]:
        if heading not in markdown:
            issues.append(f"missing heading {heading}")
    leak = detect_hidden_prompt_leak(markdown)
    issues.extend(leak["issues"])
    return {"valid": not issues, "issues": issues}
