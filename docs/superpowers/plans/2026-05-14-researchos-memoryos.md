# ResearchOS MemoryOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a file-backed MemoryOS framework and connect it to ResearchOS promotion, task, context, and API boundaries.

**Architecture:** Add focused modules under `backend/researchos/memory/` using JSON/JSONL stores. Keep existing Research Brain Markdown pages as the long-term human-readable source of truth while MemoryOS acts as structured schema, governance, retrieval, and audit layer.

**Tech Stack:** Python standard library, dataclasses, JSON/JSONL storage, existing ResearchOS Brain Page, Context Index, Graph, TaskSpec, ExecutionResult, Coordinator, and standard-library HTTP server.

---

### Task 1: Core Schemas and Stores

**Files:**
- Create: `backend/researchos/memory/memory_config.py`
- Create: `backend/researchos/memory/memory_types.py`
- Create: `backend/researchos/memory/memory_event.py`
- Create: `backend/researchos/memory/memory_item.py`
- Create: `backend/researchos/memory/events/event_store.py`
- Test: `tests/test_memory_event.py`, `tests/test_memory_item.py`, `tests/test_event_store.py`

- [ ] Write failing tests for event creation, redaction, append, replay, and high-confidence provenance validation.
- [ ] Run targeted tests and confirm imports fail.
- [ ] Implement path helpers, schema dataclasses, redaction, validation, serialization, and append-only event storage.
- [ ] Run targeted tests and confirm they pass.

### Task 2: Working, Episodic, and Semantic Memory

**Files:**
- Create: `backend/researchos/memory/working/working_memory_store.py`
- Create: `backend/researchos/memory/episodic/episodic_memory_store.py`
- Create: `backend/researchos/memory/semantic/semantic_memory_store.py`
- Test: `tests/test_working_memory_store.py`, `tests/test_episodic_memory_store.py`, `tests/test_semantic_memory_store.py`

- [ ] Write failing tests for FIFO messages, current task, task/SkillRun episodes, failed episodes, and Brain Page sync.
- [ ] Implement JSON stores and adapters over task lifecycle files, SkillRun records, and Brain Pages.
- [ ] Run targeted tests and confirm they pass.

### Task 3: Cognitive State, Retrieval, Context Assembly

**Files:**
- Create: `backend/researchos/memory/compression/cognitive_state.py`
- Create: `backend/researchos/memory/compression/cognitive_compiler.py`
- Create: `backend/researchos/memory/retrieval/hybrid_ranker.py`
- Create: `backend/researchos/memory/retrieval/memory_retriever.py`
- Create: `backend/researchos/memory/retrieval/context_assembler.py`
- Create: `backend/researchos/memory/retrieval/retrieval_audit.py`
- Test: `tests/test_cognitive_state.py`, `tests/test_context_assembler.py`, `tests/test_memory_retriever.py`

- [ ] Write failing tests for cognitive compilation, brain context, execution-minimal context, retrieval count updates, and no secret/full repo leakage.
- [ ] Implement deterministic keyword ranking with vector/graph adapters left non-failing.
- [ ] Run targeted tests and confirm they pass.

### Task 4: Governance, Decay, Health, Learning

**Files:**
- Create governance, learning, and eval modules listed in the request.
- Test: `tests/test_memory_governance.py`, `tests/test_decay_policy.py`, `tests/test_memory_health_scanner.py`, `tests/test_autonomous_learning_loop.py`

- [ ] Write failing tests for decay, reinforce, archive, conflict marking, duplicate/stale/unsupported claim scanning, and dry-run recommendations.
- [ ] Implement conservative file-backed governance with archive-not-delete semantics.
- [ ] Run targeted tests and confirm they pass.

### Task 5: Integration and API

**Files:**
- Modify: `backend/researchos/brain/memory_writer.py`
- Modify: `backend/researchos/agents/brain_agent.py`
- Modify: `backend/researchos/agents/coordinator.py`
- Modify: `backend/researchos/api/dual_agent_routes.py`
- Modify: `skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/scripts/research_agent_api.py`
- Test: `tests/test_memoryos_integration.py`

- [ ] Write failing integration tests for promotion -> MemoryEvent/MemoryItem, task completion -> episode/cognitive refresh, API no secrets, and legacy isolation.
- [ ] Connect promoted memory commit to MemoryOS and add safe API handlers.
- [ ] Run targeted integration tests.
- [ ] Run `py -m unittest discover -s tests -p "test_*.py"`.
- [ ] Run `$env:LLM_PROVIDER='mock'; py -m unittest discover -s research-agent-runtime\scripts\tests -p "test_research_os_mvp.py"` if that path exists, otherwise run the equivalent skill runtime test path under `skills/researchos_skill_library/01_core_runtime_memory/research-agent-runtime/scripts/tests`.
