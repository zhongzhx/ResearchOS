# ResearchOS Backend Consolidation Audit

Date: 2026-05-14

## Scope

Audited paths:

- MVP runtime trunk: `backend/research_agent_runtime/scripts`
- New service library: `backend/researchos`
- Web client: `web_client`
- Electron shell: `electron`

## MVP Runtime Source of Truth Policy

`backend/researchos` is a service library and adapter layer. In plain terms: backend/researchos is a service library and adapter layer. It may add supplemental features, product flows, experimental dual-agent task handling, and integration helpers, but it must not become a competing backend trunk.

Duplicate behavior must prefer the MVP runtime. When both MVP runtime and `backend/researchos` provide prompt loading, prompt routing, safety/context policy, skill routing, LLM calls, project/task/memory APIs, or chat behavior, the active route must call the MVP implementation first and only use the new backend as an additive fallback or feature extension.

Protected MVP chain:

1. `research_agent_api.py`
2. `research_os_mvp.agent_chat(...)`
3. `research_context_compiler.compile_research_context(...)`
4. `researchos_prompt_router.compose_runtime_prompt(...)`
5. `LLMAdapter.chat_text(...)`

MVP prompt content must remain loaded from `prompts/researchos_agent_system_prompt.md` and the MVP prompt fragments. New backend prompt extensions must not be appended to the runtime system prompt unless a future change explicitly routes through the MVP prompt router.

## Current True Trunk Files

- `backend/research_agent_runtime/scripts/research_agent_api.py`
  - True HTTP server entrypoint.
  - Uses `ThreadingHTTPServer` and `Handler`.
  - Starts from `main()` with `--host`, `--port`, and required `--agent-root`.
  - Exposes legacy `/research-os/...` routes and newer `/api/...` adapter routes.
- `backend/research_agent_runtime/scripts/research_os_mvp.py`
  - Main MVP domain module.
  - Owns project, task, references, memory, RAG, literature, workflow, prompt-routing, and `agent_chat`.
- `backend/research_agent_runtime/scripts/researchos_agent_prompt.py`
  - MVP system prompt loader/composer.
  - Loads `prompts/researchos_agent_system_prompt.md` and zh policy fragments.
- `backend/research_agent_runtime/scripts/researchos_prompt_router.py`
  - Prompt policy resolver and runtime prompt composer.
  - Pulls selected skill prompt metadata from MVP SQLite registry when present.
- `backend/research_agent_runtime/scripts/research_context_compiler.py`
  - Research context compiler used by `agent_chat`.
  - Sanitizes user-visible context and hides internal fields.
- `backend/research_agent_runtime/scripts/rag_retrieval_service.py`
  - Unified local RAG retrieval service used by MVP RAG paths.
- `backend/research_agent_runtime/scripts/research_memory_canonical.py`
  - Canonical project memory/context helpers behind `/research-os/memory/context`.
- `backend/research_agent_runtime/scripts/agent_memory/*`
  - Legacy local agent memory API and stores.
- `backend/research_agent_runtime/scripts/lab_agent_features.py`
  - Legacy feature adapters for data parsing, peer review, SOP, weekly digest, RAG ingestion, and failures.

## True HTTP Server Entry

Current true HTTP server after backend consolidation:

`backend/research_agent_runtime/scripts/research_agent_api.py`

Evidence:

- Imports `BaseHTTPRequestHandler` and `ThreadingHTTPServer`.
- Defines `class Handler(BaseHTTPRequestHandler)`.
- `main()` creates `ThreadingHTTPServer((args.host, args.port), Handler)` and calls `serve_forever()`.
- Electron starts this canonical script directly.

The HTTP server code now lives under `backend/research_agent_runtime/scripts`; no independent `backend/researchos` HTTP server was found. `backend/researchos/api/dual_agent_routes.py` has optional FastAPI `APIRouter` declarations, but is currently imported as a service adapter by `research_agent_api.py`.

## `/research-os/agent/chat` Handler

The real handler is in `research_agent_api.py`:

- POST path: `/research-os/agent/chat`
- Also aliases `/api/llm/chat`
- Calls `research_os.agent_chat(CONFIG.agent_root, payload)`

The implementation is in `research_os_mvp.py`:

- Function: `agent_chat(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]`
- It references `research_context_compiler.compile_research_context`
- It builds runtime prompts through `prompt_router.compose_runtime_prompt`
- It can call `query_research_rag`
- It sanitizes context through `research_context_compiler.sanitize_context_for_user_answer`

This route is a protected legacy interface and must not be replaced.

## MVP System Prompt / Router / Context Chain

System prompt sources:

- `skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/prompts/researchos_agent_system_prompt.md`
- `skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/prompts/zh/*.md`

Prompt loader/composer:

