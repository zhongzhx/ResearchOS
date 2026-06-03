# AURA Artifact, Coding Runtime, Workflow, and UI Design

## Scope

This repair delivers four connected product capabilities:

1. A project-scoped file and artifact registry.
2. A local coding runtime for real scientific deliverables.
3. A workflow execution service for nature-like workflows.
4. A user-facing desktop UI that hides developer details by default.

The implementation extends the existing MVP SQLite database and `ProjectWorkspace`.
It does not introduce a second database.

## Artifact Registry

`FileArtifactRegistry` is the canonical service for user files and generated files.
Every artifact belongs to an existing `project_id`. Files are stored beneath the
project workspace and registered in the existing `artifacts` table with additive
columns for source, run, path, hash, size, MIME type, ingest state, KB state, and
RAG state.

The registry rejects path traversal and cross-project reads. Deletion first marks
an artifact as `deleted`; physical deletion only happens when explicitly requested
or when a project is purged.

## Coding Runtime

`CodingRuntimeService` creates an isolated run workspace:

```text
projects/{project_id}/runs/{run_id}/
  workspace/
  outputs/
  logs/
```

Inputs must be registered project artifacts or explicit `TaskSpec.input_files`.
Outputs must stay under `outputs/`. Python commands use argv execution without
`shell=True`. Standard templates generate real Markdown, CSV, SVG, PNG, and PPTX
files and register each output.

## Workflow Execution

`WorkflowExecutionService` reads machine-readable JSON pipeline definitions,
validates project scope and required inputs, creates a run record, calls a
nature-like handler or coding runtime template, registers artifacts, and returns
an honest result. A successful response requires a real `run_id` and registered
artifacts. Missing material returns `needs_file` or `needs_input`; unavailable
capabilities return `not_connected`.

## UI

The normal UI exposes Chat, Workspace, Projects, Library, and Settings. Developer
mode adds technical views and raw diagnostics. Workspace execution uses the real
workflow endpoint after confirmation. Library cards show readable artifact
metadata and preview hints. Raw JSON is developer-only.

## Verification

Tests cover project isolation, deduplication, safe paths, deleted artifacts,
ingest state, coding runtime templates, real nature-like workflow artifacts,
honest failure states, chat routing, workspace integration, and developer-mode
visibility.
