from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from researchos_agent_prompt import compose_researchos_prompt, normalize_prompt_policy


SUPPORTED_TASK_TYPES = {
    "literature_mining",
    "paper_to_protocol",
    "protocol_extraction",
    "sop_generation",
    "kit_manual_parsing",
    "experiment_matrix_design",
    "qpcr_analysis",
    "elisa_analysis",
    "WB_record_structuring",
    "LCMS_feature_table_structuring",
    "animal_record_structuring",
    "experiment_log_structuring",
    "data_contextualization",
    "data_qc",
    "result_analysis",
    "claim_generation",
    "claim_evidence_review",
    "project_gap_analysis",
    "peer_review_simulation",
    "weekly_report",
    "weekly_literature_digest",
    "memory_update",
    "conflict_detection",
    "natural_language_workflow_planning",
    "reagent_calculation",
    "plate_layout",
    "result_narrative",
    "manuscript_draft",
}

TASK_PROMPT_POLICY = {
    "paper_to_protocol": "protocol_extraction",
    "protocol_extraction": "protocol_extraction",
    "sop_generation": "sop_generation",
    "kit_manual_parsing": "protocol_extraction",
    "experiment_matrix_design": "workflow_planning",
    "qPCR_analysis": "qPCR_analysis",
    "ELISA_analysis": "ELISA_analysis",
    "WB_record_structuring": "data_contextualization",
    "LCMS_feature_table_structuring": "lcms_data_analysis",
    "animal_record_structuring": "data_contextualization",
    "experiment_log_structuring": "experiment_log",
    "data_contextualization": "data_contextualization",
    "data_qc": "data_qc",
    "result_analysis": "result_analysis",
    "claim_generation": "claim_generation",
    "claim_evidence_review": "claim_evidence_review",
    "project_gap_analysis": "project_gap_analysis",
    "peer_review_simulation": "peer_review",
    "weekly_report": "weekly_research_report",
    "weekly_literature_digest": "weekly_research_digest",
    "literature_mining": "literature_mining_to_kb",
    "memory_update": "memory_update",
    "conflict_detection": "conflict_detection",
    "natural_language_workflow_planning": "workflow_planning",
    "reagent_calculation": "reagent_calculation",
    "plate_layout": "plate_layout",
    "result_narrative": "result_narrative",
    "manuscript_draft": "scientific_writing",
}

SUPPORTED_PROMPT_POLICIES = {
    "backend_llm_guardrails",
    "base_identity",
    "writing_assistant",
    "workflow_planning",
    "scientific_writing",
    "weekly_digest",
    "weekly_research_report",
    "weekly_research_digest",
    "literature_rag",
    "literature_mining_to_kb",
    "experiment_log",
    "protocol_extraction",
    "sop_generation",
    "project_retrospective",
    "project_gap_analysis",
    "peer_review",
    "memory_update",
    "conflict_detection",
    "claim_generation",
    "claim_evidence_review",
    "result_analysis",
    "data_contextualization",
    "data_qc",
    "lcms_data_analysis",
    "qPCR_analysis",
    "ELISA_analysis",
    "reagent_calculation",
    "plate_layout",
    "result_narrative",
}

SKILL_TASK_MAP = {
    "PaperToProtocolSkill": "paper_to_protocol",
    "KitManualParserSkill": "kit_manual_parsing",
    "CSVTemplateParserSkill": "data_contextualization",
    "qPCRAnalysisSkill": "qPCR_analysis",
    "ELISAAnalysisSkill": "ELISA_analysis",
    "WBRecordStructuringSkill": "WB_record_structuring",
    "LCMSFeatureTableStructuringSkill": "LCMS_feature_table_structuring",
    "AnimalRecordStructuringSkill": "animal_record_structuring",
    "ExperimentLogStructuringSkill": "experiment_log_structuring",
    "ReagentCalculationSkill": "reagent_calculation",
    "PlateLayoutSkill": "plate_layout",
    "DataNamingConventionSkill": "data_contextualization",
    "WeeklyReportSkill": "weekly_report",
    "ProjectGapAnalysisSkill": "project_gap_analysis",
    "MemoryUpdateSkill": "memory_update",
    "ConflictDetectionSkill": "conflict_detection",
}

