from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


DEMO_QUERY = "Design a RAW264.7 innate immune activation experiment based on recent literature."


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def demo_task_id(prefix: str = "task") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def lifecycle(goal: str, plan: list[str], contract: dict[str, Any], execution: dict[str, Any], artifacts: str, validation: dict[str, Any], handoff: str, memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "Goal": goal,
        "Plan": plan,
        "Contract": contract,
        "Execution": execution,
        "Artifacts": artifacts,
        "Validation": validation,
        "Handoff": handoff,
        "Memory": memory,
    }


def raw2647_design_payload(project_id: str = "demo_project") -> dict[str, Any]:
    task_id = demo_task_id()
    skillrun_id = f"sr_{uuid4().hex[:10]}"
    artifacts = [
        {
            "id": "artifact_experiment_matrix",
            "type": "experiment_matrix",
            "title": "RAW264.7 innate immune activation matrix",
            "summary": "Pilot matrix with vehicle, LPS-positive control, stimulation levels, time-course readouts, and replicate guidance.",
        },
        {
            "id": "artifact_decision_summary",
            "type": "decision_summary",
            "title": "Design decision summary",
            "summary": "Use a pilot subset before scaling; avoid significance claims until raw replicate data and statistics are available.",
        },
    ]
    validation = {
        "safe_to_return": True,
        "safe_to_promote": True,
        "safe_to_crystallize": False,
        "required_human_review": True,
        "issues": ["Wet-lab parameters are intentionally non-operational; user must confirm exact dose, timing, biosafety, and reagent details."],
    }
    memory_update = {
        "status": "dry_run",
        "written": [{"type": "decision", "title": "RAW264.7 pilot design drafted", "confidence": "medium"}],
        "rejected_items": [],
        "required_human_review": True,
    }
    matrix = {
        "variables": ["stimulus", "dose level", "time point"],
        "levels": {"stimulus": ["vehicle", "LPS positive control", "candidate activator"], "time_point": ["early", "late"]},
        "controls": ["vehicle control", "positive immune activation control", "unstimulated baseline"],
        "replicates": {"pilot": "at least biological replicates; exact n must be confirmed by power/statistical plan"},
        "readouts": ["cell viability", "qPCR cytokine markers", "ELISA secreted cytokines", "morphology / activation markers"],
        "pilot_subset": "Start with a small, non-definitive screen before committing to full statistics.",
        "risk_points": ["cell passage variability", "endotoxin contamination", "activation versus toxicity confounding", "batch effects"],
        "assumptions": ["RAW264.7 cells are already approved and available in the user's lab.", "No human or animal intervention is requested."],
        "questions": ["Which candidate stimulus is being tested?", "Which cytokines/readouts are required?", "What statistical design does the lab normally use?"],
    }
    return {
        "ok": True,
        "feature_id": "dual_agent_research_task",
        "project_id": project_id,
        "task_id": task_id,
        "skillrun_id": skillrun_id,
        "selected_pipeline": "experiment_design",
        "required_skills": ["design-experiment-matrix"],
        "execution_status": "success",
        "summary": "Brain Agent selected the experiment_design pipeline and Execution Agent produced a RAW264.7 pilot design with controls, readouts, risks, and confirmation questions.",
        "result": {"experiment_matrix": matrix},
        "artifacts": artifacts,
        "validation_report": validation,
        "promotion_decision": {"accepted_targets": ["decisions"], "rejected_items": [], "required_human_review": True},
        "memory_update": memory_update,
        "memory_updates": memory_update["written"],
        "pending_skill": {"name": "", "status": "none"},
        "handoff": "Review the design assumptions, confirm exact stimulus/readouts/statistics, then run the pilot as a tracked task.",
        "next_actions": [
            {"intent": "confirm_design_inputs", "label": "Confirm stimulus, readouts, and replicate plan"},
            {"intent": "collect_literature", "label": "Collect recent RAW264.7 activation references"},
        ],
        "warnings": validation["issues"],
        "task_lifecycle": lifecycle(
            "Design a RAW264.7 innate immune activation experiment.",
            ["Route query to experiment_design", "Run design-experiment-matrix", "Validate wet-lab assumptions", "Prepare Brain memory update and handoff"],
            {"TaskSpec": {"task_id": task_id, "project_id": project_id, "pipeline": "experiment_design", "required_skills": ["design-experiment-matrix"]}},
            {"ExecutionResult": {"skillrun_id": skillrun_id, "status": "success", "skills_used": ["design-experiment-matrix"]}},
            "Artifacts: experiment matrix, decision summary",
            validation,
            "Handoff: confirm missing inputs before wet-lab execution.",
            memory_update,
        ),
        "raw_details": {
            "TaskSpec": {"task_id": task_id, "project_id": project_id, "user_query": DEMO_QUERY, "task_type": "experiment_design"},
            "ExecutionResult": {"skillrun_id": skillrun_id, "status": "success", "structured_outputs": {"experiment_matrix": matrix}},
            "validation": validation,
            "memory": memory_update,
        },
    }