- `researchos_agent_prompt.PROMPT_PATH`
- `researchos_agent_prompt.load_researchos_system_prompt()`
- `researchos_agent_prompt.compose_researchos_prompt(...)`
- `researchos_agent_prompt.build_researchos_messages(...)`

Prompt router:

- `researchos_prompt_router.resolve_prompt_policy(...)`
- `researchos_prompt_router.compose_runtime_prompt(...)`
- Reads selected skill prompt metadata from `skill_registry` when a selected skill is known.
- It currently truncates registry `instruction_body` to 6000 characters; this is selected-skill loading, not full Skill Library loading.

Agent chat/context compiler chain:

1. `research_agent_api.Handler.do_POST`
2. `/research-os/agent/chat`
3. `research_os_mvp.agent_chat(...)`
4. `research_context_compiler.compile_research_context(...)`
5. `research_os_mvp.query_research_rag(...)` when RAG is needed
6. `researchos_prompt_router.compose_runtime_prompt(...)`
7. `LLMAdapter.chat_text(...)`
8. `research_context_compiler.sanitize_context_for_user_answer(...)`

## Old Data/API Surface

Important existing `/research-os/...` interfaces already exposed by `research_agent_api.py`:

- Projects: `/research-os/projects`, `/research-os/projects/{id}`, project status/export/archive/clear/purge/evidence-review.
- Tasks: `/research-os/tasks`, `/research-os/tasks/{id}`, run/cancel, natural language parse/create.
- Agent chat/feed/scheduler: `/research-os/agent/chat`, `/research-os/agent-feed`, `/research-os/agent/scheduler/status`, `/research-os/agent/scheduler/run`.
- References/literature/RAG: `/research-os/references`, `/research-os/reference-chunks`, `/research-os/knowledge-base-entries`, `/research-os/rag-queries`, `/research-os/rag/query`, `/research-os/literature/*`.
- Memory/context: `/research-os/memory`, `/research-os/memory/context`, `/research-os/memory/search`, `/research-os/memory/review-queue`, `/research-os/agent-memory`.
- Skill runs/execution memory: `/research-os/skill-runs`, `/research-os/execution-memory`, `/research-os/skills`, `/research-os/skills/{id}/run`.
- Canonical research objects: conclusions, decisions, failures, claims, protocols, reports, relationships, files, data-contexts, workflow-board.

These are the MVP trunk APIs and should remain stable.

## `backend/researchos` Modules Ready to Fuse

Usable as service modules/adapters:

- `backend/researchos/agents`
  - `AgentCoordinator`, `ResearchBrainAgent`, `ResearchExecutionAgent`, protocol dataclasses.
  - Status: experimental service, usable behind feature flags.
- `backend/researchos/api/dual_agent_routes.py`
  - Plain Python route functions used by MVP HTTP adapter.
  - Optional FastAPI router exists but must not become a competing server.
- `backend/researchos/brain`
  - Evidence promotion, graph, context index, memory writer, post-task reflection, skill crystallization/review.
  - Status: service layer; long-term writes should remain gated by `evidence_promotion`.
- `backend/researchos/memory`
  - Working memory, episodic, semantic, events, retrieval, governance, cognitive state, autonomous learning.
  - Status: enhancement layer; should not replace MVP canonical memory.
- `backend/researchos/tasks`
  - `ResearchTaskStateStore` persists task lifecycle files under `data/research_tasks/{task_id}` or `RESEARCHOS_TASKS_ROOT`.
  - Status: usable for new dual-agent/product flows.
- `backend/researchos/skills`
  - Catalog, pipeline registry, resolver, runtime loader.
  - Status: usable as selected-skill/pipeline service; pending generated skills remain review-gated.
- `backend/researchos/execution`
  - Runtime adapter, tool dispatcher, task runner, execution validator.
  - Status: usable with security constraints; parsers/browser remain not connected unless explicitly wired.
- `backend/researchos/product`
  - Product feature registry and flow wrappers.
  - Status: mixed; several flows are demo/partial and must be labelled truthfully.
- `backend/researchos/config`, `backend/researchos/settings`, `backend/researchos/llm`
  - Env, path, LLM settings, secret store, gateway.
  - Status: usable but should be called through MVP HTTP adapter.

## Missing Required Bridge/Prompt Modules

The following required directories/files were not present at audit time:

- `backend/researchos/prompts/__init__.py`
- `backend/researchos/prompts/mvp_prompt_adapter.py`
- `backend/researchos/prompts/agent_prompt_rules.py`
- `backend/researchos/integration/__init__.py`
- `backend/researchos/integration/mvp_runtime_bridge.py`
- `backend/researchos/integration/mvp_api_bridge.py`
- `backend/researchos/integration/mvp_memory_bridge.py`
- `backend/researchos/integration/mvp_skill_bridge.py`
- `backend/researchos/integration/mvp_task_bridge.py`
- `backend/researchos/integration/mvp_product_bridge.py`

These should be added as thin adapters that call the MVP trunk and existing service modules.

