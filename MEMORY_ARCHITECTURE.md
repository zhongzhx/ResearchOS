# ResearchOS/AURA Memory Architecture

This document defines the memory source of truth rules for ResearchOS/AURA.
The goal is to prevent answer generation, context compilation, and maintenance
jobs from treating compatibility indexes or exported views as canonical state.

## Source Of Truth

`research_group_os.sqlite` is the primary source of truth.

It owns the canonical records for:

- Projects: `projects`
- Tasks: `agent_tasks`, `literature_search_tasks`, `literature_ingest_items`, `skill_runs`, `execution_memory`
- Chat: `chat_sessions`, user-visible `chat_messages`, plus separate internal event tables
- Project memory: `agent_memory_entries`
- Literature metadata: `references`
- RAG text: `reference_chunks`
- Normalized project KB: `knowledge_base_entries`

Chat answer context must read these canonical tables first. If a fact appears
in another backend with a different value, the value from `research_group_os.sqlite`
wins.

## Backend Roles

`research_group_os.sqlite`

- Role: authoritative write/read store.
- Owner: `research_os_mvp`.
- Boundary: all project, task, chat, memory, literature, chunk, and KB state used
  by the context compiler and chat answer generation.

`agent_memory.sqlite`

- Role: compatibility layer or dedicated index.
- Owner: `agent_memory.database`.
- Boundary: may mirror or index memory for older workflows, but is derived from
  `research_group_os.sqlite` and must not override it.
- Sync policy: optional compatibility sync. Missing or stale rows must not block
  normal answers.

`lab_agent_mvp.sqlite`

- Role: legacy lab RAG index or import source.
- Owner: `lab_agent_features`.
- Boundary: may store old research interests, digest history, failure records,
  documents, and document chunks. It can be imported into the main DB, but chat
  answers must not use it as the only fact source.
- Sync policy: legacy import only.

`manage-agent-memory`

- Role: skill-local memory artifacts and compact context shards.
- Owner: `manage-agent-memory`.
- Boundary: useful for task artifacts and continuity files, not a canonical
  project-memory database.
- Sync policy: optional artifact export. Promote reviewed facts into
  `agent_memory_entries` before treating them as project memory.

`backend/researchos/brain`

- Role: Markdown Brain Repo.
- Owner: Brain Agent / human review workflow.
- Boundary: readable export, long-term summary, and human-reviewable knowledge
  view. Markdown pages do not overwrite the main DB.
- Sync policy: human-reviewable export from canonical records.

## Registry

The main DB contains `memory_backend_registry`.

Each row records:

- `memory_class`
- `backend_name`
- `owner`
- `source_of_truth`
- `derived_from`
- `sync_policy`
- `last_sync_time`
- `status`
- `notes`

The registry is bootstrapped at startup. Primary memory classes point to
`research_group_os.sqlite` with `source_of_truth=1`. Compatibility, legacy,
folder, and Markdown backends are registered as derived with `source_of_truth=0`.

## Query Rules

1. Context compilation reads canonical tables in `research_group_os.sqlite`.
2. Derived backends may be inspected for diagnostics or import, but they are not
   used as the only source for chat answers.
3. Context items from the main DB are tagged with:
   - `source_of_truth=research_group_os.sqlite`
   - `source_role=primary`
   - `memory_class=<canonical class>`
4. If a duplicate or conflicting fact exists in a derived backend, the canonical
   main DB row wins.
5. Derived backend absence is non-fatal. Missing `agent_memory.sqlite`,
   `lab_agent_mvp.sqlite`, managed-memory files, or Markdown exports must not
   block the context compiler.

## Health Check

`get_memory_source_of_truth_health()` verifies:

- The registry declares primary classes and derived backends.
- A temporary write into `agent_memory_entries` can be retrieved by the context
  compiler.
- Missing derived backends are treated as optional.
- Context items used for answers are primary, not derived.

This health check exists to protect the answer-generation path from silently
falling back to a stale compatibility or export backend.
