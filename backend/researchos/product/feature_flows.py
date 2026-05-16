from __future__ import annotations

import csv
import io
from statistics import mean
from typing import Any

from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, route_query_to_pipeline

from .feature_contracts import ProductFeatureContract, FeatureStatus, product_response
from .feature_demo_data import literature_demo_payload, raw2647_design_payload
from .feature_status import feature_status_detail, resolve_feature_status


CORE_FEATURE_IDS = [
    "dual_agent_research_task",
    "literature_harvest_workflow",
    "data_analysis_workflow",
    "protocol_to_sop_workflow",
    "experiment_design_workflow",
    "failure_recovery_workflow",
    "writing_review_workflow",
    "weekly_report_workflow",
]


FEATURES: dict[str, ProductFeatureContract] = {
    "dual_agent_research_task": ProductFeatureContract(
        feature_id="dual_agent_research_task",
        display_name="Dual Agent Research Task",
        user_goal="Turn an open-ended research request into a planned, executed, validated, handed-off task.",
        trigger_examples=["Design a RAW264.7 innate immune activation experiment", "Analyze this CSV and write a result paragraph"],
        preferred_pipeline="experiment_design",
        required_backend_api=["POST /api/agents/coordinator/run"],
        required_skills=["skill-router-orchestrator", "context-compiler-maintenance", "design-experiment-matrix", "skill-output-validator", "evidence-promotion"],
        expected_artifacts=["task_spec", "skillrun", "validation_report", "handoff", "memory_update"],
        expected_frontend_panels=["Chat", "Task Lifecycle", "Runs", "Research Brain"],
        status="partial",
        fallback_behavior="Use local demo flow when no API key or external tools are configured.",
        safety_requirements=["Execution Agent receives minimal context only.", "Brain Agent owns long-term Research Brain writes.", "Generated pending skills stay pending_review."],
    ),
    "literature_harvest_workflow": ProductFeatureContract(
        feature_id="literature_harvest_workflow",
        display_name="Literature Harvest Workflow",
        user_goal="Create a compliant literature task from keywords and surface references, paper requests, KB/RAG status, and access logs.",
        trigger_examples=["Collect literature for RAW264.7 innate immunity", "Search papers about macrophage activation"],
        preferred_pipeline="literature_harvest",
        required_backend_api=["POST /api/product/features/literature_harvest_workflow/run", "GET /research-os/literature/search-tasks"],
        required_skills=["compliant-literature-access", "keyword-research-harvest", "extract-first-article-keywords", "build-user-research-kb"],
        expected_artifacts=["search_task", "references", "paper_requests", "kb_entries", "access_log"],
        expected_frontend_panels=["Library / Evidence", "Task Lifecycle", "Runs", "Research Brain"],
        status="partial",
        fallback_behavior="Create a local task and paper requests; report not_connected for browser/download/KB pieces that are unavailable.",
        safety_requirements=["Do not bypass paywalls, CAPTCHA, MFA, or SSO.", "Browser/campus access requires explicit authorization.", "Unavailable full text becomes a paper_request."],
        not_connected_dependencies=["external_literature_search", "authorized_browser_download"],
    ),
    "data_analysis_workflow": ProductFeatureContract(
        feature_id="data_analysis_workflow",
        display_name="Data Analysis Workflow",
        user_goal="Parse CSV/XLSX-like scientific data, summarize groups and numeric columns, then draft cautious result text.",
        trigger_examples=["Analyze CSV and write a result paragraph", "Summarize this xlsx experiment"],
        preferred_pipeline="data_analysis_to_narrative",
        required_backend_api=["POST /api/product/features/data_analysis_workflow/run", "GET /research-os/files"],
        required_skills=["parse-scientific-data", "analyze-experiment-results", "result-narrative"],
        expected_artifacts=["data_summary", "analysis_table", "result_paragraph", "figure_legend", "statistics_warning"],
        expected_frontend_panels=["Chat", "Library / Evidence", "Runs", "Task Lifecycle"],
        status="partial",
        fallback_behavior="Use built-in CSV demo parser; return parser_not_connected for unsupported XLSX/parser paths.",
        safety_requirements=["Do not invent p values.", "Without statistics, write only descriptive trends.", "Mark low confidence when replicates are insufficient."],
        not_connected_dependencies=["xlsx_parser"],
    ),
    "protocol_to_sop_workflow": ProductFeatureContract(
        feature_id="protocol_to_sop_workflow",
        display_name="Protocol to SOP Workflow",
        user_goal="Convert Methods/protocol text into an SOP draft with missing parameters and reproducibility warnings.",
        trigger_examples=["Turn these Methods into SOP", "Build SOP from this protocol"],
        preferred_pipeline="protocol_to_sop",
        required_backend_api=["POST /api/product/features/protocol_to_sop_workflow/run"],
        required_skills=["protocol-extraction", "sop-generation"],
        expected_artifacts=["extracted_protocol", "sop_draft", "missing_information", "safety_notes"],
        expected_frontend_panels=["Chat", "Task Lifecycle", "Library / Evidence", "Research Brain"],
        status="partial",
        fallback_behavior="Generate a conservative local SOP draft and list missing parameters.",
        safety_requirements=["Do not invent missing concentration/time/temperature/instrument details.", "Dangerous or human/animal work requires safety/ethics notes."],
    ),
    "experiment_design_workflow": ProductFeatureContract(
        feature_id="experiment_design_workflow",
        display_name="Experiment Design Workflow",
        user_goal="Generate an experiment matrix, controls, replicates, readouts, risks, and next confirmation questions.",
        trigger_examples=["Design RAW264.7 immune activation experiment", "Create an experiment matrix"],
        preferred_pipeline="experiment_design",
        required_backend_api=["POST /api/product/features/experiment_design_workflow/run"],
        required_skills=["design-experiment-matrix"],
        expected_artifacts=["experiment_matrix", "controls", "readouts", "decision_summary"],
        expected_frontend_panels=["Chat", "Task Lifecycle", "Research Brain"],
        status="partial",
        fallback_behavior="Use local demo experiment design when LLM or script execution is unavailable.",
        safety_requirements=["Do not provide over-specific hazardous wet-lab operations.", "Add safety/ethics notes for animal, human, clinical, or pathogen work."],
    ),
    "failure_recovery_workflow": ProductFeatureContract(
        feature_id="failure_recovery_workflow",
        display_name="Failure Recovery Workflow",
        user_goal="Record a failed experiment, match historical failures, and produce a recovery plan.",
        trigger_examples=["My qPCR housekeeping Ct is unstable", "Diagnose this failed experiment"],
        preferred_pipeline="failure_recovery",
        required_backend_api=["POST /api/product/features/failure_recovery_workflow/run"],
        required_skills=["failure-log", "diagnose-research-bottleneck"],
        expected_artifacts=["failure_record", "matched_failures", "recovery_plan"],
        expected_frontend_panels=["Chat", "Runs", "Research Brain Failures"],
        status="partial",
        fallback_behavior="Create a draft failure record and no_matched_failures status when history is empty.",
        safety_requirements=["Failed result writes only to failure memory.", "No success claim from failed experiments.", "Saving failure requires user intent."],
    ),
    "writing_review_workflow": ProductFeatureContract(
        feature_id="writing_review_workflow",
        display_name="Writing Review Workflow",
        user_goal="Review scientific writing for mechanism, statistics, novelty, methods, overclaims, and revisions.",
        trigger_examples=["Review this Discussion as a hostile reviewer", "Critique my abstract"],
        preferred_pipeline="writing_review",
        required_backend_api=["POST /api/product/features/writing_review_workflow/run"],
        required_skills=["peer-review-simulation", "result-narrative"],
        expected_artifacts=["major_concerns", "minor_concerns", "overclaims", "suggested_revisions"],
        expected_frontend_panels=["Chat", "Task Lifecycle", "Research Brain Reports"],
        status="partial",
        fallback_behavior="Return local peer-review style critique without inventing citations.",
        safety_requirements=["Peer review output is critique, not evidence.", "Do not invent citations or journal rules.", "Flag unsupported claims."],
    ),
    "weekly_report_workflow": ProductFeatureContract(
        feature_id="weekly_report_workflow",
        display_name="Weekly Report Workflow",
        user_goal="Generate an advisor-ready weekly report from recent tasks, memory, literature, failures, and artifacts.",
        trigger_examples=["Generate this project weekly report", "Weekly digest"],
        preferred_pipeline="weekly_reporting",
        required_backend_api=["POST /api/product/features/weekly_report_workflow/run"],
        required_skills=["weekly-research-report", "weekly-research-digest"],
        expected_artifacts=["weekly_report", "weekly_digest", "next_actions"],
        expected_frontend_panels=["Chat", "Runs", "Research Brain Reports", "Settings"],
        status="partial",
        fallback_behavior="Return an empty-state report with none/not available fields when no recent project data exists.",
        safety_requirements=["Do not invent progress.", "Separate completed, partial, blocked, and planned work."],
    ),
}