CORE_SKILL_TASK_MAP = {
    "keyword-research-harvest": "literature_mining",
    "weekly-research-digest": "weekly_literature_digest",
    "weekly-research-report": "weekly_report",
    "protocol-extraction": "protocol_extraction",
    "sop-generation": "sop_generation",
    "design-experiment-matrix": "experiment_matrix_design",
    "parse-scientific-data": "data_contextualization",
    "analyze-experiment-results": "result_analysis",
    "result-narrative": "result_narrative",
    "peer-review-simulation": "peer_review_simulation",
    "diagnose-research-bottleneck": "project_gap_analysis",
    "manage-agent-memory": "memory_update",
    "failure-log": "experiment_log_structuring",
    "ingest-research-evidence": "claim_evidence_review",
    "plan-research-route": "natural_language_workflow_planning",
}

AGENT_TASK_MAP = {
    "ProtocolAgent": "protocol_extraction",
    "DataQCAgent": "data_qc",
    "ReagentCalculatorAgent": "reagent_calculation",
    "NamingConventionAgent": "data_contextualization",
    "ReportAgent": "weekly_report",
    "MemoryUpdateAgent": "memory_update",
    "ConflictDetectionAgent": "conflict_detection",
    "ProjectGapAnalysisAgent": "project_gap_analysis",
    "LiteratureAgent": "literature_mining",
    "WorkflowAgent": "natural_language_workflow_planning",
    "WritingAgent": "manuscript_draft",
}

FILE_CATEGORY_PATTERNS = [
    (r"\bq\s*pcr\b|rt[- ]?qpcr|ct value|cq value", "qPCR_analysis"),
    (r"\belisa\b|plate reader|standard curve", "ELISA_analysis"),
    (r"\blc[- ]?ms\b|feature table|m/z|metabolomics", "LCMS_feature_table_structuring"),
    (r"western blot|\bwb\b|imagej|protein band", "WB_record_structuring"),
    (r"animal|body weight|dose record|mouse|mice|rat", "animal_record_structuring"),
    (r"kit manual|vendor manual|datasheet", "kit_manual_parsing"),
    (r"protocol|methods|sop", "protocol_extraction"),
    (r"experiment log|eln|lab note|failure", "experiment_log_structuring"),
    (r"csv|xlsx|instrument export|data file", "data_contextualization"),
    (r"pdf|paper|article|literature|reference", "literature_mining"),
]

