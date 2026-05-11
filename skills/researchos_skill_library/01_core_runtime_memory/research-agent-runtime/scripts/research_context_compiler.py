from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def research_os_db(agent_root: Path) -> Path:
    return Path(agent_root) / "research_group_os.sqlite"


def connect(agent_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(research_os_db(agent_root), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {clean(row["name"]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    item = dict(row)
    for key in list(item.keys()):
        if key.endswith("_json"):
            item[key[:-5]] = json_loads(item.pop(key), [])
        elif key in {"metadata", "provenance", "input_payload", "output_payload", "logs", "input_object_refs", "output_object_refs"}:
            item[key] = json_loads(item[key], item[key])
    return item


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def select_recent(
    conn: sqlite3.Connection,
    table: str,
    *,
    project_id: str = "",
    fields: list[str] | None = None,
    where: str = "",
    params: list[Any] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    columns = table_columns(conn, table)
    if not columns:
        return []
    selected = [field for field in (fields or ["*"]) if field == "*" or field in columns]
    if not selected:
        selected = ["*"]
    clauses: list[str] = []
    values: list[Any] = []
    if project_id and "project_id" in columns:
        clauses.append("project_id=?")
        values.append(project_id)
    if where:
        clauses.append(where)
        values.extend(params or [])
    order_col = "updated_at" if "updated_at" in columns else ("created_at" if "created_at" in columns else ("imported_at" if "imported_at" in columns else "rowid"))
    sql = f'SELECT {", ".join(selected)} FROM "{table}"'
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {order_col} DESC LIMIT ?"
    values.append(max(int(limit or 20), 1))
    return rows_to_dicts(conn.execute(sql, values).fetchall())


def terms_for_query(text: str) -> list[str]:
    words = re.findall(r"[\w\u4e00-\u9fff\-]+", clean(text).lower())
    stop = {"the", "and", "or", "with", "for", "this", "that", "what", "how", "why", "你", "我", "的", "了", "吗", "呢"}
    return [word for word in words if len(word) > 1 and word not in stop][:20]


def text_score(item: dict[str, Any], terms: list[str]) -> int:
    haystack = json_dumps(item).lower()
    return sum(1 for term in terms if term.lower() in haystack)


def add_context_item(
    items: list[dict[str, Any]],
    *,
    source_type: str,
    source_id: str,
    title: str,
    content: str,
    priority: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    content = clean(content)
    source_id = clean(source_id)
    if not content and not title:
        return
    items.append(
        {
            "source_type": source_type,
            "source_id": source_id,
            "title": clean(title)[:180],
            "content": content[:1800],
            "priority": int(priority),
            "metadata": metadata or {},
        }
    )


def summarize_project(row: dict[str, Any]) -> str:
    parts = [
        f"title={clean(row.get('title'))}",
        f"area={clean(row.get('research_area'))}",
        f"status={clean(row.get('status'))}",
        f"description={clean(row.get('short_description'))}",
        f"keywords={json_dumps(row.get('keywords') or [])}",
    ]
    return "; ".join(part for part in parts if not part.endswith("=") and part != "keywords=[]")


def project_display_name(project: dict[str, Any] | None) -> str:
    project = project or {}
    return clean(project.get("display_name") or project.get("project_name") or project.get("title")) or "未命名项目"


STATUS_QUERY_INTENTS = {"task_status_query", "project_status_query", "proactive_status_query"}
FILE_QUERY_INTENTS = {"file_location_query", "uploaded_file_query", "file_registry_query", "uploaded_file_parse"}
SAFETY_CONTEXT_INTENTS = {
    "identity",
    "identity_query",
    "safety",
    "safety_query",
    "system_prompt_request",
    "self_description_or_architecture",
}

HIDDEN_INTERNAL_FIELDS = [
    "project_id",
    "task_id",
    "memory_id",
    "candidate_id",
    "file_id",
    "chunk_id",
    "session_id",
    "message_id",
    "internal_path",
    "raw_json",
    "error_stack",
    "debug_trace",
    "context_hash",
]

USER_VISIBLE_CONTEXT_FIELDS = [
    "display_name",
    "original_filename",
    "human_readable_status",
    "stored_path",
    "created_at",
    "updated_at",
    "source title",
    "citation id",
    "short excerpt",
]

_LONG_INTERNAL_ID_RE = re.compile(r"\b(?:[a-f0-9]{16,}|[A-Za-z]+[_-][A-Za-z0-9_.:-]{8,})\b")
_LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s;,)\]]+|/(?:Users|home|mnt|tmp|var)/[^\s;,)\]]+)")


def _truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on", "debug", "developer"}


def _hidden_key_pattern(key: str) -> str:
    return re.escape(key).replace("_", r"[_\s-]?")