def literature_demo_payload(project_id: str = "demo_project", keywords: list[str] | None = None) -> dict[str, Any]:
    keywords = keywords or ["RAW264.7", "innate immunity"]
    task_id = demo_task_id("lit")
    references = [
        {"id": "ref_demo_1", "title": "Demo reference placeholder for RAW264.7 immune activation", "status": "metadata_only", "source": "demo"},
    ]
    paper_requests = [
        {"id": "paper_req_demo_1", "title": "Full text access requires user-provided legal access route", "status": "needs_user_access"},
    ]
    validation = {"safe_to_return": True, "safe_to_promote": False, "required_human_review": True, "issues": ["External literature download is not run in demo/dry_run mode."]}
    return {
        "ok": True,
        "feature_id": "literature_harvest_workflow",
        "project_id": project_id,
        "task_id": task_id,
        "selected_pipeline": "literature_harvest",
        "required_skills": ["research-agent-runtime", "compliant-literature-access", "keyword-research-harvest", "extract-first-article-keywords", "build-user-research-kb"],
        "execution_status": "partial",
        "summary": f"Created a literature harvest task for: {', '.join(keywords)}. Demo mode records references/paper requests without external network access.",
        "result": {"keywords": keywords, "references": references, "paper_requests": paper_requests, "kb_status": "not_connected"},
        "artifacts": [{"id": "lit_task_demo", "type": "literature_task", "title": "Demo literature harvest task", "summary": "Contains metadata placeholders and paper requests."}],
        "memory_update": {"status": "dry_run", "written": [{"type": "literature_task", "title": "RAW264.7 literature task queued", "confidence": "low"}]},
        "memory_updates": [{"type": "literature_task", "title": "RAW264.7 literature task queued", "confidence": "low"}],
        "next_actions": [{"intent": "review_paper_requests", "label": "Review paper requests and provide legal full-text access"}],
        "warnings": ["browser_not_authorized", "external_search_not_run", "kb_builder_not_connected_in_demo"],
        "validation_report": validation,
        "promotion_decision": {"accepted_targets": [], "rejected_items": [{"target": "claims", "reason": "demo metadata is not evidence"}], "required_human_review": True},
        "pending_skill": {"name": "", "status": "none"},
        "handoff": "Review paper requests; no paywall, CAPTCHA, MFA, SSO, or illegal access path was attempted.",
        "task_lifecycle": lifecycle(
            "Collect compliant literature for the keyword set.",
            ["Create search task", "Record compliant-access guardrails", "Add paper requests for inaccessible full text"],
            {"keywords": keywords, "include_oa_only": True, "requires_browser_authorization": True},
            {"status": "partial", "access_log": ["demo mode: no external access"]},
            "Library / Evidence: references, paper requests, KB/RAG status, access log",
            validation,
            "Handoff: user reviews paper requests and can rerun with authorized access.",
            {"status": "dry_run", "writes": ["literature_task"]},
        ),
        "raw_details": {"TaskSpec": {"task_id": task_id, "pipeline": "literature_harvest"}, "ExecutionResult": {"status": "partial", "references": references, "paper_requests": paper_requests}},
    }
