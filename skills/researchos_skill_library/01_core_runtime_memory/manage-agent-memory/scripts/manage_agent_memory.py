from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import textwrap
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv", ".tsv", ".yaml", ".yml", ".py", ".sql"}
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|passwd|secret)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._-]+"),
]


@dataclass
class Artifact:
    path: str
    kind: str
    exists: bool
    size_bytes: int
    sha1: str


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_")
    if not text:
        return "task"
    if len(text) <= 60:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:51]}_{digest}"


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def redact(text: str) -> str:
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(lambda match: match.group(0).split("=", 1)[0] + "=<redacted>" if "=" in match.group(0) else "<redacted>", result)
    return result


def file_sha1(path: Path, max_bytes: int = 10_000_000) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha1()
    total = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                h.update(b"<truncated>")
                break
            h.update(chunk)
    return h.hexdigest()


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def init_memory(memory_root: Path) -> None:
    for name in ["tasks", "contexts", "artifacts", "knowledge_bases", "skills", "archive"]:
        (memory_root / name).mkdir(parents=True, exist_ok=True)
    manifest = memory_root / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "created_at": now(),
                    "memory_schema": "agent_memory_v1",
                    "description": "Central task memory and context shards for the research agent.",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    conn = open_index(memory_root)
    conn.close()


