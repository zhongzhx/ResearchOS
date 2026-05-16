from __future__ import annotations

import re
from typing import Any


TASK_TYPES = {
    "literature_harvest",
    "weekly_research_digest",
    "kb_ingestion",
    "protocol_extraction",
    "data_analysis",
    "paper_recommendation",
    "project_learning_summary",
    "pdf_ingest",
    "kb_summary",
    "protocol_search",
    "experiment_plan",
    "report_generation",
    "memory_consolidation",
    "skill_learning",
    "inventory_scan",
    "citation_index_update",
}

TASK_STATUSES = {"pending", "running", "paused", "waiting_for_user", "completed", "failed", "cancelled"}
TASK_PRIORITIES = {"low", "medium", "high"}

LOW_RISK_AUTO_TASKS = {"pdf_ingest", "kb_summary", "memory_consolidation", "inventory_scan", "citation_index_update", "skill_learning", "report_generation"}
USER_CONFIRM_TASKS = {
    "literature_harvest",
    "protocol_search",
    "experiment_plan",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def task_skill_id(task_type: str) -> str:
    return {
        "literature_harvest": "core_keyword_research_harvest",
        "weekly_research_digest": "core_weekly_research_digest",
        "kb_ingestion": "core_build_user_research_kb",
        "protocol_extraction": "core_protocol_extraction",
        "data_analysis": "core_data_analysis",
        "paper_recommendation": "core_query_research_rag",
        "project_learning_summary": "core_query_research_rag",
        "pdf_ingest": "core_build_user_research_kb",
        "kb_summary": "core_diagnose_research_bottleneck",
        "protocol_search": "core_protocol_extraction",
        "experiment_plan": "core_design_experiment_matrix",
        "report_generation": "core_weekly_research_report",
        "memory_consolidation": "core_manage_agent_memory",
        "skill_learning": "core_manage_agent_memory",
        "inventory_scan": "core_manage_agent_memory",
        "citation_index_update": "core_manage_agent_memory",
    }.get(clean(task_type), "core_manage_agent_memory")


def task_requires_user_confirmation(task_type: str, payload: dict[str, Any] | None = None) -> bool:
    payload = payload or {}
    task_type = clean(task_type)
    if task_type in USER_CONFIRM_TASKS:
        return True
    if payload.get("requires_approval") or payload.get("activate_skill") or payload.get("confirmed_conclusion"):
        return True
    return False


def project_keywords(project: dict[str, Any]) -> list[str]:
    keywords = as_list(project.get("keywords") or project.get("keywords_json"))
    if not keywords:
        text = " ".join(
            clean(project.get(key))
            for key in ["title", "research_area", "short_description", "description"]
            if clean(project.get(key))
        )
        keywords = [part for part in re.split(r"[,;，；/\\\s]+", text) if len(clean(part)) >= 2]
    seen: set[str] = set()
    result: list[str] = []
    for item in keywords:
        keyword = clean(item)
        if keyword and keyword.lower() not in seen:
            seen.add(keyword.lower())
            result.append(keyword)
    return result[:8]


def _has_open_task(existing_tasks: list[dict[str, Any]], task_type: str) -> bool:
    for task in existing_tasks:
        if clean(task.get("task_type")) == task_type and clean(task.get("status")) in {"pending", "running", "waiting_for_user"}:
            return True
    return False


def propose_tasks_from_workspace(workspace_state: dict[str, Any], existing_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    project = workspace_state.get("project") or {}
    literature = workspace_state.get("literature") or {}
    data = workspace_state.get("data") or {}
    memory = workspace_state.get("memory") or {}
    tasks: list[dict[str, Any]] = []
    keywords = project_keywords(project)

    pdf_count = int(literature.get("pdf_files_found") or 0)
    refs = int(literature.get("references_count") or 0)
    chunks = int(literature.get("chunks_count") or 0)
    kb_entries = int(literature.get("kb_entries_count") or 0)
    not_ingested = int(literature.get("discovered_not_ingested") or 0)
    not_chunked = int(literature.get("registered_not_chunked") or 0)

    if refs == 0 and pdf_count == 0 and keywords and not _has_open_task(existing_tasks, "literature_harvest"):
        tasks.append(
            {
                "task_type": "literature_harvest",
                "status": "waiting_for_user",
                "priority": "medium",
                "input": {"keywords": keywords, "query": " ".join(keywords), "provider": "all"},
                "next_action": "确认后启动联网文献采集。",
            }
        )

    if (not_ingested > 0 or not_chunked > 0 or pdf_count > refs) and not _has_open_task(existing_tasks, "pdf_ingest"):
        tasks.append(
            {
                "task_type": "pdf_ingest",
                "status": "pending",
                "priority": "high",
                "input": {"include_article_analysis": True},
                "next_action": "自动解析已下载 PDF，并写入本地 KB/RAG。",
            }
        )

    if (chunks > 0 or kb_entries > 0) and int(memory.get("agent_memory_count") or 0) == 0 and not _has_open_task(existing_tasks, "memory_consolidation"):
        tasks.append(
            {
                "task_type": "memory_consolidation",
                "status": "pending",
                "priority": "medium",
                "input": {"trigger": "workspace_has_kb"},
                "next_action": "自动整理文献方向、方法图谱、缺口和下一步建议。",
            }
        )

    if (chunks > 0 or kb_entries > 0) and not _has_open_task(existing_tasks, "kb_summary"):
        tasks.append(
            {
                "task_type": "kb_summary",
                "status": "pending",
                "priority": "low",
                "input": {"summary_scope": "current_project_kb"},
                "next_action": "生成可复用的 KB 摘要草稿。",
            }
        )

    if int(data.get("experiments_count") or 0) == 0 and (chunks > 0 or refs > 0) and not _has_open_task(existing_tasks, "experiment_plan"):
        tasks.append(
            {
                "task_type": "experiment_plan",
                "status": "waiting_for_user",
                "priority": "medium",
                "input": {"source": "literature_context"},
                "next_action": "确认后基于文献证据生成实验方案草稿。",
            }
        )

    return tasks[:6]


def _keyword_hits(text: str, vocabulary: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in vocabulary if term.lower() in lower]


def consolidate_workspace_memory(workspace_state: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    event = event or {}
    project = workspace_state.get("project") or {}
    literature = workspace_state.get("literature") or {}
    data = workspace_state.get("data") or {}
    recent_refs = as_list(literature.get("recent_references"))[:30]
    title_text = " ".join(clean(ref.get("title")) for ref in recent_refs if isinstance(ref, dict))
    keywords = project_keywords(project)

    target_terms = _keyword_hits(
        title_text,
        ["TLR4", "NF-kB", "NLRP3", "STING", "RAW264.7", "BV2", "LPS", "macrophage", "microglia", "cytokine", "IL-6", "TNF"],
    )
    method_terms = _keyword_hits(
        title_text,
        ["qPCR", "ELISA", "Western blot", "RNA-seq", "flow cytometry", "LC-MS", "metabolomics", "immunofluorescence", "animal model"],
    )
    assay_terms = _keyword_hits(title_text, ["NO", "ROS", "cytokine", "luciferase", "cell viability", "inflammation"])

    pdf_count = int(literature.get("pdf_files_found") or 0)
    ref_count = int(literature.get("references_count") or 0)
    chunk_count = int(literature.get("chunks_count") or 0)
    kb_count = int(literature.get("kb_entries_count") or 0)

    gaps: list[dict[str, Any]] = []
    if pdf_count > ref_count:
        gaps.append({"gap": f"已发现 {pdf_count} 个 PDF，但只有 {ref_count} 篇文献记录完成入库。", "priority": "high", "source": "workspace"})
    if ref_count > 0 and chunk_count == 0:
        gaps.append({"gap": "已有文献记录，但还没有可检索 chunks。", "priority": "high", "source": "RAG"})
    if kb_count == 0 and chunk_count > 0:
        gaps.append({"gap": "已有 chunks，但 KB 条目还需要整理。", "priority": "medium", "source": "KB"})
    if int(data.get("experiments_count") or 0) == 0:
        gaps.append({"gap": "当前项目尚无本项目实验记录，不能把文献结论当成本项目结论。", "priority": "medium", "source": "project_data"})

    project_title = clean(project.get("title")) or clean(workspace_state.get("active_project_id")) or "当前项目"
    summary = f"{project_title}: PDF {pdf_count} 个，文献记录 {ref_count} 篇，RAG chunks {chunk_count} 个，KB 条目 {kb_count} 个，实验记录 {int(data.get('experiments_count') or 0)} 条。"
    direction = "；".join(keywords[:6]) if keywords else clean(project.get("research_area")) or "未设置明确方向"

    next_actions = []
    if pdf_count > ref_count or int(literature.get("registered_not_chunked") or 0) > 0:
        next_actions.append("优先完成 PDF 解析、切块和 KB/RAG 入库。")
    if chunk_count > 0:
        next_actions.append("按模型、靶点、方法和指标生成一次文献缺口分析。")
    if int(data.get("experiments_count") or 0) == 0:
        next_actions.append("在形成项目结论前，先补充实验记录或设计验证实验。")

    memory_content = "\n".join(
        [
            summary,
            f"方向摘要: {direction}",
            f"高频靶点/对象: {', '.join(target_terms[:12]) or '待从文献中进一步提取'}",
            f"常见方法: {', '.join(method_terms[:12]) or '待从文献中进一步提取'}",
            f"主要缺口: {'; '.join(item['gap'] for item in gaps[:5]) or '暂无明显缺口'}",
        ]
    )
    literature_summary = f"当前文献状态：PDF {pdf_count} 个，reference {ref_count} 篇，chunk {chunk_count} 个，KB entry {kb_count} 个。"
    project_risks = []
    if int(data.get("experiments_count") or 0) == 0:
        project_risks.append({"risk": "项目还没有本地实验记录，文献结论不能直接当成本项目结论。", "priority": "medium", "source": "workspace"})
    if pdf_count > ref_count:
        project_risks.append({"risk": "存在已下载但未完成入库的 PDF，RAG 总结覆盖不完整。", "priority": "high", "source": "workspace"})
    feed_items = []
    if chunk_count > 0 or kb_count > 0:
        feed_items.append(
            {
                "type": "literature_update",
                "title": "文献知识库已可用于总结",
                "message": literature_summary,
                "priority": "medium",
                "actions": [{"label": "总结文献", "action": "ask_agent", "prompt": "总结当前已入库文献"}],
            }
        )
    if gaps:
        feed_items.append(
            {
                "type": "gap_alert",
                "title": "发现项目缺口",
                "message": clean(gaps[0].get("gap")),
                "priority": clean(gaps[0].get("priority")) or "medium",
                "actions": [{"label": "查看下一步", "action": "ask_agent", "prompt": "下一步做什么"}],
            }
        )

    return {
        "project_summary_update": summary,
        "direction_summary_update": direction,
        "literature_summary_update": literature_summary,
        "key_targets": target_terms[:12],
        "methods_map": method_terms[:12],
        "assay_map": assay_terms[:12],
        "knowledge_gaps": gaps[:8],
        "project_risks": project_risks[:8],
        "next_actions": next_actions[:6],
        "memory_writes": [
            {
                "memory_type": "project_operating_summary",
                "title": "Project operating summary",
                "content": memory_content,
                "structured_content": {
                    "summary": summary,
                    "direction": direction,
                    "key_targets": target_terms[:12],
                    "methods_map": method_terms[:12],
                    "assay_map": assay_terms[:12],
                    "knowledge_gaps": gaps[:8],
                    "project_risks": project_risks[:8],
                    "next_actions": next_actions[:6],
                    "event": event,
                },
                "confidence": 0.72,
                "trust_level": "raw_extracted",
            }
        ],
        "review_queue_items": [
            {
                "type": "memory_review",
                "reason": item["gap"],
                "priority": item.get("priority", "medium"),
                "status": "pending",
            }
            for item in gaps
            if item.get("priority") in {"high", "medium"}
        ],
        "feed_items": feed_items,
    }


def build_skill_draft(
    project_id: str,
    user_request: str,
    skill_runs: list[dict[str, Any]],
    execution_memory: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    recent_runs = [run for run in skill_runs if clean(run.get("status")) in {"completed", "running"}][:8]
    steps = []
    tools = []
    for run in recent_runs:
        skill_name = clean(run.get("skill_name") or run.get("skill_id"))
        if skill_name:
            steps.append({"step": f"Run {skill_name}", "source_skill_run_id": clean(run.get("id"))})
            tools.append(skill_name)
    for item in execution_memory[:6]:
        lesson = clean(item.get("reusable_lesson") or item.get("task_title"))
        if lesson:
            steps.append({"step": lesson, "source_execution_memory_id": clean(item.get("id"))})
    artifact_types = sorted({clean(item.get("type")) for item in artifacts if clean(item.get("type"))})
    return {
        "project_id": project_id,
        "skill_name": clean(user_request)[:64] or "Learned Research Workflow",
        "purpose": "把当前项目已经执行过的任务流程整理成可复用 skill 草稿，等待用户审阅后再激活。",
        "input_schema": {"project_id": "string", "keywords_or_files": "array|string optional", "user_goal": "string"},
        "steps": steps[:12] or [{"step": "Review recent task history and define repeatable workflow."}],
        "tools_required": sorted(set(tools))[:12],
        "output_schema": {"artifacts": "array", "memory_updates": "array", "review_items": "array"},
        "failure_modes": ["缺少真实执行历史", "输入文件未入库", "用户未确认 memory 写入", "外部联网检索失败"],
        "test_cases": [
            {"name": "replay_recent_workflow", "expected": "produces artifacts and draft memory without confirmed claims"},
            {"name": "missing_input_files", "expected": "returns waiting_for_user instead of fabricating outputs"},
        ],
        "status": "draft",
        "source_summary": {
            "skill_runs": [clean(run.get("id")) for run in recent_runs],
            "execution_memory": [clean(item.get("id")) for item in execution_memory[:8]],
            "artifact_types": artifact_types,
        },
    }


def feed_item_for_task(project_id: str, task: dict[str, Any], message: str = "") -> dict[str, Any]:
    task_type = clean(task.get("task_type"))
    status = clean(task.get("status"))
    return {
        "type": "task_update",
        "title": f"{task_type} 任务：{status}",
        "message": message or clean(task.get("next_action")) or f"任务 {clean(task.get('task_id'))} 状态为 {status}。",
        "priority": clean(task.get("priority")) or "medium",
        "project_id": project_id,
        "related_sources": [{"source_type": "agent_task", "id": clean(task.get("task_id"))}],
        "actions": [{"label": "查看任务", "action": "open_task", "task_id": clean(task.get("task_id"))}],
    }
