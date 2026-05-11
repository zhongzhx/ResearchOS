---
name: manage-agent-memory
description: Manage a central agent memory folder for long-running research agents. Use when Codex needs to record every task as a skill output or knowledge-base event, keep artifacts in one folder, compact oversized task context into summary shards, create new context files when a shard is full, and preserve continuity across many tasks without overloading the active prompt.
---

# Manage Agent Memory

## Overview

Use this skill as the memory lifecycle layer for the research agent. Every meaningful task should leave a small task record, links to artifacts, and a compact context summary in one central folder.

## Memory Folder

Default root:

```text
agent_memory/
  manifest.json
  memory_index.sqlite
  tasks/
  contexts/
  artifacts/
  knowledge_bases/
  skills/
  archive/
```

Do not put unrelated temporary files here. Store large outputs as artifacts and keep the active context as summaries.

## Fast Path

Initialize memory:

```powershell
py .\scripts\manage_agent_memory.py init --memory-root ".\agent_memory"
```

Record one completed task:

```powershell
py .\scripts\manage_agent_memory.py record --memory-root ".\agent_memory" --project-name "my_project" --task-title "Extract domain entities" --task-kind "skill" --summary "Extracted biological and materials entities from advisor notes." --artifact-path ".\extract-domain-entities"
```

Compact and shard context:

```powershell
py .\scripts\manage_agent_memory.py compact --memory-root ".\agent_memory" --max-shard-bytes 120000
```

Check status:

```powershell
py .\scripts\manage_agent_memory.py status --memory-root ".\agent_memory"
```

## Required Agent Behavior

At the end of every non-trivial task:

1. Record what was done with `record`.
2. Link files, folders, KB roots, skill folders, and output reports as artifacts.
3. Run `compact` when the memory folder or context shard exceeds the threshold.
4. When a context shard is full, create the next shard instead of overwriting it.
5. Use the latest context shard plus the project KB before starting a new task.

## What Gets Recorded

- Skill creation or update.
- Knowledge-base ingestion.
- Literature search or browser learning run.
- Entity extraction.
- Experiment design.
- Experiment result analysis.
- Bottleneck diagnosis.
- Weekly report.
- Important user decision or advisor feedback.

## Compaction Rule

Compaction is not deletion. It creates summary shards under `contexts/` while keeping original task records and artifact links.

If one compressed summary entry is still too large, split it into continuation entries. If the current context shard is full, write the next file:

```text
contexts/context_0001.md
contexts/context_0002.md
contexts/context_0003.md
```

## References

Read `references/memory_lifecycle.md` when changing storage rules or integrating this into runtime APIs.

## Rules

- Keep names explicit: use `task_record`, `context_shard`, `artifact_manifest`, `knowledge_base_root`.
- Do not call compressed summaries the source of truth; they are navigation aids.
- Do not store passwords, tokens, private identifiers, or sensitive raw data in context shards.
- Preserve source paths and hashes so artifacts can be found later.
- Prefer append-only records over rewriting history.
