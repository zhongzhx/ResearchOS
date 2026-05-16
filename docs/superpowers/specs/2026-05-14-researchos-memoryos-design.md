# ResearchOS MemoryOS Design

## Goal

Add a product-grade MemoryOS framework to ResearchOS without rewriting the existing dual-agent runtime, legacy chat endpoint, Research Brain Repo, SkillRun records, execution memory, artifact registry, or task lifecycle.

## Recommended Approach

MemoryOS is added as an adapter-first backend framework under `backend/researchos/memory/`. It introduces unified `MemoryEvent` and `MemoryItem` schemas, short-term working memory, episodic task memory, semantic memory indexing over existing Brain Pages, cognitive state compilation, scoped context assembly, governance, decay/archive, health scanning, and autonomous learning recommendations.

The existing Research Brain Markdown repository remains the human-readable long-term source of truth. MemoryOS provides a structured index and governance layer around it. Existing `TaskSpec`, `ExecutionResult`, `BrainDecision`, `ContextEnvelope`, SkillRun, task lifecycle files, and artifact registry remain authoritative for their own domains.

## Architecture

MemoryOS stores append-only events in `data/memoryos/events/{project_id}/events.jsonl`, working state in `data/memoryos/working/`, episodes in `data/memoryos/episodic/`, semantic indexes in `data/memoryos/semantic/`, retrieval audits in `data/memoryos/retrieval_audits/`, health reports in `data/memoryos/health_reports/`, and archived records in `data/memoryos/archives/`.

Long-term writes flow through validation and evidence promotion:

`ExecutionResult -> validation_report -> evidence_promotion -> MemoryEvent -> MemoryItem -> Semantic Memory / Brain Page -> Context Index -> Research Graph -> Cognitive State -> Episode`

Execution Agent does not write long-term memory. It receives only `execution_minimal` context assembled from task-specific summaries, selected source references, validation rules, constraints, output schema, and selected skill instructions.

## Components

- `memory_event.py`: canonical event-source schema with secret redaction and validation.
- `memory_item.py`: canonical memory item schema with confidence, provenance, retrieval, decay, supersede, archive, and safety metadata.
- `events/event_store.py`: append-only JSONL event store with replay/export.
- `working/working_memory_store.py`: per-conversation short-term state with FIFO recent messages and current task pointer.
- `episodic/episodic_memory_store.py`: task and SkillRun summaries searchable by project.
- `semantic/semantic_memory_store.py`: structured long-term memory index synchronized with Brain Pages.
- `compression/cognitive_state.py`: compressed project state stored under `data/research_brain/projects/{project_id}/cognitive_state.json`.
- `retrieval/*`: memory retrieval, ranking, scoped context assembly, and retrieval audit.
- `governance/*`: merge, conflict, confidence, decay, archive, janitor, and maintenance APIs.
- `learning/*` and `eval/*`: health scanning, gap scanning, autonomous learning recommendations, leakage and budget checks.

## Integration Points

- `memory_writer.py`: commits promoted memory into MemoryOS before/while syncing Brain Pages.
- `evidence_promotion.py`: remains the gate deciding what may become long-term memory.
- `brain_agent.py`: reads cognitive state and assembled MemoryOS context before planning; refreshes cognitive state after commits.
- `coordinator.py`: writes user/task lifecycle events, updates working memory, creates episodes, and refreshes cognitive state after task completion.
- `research_agent_api.py`: exposes MemoryOS JSON endpoints while keeping legacy `/research-os/agent/chat` unchanged.

## Safety Rules

MemoryOS redacts API keys, tokens, cookies, passwords, bearer credentials, and secret-like values from events, memory items, logs, audits, and API responses. High-confidence memory requires provenance through `source_ids`, `task_ids`, `skillrun_ids`, `artifact_ids`, or user confirmation. Browser learning defaults to low confidence. Peer-review simulation output is stored as criticism/report, not factual evidence. Failed results can create failure memory and episodes, not success claims.

## Context Rules

Brain context may include cognitive state summary, project context index summary, selected semantic memories, episodes, failures, claims, skill summaries, and retrieval audit metadata.

Execution context may include only task brief, project short summary, selected task-relevant sources, validation rules, known constraints, required output schema, and selected skill instructions. It must not include full Research Brain Repo, full Agent Memory, full user profile, full Skill Library, full logs, secrets, unrelated files, or all claims/evidence.

## Scope Notes

The first implementation provides file-backed adapters and deterministic keyword ranking. Vector retrieval remains an adapter returning score `0` until a vector backend is configured. Autonomous learning is dry-run only and creates pending recommendations instead of executing browser, download, code, wet-lab, or external actions.
