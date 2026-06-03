from __future__ import annotations

from pathlib import Path

from .consolidation import consolidate_memory
from .database import connect
from .models import truncate
from .retrieval import retrieve_memory
from .views import get_current_project_view


def _limit(text: str, max_tokens: int) -> str:
    return truncate(text, max(500, max_tokens * 4))


def _lines_for_memories(memories: list[dict], memory_type: str, limit: int = 6) -> list[str]:
    lines = []
    for item in [memory for memory in memories if memory.get("memory_type") == memory_type][:limit]:
        lines.append(f"- {truncate(item.get('subject') or item.get('content') or '', 80)}: {truncate(item.get('content') or '', 220)}")
    return lines or ["- None found in active memory."]


def build_memory_context(
    agent_root: Path,
    user_id: str,
    query: str,
    group_id: str | None = None,
    project_id: str | None = None,
    max_tokens: int = 1500,
) -> str:
    project_id = str(project_id or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    if not get_current_project_view(agent_root, project_id):
        consolidate_memory(agent_root, user_id=user_id, group_id=group_id, project_id=project_id)

    view = get_current_project_view(agent_root, project_id)
    memories = retrieve_memory(
        agent_root,
        user_id=user_id,
        group_id=group_id,
        query=query,
        project_id=project_id,
        max_results=80,
    )

    conn = connect(agent_root)
    experiments = []
    samples = []
    files = []
    if project_id:
        experiments = [dict(row) for row in conn.execute("SELECT * FROM experiments WHERE project_id=? ORDER BY COALESCE(date, created_at) DESC LIMIT 10", (project_id,)).fetchall()]
        samples = [dict(row) for row in conn.execute("SELECT * FROM samples WHERE project_id=? ORDER BY sample_code LIMIT 12", (project_id,)).fetchall()]
        files = [dict(row) for row in conn.execute("SELECT * FROM data_files WHERE project_id=? ORDER BY upload_time DESC LIMIT 10", (project_id,)).fetchall()]
    conn.close()

    structured = view.get("structured_summary", {}) if view else {}
    lines = [
        "Relevant Research Memory:",
        "1. Current project state:",
        f"- {view.get('summary') if view else 'No consolidated project view found.'}",
    ]
    if structured.get("research_question"):
        lines.append(f"- Research question: {structured['research_question']}")
    if structured.get("current_stage"):
        lines.append(f"- Stage: {structured['current_stage']}")

    lines.append("2. Completed experiments:")
    if experiments:
        for exp in experiments[:8]:
            lines.append(f"- {exp.get('title')} ({exp.get('experiment_type')}, {exp.get('status')}): {truncate(exp.get('result_summary') or exp.get('conclusion') or '', 180)}")
    else:
        lines.extend(_lines_for_memories(memories, "experiment_memory", 5))

    lines.append("3. Key samples and batches:")
    if samples:
        for sample in samples[:10]:
            lines.append(f"- {sample.get('sample_code')} | {sample.get('sample_type') or 'sample'} | batch {sample.get('batch') or 'unknown'} | status {sample.get('current_status') or 'unknown'}")
    else:
        lines.extend(_lines_for_memories(memories, "sample_memory", 5))

    lines.append("4. Available datasets and files:")
    if files:
        for data_file in files[:8]:
            lines.append(f"- {data_file.get('filename')} | {data_file.get('file_type')} | {data_file.get('analysis_status')} | {truncate(data_file.get('parsed_summary') or data_file.get('description') or '', 140)}")
    else:
        lines.extend(_lines_for_memories(memories, "dataset_memory", 5))

    lines.append("5. Current conclusions:")
    lines.extend(_lines_for_memories(memories, "conclusion_memory", 6))

    lines.append("6. Failed or negative results:")
    lines.extend(_lines_for_memories(memories, "failure_memory", 6))

    lines.append("7. Important decisions:")
    lines.extend(_lines_for_memories(memories, "decision_memory", 6))

    lines.append("8. Pending tasks:")
    lines.extend(_lines_for_memories(memories, "task_memory", 6))

    lines.append("9. User or group preferences:")
    pref = [memory for memory in memories if memory.get("memory_type") in {"preference_memory", "user_profile_memory", "group_profile_memory", "writing_memory"}]
    if pref:
        for item in pref[:6]:
            lines.append(f"- {truncate(item.get('content') or '', 180)}")
    else:
        lines.append("- None found in active memory.")

    return _limit("\n".join(lines), max_tokens)
