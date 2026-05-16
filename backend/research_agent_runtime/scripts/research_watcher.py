from __future__ import annotations

import re
from typing import Any


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _project_keywords(project: dict[str, Any]) -> list[str]:
    keywords = _as_list(project.get("keywords") or project.get("keywords_json"))
    if not keywords:
        text = " ".join([_clean(project.get("title")), _clean(project.get("research_area")), _clean(project.get("short_description"))])
        keywords = [item for item in re.split(r"[,;，；/\\\s]+", text) if len(item) >= 2]
    seen: set[str] = set()
    result: list[str] = []
    for item in keywords:
        keyword = _clean(item)
        if keyword and keyword.lower() not in seen:
            seen.add(keyword.lower())
            result.append(keyword)
    return result[:8]


def analyze_project_state(workspace_state: dict[str, Any]) -> list[str]:
    literature = workspace_state.get("literature") or {}
    data = workspace_state.get("data") or {}
    tasks = workspace_state.get("tasks") or {}
    memory = workspace_state.get("memory") or {}
    tags: list[str] = []

    pdf_count = int(literature.get("pdf_files_found") or 0)
    reference_count = int(literature.get("references_count") or 0)
    chunks_count = int(literature.get("chunks_count") or 0)
    kb_count = int(literature.get("kb_entries_count") or 0)
    experiments_count = int(data.get("experiments_count") or 0)
    data_files_count = int(data.get("data_files_count") or 0)
    conclusions_count = int(data.get("analysis_results_count") or 0)

    if reference_count == 0 and pdf_count == 0:
        tags.append("no_literature")
    if pdf_count > reference_count or int(literature.get("discovered_not_ingested") or 0) > 0:
        tags.append("literature_downloaded_not_ingested")
    if reference_count > 0 and (chunks_count == 0 or int(literature.get("registered_not_chunked") or 0) > 0):
        tags.append("registered_not_chunked")
    if chunks_count > 0 and kb_count == 0:
        tags.append("chunked_not_indexed")
    if reference_count > 0 and chunks_count > 0 and int(memory.get("agent_memory_count") or 0) == 0:
        tags.append("literature_ingested_not_summarized")
    if chunks_count > 0 or kb_count > 0:
        tags.append("has_kb_needs_gap_analysis")
    if experiments_count > 0 and conclusions_count == 0:
        tags.append("has_experiments_needs_claims")
    if data_files_count > 0 and conclusions_count == 0:
        tags.append("has_data_needs_analysis")
    if experiments_count == 0:
        tags.append("needs_protocols")
    if any(_clean(task.get("status")) in {"running", "pending", "waiting_approval"} for task in _as_list(tasks.get("running"))):
        tags.append("has_unfinished_tasks")
    if reference_count > 0 or experiments_count > 0:
        tags.append("ready_for_weekly_report")
    return tags


def summarize_project_state(workspace_state: dict[str, Any], state_tags: list[str]) -> str:
    project = workspace_state.get("project") or {}
    literature = workspace_state.get("literature") or {}
    data = workspace_state.get("data") or {}
    tasks = workspace_state.get("tasks") or {}
    title = _clean(project.get("title")) or "当前项目"
    return (
        f"{title}: PDF {int(literature.get('pdf_files_found') or 0)} 个，"
        f"已入库文献 {int(literature.get('references_count') or 0)} 篇，"
        f"可检索 chunks {int(literature.get('chunks_count') or 0)} 个，"
        f"实验 {int(data.get('experiments_count') or 0)} 条，"
        f"数据文件 {int(data.get('data_files_count') or 0)} 个，"
        f"运行中任务 {len(_as_list(tasks.get('running')))} 个。"
    )