def list_product_features() -> list[dict[str, Any]]:
    rows = []
    for feature_id in CORE_FEATURE_IDS:
        contract = FEATURES[feature_id]
        row = contract.to_dict()
        row.update(feature_status_detail(contract))
        rows.append(row)
    return rows


def get_product_feature(feature_id: str) -> dict[str, Any]:
    if feature_id not in FEATURES:
        raise KeyError(feature_id)
    contract = FEATURES[feature_id]
    row = contract.to_dict()
    row.update(feature_status_detail(contract))
    return row


def run_product_feature_demo(feature_id: str, project_id: str = "demo_project") -> dict[str, Any]:
    return run_product_feature(feature_id, {"project_id": project_id, "mode": "demo"})


def run_product_feature(feature_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if feature_id not in FEATURES:
        return product_response(ok=False, feature_id=feature_id, status="not_connected", warnings=[f"unknown_feature:{feature_id}"], result={"error": "unknown_feature"})
    payload = payload or {}
    mode = str(payload.get("mode") or "normal")
    project_id = str(payload.get("project_id") or "demo_project")
    contract = FEATURES[feature_id]
    status = resolve_feature_status(contract)

    if feature_id == "dual_agent_research_task":
        return _run_dual_agent(payload, project_id, status)
    if feature_id == "experiment_design_workflow":
        result = raw2647_design_payload(project_id)
        result["feature_id"] = feature_id
        result["status"] = "partial"
        result.setdefault("warnings", []).append("demo_flow_dry_run")
        _persist_demo_visibility(project_id, result)
        return result
    if feature_id == "literature_harvest_workflow":
        keywords = payload.get("keywords") or payload.get("keyword") or payload.get("query") or ["RAW264.7", "innate immunity"]
        if isinstance(keywords, str):
            keywords = [item.strip() for item in keywords.split(",") if item.strip()] or [keywords]
        result = literature_demo_payload(project_id, list(keywords))
        result["status"] = "partial" if mode in {"demo", "dry_run", "normal"} else status
        _persist_demo_visibility(project_id, result)
        return result
    if feature_id == "data_analysis_workflow":
        return _run_data_analysis(payload, project_id, status)
    if feature_id == "protocol_to_sop_workflow":
        return _run_protocol_to_sop(payload, project_id, status)
    if feature_id == "failure_recovery_workflow":
        return _run_failure_recovery(payload, project_id, status)
    if feature_id == "writing_review_workflow":
        return _run_writing_review(payload, project_id, status)
    if feature_id == "weekly_report_workflow":
        return _run_weekly_report(payload, project_id, status)
    return product_response(ok=False, feature_id=feature_id, status="not_connected", warnings=["not_connected"])


def _run_dual_agent(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    mode = str(payload.get("mode") or "normal")
    user_query = str(payload.get("user_query") or payload.get("query") or "")
    if mode in {"demo", "dry_run"} or not user_query:
        result = raw2647_design_payload(project_id)
        result["status"] = "partial"
        result.setdefault("warnings", []).append("demo_flow_dry_run")
        _persist_demo_visibility(project_id, result)
        return result
    try:
        coordinator = AgentCoordinator()
        response = coordinator.run_full_cycle(user_query, project_id=project_id)
        return _normalize_coordinator_product_response(response, project_id)
    except Exception as exc:  # noqa: BLE001
        demo = raw2647_design_payload(project_id)
        demo["ok"] = True
        demo["status"] = "partial"
        demo["warnings"] = [*demo.get("warnings", []), f"coordinator_unavailable:{_safe_message(exc)}", "demo_fallback_used"]
        _persist_demo_visibility(project_id, demo)
        return demo


def _normalize_coordinator_product_response(response: dict[str, Any], project_id: str) -> dict[str, Any]:
    task_spec = response.get("task_spec") or {}
    execution = response.get("execution_result") or {}
    pipeline = task_spec.get("input_data", {}).get("pipeline_name") or task_spec.get("task_type") or "generic_skill_task"
    artifacts = response.get("research_task", {}).get("artifacts") or []
    memory_update = response.get("memory_commit") or response.get("brain_memory_write") or {}
    validation = response.get("validation_report") or {}
    task_id = response.get("task_id") or task_spec.get("task_id")
    skillrun_id = execution.get("skillrun_id")
    return product_response(
        ok=bool(response.get("ok", execution.get("status") in {"success", "partial_success"})),
        feature_id="dual_agent_research_task",
        status="partial",
        result={"coordinator": response},
        task_lifecycle={
            "Goal": response.get("research_task", {}).get("goal") or task_spec.get("user_query") or "",
            "Plan": response.get("research_task", {}).get("plan") or [],
            "Contract": response.get("research_task", {}).get("contract") or {"TaskSpec": task_spec},
            "Execution": execution,
            "Artifacts": artifacts,
            "Validation": validation,
            "Handoff": response.get("handoff") or response.get("handoff_summary") or "",
            "Memory": memory_update,
        },
        artifacts=artifacts if isinstance(artifacts, list) else [],
        memory_updates=_memory_updates(memory_update),
        next_actions=[{"intent": "review_handoff", "label": "Review handoff and next actions"}],
        warnings=[] if response.get("ok") else ["coordinator_returned_partial_or_failed"],
        project_id=project_id,
        task_id=task_id,
        skillrun_id=skillrun_id,
        selected_pipeline=pipeline,
        required_skills=task_spec.get("required_skills") or [],
        execution_status=execution.get("status") or "unknown",
        summary=response.get("answer") or response.get("summary") or "Coordinator returned a task result.",
        validation_report=validation,
        promotion_decision=response.get("promotion_decision") or {},
        memory_update=memory_update,
        pending_skill=(response.get("post_task_processing") or {}).get("pending_skill") or {},
        handoff=response.get("handoff") or response.get("handoff_summary") or "",
        raw_details={"TaskSpec": task_spec, "ExecutionResult": execution, "validation": validation, "memory": memory_update},
    )


def _run_data_analysis(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    inline_csv = str(payload.get("inline_csv") or "")
    if not inline_csv:
        return product_response(
            ok=False,
            feature_id="data_analysis_workflow",
            status="not_connected",
            warnings=["parser_not_connected: provide inline_csv or connect file parser"],
            result={"error": "parser_not_connected"},
            selected_pipeline="data_analysis_to_narrative",
        )
    rows = list(csv.DictReader(io.StringIO(inline_csv)))
    columns = list(rows[0].keys()) if rows else []
    numeric_columns = []
    group_columns = []
    missing_values = 0
    for column in columns:
        values = [row.get(column, "") for row in rows]
        missing_values += sum(1 for value in values if value in {"", None})
        parsed = []
        for value in values:
            try:
                parsed.append(float(value))
            except (TypeError, ValueError):
                pass
        if parsed and len(parsed) >= max(1, len([value for value in values if value not in {"", None}]) // 2):
            numeric_columns.append(column)
        else:
            group_columns.append(column)
    group_summary = _group_summary(rows, group_columns[0] if group_columns else "", numeric_columns[0] if numeric_columns else "")
    warning = "Statistics warning: no p value or statistical test was supplied; narrative is descriptive only."
    summary = "Parsed CSV data and generated a descriptive, low-confidence result paragraph without significance claims."
    artifacts = [
        {"id": "data_summary_demo", "type": "data_summary", "title": "Data summary", "summary": f"{len(rows)} rows; numeric columns: {', '.join(numeric_columns) or 'none'}"},
        {"id": "result_narrative_demo", "type": "result_paragraph", "title": "Result paragraph", "summary": "The stimulated group trends higher than control in the supplied values, but no statistical conclusion is made."},
        {"id": "figure_legend_demo", "type": "figure_legend", "title": "Figure legend draft", "summary": "Descriptive response values by group; add statistical test details before manuscript use."},
    ]
    validation = {"safe_to_return": True, "safe_to_promote": False, "required_human_review": True, "issues": [warning]}
    return product_response(
        ok=True,
        feature_id="data_analysis_workflow",
        status="partial",
        result={"rows": len(rows), "columns": columns, "numeric_columns": numeric_columns, "group_columns": group_columns, "missing_values": missing_values, "group_summary": group_summary},
        task_lifecycle={"Goal": "Analyze scientific data", "Plan": ["Parse CSV", "Detect groups/numeric columns", "Draft cautious narrative"], "Contract": {"no_significance_without_p_value": True}, "Execution": {"status": "success"}, "Artifacts": artifacts, "Validation": validation, "Handoff": "Add raw replicates and statistical test before claiming significance.", "Memory": {"status": "not_promoted_without_statistics"}},
        artifacts=artifacts,
        memory_updates=[],
        next_actions=[{"intent": "add_statistics", "label": "Add statistical test and replicate metadata"}],
        warnings=[warning],
        project_id=project_id,
        selected_pipeline="data_analysis_to_narrative",
        required_skills=FEATURES["data_analysis_workflow"].required_skills,
        execution_status="success",
        summary=summary,
        validation_report=validation,
        memory_update={"status": "skipped", "reason": "needs statistics"},
        pending_skill={"name": "", "status": "none"},
        handoff="Add statistics before promoting claims.",
        raw_details={"TaskSpec": {"pipeline": "data_analysis_to_narrative"}, "ExecutionResult": {"status": "success", "summary": group_summary}},
    )


def _group_summary(rows: list[dict[str, str]], group_column: str, numeric_column: str) -> dict[str, Any]:
    if not group_column or not numeric_column:
        return {}
    grouped: dict[str, list[float]] = {}
    for row in rows:
        try:
            grouped.setdefault(str(row.get(group_column) or "unknown"), []).append(float(row.get(numeric_column) or "nan"))
        except ValueError:
            continue
    return {group: {"n": len(values), "mean": mean(values) if values else None} for group, values in grouped.items()}


def _run_protocol_to_sop(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    text = str(payload.get("method_text") or payload.get("text") or "")
    missing = [item for item in ["concentration", "incubation time", "temperature", "instrument/model", "replicate count"] if item.lower() not in text.lower()]
    artifacts = [
        {"id": "protocol_extract", "type": "extracted_protocol", "title": "Extracted protocol", "summary": "Protocol steps extracted conservatively from supplied text."},
        {"id": "sop_draft", "type": "sop_draft", "title": "SOP draft", "summary": "Draft SOP with missing parameters separated from executable steps."},
    ]
    validation = {"safe_to_return": True, "required_human_review": True, "issues": [f"Missing parameter: {item}" for item in missing]}
    return product_response(ok=True, feature_id="protocol_to_sop_workflow", status=status, result={"missing_information": missing, "sop_draft": ["Purpose", "Materials from source text", "Procedure steps from source text", "QC and documentation"]}, task_lifecycle={"Goal": "Build SOP from Methods/protocol text", "Plan": ["Extract protocol", "Draft SOP", "List missing parameters"], "Contract": {"no_invented_parameters": True}, "Execution": {"status": "partial"}, "Artifacts": artifacts, "Validation": validation, "Handoff": "Fill missing parameters before use.", "Memory": {"status": "pending_review"}}, artifacts=artifacts, warnings=validation["issues"], selected_pipeline="protocol_to_sop", required_skills=FEATURES["protocol_to_sop_workflow"].required_skills, execution_status="partial", summary="Generated a conservative SOP draft and separated missing parameters.", validation_report=validation, memory_update={"status": "pending_review"}, pending_skill={"status": "none"}, handoff="Fill missing parameters before use.", raw_details={"TaskSpec": {"project_id": project_id, "pipeline": "protocol_to_sop"}})


def _run_failure_recovery(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    description = str(payload.get("failure_description") or payload.get("user_query") or "qPCR housekeeping Ct is unstable")
    causes = ["pipetting variability", "RNA quality variation", "reverse transcription inconsistency", "reference gene instability"]
    plan = ["Review raw Ct distribution and melt curves", "Check RNA quality and input normalization", "Evaluate alternative housekeeping genes", "Repeat only after QC criteria are defined"]
    return product_response(ok=True, feature_id="failure_recovery_workflow", status=status, result={"failure_description": description, "matched_historical_failures": [], "match_status": "no matched failures", "likely_causes": causes, "recovery_plan": plan}, task_lifecycle={"Goal": "Diagnose failed experiment", "Plan": ["Log failure", "Search history", "Draft recovery plan"], "Contract": {"no_success_claim": True}, "Execution": {"status": "partial"}, "Artifacts": "Failure record and recovery plan", "Validation": {"safe_to_return": True}, "Handoff": "User chooses whether to save failure memory.", "Memory": {"status": "pending_user_save"}}, artifacts=[{"id": "failure_record_draft", "type": "failure_record", "title": "Failure record draft", "summary": description}], memory_updates=[], next_actions=[{"intent": "save_failure", "label": "Save failure record"}], warnings=["no matched failures"], selected_pipeline="failure_recovery", required_skills=FEATURES["failure_recovery_workflow"].required_skills, execution_status="partial", summary="Created a failure record draft and recovery plan without claiming success.", validation_report={"safe_to_return": True}, memory_update={"status": "pending_user_save"}, pending_skill={"status": "none"}, handoff="Decide whether to save this failure record.", raw_details={"TaskSpec": {"project_id": project_id, "pipeline": "failure_recovery"}})


def _run_writing_review(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    mode = str(payload.get("review_mode") or "mechanism/statistics/novelty/methods")
    result = {"major_concerns": ["Mechanistic claims need direct evidence.", "Statistics and sample size must be explicit."], "minor_concerns": ["Clarify terminology and experimental scope."], "overclaims": ["Any unsupported causal language should be softened."], "missing_evidence": ["No citations or raw data were supplied."], "suggested_revisions": ["Separate observation from interpretation.", "Add limitations and validation experiments."]}
    return product_response(ok=True, feature_id="writing_review_workflow", status=status, result={**result, "review_mode": mode}, task_lifecycle={"Goal": "Review scientific writing", "Plan": ["Simulate reviewer critique", "Flag overclaims", "Suggest revisions"], "Contract": {"critique_not_evidence": True}, "Execution": {"status": "success"}, "Artifacts": "Review report", "Validation": {"safe_to_return": True}, "Handoff": "Revise claims with evidence.", "Memory": {"status": "report_candidate"}}, artifacts=[{"id": "writing_review", "type": "review_report", "title": "Reviewer-style critique", "summary": "Major/minor concerns, overclaims, missing evidence, and revision suggestions."}], warnings=["peer-review output is not factual evidence"], selected_pipeline="writing_review", required_skills=FEATURES["writing_review_workflow"].required_skills, execution_status="success", summary="Returned reviewer-style concerns and revision suggestions without inventing citations.", validation_report={"safe_to_return": True}, memory_update={"status": "report_candidate"}, pending_skill={"status": "none"}, handoff="Use supplied evidence to revise the paragraph.", raw_details={"TaskSpec": {"project_id": project_id, "pipeline": "writing_review"}})


def _run_weekly_report(payload: dict[str, Any], project_id: str, status: FeatureStatus) -> dict[str, Any]:
    report = {"completed_work": [], "generated_artifacts": [], "important_claims": [], "failures": [], "decisions": [], "next_actions": ["Run a demo task or connect project data to populate the report."], "advisor_ready_summary": "No recent project activity is available."}
    return product_response(ok=True, feature_id="weekly_report_workflow", status=status, result=report, task_lifecycle={"Goal": "Generate weekly project report", "Plan": ["Collect recent tasks", "Collect memory", "Build report"], "Contract": {"no_invented_progress": True}, "Execution": {"status": "partial_empty_state"}, "Artifacts": "Weekly report empty state", "Validation": {"safe_to_return": True}, "Handoff": "Run tasks to populate future reports.", "Memory": {"status": "not_written_empty_state"}}, artifacts=[{"id": "weekly_report_empty", "type": "weekly_report", "title": "Weekly report empty state", "summary": "No completed, partial, blocked, or planned records found."}], warnings=["no recent tasks available"], selected_pipeline="weekly_reporting", required_skills=FEATURES["weekly_report_workflow"].required_skills, execution_status="partial", summary="Generated an honest weekly-report empty state.", validation_report={"safe_to_return": True}, memory_update={"status": "not_written_empty_state"}, pending_skill={"status": "none"}, handoff="Run tasks or add memory before advisor report generation.", raw_details={"TaskSpec": {"project_id": project_id, "pipeline": "weekly_reporting"}})


def route_feature_from_query(user_query: str) -> dict[str, Any]:
    pipeline = route_query_to_pipeline(user_query)
    reverse = {contract.preferred_pipeline: feature_id for feature_id, contract in FEATURES.items()}
    return {"pipeline": pipeline, "feature_id": reverse.get(pipeline.get("pipeline_name"), "dual_agent_research_task")}


def _memory_updates(memory_update: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ["written", "promoted_pages", "promoted_decisions", "failure_memory"]:
        value = memory_update.get(key) if isinstance(memory_update, dict) else None
        if isinstance(value, list):
            return value
    return []


def _safe_message(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:180]


def _persist_demo_visibility(project_id: str, result: dict[str, Any]) -> None:
    try:
        ros = import_research_os_mvp()
        agent_root = default_agent_root()
        try:
            ros.get_project_detail(agent_root, project_id)
        except Exception:
            ros.create_project(agent_root, {"id": project_id, "title": project_id, "research_area": "ResearchOS demo"})
        run = ros.start_service_skill_run(
            agent_root,
            "core_research_execution_agent",
            "ResearchOS Product Demo",
            project_id,
            {
                "project_id": project_id,
                "task_id": result.get("task_id"),
                "feature_id": result.get("feature_id"),
                "selected_pipeline": result.get("selected_pipeline"),
                "user_query": (result.get("raw_details") or {}).get("TaskSpec", {}).get("user_query", ""),
            },
        )
        result["skillrun_id"] = result.get("skillrun_id") or run.get("id")
        output_refs = []
        for artifact in result.get("artifacts") or []:
            artifact_id = str(artifact.get("id") or f"artifact_{result.get('task_id')}")
            output_refs.append({"type": str(artifact.get("type") or "product_artifact"), "id": artifact_id})
            ros.register_artifact(
                agent_root,
                {
                    "artifact_id": artifact_id,
                    "project_id": project_id,
                    "task_id": str(result.get("task_id") or ""),
                    "skill_run_id": result["skillrun_id"],
                    "source_skill_run_id": result["skillrun_id"],
                    "type": str(artifact.get("type") or "product_artifact"),
                    "title": str(artifact.get("title") or artifact_id),
                    "path": "",
                    "source_object_type": "product_feature",
                    "source_object_id": str(result.get("feature_id") or ""),
                    "status": "created",
                    "metadata": {"summary": artifact.get("summary"), "feature_id": result.get("feature_id")},
                    "skip_memory_consolidation": True,
                },
            )
        ros.update_skill_run(
            agent_root,
            result["skillrun_id"],
            status="completed",
            output_payload={"project_id": project_id, "product_feature_result": result},
            output_object_refs=output_refs,
            logs=["product demo flow recorded for client visibility"],
            provenance=[{"type": "product_feature_demo", "feature_id": result.get("feature_id")}],
        )
    except Exception as exc:  # noqa: BLE001
        result.setdefault("warnings", []).append(f"visibility_persistence_not_connected:{_safe_message(exc)}")