def _redact_internal_text(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    text = _LOCAL_PATH_RE.sub("[internal path hidden]", text)
    if re.search(r"Traceback \(most recent call last\)|\bFile \"[^\"]+\", line \d+|^\s*at\s+", text, flags=re.IGNORECASE):
        text = re.split(r"Traceback \(most recent call last\)|\bFile \"[^\"]+\", line \d+|^\s*at\s+", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if not text:
            return "Internal error details hidden."
    for key in HIDDEN_INTERNAL_FIELDS:
        pattern = _hidden_key_pattern(key)
        text = re.sub(rf'"{pattern}"\s*:\s*"[^"]*"\s*,?', "", text, flags=re.IGNORECASE)
        text = re.sub(rf'"{pattern}"\s*:\s*[^,}}\]]+\s*,?', "", text, flags=re.IGNORECASE)
        text = re.sub(rf"\b{pattern}\s*[=:]\s*[^;,\n]+", "", text, flags=re.IGNORECASE)
    text = _LONG_INTERNAL_ID_RE.sub("[id hidden]", text)
    text = re.sub(r"\s*;\s*;", ";", text)
    text = re.sub(r"\{\s*,?\s*\}", "", text)
    text = re.sub(r"\[\s*,?\s*\]", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ;,")


def human_readable_status(status: Any) -> str:
    value = clean(status).replace("_", " ")
    return value or "unknown"


def _progress_summary(progress: Any, counters: Any = None) -> str:
    data = counters if isinstance(counters, dict) and counters else progress if isinstance(progress, dict) else {}
    if not data:
        return "No progress counters available."
    total = data.get("found", data.get("total", ""))
    downloaded = data.get("downloaded", "")
    parsed = data.get("parsed", "")
    indexed = data.get("ingested", data.get("indexed", ""))
    failed = data.get("failed", "")
    parts: list[str] = []
    if total != "":
        parts.append(f"found {int(total or 0)}")
    if downloaded != "":
        parts.append(f"downloaded {int(downloaded or 0)}")
    if parsed != "":
        parts.append(f"parsed {int(parsed or 0)}")
    if indexed != "":
        parts.append(f"indexed {int(indexed or 0)}")
    if failed != "":
        parts.append(f"failed {int(failed or 0)}")
    stage = clean(data.get("current_stage") or data.get("stage"))
    if stage:
        parts.append(f"stage {human_readable_status(stage)}")
    title = _redact_internal_text(data.get("current_title"))
    if title:
        parts.append(f"current item {title[:120]}")
    return ", ".join(parts) if parts else "Progress recorded without public counters."


def _error_summary(error: Any) -> str:
    text = _redact_internal_text(error)
    if not text:
        return ""
    if "Internal error details hidden" in text:
        return text
    return text.splitlines()[0][:220]


def build_user_visible_task_status(task_status: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    visible: list[dict[str, str]] = []
    for task in task_status or []:
        if not isinstance(task, dict):
            continue
        visible.append(
            {
                "task name": _redact_internal_text(task.get("task_name") or task.get("query") or task.get("task_type"))[:160] or "Task",
                "human readable status": human_readable_status(task.get("status")),
                "progress summary": _progress_summary(task.get("progress"), task.get("counters")),
                "last update": clean(task.get("updated_at") or task.get("finished_at") or task.get("started_at")),
                "error summary": _error_summary(task.get("error") or task.get("error_message")),
                "next action": _redact_internal_text(task.get("next_action"))[:220],
            }
        )
    return visible


def _project_status_excerpt(summary: Any) -> str:
    data = summary if isinstance(summary, dict) else json_loads(summary, {})
    if not isinstance(data, dict):
        return _redact_internal_text(summary)
    parts = []
    labels = [
        ("file_count", "files"),
        ("pdf_count", "PDFs"),
        ("kb_count", "indexed knowledge items"),
        ("memory_count", "project memories"),
        ("tasks_count", "tasks"),
    ]
    for key, label in labels:
        if key in data:
            parts.append(f"{label}: {int(data.get(key) or 0)}")
    return ", ".join(parts)


def _context_item_excerpt(item: dict[str, Any]) -> str:
    source_type = clean(item.get("source_type"))
    content = clean(item.get("content"))
    if source_type == "project_status":
        return _project_status_excerpt(content)
    if source_type == "task_status":
        return ""
    if re.search(r"\bprogress\s*=\s*\{", content):
        content = re.sub(r"\bprogress\s*=\s*\{[^{}]*\}", "progress summary hidden", content)
    return _redact_internal_text(content)[:520]


def _render_user_answer_context(raw_context: dict[str, Any], user_visible_task_status: list[dict[str, str]], user_visible_sources: list[dict[str, str]]) -> str:
    items = [item for item in raw_context.get("context_items", []) if isinstance(item, dict)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(clean(item.get("source_type")) or "context", []).append(item)

    lines = ["Relevant Research Context:"]
    lines.append("Project summary")
    display_name = _redact_internal_text(raw_context.get("active_project_display_name"))
    if display_name:
        lines.append(f"- display_name: {display_name}")
    summary = raw_context.get("project_status_summary")
    if summary:
        lines.append(f"- short excerpt: {_project_status_excerpt(summary)}")

    lines.append("Current task status")
    if user_visible_task_status:
        for task in user_visible_task_status[:8]:
            parts = [
                f"task name: {task['task name']}",
                f"human readable status: {task['human readable status']}",
                f"progress summary: {task['progress summary']}",
            ]
            if task.get("last update"):
                parts.append(f"last update: {task['last update']}")
            if task.get("error summary"):
                parts.append(f"error summary: {task['error summary']}")
            if task.get("next action"):
                parts.append(f"next action: {task['next action']}")
            lines.append("- " + "; ".join(parts))
    else:
        lines.append("- None selected.")

    lines.append("Recent uploaded files")
    files = raw_context.get("recent_uploaded_files") if isinstance(raw_context.get("recent_uploaded_files"), list) else []
    if files:
        for file_item in files[:8]:
            if not isinstance(file_item, dict):
                continue
            parts = [
                f"original_filename: {_redact_internal_text(file_item.get('original_filename'))}",
                f"human_readable_status: {human_readable_status(file_item.get('parse_status'))}",
            ]
            stored_path = _redact_internal_text(file_item.get("stored_path"))
            if stored_path:
                parts.append(f"stored_path: {stored_path}")
            updated = clean(file_item.get("updated_at") or file_item.get("upload_time"))
            if updated:
                parts.append(f"updated_at: {updated}")
            lines.append("- " + "; ".join(part for part in parts if not part.endswith(": ")))
    else:
        lines.append("- None selected.")

    section_specs = [
        ("Relevant memory", ["memory_entity", "agent_memory", "experiment", "sample", "data_context", "claim", "failure", "decision"]),
        ("Evidence/RAG", ["reference", "rag_chunk"]),
        ("Capability summary", ["capability", "safety_policy"]),
    ]
    for section_title, source_types in section_specs:
        lines.append(section_title)
        rows = [row for source_type in source_types for row in grouped.get(source_type, [])]
        if not rows:
            lines.append("- None selected.")
            continue
        for row in rows[:8]:
            title = _redact_internal_text(row.get("title"))
            excerpt = _context_item_excerpt(row)
            if not title and not excerpt:
                continue
            if section_title == "Evidence/RAG":
                citation = clean((row.get("metadata") or {}).get("citation_id"))
                parts = []
                if title:
                    parts.append(f"source title: {title}")
                if citation:
                    parts.append(f"citation id: {citation}")
                if excerpt:
                    parts.append(f"short excerpt: {excerpt}")
                lines.append("- " + "; ".join(parts))
            else:
                parts = []
                if title:
                    parts.append(f"display_name: {title}")
                if excerpt:
                    parts.append(f"short excerpt: {excerpt}")
                lines.append("- " + "; ".join(parts))

    warnings = [_redact_internal_text(item) for item in raw_context.get("warnings", []) if clean(item)]
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- short excerpt: {warning}" for warning in warnings[:5])
    return "\n".join(line for line in lines if clean(line))


def _sanitize_user_visible_sources(sources: Any) -> list[dict[str, str]]:
    visible: list[dict[str, str]] = []
    if not isinstance(sources, list):
        return visible
    for source in sources[:20]:
        if not isinstance(source, dict):
            continue
        visible.append(
            {
                "source title": _redact_internal_text(source.get("title") or source.get("display_title"))[:180],
                "citation id": clean(source.get("citation_id")),
                "short excerpt": _redact_internal_text(source.get("excerpt"))[:360],
            }
        )
    return visible


def sanitize_workspace_for_user_answer(workspace: dict[str, Any], *, developer_debug: bool = False) -> dict[str, Any]:
    if developer_debug:
        return workspace or {}
    workspace = workspace or {}
    project = workspace.get("project") if isinstance(workspace.get("project"), dict) else {}
    literature = workspace.get("literature") if isinstance(workspace.get("literature"), dict) else {}
    data = workspace.get("data") if isinstance(workspace.get("data"), dict) else {}
    memory = workspace.get("memory") if isinstance(workspace.get("memory"), dict) else {}
    rag = workspace.get("rag") if isinstance(workspace.get("rag"), dict) else {}
    artifacts = workspace.get("artifacts") if isinstance(workspace.get("artifacts"), list) else []
    recent_references = literature.get("recent_references") if isinstance(literature.get("recent_references"), list) else []
    return {
        "project": {
            "display_name": _redact_internal_text(project.get("display_name") or project.get("title") or workspace.get("active_project_display_name")),
            "human_readable_status": human_readable_status(project.get("status")),
            "created_at": clean(project.get("created_at")),
            "updated_at": clean(project.get("updated_at")),
        },
        "literature": {
            "human_readable_status": _project_status_excerpt(
                {
                    "pdf_count": literature.get("pdf_files_count", literature.get("pdf_count", 0)),
                    "kb_count": literature.get("chunks_count", 0),
                    "tasks_count": literature.get("search_tasks_count", 0),
                }
            ),
            "recent_references": [
                {
                    "source title": _redact_internal_text(item.get("title"))[:180],
                    "short excerpt": _redact_internal_text(item.get("abstract") or item.get("summary"))[:360],
                    "updated_at": clean(item.get("updated_at") or item.get("created_at")),
                }
                for item in recent_references[:8]
                if isinstance(item, dict)
            ],
        },
        "data": {"human_readable_status": _project_status_excerpt({"file_count": data.get("file_count", 0), "pdf_count": data.get("pdf_count", 0)})},
        "memory": {"human_readable_status": _project_status_excerpt({"memory_count": memory.get("agent_memory_count", memory.get("memory_count", 0))})},
        "rag": {"human_readable_status": _project_status_excerpt({"kb_count": rag.get("chunks_count", rag.get("kb_count", 0))})},
        "recent_artifacts": [
            {
                "display_name": _redact_internal_text(item.get("title") or item.get("type"))[:180],
                "human_readable_status": human_readable_status(item.get("status")),
                "created_at": clean(item.get("created_at")),
                "updated_at": clean(item.get("updated_at")),
            }
            for item in artifacts[:12]
            if isinstance(item, dict)
        ],
    }


def sanitize_context_for_user_answer(compiled_context: dict[str, Any], *, developer_debug: bool = False) -> dict[str, Any]:
    raw_context = compiled_context or {}
    if developer_debug:
        visible_tasks = build_user_visible_task_status(raw_context.get("task_status") if isinstance(raw_context.get("task_status"), list) else [])
        return {**raw_context, "user_visible_task_status": visible_tasks, "answer_context_sanitized": False}
    user_visible_task_status = build_user_visible_task_status(raw_context.get("task_status") if isinstance(raw_context.get("task_status"), list) else [])
    user_visible_sources = _sanitize_user_visible_sources(raw_context.get("sources"))
    return {
        "active_project_display_name": _redact_internal_text(raw_context.get("active_project_display_name")),
        "recent_uploaded_files": [
            {
                "original_filename": _redact_internal_text(item.get("original_filename")),
                "human_readable_status": human_readable_status(item.get("parse_status")),
                "stored_path": _redact_internal_text(item.get("stored_path")),
                "created_at": clean(item.get("created_at")),
                "updated_at": clean(item.get("updated_at") or item.get("upload_time")),
            }
            for item in (raw_context.get("recent_uploaded_files") if isinstance(raw_context.get("recent_uploaded_files"), list) else [])
            if isinstance(item, dict)
        ],
        "compiled_context": _render_user_answer_context(raw_context, user_visible_task_status, user_visible_sources),
        "user_visible_task_status": user_visible_task_status,
        "user_visible_sources": user_visible_sources,
        "allowed_user_visible_identifiers": list(USER_VISIBLE_CONTEXT_FIELDS),
        "hidden_internal_identifiers": list(HIDDEN_INTERNAL_FIELDS),
        "answer_context_sanitized": True,
    }


def is_status_query_message(message: str) -> bool:
    text = clean(message)
    lower = text.lower()
    compact = re.sub(r"[\s\?？!！。.,，、:：;；]+", "", lower)
    chinese_terms = [
        "最近有什么进展",
        "最近进展",
        "当前进度",
        "现在进度",
        "任务状态",
        "任务进度",
        "文献采集进度",
        "入库多少",
        "入库了多少",
        "下载多少",
        "下载了多少",
        "跑到哪了",
        "现在跑到哪了",
        "任务完成了吗",
        "文献采集完成了吗",
        "项目状态",
        "项目进展",
        "有哪些新结果",
        "你学到了什么",
    ]
    english_terms = [
        "current progress",
        "current status",
        "task status",
        "task progress",
        "harvest progress",
        "harvest status",
        "literature harvest progress",
        "how many downloaded",
        "how many ingested",
        "where are we",
        "where is it",
        "any updates",
        "recent updates",
        "new results",
    ]
    return any(term in compact for term in chinese_terms) or any(term in lower for term in english_terms)


def is_file_query_message(message: str) -> bool:
    text = clean(message)
    lower = text.lower()
    return any(term in lower for term in ["file path", "where is the file", "uploaded file", "recent upload", "save path"]) or any(
        term in text for term in ["文件在哪", "文件路径", "上传到哪", "最近上传", "保存路径"]
    )


def effective_context_intent(intent: str, user_message: str) -> str:
    intent = clean(intent)
    if intent in SAFETY_CONTEXT_INTENTS:
        return "safety_context"
    if intent in FILE_QUERY_INTENTS or is_file_query_message(user_message):
        return "file_query"
    if intent in STATUS_QUERY_INTENTS or is_status_query_message(user_message):
        return "status_query"
    if intent == "research_advice":
        return "research_advice"
    return intent


def recent_uploaded_files_for_context(conn: sqlite3.Connection, project_id: str, limit: int = 8) -> list[dict[str, Any]]:
    if not table_exists(conn, "research_files"):
        return []
    fields = [
        "original_filename",
        "stored_path",
        "parse_status",
        "file_type",
        "upload_time",
        "imported_at",
        "created_at",
    ]
    rows = select_recent(conn, "research_files", project_id=project_id, fields=fields, limit=limit)
    files: list[dict[str, Any]] = []
    for row in rows:
        files.append(
            {
                "original_filename": clean(row.get("original_filename")),
                "stored_path": clean(row.get("stored_path")),
                "parse_status": clean(row.get("parse_status")) or "not_parsed",
                "file_type": clean(row.get("file_type")),
                "upload_time": clean(row.get("upload_time") or row.get("imported_at") or row.get("created_at")),
            }
        )
    return files


def project_status_summary_for_context(conn: sqlite3.Connection, project_id: str) -> dict[str, int]:
    def count(table: str, where: str = "project_id=?", params: tuple[Any, ...] | None = None) -> int:
        if not table_exists(conn, table):
            return 0
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}', params or (project_id,)).fetchone()[0])

    file_count = count("research_files")
    pdf_count = count(
        "research_files",
        "project_id=? AND (file_type='pdf' OR mime_type='application/pdf' OR detected_document_category='paper')",
        (project_id,),
    )
    kb_count = count("knowledge_base_entries") + count("reference_chunks") + count("document_chunks")
    memory_count = count("agent_memory_entries", "project_id=? AND memory_scope='project' AND status='active'", (project_id,))
    task_count = count("literature_search_tasks") + count("skill_runs") + count("agent_tasks")
    return {
        "file_count": file_count,
        "pdf_count": pdf_count,
        "kb_count": kb_count,
        "memory_count": memory_count,
        "tasks_count": task_count,
    }


def collect_task_status(conn: sqlite3.Connection, project_id: str, limit: int = 8) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for task in select_recent(conn, "literature_search_tasks", project_id=project_id, limit=max(limit * 3, 12)):
        task_id = clean(task.get("id"))
        ingest_items = select_recent(conn, "literature_ingest_items", where="task_id=?", params=[task_id], limit=5000)
        notes = task.get("notes") if isinstance(task.get("notes"), dict) else json_loads(task.get("notes"), {})
        run_root = Path(clean(notes.get("run_root"))) if clean(notes.get("run_root")) else None
        candidate_count = 0
        pdf_count = 0
        if run_root and run_root.exists():
            candidate_table = run_root / "keyword_research_candidate_table.csv"
            if candidate_table.exists():
                try:
                    with candidate_table.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
                        candidate_count = max(sum(1 for _ in handle) - 1, 0)
                except Exception:
                    candidate_count = 0
            try:
                pdf_count = sum(1 for path in run_root.rglob("*.pdf") if path.is_file())
            except Exception:
                pdf_count = 0
        downloaded = sum(1 for item in ingest_items if clean(item.get("download_status")) == "downloaded")
        parsed = sum(1 for item in ingest_items if clean(item.get("ingest_status")) in {"chunked", "indexed"})
        indexed = sum(1 for item in ingest_items if clean(item.get("ingest_status")) == "indexed")
        failed = sum(1 for item in ingest_items if clean(item.get("download_status")) == "failed" or clean(item.get("ingest_status")) == "failed")
        current = next((item for item in ingest_items if clean(item.get("ingest_status")) in {"pending", "parsing", "chunked"}), {})
        statuses.append(
            {
                "task_type": "literature_harvest",
                "task_name": "文献采集",
                "task_id": task_id,
                "skill_id": "core_keyword_research_harvest",
                "status": task.get("status"),
                "query": task.get("query"),
                "started_at": task.get("created_at"),
                "finished_at": task.get("updated_at") if clean(task.get("status")) in {"completed", "failed"} else "",
                "progress": {
                    "total": max(candidate_count, len(ingest_items), len(task.get("result_reference_ids") or [])),
                    "downloaded": max(downloaded, pdf_count),
                    "parsed": parsed,
                    "indexed": indexed,
                    "failed": failed,
                    "current_title": clean(current.get("title")),
                    "current_stage": clean(current.get("ingest_status")) or clean(notes.get("phase")),
                    "chunks_count": sum(int(item.get("chunks_count") or 0) for item in ingest_items),
                },
                "artifacts": {"run_root": clean(notes.get("run_root")), "log_path": clean(notes.get("log_path"))},
                "error": clean(notes.get("error")),
            }
        )
    for row in select_recent(
        conn,
        "skill_runs",
        project_id=project_id,
        fields=["id", "skill_id", "skill_name", "status", "created_at", "updated_at", "output_object_refs_json", "logs_json"],
        limit=limit,
    ):
        statuses.append(
            {
                "task_type": "skill_run",
                "task_name": clean(row.get("skill_name")) or clean(row.get("skill_id")),
                "task_id": row.get("id"),
                "skill_id": row.get("skill_id"),
                "status": row.get("status"),
                "started_at": row.get("created_at"),
                "finished_at": row.get("updated_at") if clean(row.get("status")) in {"completed", "failed"} else "",
                "progress": {},
                "artifacts": row.get("output_object_refs") or [],
                "error": "",
            }
        )
    for row in select_recent(
        conn,
        "execution_memory",
        project_id=project_id,
        fields=["id", "skill_id", "task_title", "status", "error_message", "created_at", "updated_at"],
        limit=limit,
    ):
        statuses.append(
            {
                "task_type": "execution_memory",
                "task_name": clean(row.get("task_title")) or "执行记录",
                "task_id": row.get("id"),
                "skill_id": row.get("skill_id"),
                "status": row.get("status"),
                "started_at": row.get("created_at"),
                "finished_at": row.get("updated_at") if clean(row.get("status")) in {"completed", "failed"} else "",
                "progress": {},
                "artifacts": [],
                "error": row.get("error_message") or "",
            }
        )

    def rank(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
        progress = item.get("progress") if isinstance(item.get("progress"), dict) else {}
        return (
            1 if clean(item.get("status")) in {"running", "pending", "waiting_approval"} else 0,
            int(progress.get("downloaded") or 0),
            int(progress.get("indexed") or 0),
            clean(item.get("started_at") or item.get("finished_at")),
            clean(item.get("task_id")),
        )

    statuses.sort(key=rank, reverse=True)
    return statuses[: max(int(limit or 8), 1)]


def context_sections_for_intent(intent: str) -> set[str]:
    if intent == "safety_context":
        return set()
    if intent == "status_query":
        return {"project", "tasks", "files", "memory", "rag", "references"}
    if intent == "file_query":
        return {"project", "files"}
    if intent == "task_status_query":
        return {"project", "tasks", "capabilities"}
    if intent == "kb_query":
        return {"project", "rag", "references", "kb", "capabilities"}
    if intent == "memory_query":
        return {"project", "memory", "claims", "decisions", "failures", "capabilities"}
    if intent == "project_status_query":
        return {"project", "experiments", "samples", "files", "claims", "tasks", "capabilities"}
    if intent in {"research_advice", "proactive_status_query", "capability_query", "start_skill_request"}:
        return {"project", "memory", "experiments", "samples", "files", "data_contexts", "claims", "failures", "decisions", "rag", "references", "tasks", "capabilities"}
    return {"project", "memory", "rag", "tasks", "capabilities"}


def source_budget_for_intent(intent: str) -> dict[str, int]:
    if intent == "status_query":
        return {
            "project": 1,
            "project_status": 1,
            "task_status": 8,
            "recent_uploaded_file": 6,
            "data_file": 3,
            "memory_entity": 2,
            "agent_memory": 2,
            "reference": 2,
            "rag_chunk": 2,
        }
    if intent == "file_query":
        return {"project": 1, "project_status": 1, "recent_uploaded_file": 10, "data_file": 10}
    if intent == "research_advice":
        return {
            "project": 1,
            "project_status": 1,
            "memory_entity": 5,
            "agent_memory": 5,
            "reference": 5,
            "rag_chunk": 6,
            "task_status": 2,
            "recent_uploaded_file": 3,
            "data_file": 3,
        }
    if intent == "safety_context":
        return {"safety_policy": 2}
    return {}


def priority_for_source(intent: str, source_type: str, base_priority: int) -> int:
    if intent == "status_query":
        boosts = {
            "project_status": 118,
            "task_status": 116,
            "project": 112,
            "recent_uploaded_file": 108,
            "data_file": 88,
            "memory_entity": 45,
            "agent_memory": 45,
            "reference": 35,
            "rag_chunk": 35,
        }
        return boosts.get(source_type, min(base_priority, 40))
    if intent == "file_query":
        boosts = {"recent_uploaded_file": 118, "data_file": 112, "project": 80, "project_status": 78}
        return boosts.get(source_type, min(base_priority, 30))
    if intent == "research_advice":
        boosts = {"project": 100, "project_status": 92, "memory_entity": 84, "agent_memory": 84, "reference": 82, "rag_chunk": 82, "task_status": 60}
        return boosts.get(source_type, base_priority)
    return base_priority


def apply_source_budget(items: list[dict[str, Any]], intent: str) -> list[dict[str, Any]]:
    budget = source_budget_for_intent(intent)
    if not budget:
        return items
    kept: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for item in items:
        source_type = clean(item.get("source_type"))
        limit = budget.get(source_type)
        if limit is None:
            if intent in {"status_query", "file_query", "safety_context"}:
                continue
            kept.append(item)
            continue
        if counts.get(source_type, 0) >= limit:
            continue
        counts[source_type] = counts.get(source_type, 0) + 1
        kept.append(item)
    return kept


def trim_context(items: list[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    budget = max(int(max_tokens or 2000) * 4, 1200)
    kept: list[dict[str, Any]] = []
    used = 0
    for item in items:
        line_size = len(clean(item.get("title"))) + len(clean(item.get("content"))) + 80
        if kept and used + line_size > budget:
            break
        kept.append(item)
        used += line_size
    return kept


def render_context(items: list[dict[str, Any]], warnings: list[str]) -> str:
    lines = ["Relevant Research Context:"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(clean(item.get("source_type")) or "context", []).append(item)

    sections = [
        ("Project summary", ["project", "project_status", "capability", "safety_policy"]),
        ("Current task status", ["task_status"]),
        ("Recent uploaded files", ["recent_uploaded_file", "data_file"]),
        ("Relevant memory", ["memory_entity", "agent_memory", "experiment", "sample", "data_context", "claim", "failure", "decision"]),
        ("Evidence/RAG", ["reference", "rag_chunk"]),
    ]
    for section_title, source_types in sections:
        rows = [row for source_type in source_types for row in grouped.get(source_type, [])]
        lines.append(section_title)
        if not rows:
            lines.append("- None selected.")
            continue
        for row in rows[:8]:
            source_type = clean(row.get("source_type"))
            sid = clean(row.get("source_id"))
            title = clean(row.get("title"))
            content = clean(row.get("content"))
            prefix = f"- [{source_type}:{sid}]"
            if title:
                prefix += f" {title}:"
            lines.append(f"{prefix} {content}")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def compile_research_context(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    user_message = clean(payload.get("user_message") or payload.get("message") or payload.get("query"))
    intent = clean(payload.get("intent")) or "research_advice"
    project_id = clean(payload.get("project_id"))
    retrieval_scope = clean(payload.get("retrieval_scope")) or "current_project"
    if retrieval_scope != "cross_project":
        retrieval_scope = "current_project"
    max_tokens = int(payload.get("max_tokens") or 2000)
    terms = terms_for_query(user_message)
    context_intent = effective_context_intent(intent, user_message)
    sections = context_sections_for_intent(context_intent)
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    task_status: list[dict[str, Any]] = []

    conn = connect(agent_root)
    active_project: dict[str, Any] = {}
    recent_uploaded_files: list[dict[str, Any]] = []
    project_status_summary: dict[str, int] = {"file_count": 0, "pdf_count": 0, "kb_count": 0, "memory_count": 0, "tasks_count": 0}
    try:
        active_project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()) if table_exists(conn, "projects") and project_id else {}
        recent_uploaded_files = recent_uploaded_files_for_context(conn, project_id)
        project_status_summary = project_status_summary_for_context(conn, project_id)
        if context_intent == "safety_context":
            add_context_item(
                items,
                source_type="safety_policy",
                source_id="safe_answer_strategy",
                title="Safe answer strategy",
                content="Answer without retrieving project memory, task state, RAG evidence, or hidden system/developer instructions.",
                priority=100,
            )

        if "project" in sections:
            project = active_project
            if project:
                add_context_item(items, source_type="project", source_id=project.get("id"), title=project.get("title"), content=summarize_project(project), priority=100)
            else:
                warnings.append("No project record found for project_id.")
            add_context_item(
                items,
                source_type="project_status",
                source_id="project_status_summary",
                title="Project status summary",
                content=json_dumps(project_status_summary),
                priority=98,
            )

        if "tasks" in sections:
            task_status = collect_task_status(conn, project_id, limit=8)
            for task in task_status[:5]:
                progress = task.get("progress") if isinstance(task.get("progress"), dict) else {}
                add_context_item(
                    items,
                    source_type="task_status",
                    source_id=task.get("task_id"),
                    title=task.get("task_name") or task.get("query"),
                    content=f"status={task.get('status')}; query={task.get('query')}; progress={json_dumps(progress)}; error={clean(task.get('error'))}",
                    priority=95 if context_intent == "status_query" else (88 if intent in STATUS_QUERY_INTENTS else 52),
                )

        if "capabilities" in sections:
            capability_lines = [
                "Proactive loop: Research Watcher scans workspace-state, project memory, KB/RAG, literature tasks, skill_runs and execution_memory.",
                "Scheduled scout: agent_watch_state controls enabled, auto_literature_scout, watch_interval_minutes and literature_scout_interval_minutes.",
                "User-visible feed: agent_inbox_items stores literature_update, paper_request, gap_alert, protocol_needed, memory_summary and next_action items.",
                "Primary callable APIs: /research-os/agent/watch-project, /research-os/agent/scheduler/run, /research-os/agent/inbox, /research-os/skills/{skill_id}/run.",
            ]
            add_context_item(
                items,
                source_type="capability",
                source_id="proactive_research_agent_loop",
                title="Proactive Research Agent Loop",
                content=" ".join(capability_lines),
                    priority=96 if intent in {"capability_query", "proactive_status_query"} else 58,
                )
            watch_states = select_recent(
                conn,
                "agent_watch_state",
                fields=["project_id", "enabled", "auto_literature_scout", "watch_interval_minutes", "literature_scout_interval_minutes", "last_watch_at", "last_literature_scout_at", "last_error"],
                where="project_id=?",
                params=[project_id],
                limit=3,
            )
            for state in watch_states:
                add_context_item(
                    items,
                    source_type="capability",
                    source_id=f"watch_state:{project_id}",
                    title="Current project watch state",
                    content=f"enabled={state.get('enabled')}; auto_literature_scout={state.get('auto_literature_scout')}; watch_interval_minutes={state.get('watch_interval_minutes')}; literature_scout_interval_minutes={state.get('literature_scout_interval_minutes')}; last_watch_at={state.get('last_watch_at')}; last_literature_scout_at={state.get('last_literature_scout_at')}; last_error={state.get('last_error')}",
                    priority=94 if intent in {"capability_query", "proactive_status_query"} else 56,
                )
            skill_rows = select_recent(
                conn,
                "skill_registry",
                fields=["skill_id", "skill_name", "description", "domain", "skill_type", "handler", "handler_ref", "status", "applicable_domains_json", "input_schema_json", "output_schema_json"],
                where="status!='disabled'",
                limit=240,
            )
            preferred_skill_ids = {
                "core_keyword_research_harvest",
                "core_extract_first_article_keywords",
                "core_build_user_research_kb",
                "core_ingest_research_evidence",
                "core_manage_agent_memory",
                "core_query_research_rag",
                "core_weekly_research_digest",
            }
            scored_skills = sorted(
                skill_rows,
                key=lambda row: (
                    5 if clean(row.get("skill_id")) in preferred_skill_ids else 0,
                    text_score(row, terms),
                    1 if clean(row.get("status")) == "enabled" else 0,
                    clean(row.get("skill_name")),
                ),
                reverse=True,
            )
            for row in scored_skills[:18]:
                domains = row.get("applicable_domains") or []
                input_schema = row.get("input_schema") or {}
                content = (
                    f"skill_id={clean(row.get('skill_id'))}; name={clean(row.get('skill_name'))}; "
                    f"type={clean(row.get('skill_type'))}; handler={clean(row.get('handler') or row.get('handler_ref'))}; "
                    f"description={clean(row.get('description'))}; domains={json_dumps(domains)[:360]}; "
                    f"input_schema={json_dumps(input_schema)[:420]}"
                )
                add_context_item(
                    items,
                    source_type="capability",
                    source_id=row.get("skill_id"),
                    title=row.get("skill_name"),
                    content=content,
                    priority=90 + text_score(row, terms) + (10 if clean(row.get("skill_id")) in preferred_skill_ids else 0),
                    metadata={"skill_id": row.get("skill_id"), "handler": row.get("handler") or row.get("handler_ref")},
                )

        if "memory" in sections:
            for row in select_recent(conn, "memory_entities", project_id=project_id, limit=8):
                add_context_item(items, source_type="memory_entity", source_id=row.get("id"), title=row.get("canonical_name") or row.get("entity_type"), content=json_dumps(row)[:1600], priority=80 + text_score(row, terms))
            for row in select_recent(conn, "agent_memory_entries", project_id=project_id, where="enabled=1" if "enabled" in table_columns(conn, "agent_memory_entries") else "", limit=8):
                add_context_item(items, source_type="agent_memory", source_id=row.get("id"), title=row.get("title") or row.get("memory_type"), content=clean(row.get("content") or json_dumps(row))[:1600], priority=78 + text_score(row, terms))

        if "experiments" in sections:
            for row in select_recent(conn, "experiments", project_id=project_id, limit=15):
                content = f"type={row.get('experiment_type')}; date={row.get('date')}; operator={row.get('operator')}; purpose={row.get('purpose')}; result={row.get('result_summary')}; conclusion={row.get('conclusion')}; status={row.get('status')}"
                add_context_item(items, source_type="experiment", source_id=row.get("id"), title=row.get("title"), content=content, priority=76 + text_score(row, terms))

        if "samples" in sections:
            for row in select_recent(conn, "samples", project_id=project_id, limit=20):
                content = f"sample_code={row.get('sample_code')}; type={row.get('sample_type')}; source={row.get('source')}; batch={row.get('batch')}; status={row.get('current_status')}; metadata={json_dumps(row.get('metadata') or {})}"
                add_context_item(items, source_type="sample", source_id=row.get("id"), title=row.get("name") or row.get("sample_code"), content=content, priority=70 + text_score(row, terms))

        if "files" in sections:
            for file_item in recent_uploaded_files:
                add_context_item(
                    items,
                    source_type="recent_uploaded_file",
                    source_id=clean(file_item.get("original_filename")) or clean(file_item.get("stored_path")),
                    title=file_item.get("original_filename"),
                    content=(
                        f"file_type={file_item.get('file_type')}; parse_status={file_item.get('parse_status')}; "
                        f"upload_time={file_item.get('upload_time')}; stored_path={file_item.get('stored_path')}"
                    ),
                    priority=86,
                )
            for row in select_recent(conn, "research_files", project_id=project_id, limit=20):
                content = f"filename={row.get('original_filename')}; category={row.get('detected_document_category')}; type={row.get('file_type')}; path={row.get('file_path')}; imported_at={row.get('imported_at')}"
                add_context_item(items, source_type="data_file", source_id=row.get("id"), title=row.get("original_filename"), content=content, priority=68 + text_score(row, terms))

        if "data_contexts" in sections:
            for row in select_recent(conn, "data_contexts", project_id=project_id, limit=20):
                content = f"file_id={row.get('file_id')}; experiment_id={row.get('experiment_id')}; protocol_id={row.get('protocol_id')}; assay={row.get('assay_type')}; status={row.get('context_status')}; missing={json_dumps(row.get('missing_metadata') or [])}"
                add_context_item(items, source_type="data_context", source_id=row.get("id"), title=row.get("assay_type") or row.get("file_id"), content=content, priority=67 + text_score(row, terms))

        if "claims" in sections:
            for row in select_recent(conn, "claims", project_id=project_id, where="status NOT IN ('rejected','superseded')" if "status" in table_columns(conn, "claims") else "", limit=20):
                content = f"type={row.get('claim_type')}; status={row.get('status')}; confidence={row.get('confidence')}; text={row.get('claim_text')}"
                add_context_item(items, source_type="claim", source_id=row.get("id"), title=row.get("claim_type"), content=content, priority=74 + text_score(row, terms))

        if "failures" in sections:
            for row in select_recent(conn, "failure_logs", project_id=project_id, limit=12):
                content = f"experiment_id={row.get('experiment_id')}; type={row.get('failure_type')}; likely_reason={row.get('likely_reason')}; description={row.get('failure_description')}"
                add_context_item(items, source_type="failure", source_id=row.get("id"), title=row.get("failure_type"), content=content, priority=72 + text_score(row, terms))

        if "decisions" in sections:
            for row in select_recent(conn, "decisions", project_id=project_id, where="status!='superseded'" if "status" in table_columns(conn, "decisions") else "", limit=12):
                content = f"status={row.get('status')}; decision={row.get('decision_text')}; reason={row.get('reason')}; effects={json_dumps(row.get('downstream_effects') or [])}"
                add_context_item(items, source_type="decision", source_id=row.get("id"), title=row.get("decision_text"), content=content, priority=73 + text_score(row, terms))

        if "references" in sections:
            for row in select_recent(conn, "references", project_id=project_id, limit=16):
                content = f"title={row.get('title')}; year={row.get('year')}; journal={row.get('journal')}; doi={row.get('doi')}; abstract={clean(row.get('abstract'))[:900]}"
                add_context_item(items, source_type="reference", source_id=row.get("id"), title=row.get("title"), content=content, priority=72 + text_score(row, terms))

        if "rag" in sections or "kb" in sections:
            chunk_columns = table_columns(conn, "reference_chunks")
            if chunk_columns:
                chunks = select_recent(
                    conn,
                    "reference_chunks",
                    project_id=project_id,
                    fields=["id", "reference_id", "chunk_text", "text", "citation_id", "source_kind", "updated_at"],
                    limit=80,
                )
                scored = sorted(chunks, key=lambda row: (text_score(row, terms), clean(row.get("updated_at")), clean(row.get("id"))), reverse=True)
                for row in scored[:12]:
                    excerpt = clean(row.get("chunk_text") or row.get("text"))
                    add_context_item(
                        items,
                        source_type="rag_chunk",
                        source_id=row.get("id"),
                        title=row.get("citation_id") or row.get("reference_id"),
                        content=excerpt[:1100],
                        priority=76 + text_score(row, terms),
                        metadata={"reference_id": row.get("reference_id"), "citation_id": row.get("citation_id")},
                    )
            for row in select_recent(conn, "knowledge_base_entries", project_id=project_id, limit=16):
                content = clean(row.get("content") or row.get("summary") or json_dumps(row))[:1100]
                add_context_item(items, source_type="rag_chunk", source_id=row.get("id"), title=row.get("title") or row.get("entry_type"), content=content, priority=76 + text_score(row, terms))

    finally:
        conn.close()

    if intent == "task_status_query" and context_intent != "status_query":
        items = [item for item in items if item.get("source_type") in {"project", "task_status"}]
    for item in items:
        item["priority"] = priority_for_source(context_intent, clean(item.get("source_type")), int(item.get("priority") or 0))
    items.sort(key=lambda item: (-int(item.get("priority") or 0), clean(item.get("source_type")), clean(item.get("source_id"))))
    items = apply_source_budget(items, context_intent)
    items = trim_context(items, max_tokens)

    memory_used = [
        {
            "id": item.get("source_id"),
            "type": item.get("source_type"),
            "title": item.get("title"),
            "status": item.get("metadata", {}).get("status"),
        }
        for item in items
        if item.get("source_type") in {"memory_entity", "agent_memory", "experiment", "sample", "data_file", "data_context", "claim", "failure", "decision", "project"}
    ][:20]
    sources = [
        {
            "reference_id": item.get("metadata", {}).get("reference_id") or (item.get("source_id") if item.get("source_type") == "reference" else ""),
            "chunk_id": item.get("source_id") if item.get("source_type") == "rag_chunk" else "",
            "title": item.get("title"),
            "source_kind": item.get("source_type"),
            "citation_id": item.get("metadata", {}).get("citation_id"),
            "excerpt": clean(item.get("content"))[:360],
        }
        for item in items
        if item.get("source_type") in {"reference", "rag_chunk"}
    ][:20]
    compiled_context = render_context(items, warnings)
    hash_payload = {
        "intent": intent,
        "project_id": project_id,
        "query": user_message,
        "items": [(item.get("source_type"), item.get("source_id"), item.get("content")) for item in items],
        "warnings": warnings,
    }
    context_hash = hashlib.sha256(json_dumps(hash_payload).encode("utf-8")).hexdigest()[:24]
    raw_context = {
        "active_project_id": project_id,
        "active_project_display_name": project_display_name(active_project),
        "recent_uploaded_files": recent_uploaded_files,
        "project_status_summary": project_status_summary,
        "retrieval_scope": retrieval_scope,
        "context_intent": context_intent,
        "allowed_user_visible_identifiers": list(USER_VISIBLE_CONTEXT_FIELDS),
        "hidden_internal_identifiers": list(HIDDEN_INTERNAL_FIELDS),
        "compiled_context": compiled_context,
        "context_items": items,
        "memory_used": memory_used,
        "sources": sources,
        "task_status": task_status,
        "warnings": warnings,
        "context_hash": context_hash,
    }
    developer_debug = _truthy(payload.get("developer_debug") or payload.get("debug_context") or payload.get("include_internal_ids"))
    user_answer_context = sanitize_context_for_user_answer(raw_context, developer_debug=developer_debug)
    return {
        **raw_context,
        "compiled_context": user_answer_context["compiled_context"],
        "user_visible_task_status": user_answer_context.get("user_visible_task_status", []),
        "user_visible_sources": user_answer_context.get("user_visible_sources", []),
        "answer_context_sanitized": bool(user_answer_context.get("answer_context_sanitized")),
    }


def build_research_context(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return compile_research_context(agent_root, payload)
