# AURA Research Project Workspace Isolation Design

## Goal

Give every AURA Research project one stable, auditable local workspace. The normal client must show the active project identity and truthful project status while all project-bound reads, writes, chats, KB/RAG operations, workflow runs, and artifacts remain isolated by explicit `project_id`.

## Reset Policy

This delivery intentionally does not migrate legacy local projects. Existing local runtime directories and browser caches are discarded. New projects use only the canonical layout below. The client performs a one-time cache schema reset so stale `localStorage` records cannot reappear after the backend reset.

## Runtime Boundary

`backend/researchos/workspace/project_workspace.py` owns the filesystem contract. MVP runtime code remains under `backend/`; registered skills remain under `skills/`.

Each project root is:

```text
RESEARCHOS_AGENT_ROOT/projects/{project_id}/
```

Each project contains:

```text
inbox/
papers/
papers/pdfs/
papers/manual_queue/
kb/
rag/
chats/
workflows/
runs/
artifacts/
artifacts/markdown/
artifacts/pptx/
artifacts/figures/
artifacts/tables/
artifacts/data/
logs/
tmp/
manifests/
project_manifest.json
```

Legacy database columns remain usable as compatibility aliases:

- `root_dir` -> project root
- `uploads_dir` -> `inbox/`
- `pdf_dir` -> `papers/pdfs/`
- `kb_dir` -> `kb/`

## Manifest And Status

`project_manifest.json` is refreshed from authoritative database and filesystem state. It contains:

- `display_name`
- `project_id`
- `created_at`
- `updated_at`
- `root_path`
- `kb_path`
- `rag_path`
- `artifact_path`
- `file_count`
- `reference_count`
- `kb_entry_count`
- `rag_chunk_count`
- `workflow_run_count`
- `last_activity_at`

The API status response also exposes normal-user summaries for library readiness, KB/RAG status, artifact count, latest workflow run, and archive state. Developer-only details include the database path, debug log path, full path map, and raw JSON.

## API Contract

The MVP HTTP runtime exposes:

- `GET /research-os/projects`
- `GET /research-os/projects/{project_id}`
- `GET /research-os/projects/{project_id}/status`
- `GET /research-os/projects/{project_id}/paths`
- `POST /research-os/projects`
- `POST /research-os/projects/{project_id}/archive`
- `POST /research-os/projects/{project_id}/clear`
- `POST /research-os/projects/{project_id}/purge`

Every project mutation receives its target `project_id` in the URL or payload. There is no silent fallback to `default`. `purge` executes only when the JSON payload contains `confirm: true`.

## Clear And Purge

`clear` deletes project files, chats, KB/RAG records, file indexes, workflow records, runs, and generated artifacts. It preserves the project row and immediately recreates the empty canonical directory tree and base manifest.

`purge` deletes all project-scoped records and the entire project directory. It keeps only the existing minimal purge audit record outside the project workspace.

## Client Context

`activeProjectId` is the only active project selector. Chat, Workspace, Library, Runs, and Settings read it directly. When it changes:

- chat conversation view and pending chat workflow are cleared;
- workspace draft, plan, result, and form values are cleared;
- library refreshes from the selected project only;
- workflow history and artifact cache helpers reject empty project IDs;
- API chat and coordinator calls reject empty project IDs instead of sending `default`.

The Projects page shows a normal-user status card with project name, project ID, root path, library status, KB/RAG status, file count, artifact count, latest workflow run, update time, and archive state. Developer mode adds database path, debug log path, and raw JSON.

## Error Handling

- Missing `project_id`: return a friendly validation error.
- No project selected: block Chat and workflow execution in the client.
- KB/RAG not built: return `not_connected` or `needs_input` as appropriate; never claim success.
- Empty workflow history: display an empty state, not a fabricated run.
- Failed clear or purge deletion: return `failed` with the failed paths or tables.

## Verification

Add tests for canonical layout, manifest fields, A/B isolation, clear versus purge behavior, HTTP status and paths routes, purge confirmation, and client status/context-reset contracts. Run `npm run client:check` and the Python unittest suite.