def literature_scout(workspace_state: dict[str, Any]) -> dict[str, Any]:
    project = workspace_state.get("project") or {}
    literature = workspace_state.get("literature") or {}
    keywords = _project_keywords(project)
    recent_refs = _as_list(literature.get("recent_references"))[:12]
    high_value: list[dict[str, Any]] = []
    non_oa: list[dict[str, Any]] = []

    for ref in recent_refs:
        title = _clean(ref.get("title"))
        year = _clean(ref.get("year"))
        access = _clean(ref.get("access_status")).lower()
        score = 0
        lower_title = title.lower()
        if any(keyword.lower() in lower_title for keyword in keywords):
            score += 2
        if year and year.isdigit() and int(year) >= 2021:
            score += 1
        if any(term in lower_title for term in ["review", "protocol", "mechanism", "guideline", "assay"]):
            score += 1
        item = {
            "reference_id": _clean(ref.get("id")),
            "title": title,
            "year": year,
            "doi": _clean(ref.get("doi")),
            "reason": "与项目关键词、年份或方法价值匹配。",
            "source": "KB/reference",
            "score": score,
        }
        if score > 0:
            high_value.append(item)
        if access in {"closed", "paywalled", "unknown", "metadata_only"} and not _clean(ref.get("full_text_path")):
            non_oa.append({**item, "reason": "该文献可能没有本地全文，需要用户提供 PDF 后才能入库。"})

    search_queries = []
    if keywords:
        search_queries.append(" ".join(keywords[:5]))
        if len(keywords) >= 2:
            search_queries.append(f"{keywords[0]} {keywords[1]} review")
            search_queries.append(f"{keywords[0]} {keywords[1]} protocol")

    return {
        "search_queries": search_queries[:3],
        "oa_downloaded": [],
        "non_oa_requests": non_oa[:6],
        "high_value_papers": sorted(high_value, key=lambda item: int(item.get("score") or 0), reverse=True)[:8],
        "reason": "根据项目关键词、已入库文献标题、年份和方法关键词生成。",
    }


def gap_analyzer(workspace_state: dict[str, Any], state_tags: list[str]) -> list[dict[str, Any]]:
    literature = workspace_state.get("literature") or {}
    data = workspace_state.get("data") or {}
    gaps: list[dict[str, Any]] = []
    if "no_literature" in state_tags:
        gaps.append({"gap": "项目还没有本地文献证据。", "priority": "high", "source": "workspace"})
    if "literature_downloaded_not_ingested" in state_tags:
        gaps.append({"gap": f"发现 PDF {int(literature.get('pdf_files_found') or 0)} 个，但部分还未解析入库。", "priority": "high", "source": "workspace"})
    if "registered_not_chunked" in state_tags or "chunked_not_indexed" in state_tags:
        gaps.append({"gap": "已有文献记录尚未完全切块或进入可检索 KB。", "priority": "medium", "source": "workspace"})
    if int(data.get("experiments_count") or 0) == 0:
        gaps.append({"gap": "当前项目还没有实验记录，不能形成项目级实验结论。", "priority": "medium", "source": "workspace"})
    if int(data.get("data_files_count") or 0) > 0 and int(data.get("analysis_results_count") or 0) == 0:
        gaps.append({"gap": "已有数据文件但缺少分析结果或结论记录。", "priority": "medium", "source": "workspace"})
    if "has_kb_needs_gap_analysis" in state_tags:
        gaps.append({"gap": "已有可检索文献，建议按模型、方法、靶点和指标做一次缺口分析。", "priority": "medium", "source": "KB"})
    return gaps[:8]


def build_recommended_actions(workspace_state: dict[str, Any], state_tags: list[str], scout: dict[str, Any]) -> list[dict[str, Any]]:
    project = workspace_state.get("project") or {}
    keywords = _project_keywords(project)
    actions: list[dict[str, Any]] = []
    if "no_literature" in state_tags:
        actions.append({"label": "启动文献采集", "action": "run_skill", "skill_id": "core_keyword_research_harvest", "payload": {"keywords": keywords}})
    if "literature_downloaded_not_ingested" in state_tags or "registered_not_chunked" in state_tags:
        actions.append({"label": "继续 PDF 入库", "action": "run_skill", "skill_id": "core_build_user_research_kb", "payload": {}})
    if "has_kb_needs_gap_analysis" in state_tags:
        actions.append({"label": "生成文献缺口分析", "action": "ask_agent", "message": "基于当前已入库文献，按模型、方法、靶点和指标做缺口分析。"})
    if "needs_protocols" in state_tags and "no_literature" not in state_tags:
        actions.append({"label": "生成实验方案草稿", "action": "ask_agent", "message": "基于当前文献证据，提出下一步可执行实验方案。"})
    if scout.get("non_oa_requests"):
        actions.append({"label": "查看需要用户下载的 PDF", "action": "open_feed", "payload": {"filter": "paper_request"}})
    actions.append({"label": "刷新项目观察", "action": "watch_project", "payload": {}})
    return actions[:6]