MESSAGE_INTENT_PATTERNS = [
    (r"结果段|result narrative|figure legend|图注", "result_narrative"),
    (r"manuscript|论文|写作|引言|讨论|摘要", "manuscript_draft"),
    (r"证据|evidence|是否支持|能否确认|whether.*claim|claim.*confirm|confirmed", "claim_evidence_review"),
    (r"文献|paper|literature|pubmed|pmc|crossref|openalex|harvest|mine", "literature_mining"),
    (r"protocol|methods|方法|实验步骤|提取.*步骤", "protocol_extraction"),
    (r"sop|标准操作", "sop_generation"),
    (r"kit|试剂盒|manual|说明书", "kit_manual_parsing"),
    (r"matrix|实验矩阵|设计.*实验|分组设计", "experiment_matrix_design"),
    (r"qpcr|rt[- ]?qpcr|ct值|ct value|cq", "qPCR_analysis"),
    (r"elisa|标准曲线|吸光度|od450", "ELISA_analysis"),
    (r"western blot|\bwb\b|条带", "WB_record_structuring"),
    (r"lc[- ]?ms|代谢组|feature table|m/z", "LCMS_feature_table_structuring"),
    (r"动物|小鼠|大鼠|体重|给药", "animal_record_structuring"),
    (r"实验记录|实验日志|复盘|失败记录|lab note|eln", "experiment_log_structuring"),
    (r"data context|上下文|样品.*文件|文件.*样品", "data_contextualization"),
    (r"\bqc\b|质量控制|异常值|outlier", "data_qc"),
    (r"分析.*结果|result analysis|统计|显著性", "result_analysis"),
    (r"生成.*结论|claim|conclusion|结论", "claim_generation"),
    (r"gap|缺口|卡在哪|瓶颈|bottleneck", "project_gap_analysis"),
    (r"peer review|审稿|挑错|风险", "peer_review_simulation"),
    (r"周报|weekly report|本周总结", "weekly_report"),
    (r"文献周报|weekly digest|digest", "weekly_literature_digest"),
    (r"记忆|memory|写入项目|更新记忆", "memory_update"),
    (r"冲突|conflict|矛盾|不一致", "conflict_detection"),
    (r"workflow|工作流|安排任务|计划", "natural_language_workflow_planning"),
    (r"reagent|试剂|稀释|浓度|配液", "reagent_calculation"),
    (r"plate|孔板|96孔|layout", "plate_layout"),
]


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _row_to_dict(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


def _normalize_task_type(value: Any) -> str:
    task = _clean(value).replace("-", "_").replace(" ", "_")
    if not task:
        return ""
    lower = task.lower()
    for supported in SUPPORTED_TASK_TYPES:
        if lower == supported.lower():
            return supported
    return task if task in SUPPORTED_TASK_TYPES else ""


def _match_patterns(text: str, patterns: list[tuple[str, str]]) -> str:
    haystack = _clean(text)
    if not haystack:
        return ""
    for pattern, task_type in patterns:
        if re.search(pattern, haystack, re.IGNORECASE):
            return task_type
    return ""


def infer_task_type(
    user_message: str | None = None,
    file_context: dict[str, Any] | None = None,
    workflow_step: dict[str, Any] | None = None,
    skill_name: str | None = None,
    agent_type: str | None = None,
    file_category: str | None = None,
) -> str:
    """Infer a ResearchOS task type using deterministic priority routing."""
    workflow_step = workflow_step or {}
    file_context = file_context or {}

    for explicit in [
        workflow_step.get("task_type"),
        workflow_step.get("analysis_skill_id"),
        file_context.get("task_type"),
    ]:
        task = _normalize_task_type(explicit)
        if task:
            return task
        skill_task = _task_from_skill_name(_clean(explicit))
        if skill_task:
            return skill_task

    for candidate in [skill_name, workflow_step.get("skill_name"), workflow_step.get("agent_type"), agent_type]:
        skill_task = _task_from_skill_name(_clean(candidate))
        if skill_task:
            return skill_task
        if _clean(candidate) in AGENT_TASK_MAP:
            return AGENT_TASK_MAP[_clean(candidate)]

    category_task = _match_patterns(
        " ".join([_clean(file_category), _clean(file_context.get("file_category")), _clean(file_context.get("category")), _clean(file_context.get("filename"))]),
        FILE_CATEGORY_PATTERNS,
    )
    if category_task:
        return category_task

    for explicit in [file_context.get("explicit_task_type"), file_context.get("prompt_policy")]:
        task = _normalize_task_type(explicit)
        if task:
            return task

    message_task = _match_patterns(_clean(user_message), MESSAGE_INTENT_PATTERNS)
    return message_task or "natural_language_workflow_planning"


def _task_from_skill_name(value: str) -> str:
    if not value:
        return ""
    for key, task_type in SKILL_TASK_MAP.items():
        if value == key or key.lower() in value.lower():
            return task_type
    normalized = value.replace("core_skill:", "").strip()
    for key, task_type in CORE_SKILL_TASK_MAP.items():
        if normalized == key or key in normalized:
            return task_type
    return ""


def resolve_prompt_policy(
    task_type: str,
    skill_name: str | None = None,
    agent_type: str | None = None,
    file_category: str | None = None,
) -> str:
    explicit_policy = normalize_prompt_policy(task_type)
    if explicit_policy in SUPPORTED_PROMPT_POLICIES:
        return explicit_policy
    task = _normalize_task_type(task_type) or infer_task_type(skill_name=skill_name, agent_type=agent_type, file_category=file_category)
    return normalize_prompt_policy(TASK_PROMPT_POLICY.get(task, task or "backend_llm_guardrails"))


def load_skill_prompt_from_registry(conn: sqlite3.Connection, skill_name: str | None = None, skill_id: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if skill_id:
        row = _row_to_dict(conn.execute("SELECT * FROM skill_registry WHERE skill_id=?", (_clean(skill_id),)).fetchone())
    if not row and skill_name:
        row = _row_to_dict(
            conn.execute(
                "SELECT * FROM skill_registry WHERE skill_name=? OR handler=? OR handler_ref=? ORDER BY version DESC LIMIT 1",
                (_clean(skill_name), _clean(skill_name), _clean(skill_name)),
            ).fetchone()
        )
    if not row and skill_name:
        pattern = f"%{_clean(skill_name)}%"
        row = _row_to_dict(
            conn.execute(
                "SELECT * FROM skill_registry WHERE skill_name LIKE ? OR handler LIKE ? OR handler_ref LIKE ? ORDER BY version DESC LIMIT 1",
                (pattern, pattern, pattern),
            ).fetchone()
        )
    if not row:
        return {}
    return {
        "skill_id": _clean(row.get("skill_id")),
        "skill_name": _clean(row.get("skill_name")),
        "source_path": _clean(row.get("source_path")),
        "prompt_template": _clean(row.get("prompt_template")),
        "instruction_body": _clean(row.get("instruction_body")),
        "citation_policy": _clean(row.get("citation_policy")),
        "memory_policy": _clean(row.get("memory_policy")),
        "required_models": _json_loads(row.get("required_models_json"), []),
        "handler_ref": _clean(row.get("handler_ref") or row.get("handler")),
    }


def compose_runtime_prompt(
    conn: sqlite3.Connection | None = None,
    *,
    language: str = "zh",
    policy: str | None = None,
    user_message: str | None = None,
    task_type: str | None = None,
    skill_name: str | None = None,
    skill_id: str | None = None,
    agent_type: str | None = None,
    workflow_step: dict[str, Any] | None = None,
    workflow_step_id: str | None = None,
    file_context: dict[str, Any] | None = None,
    file_id: str | None = None,
    file_category: str | None = None,
    project_id: str | None = None,
    prompt_context: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_context = prompt_context or {}
    file_context = dict(file_context or {})
    workflow_step = dict(workflow_step or {})
    if conn:
        if workflow_step_id and not workflow_step:
            workflow_step = _load_workflow_step(conn, workflow_step_id)
        if file_id and not file_context:
            file_context = _load_file_context(conn, file_id)
    inferred_task = _normalize_task_type(task_type) or infer_task_type(
        user_message=user_message,
        file_context=file_context,
        workflow_step=workflow_step,
        skill_name=skill_name,
        agent_type=agent_type,
        file_category=file_category,
    )
    prompt_policy = resolve_prompt_policy(policy or inferred_task, skill_name=skill_name, agent_type=agent_type, file_category=file_category)
    composed = compose_researchos_prompt(language, prompt_policy, include_backend_guardrails=True)
    skill_prompt = load_skill_prompt_from_registry(conn, skill_name=skill_name, skill_id=skill_id) if conn else {}
    resolved_skill_name = skill_prompt.get("skill_name") or _clean(skill_name)
    prompt_files = list(composed.get("prompt_files") or [])
    if skill_prompt.get("source_path"):
        prompt_files.append(skill_prompt["source_path"])
    skill_parts = []
    if skill_prompt.get("source_path"):
        skill_parts.append("Skill source path:\n" + skill_prompt["source_path"])
    if skill_prompt.get("prompt_template"):
        skill_parts.append("Skill prompt template:\n" + skill_prompt["prompt_template"])
    if skill_prompt.get("instruction_body"):
        skill_parts.append("Skill instruction body:\n" + skill_prompt["instruction_body"][:6000])
    skill_prompt_source = "skill_registry" if skill_parts else ("researchos_agent_prompt" if not composed.get("fallback_used") else "fallback")
    citation_policy = skill_prompt.get("citation_policy") or "Cite local files, references, chunks, claims, and provenance records for every scientific claim."
    memory_policy = skill_prompt.get("memory_policy") or "Use project memory only for project answers; do not promote private project facts into system memory."
    context_sections = _context_sections(
        conn,
        project_id=_clean(project_id),
        file_context=file_context,
        workflow_step=workflow_step,
        prompt_context=prompt_context,
        output_schema=output_schema,
    )
    warnings = []
    if skill_prompt_source == "fallback":
        warnings.append("No task-specific prompt found; using backend default prompt.")
    system_prompt = "\n\n".join(
        part
        for part in [
            composed["prompt"],
            "\n\n".join(skill_parts),
            f"Task type: {inferred_task}",
            f"Citation policy: {citation_policy}",
            f"Memory policy: {memory_policy}",
            "Claim/evidence rules: unsupported claims must be draft, weak, or unsupported; never create confirmed claims from LLM output; require human confirmation for confirmed conclusions.",
            "Workflow constraints: respect workflow step inputs, required tools, output targets, and project isolation. Preserve raw files and provenance identifiers.",
            "Output schema constraints: return valid JSON when JSON is requested; include evidence/source ids when available; mark missing context explicitly.",
            "Human confirmation rules: protocol execution, memory promotion, project decisions, and claim confirmation require explicit human approval.",
            context_sections,
            "\n".join(warnings),
        ]
        if part
    ).strip()
    return {
        "system_prompt": system_prompt,
        "prompt_policy": prompt_policy,
        "prompt_language": "zh" if language.lower().startswith("zh") else "en",
        "prompt_files": prompt_files,
        "skill_prompt_source": skill_prompt_source,
        "citation_policy": citation_policy,
        "memory_policy": memory_policy,
        "task_type": inferred_task,
        "resolved_skill_name": resolved_skill_name,
        "warnings": warnings,
    }


def _load_workflow_step(conn: sqlite3.Connection, workflow_step_id: str) -> dict[str, Any]:
    row = _row_to_dict(conn.execute("SELECT * FROM workflow_steps WHERE id=?", (_clean(workflow_step_id),)).fetchone())
    if not row:
        return {}
    row["tool_required"] = _json_loads(row.get("tool_required_json"), [])
    return row


def _load_file_context(conn: sqlite3.Connection, file_id: str) -> dict[str, Any]:
    row = _row_to_dict(conn.execute("SELECT * FROM research_files WHERE id=?", (_clean(file_id),)).fetchone())
    if not row:
        return {}
    return {
        "id": row.get("id"),
        "filename": row.get("original_filename") or row.get("stored_filename"),
        "file_category": row.get("detected_document_category") or row.get("category"),
        "summary": row.get("summary"),
    }


def _context_sections(
    conn: sqlite3.Connection | None,
    *,
    project_id: str,
    file_context: dict[str, Any],
    workflow_step: dict[str, Any],
    prompt_context: dict[str, Any],
    output_schema: dict[str, Any] | None,
) -> str:
    sections: list[str] = []
    if project_id and conn:
        sections.append(_project_memory_summary(conn, project_id))
        sections.append(_data_context_summary(conn, project_id, _clean(file_context.get("id"))))
    if workflow_step:
        sections.append("Workflow step context:\n" + json.dumps(workflow_step, ensure_ascii=False, indent=2)[:3000])
    if file_context:
        sections.append("File context:\n" + json.dumps(file_context, ensure_ascii=False, indent=2)[:3000])
    if prompt_context:
        sections.append("Additional prompt context:\n" + json.dumps(prompt_context, ensure_ascii=False, indent=2)[:4000])
    if output_schema:
        sections.append("Required output schema:\n" + json.dumps(output_schema, ensure_ascii=False, indent=2)[:3000])
    return "\n\n".join(part for part in sections if part)


def _project_memory_summary(conn: sqlite3.Connection, project_id: str) -> str:
    try:
        rows = conn.execute(
            "SELECT entity_type, canonical_name, confidence, trust_level FROM memory_entities WHERE project_id=? AND status='active' ORDER BY updated_at DESC LIMIT 8",
            (project_id,),
        ).fetchall()
    except Exception:
        rows = []
    items = [_row_to_dict(row) for row in rows]
    if not items:
        return "Project memory summary: no active project memory found."
    return "Project memory summary:\n" + json.dumps(items, ensure_ascii=False, indent=2)


def _data_context_summary(conn: sqlite3.Connection, project_id: str, file_id: str = "") -> str:
    try:
        if file_id:
            rows = conn.execute("SELECT * FROM data_contexts WHERE project_id=? AND file_id=? LIMIT 5", (project_id, file_id)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM data_contexts WHERE project_id=? ORDER BY updated_at DESC LIMIT 5", (project_id,)).fetchall()
    except Exception:
        rows = []
    items = [_row_to_dict(row) for row in rows]
    if not items:
        return "Data context summary: no DataContext records found for this scope; mark missing context explicitly."
    slim = [
        {
            "id": item.get("id"),
            "file_id": item.get("file_id"),
            "experiment_id": item.get("experiment_id"),
            "protocol_id": item.get("protocol_id"),
            "assay_type": item.get("assay_type"),
            "context_status": item.get("context_status"),
            "missing_metadata": _json_loads(item.get("missing_metadata_json"), []),
        }
        for item in items
    ]
    return "Data context summary:\n" + json.dumps(slim, ensure_ascii=False, indent=2)
