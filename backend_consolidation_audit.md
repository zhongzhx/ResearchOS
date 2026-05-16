# ResearchOS Backend Consolidation Audit

Date: 2026-05-17

## MVP Runtime Source of Truth Policy

`backend/researchos` is a service library and adapter layer. In plain text for audit checks: backend/researchos is a service library and adapter layer. Duplicate behavior must prefer the MVP runtime and should only use `backend/researchos` as an additive adapter or feature service.

Protected MVP chain:

1. `backend/research_agent_runtime/scripts/research_agent_api.py`
2. `research_os_mvp.agent_chat(...)`
3. `research_context_compiler.compile_research_context(...)`
4. `researchos_prompt_router.compose_runtime_prompt(...)`
5. `LLMAdapter.chat_text(...)`

The protected chat route remains:

```text
POST /research-os/agent/chat
```

## Directory Boundary

`backend/` owns HTTP server code, MVP runtime code, `research_os_mvp.py`, `research_agent_api.py`, `research_context_compiler.py`, prompt routing, global agent system prompts, RAG, memory, context compiler, task lifecycle, product feature bridges, skill dispatch/runtime loading, and LLM settings/gateway.

`skills/researchos_skill_library/` owns only registerable skill material: manifests, `SKILL.md`, skill-specific prompts, parameter schemas, examples, lightweight scripts, `skill_catalog.json`, `pipeline_registry.json`, and resolver metadata.

`skills/` must not contain HTTP server code, global agent runtime, global system prompt files, full context compiler, memory/database runtime, `ThreadingHTTPServer`, `BaseHTTPRequestHandler`, FastAPI app definitions, `research_os_mvp.py`, or `research_agent_api.py`.

## Runtime Assets Migrated Out Of Skills

Moved from:

```text
skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/
```

Moved to:

```text
backend/research_agent_runtime/prompts/
backend/research_agent_runtime/config/
backend/research_agent_runtime/templates/
```

Specific migrated assets:

- Global system prompt: `backend/research_agent_runtime/prompts/researchos_agent_system_prompt.md`
- zh prompt fragments: `backend/research_agent_runtime/prompts/zh/*.md`
- Runtime prompt config: `backend/research_agent_runtime/config/openai.yaml`
- Runtime reference templates: `backend/research_agent_runtime/templates/references/*.md`

The `research-agent-runtime` wrapper is no longer registered in `skills/researchos_skill_library/skill_catalog.json` and no longer appears in `legacy_skill_path_map.json`.

## Skills Still Kept In Skills

The skill library still keeps true registerable skills, including:

- Core memory/control skills: `manage-agent-memory`, `ingest-research-evidence`, `build-user-research-kb`, `skill-router-orchestrator`, `evidence-promotion`, `context-compiler-maintenance`, `skill-output-validator`
- Literature/browser ingestion skills: `keyword-research-harvest`, `compliant-literature-access`, `extract-first-article-keywords`, `browser-research-learning`, browser-use reference skills
- Research design/protocol skills: `plan-research-route`, `protocol-extraction`, `sop-generation`, `design-experiment-matrix`, `extract-domain-entities`
- Data/writing/review skills: `parse-scientific-data`, `analyze-experiment-results`, `result-narrative`, `peer-review-simulation`, `failure-log`, `weekly-research-report`, `weekly-research-digest`
- Nature workflow skills: `nature-citation`, `nature-figure`, `nature-paper2ppt`, `nature-polishing`, `nature-response`, `nature-data`

## Compatibility Fallbacks

New code defaults to:

```text
backend/research_agent_runtime/prompts/
```

Compatibility fallback remains only for old prompt/runtime references:

```text
skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/
skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/prompts/
```

Fallback is implemented in:

- `backend/research_agent_runtime/scripts/runtime_paths.py`
- `backend/researchos/prompts/mvp_prompt_adapter.py`
- `backend/researchos/integration/mvp_runtime_bridge.py`
- `backend/researchos/execution/runtime_adapter.py`

Fallback emits a `DeprecationWarning` and should be removed after downstream callers stop referencing the old skill-library runtime path.

## Current True Trunk Files

- `backend/research_agent_runtime/scripts/research_agent_api.py`
  - True HTTP server entrypoint.
  - Uses `ThreadingHTTPServer` and `Handler`.
  - Exposes legacy `/research-os/...` routes and newer `/api/...` adapter routes.
- `backend/research_agent_runtime/scripts/research_os_mvp.py`
  - Main MVP domain module.
  - Owns project, task, references, memory, RAG, literature, workflow, prompt-routing, and `agent_chat`.
- `backend/research_agent_runtime/scripts/researchos_agent_prompt.py`
  - MVP system prompt loader/composer.
  - Loads `backend/research_agent_runtime/prompts/researchos_agent_system_prompt.md` and zh policy fragments.
- `backend/research_agent_runtime/scripts/researchos_prompt_router.py`
  - Prompt policy resolver and runtime prompt composer.
  - Pulls selected skill prompt metadata from MVP SQLite registry when present.
- `backend/research_agent_runtime/scripts/research_context_compiler.py`
  - Research context compiler used by `agent_chat`.
  - Sanitizes user-visible context and hides internal fields.

## Agent Chat / Context Compiler Chain

1. `research_agent_api.Handler.do_POST`
2. `/research-os/agent/chat`
3. `research_os_mvp.agent_chat(...)`
4. `research_context_compiler.compile_research_context(...)`
5. `research_os_mvp.query_research_rag(...)` when RAG is needed
6. `researchos_prompt_router.compose_runtime_prompt(...)`
7. `LLMAdapter.chat_text(...)`
8. `research_context_compiler.sanitize_context_for_user_answer(...)`

## Deprecated Paths To Delete Later

- Any downstream reference to `skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/`
- Any persisted SkillRun or legacy DB row that calls `research-agent-runtime` as a normal skill
- Any documentation example that treats runtime data as living under `skills/researchos_skill_library`

## Recommended Fusion Order

1. Keep prompt adapters pointed at `backend/research_agent_runtime/prompts`.
2. Keep legacy `/research-os/...` APIs on the MVP trunk.
3. Route additive `/api/...` endpoints through bridge functions where practical.
4. Keep product demo/dry-run flows truthfully labelled as `partial`, `not_connected`, `needs_authorization`, or `parser_not_connected`.
5. Keep generated skills pending review until explicitly activated.
6. Continue directory-boundary tests so backend runtime assets do not re-enter `skills/researchos_skill_library`.