def suggestion_items(project_id: str, state_tags: list[str], gaps: list[dict[str, Any]], scout: dict[str, Any], workspace_state: dict[str, Any]) -> list[dict[str, Any]]:
    literature = workspace_state.get("literature") or {}
    items: list[dict[str, Any]] = []
    if "no_literature" in state_tags:
        items.append(
            {
                "type": "literature_update",
                "title": "还没有本地文献证据",
                "message": "可以先用项目关键词启动文献采集，建立可追溯的本地知识库。",
                "priority": "high",
                "project_id": project_id,
                "related_sources": [{"source_type": "workspace", "id": project_id}],
                "actions": [{"label": "启动文献采集", "action": "run_skill", "skill_id": "core_keyword_research_harvest"}],
            }
        )
    if "literature_downloaded_not_ingested" in state_tags:
        items.append(
            {
                "type": "gap_alert",
                "title": "PDF 已下载但未完全入库",
                "message": f"当前发现 PDF {int(literature.get('pdf_files_found') or 0)} 个，部分还没有解析、切块或写入 KB。",
                "priority": "high",
                "project_id": project_id,
                "related_sources": [{"source_type": "workspace", "id": project_id}],
                "actions": [{"label": "继续入库", "action": "run_skill", "skill_id": "core_build_user_research_kb"}],
            }
        )
    if scout.get("high_value_papers"):
        items.append(
            {
                "type": "literature_update",
                "title": "发现值得优先阅读的文献",
                "message": f"根据标题、年份和项目关键词，筛出 {len(scout.get('high_value_papers') or [])} 篇可优先阅读的文献。",
                "priority": "medium",
                "project_id": project_id,
                "related_sources": scout.get("high_value_papers")[:5],
                "actions": [{"label": "查看文献", "action": "open_reference"}],
            }
        )
    if scout.get("non_oa_requests"):
        items.append(
            {
                "type": "paper_request",
                "title": "有高价值文献需要用户提供 PDF",
                "message": f"发现 {len(scout.get('non_oa_requests') or [])} 篇可能没有本地全文的文献。请下载 PDF 放入项目文件夹后再入库。",
                "priority": "medium",
                "project_id": project_id,
                "related_sources": scout.get("non_oa_requests")[:5],
                "actions": [{"label": "我已下载 PDF", "action": "open_watched_folder"}],
            }
        )
    for gap in gaps[:3]:
        items.append(
            {
                "type": "gap_alert",
                "title": "项目缺口提示",
                "message": _clean(gap.get("gap")),
                "priority": _clean(gap.get("priority")) or "medium",
                "project_id": project_id,
                "related_sources": [{"source_type": _clean(gap.get("source")) or "workspace", "id": project_id}],
                "actions": [{"label": "让 Agent 解释", "action": "ask_agent", "message": _clean(gap.get("gap"))}],
            }
        )
    if "ready_for_weekly_report" in state_tags:
        items.append(
            {
                "type": "next_action",
                "title": "可以生成阶段性项目汇报",
                "message": "项目已有文献或实验资产，可以生成一次简短周报或进展摘要。",
                "priority": "low",
                "project_id": project_id,
                "related_sources": [{"source_type": "workspace", "id": project_id}],
                "actions": [{"label": "生成周报", "action": "ask_agent", "message": "根据当前项目状态生成一份简短周报。"}],
            }
        )
    return items[:10]


def watch_project(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = _clean(payload.get("project_id"))
    workspace_state = payload.get("workspace_state") or {}
    trigger = _clean(payload.get("trigger")) or "manual"
    state_tags = analyze_project_state(workspace_state)
    scout = literature_scout(workspace_state)
    gaps = gap_analyzer(workspace_state, state_tags)
    actions = build_recommended_actions(workspace_state, state_tags, scout)
    items = suggestion_items(project_id, state_tags, gaps, scout, workspace_state)
    summary = summarize_project_state(workspace_state, state_tags)
    memory_updates = [
        {
            "memory_type": "project_watch_summary",
            "title": "Agent project watch summary",
            "content": summary,
            "structured_content": {
                "state_tags": state_tags,
                "knowledge_gaps": gaps,
                "recommended_actions": actions,
                "literature_scout": scout,
                "trigger": trigger,
            },
            "confidence": 0.76,
            "trust_level": "raw_extracted",
        }
    ]
    questions: list[str] = []
    if "no_literature" in state_tags:
        questions.append("要不要用当前项目关键词启动第一轮文献采集？")
    if scout.get("non_oa_requests"):
        questions.append("这些非 OA 文献是否由你手动下载 PDF 后放入项目文件夹？")
    if "needs_protocols" in state_tags and "no_literature" not in state_tags:
        questions.append("是否需要我把已入库文献整理成下一步实验方案？")
    return {
        "project_state_summary": summary,
        "project_state_tags": state_tags,
        "new_findings": scout.get("high_value_papers", []),
        "knowledge_gaps": gaps,
        "recommended_actions": actions,
        "papers_to_read": scout.get("high_value_papers", []),
        "papers_need_user_download": scout.get("non_oa_requests", []),
        "memory_updates": memory_updates,
        "questions_for_user": questions,
        "literature_scout": scout,
        "inbox_items": items,
        "trigger": trigger,
    }