def open_index(memory_root: Path) -> sqlite3.Connection:
    memory_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(memory_root / "memory_index.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_records (
            task_id TEXT PRIMARY KEY,
            project_name TEXT,
            task_title TEXT,
            task_kind TEXT,
            summary TEXT,
            task_record_path TEXT,
            task_json_path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            task_id TEXT,
            path TEXT,
            kind TEXT,
            exists_flag INTEGER,
            size_bytes INTEGER,
            sha1 TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS context_shards (
            shard_id TEXT PRIMARY KEY,
            shard_path TEXT,
            shard_index INTEGER,
            size_bytes INTEGER,
            task_count INTEGER,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    return conn


def artifact_for(path_value: str) -> Artifact:
    path = Path(path_value).expanduser()
    resolved = path.resolve() if path.exists() else path
    if path.is_dir():
        kind = "directory"
    elif path.is_file():
        kind = "file"
    else:
        kind = "missing"
    return Artifact(
        path=str(resolved),
        kind=kind,
        exists=path.exists(),
        size_bytes=path_size(path),
        sha1=file_sha1(path),
    )


def summarize_artifact(artifact: Artifact, max_chars: int = 1200) -> str:
    path = Path(artifact.path)
    if not artifact.exists:
        return "Artifact missing at record time."
    if path.is_dir():
        entries = []
        for item in sorted(path.rglob("*"))[:60]:
            if item.is_file():
                try:
                    entries.append(f"{item.relative_to(path)} ({item.stat().st_size} bytes)")
                except OSError:
                    pass
        return "Directory sample:\n" + "\n".join(entries[:30])
    if path.suffix.lower() in TEXT_SUFFIXES:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return redact(text[:max_chars])
        except OSError:
            return "Could not read text preview."
    return f"Binary or unsupported preview. Size: {artifact.size_bytes} bytes."


def write_task_record(
    memory_root: Path,
    project_name: str,
    task_title: str,
    task_kind: str,
    summary: str,
    artifacts: list[Artifact],
    notes: str,
) -> tuple[str, Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_dir = memory_root / "tasks" / datetime.now().strftime("%Y%m%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    task_id = stable_id(project_name, task_title, task_kind, timestamp)
    slug = safe_slug(task_title)
    md_path = date_dir / f"{timestamp}_{slug}.md"
    json_path = date_dir / f"{timestamp}_{slug}.json"

    lines = [
        "# Agent Task Record",
        "",
        f"- Task id: {task_id}",
        f"- Project: {project_name}",
        f"- Title: {task_title}",
        f"- Kind: {task_kind}",
        f"- Created at: {now()}",
        "",
        "## Summary",
        "",
        redact(summary or "No summary provided."),
        "",
    ]
    if notes:
        lines.extend(["## Notes", "", redact(notes), ""])
    lines.extend(["## Artifacts", ""])
    for artifact in artifacts:
        lines.extend(
            [
                f"### {artifact.kind}: {artifact.path}",
                f"- Exists: {artifact.exists}",
                f"- Size bytes: {artifact.size_bytes}",
                f"- SHA1: {artifact.sha1 or 'not available'}",
                "",
                "Preview:",
                "",
                "```text",
                summarize_artifact(artifact),
                "```",
                "",
            ]
        )

    payload = {
        "task_id": task_id,
        "project_name": project_name,
        "task_title": task_title,
        "task_kind": task_kind,
        "summary": redact(summary),
        "notes": redact(notes),
        "artifacts": [asdict(item) for item in artifacts],
        "created_at": now(),
    }
    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return task_id, md_path, json_path


def record_task(args: argparse.Namespace) -> dict[str, Any]:
    memory_root = Path(args.memory_root)
    init_memory(memory_root)
    artifacts = [artifact_for(value) for value in args.artifact_path or []]
    task_id, md_path, json_path = write_task_record(
        memory_root,
        args.project_name,
        args.task_title,
        args.task_kind,
        args.summary,
        artifacts,
        args.notes,
    )
    conn = open_index(memory_root)
    conn.execute(
        """
        INSERT OR REPLACE INTO task_records(
            task_id, project_name, task_title, task_kind, summary, task_record_path, task_json_path, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task_id, args.project_name, args.task_title, args.task_kind, redact(args.summary), str(md_path), str(json_path), now()),
    )
    for artifact in artifacts:
        artifact_id = stable_id(task_id, artifact.path)
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts(
                artifact_id, task_id, path, kind, exists_flag, size_bytes, sha1, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, task_id, artifact.path, artifact.kind, 1 if artifact.exists else 0, artifact.size_bytes, artifact.sha1, now()),
        )
    conn.commit()
    conn.close()

    compact_result = None
    if args.auto_compact:
        compact_result = compact_memory(memory_root, args.max_shard_bytes, args.max_entry_bytes)
    return {"task_id": task_id, "task_record": str(md_path), "task_json": str(json_path), "compact": compact_result}


def task_entries(memory_root: Path, max_entry_bytes: int) -> list[str]:
    conn = open_index(memory_root)
    rows = conn.execute("SELECT * FROM task_records ORDER BY created_at").fetchall()
    entries = []
    for row in rows:
        artifacts = conn.execute("SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at", (row["task_id"],)).fetchall()
        lines = [
            f"## Task: {row['task_title']}",
            "",
            f"- Task id: {row['task_id']}",
            f"- Project: {row['project_name']}",
            f"- Kind: {row['task_kind']}",
            f"- Created at: {row['created_at']}",
            f"- Record: {row['task_record_path']}",
            "",
            "Summary:",
            redact(row["summary"] or ""),
            "",
            "Artifacts:",
        ]
        for artifact in artifacts:
            lines.append(f"- {artifact['kind']} | {artifact['path']} | {artifact['size_bytes']} bytes | sha1={artifact['sha1'] or 'n/a'}")
        entry = "\n".join(lines).strip() + "\n\n"
        encoded = entry.encode("utf-8")
        if len(encoded) <= max_entry_bytes:
            entries.append(entry)
        else:
            chunks = split_bytes(entry, max_entry_bytes)
            for idx, chunk in enumerate(chunks, 1):
                entries.append(f"## Task: {row['task_title']} part {idx}\n\n{chunk}\n\n")
    conn.close()
    return entries


def split_bytes(text: str, max_bytes: int) -> list[str]:
    paragraphs = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for line in paragraphs:
        line_bytes = len((line + "\n").encode("utf-8"))
        if current and current_bytes + line_bytes > max_bytes:
            chunks.append("\n".join(current))
            current = []
            current_bytes = 0
        if line_bytes > max_bytes:
            wrapped = textwrap.wrap(line, width=max(80, max_bytes // 4))
            for piece in wrapped:
                chunks.append(piece)
            continue
        current.append(line)
        current_bytes += line_bytes
    if current:
        chunks.append("\n".join(current))
    return chunks


def next_shard_path(contexts_dir: Path, index: int) -> Path:
    return contexts_dir / f"context_{index:04d}.md"


def compact_memory(memory_root: Path, max_shard_bytes: int, max_entry_bytes: int) -> dict[str, Any]:
    init_memory(memory_root)
    contexts_dir = memory_root / "contexts"
    for old in contexts_dir.glob("context_*.md"):
        old.unlink()

    header = [
        "# Agent Memory Context",
        "",
        f"- Generated at: {now()}",
        f"- Memory root: {memory_root.resolve()}",
        "",
        "This file is a compressed navigation context. Source task records and artifacts remain the source of truth.",
        "",
    ]
    header_text = "\n".join(header)
    entries = task_entries(memory_root, max_entry_bytes)
    shard_index = 1
    current = header_text
    current_count = 0
    shard_paths: list[Path] = []

    for entry in entries:
        if len((current + entry).encode("utf-8")) > max_shard_bytes and current_count > 0:
            path = next_shard_path(contexts_dir, shard_index)
            path.write_text(current, encoding="utf-8")
            shard_paths.append(path)
            shard_index += 1
            current = header_text
            current_count = 0
        if len((current + entry).encode("utf-8")) > max_shard_bytes:
            for chunk in split_bytes(entry, max(max_entry_bytes, max_shard_bytes - len(header_text.encode("utf-8")) - 1000)):
                if len((current + chunk).encode("utf-8")) > max_shard_bytes and current_count > 0:
                    path = next_shard_path(contexts_dir, shard_index)
                    path.write_text(current, encoding="utf-8")
                    shard_paths.append(path)
                    shard_index += 1
                    current = header_text
                    current_count = 0
                current += chunk + "\n\n"
                current_count += 1
            continue
        current += entry
        current_count += 1

    path = next_shard_path(contexts_dir, shard_index)
    path.write_text(current, encoding="utf-8")
    shard_paths.append(path)

    conn = open_index(memory_root)
    conn.execute("DELETE FROM context_shards")
    for idx, path in enumerate(shard_paths, 1):
        shard_id = stable_id(str(path), now())
        size = path.stat().st_size
        task_count = path.read_text(encoding="utf-8", errors="replace").count("## Task:")
        conn.execute(
            "INSERT INTO context_shards(shard_id, shard_path, shard_index, size_bytes, task_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (shard_id, str(path), idx, size, task_count, now()),
        )
    conn.commit()
    conn.close()

    latest = memory_root / "contexts" / "LATEST_CONTEXT.md"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    shutil.copyfile(shard_paths[-1], latest)

    return {
        "shard_count": len(shard_paths),
        "shards": [str(path) for path in shard_paths],
        "latest_context": str(latest),
    }


def memory_status(memory_root: Path) -> dict[str, Any]:
    init_memory(memory_root)
    conn = open_index(memory_root)
    task_count = conn.execute("SELECT COUNT(*) AS c FROM task_records").fetchone()["c"]
    artifact_count = conn.execute("SELECT COUNT(*) AS c FROM artifacts").fetchone()["c"]
    shards = [dict(row) for row in conn.execute("SELECT * FROM context_shards ORDER BY shard_index").fetchall()]
    conn.close()
    return {
        "memory_root": str(memory_root.resolve()),
        "size_bytes": path_size(memory_root),
        "task_count": task_count,
        "artifact_count": artifact_count,
        "context_shards": shards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage central agent memory and compact context shards.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--memory-root", required=True)

    record_p = sub.add_parser("record")
    record_p.add_argument("--memory-root", required=True)
    record_p.add_argument("--project-name", default="default_project")
    record_p.add_argument("--task-title", required=True)
    record_p.add_argument("--task-kind", default="task")
    record_p.add_argument("--summary", default="")
    record_p.add_argument("--notes", default="")
    record_p.add_argument("--artifact-path", action="append", default=None)
    record_p.add_argument("--auto-compact", action="store_true")
    record_p.add_argument("--max-shard-bytes", type=int, default=120000)
    record_p.add_argument("--max-entry-bytes", type=int, default=24000)

    compact_p = sub.add_parser("compact")
    compact_p.add_argument("--memory-root", required=True)
    compact_p.add_argument("--max-shard-bytes", type=int, default=120000)
    compact_p.add_argument("--max-entry-bytes", type=int, default=24000)

    status_p = sub.add_parser("status")
    status_p.add_argument("--memory-root", required=True)

    args = parser.parse_args()
    memory_root = Path(args.memory_root)
    if args.command == "init":
        init_memory(memory_root)
        result = {"memory_root": str(memory_root.resolve()), "status": "initialized"}
    elif args.command == "record":
        result = record_task(args)
    elif args.command == "compact":
        result = compact_memory(memory_root, args.max_shard_bytes, args.max_entry_bytes)
    elif args.command == "status":
        result = memory_status(memory_root)
    else:
        raise SystemExit(f"Unknown command: {args.command}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