## Conflict Modules

- `backend/researchos/api/dual_agent_routes.py`
  - Contains FastAPI router declarations. These are not currently serving independently, but should remain secondary to `research_agent_api.py`.
- `backend/researchos/agents/coordinator.py`
  - Owns a dual-agent chat/task chain. It must remain experimental and must not replace `research_os_mvp.agent_chat`.
- `backend/researchos/memory/*`
  - Adds MemoryOS stores. These must enhance MVP memory and Research Brain, not become a second source of truth.
- `backend/researchos/product/feature_flows.py`
  - Some demo/dry-run flows record MVP SkillRuns for visibility. Status labels need stricter truthfulness.
- `backend/researchos/skills/runtime_skill_loader.py`
  - Must continue to block `pending_review` generated skills from automatic execution.

## New Backend Partial/Demo Areas

- Literature harvest external search/browser/PDF download is not fully connected; should be `partial` or `not_connected`.
- Data parser supports inline CSV-style flow but not general XLSX/file parser; unsupported parser path must be `parser_not_connected`.
- Browser/remote browser authorization is not generally connected; should return `needs_authorization`.
- Subscription LLM gateway returns `not_connected` in local build.
- Product demo flows are dry-run/demo visibility paths, not proof of ready execution.
- Optional FastAPI route declarations are adapter-compatible only; they are not the true server.

## Web Client API Contract

`web_client/api.js` calls backend through `/api/backend`, proxied by `electron/main.js` to the MVP HTTP server.

Client endpoints found:

- Existing MVP endpoints: `/health`, `/research-os/projects`, `/research-os/tasks`, `/research-os/references`, `/research-os/memory/context`, `/research-os/memory/review-queue`, `/research-os/agent/chat`, `/research-os/skill-runs`, `/research-os/execution-memory`, `/research-os/claims`, `/research-os/decisions`, `/research-os/failures`, `/research-os/protocols`, `/research-os/reports`, `/research-os/relationships`, `/research-os/files`, `/research-os/runtime/status`, `/research-os/agent/scheduler/status`, `/research-os/reference-chunks`, `/research-os/knowledge-base-entries`, `/research-os/rag-queries`, `/research-os/literature/search-tasks`, `/research-os/literature/paper-requests`, `/research-os/literature/unmatched-pdfs`, `/research-os/agent-feed`, `/research-os/workflow-board`.
- New adapter endpoints: `/api/agents/coordinator/run`, `/api/demo/dual-agent`, `/api/product/features`, `/api/product/features/{feature_id}`, `/api/product/features/{feature_id}/run`, `/api/product/features/{feature_id}/demo`, `/api/demo/product-flow/run`, `/api/skills/catalog`, `/api/skills/pipelines`, `/api/skills/route`, `/api/skills/resolver/check`, `/api/self-evolution/pending-skills`, `/api/self-evolution/skills/{skill_name}/activate`, `/api/self-evolution/skills/{skill_name}/reject`, `/api/settings/llm`, `/api/settings/llm/test`.

Missing or incomplete for requested MemoryOS client contract:

- `web_client/api.js` does not currently expose direct helpers for `/api/memory/working`, `/api/memory/cognitive-state`, `/api/memory/episodes`, `/api/memory/items`, `/api/memory/search`, `/api/memory/health`, `/api/memory/events`, `/api/memory/maintenance/run`, `/api/memory/autonomous-learning/check`.
- Current Research Brain view still uses MVP `/research-os/...` canonical endpoints, which is acceptable for trunk continuity but does not exercise the MemoryOS API surface.

## APIs That Must Not Move

- `POST /research-os/agent/chat`
- `GET/POST /research-os/projects`
- `GET/POST /research-os/tasks`
- `GET/POST /research-os/references`
- `GET/POST /research-os/memory/context`
- `/research-os/literature/*`
- `/research-os/rag/query`
- `/research-os/skill-runs`
- `/research-os/execution-memory`
- `/memory/*` legacy agent-memory compatibility routes

## Recommended Fusion Order

1. Add prompt adapters that locate and reuse MVP prompt sources without modifying prompt content.
2. Add integration bridge package with thin runtime/API/memory/skill/task/product adapters.
3. Route `research_agent_api.py` new `/api/...` endpoints through bridge functions where practical, leaving legacy `/research-os/...` untouched.
4. Tighten Product Feature truthfulness: ready only for genuinely connected paths; demo/dry-run is explicit; parser/browser/PDF gaps return `partial`, `not_connected`, `needs_authorization`, or `parser_not_connected`.
5. Add client helpers for MemoryOS endpoints while keeping Research Brain canonical MVP calls.
6. Add/align tests for prompt discovery, bridge behavior, route gating, secret masking, product status, task lifecycle persistence, evidence promotion gate, and tool security.
7. Run full `py -m unittest discover -s tests -p "test_*.py"` and MVP script tests.
