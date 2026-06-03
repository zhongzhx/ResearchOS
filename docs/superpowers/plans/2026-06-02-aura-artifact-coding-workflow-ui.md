# AURA Artifact, Coding Runtime, Workflow, and UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver project-scoped artifacts, real local scientific file generation, real nature-like workflow execution, and a non-technical desktop UI.

**Architecture:** Extend the MVP SQLite database additively and keep `ProjectWorkspace` as the filesystem authority. Add focused registry, runtime, and workflow services in `backend/researchos`, then expose them through the existing MVP HTTP adapter. Update the plain HTML client to consume honest backend state.

**Tech Stack:** Python 3, SQLite, pathlib, subprocess argv execution, csv, matplotlib, python-pptx, plain HTML/CSS/JavaScript, unittest.

---

### Task 1: File Artifact Registry

**Files:**
- Create: `backend/researchos/workspace/file_artifact_registry.py`
- Modify: `backend/research_agent_runtime/scripts/research_os_mvp.py`
- Modify: `backend/research_agent_runtime/scripts/research_agent_api.py`
- Test: `tests/test_artifact_registry.py`
- Test: `tests/test_file_project_isolation.py`
- Test: `tests/test_kb_ingest_status.py`

- [ ] Add failing tests for safe project paths, hash dedupe, soft delete, and cross-project rejection.
- [ ] Extend the `artifacts` schema with additive registry columns.
- [ ] Implement registration, listing, lookup, ingest state updates, open info, and soft deletion.
- [ ] Expose file and project artifact APIs.
- [ ] Run registry tests until green.

### Task 2: Coding Runtime

**Files:**
- Create: `backend/researchos/execution/coding_runtime.py`
- Modify: `backend/researchos/execution/tool_dispatcher.py`
- Test: `tests/test_coding_runtime_security.py`
- Test: `tests/test_coding_runtime_artifacts.py`
- Test: `tests/test_nature_figure_generates_files.py`
- Test: `tests/test_ppt_generation_artifact.py`
- Test: `tests/test_data_profile_workflow.py`

- [ ] Add failing tests for run workspace isolation, output registration, CSV profiling, plotting, PPTX generation, missing fields, missing dependencies, and unsafe paths.
- [ ] Implement the project-scoped run workspace and output protocol.
- [ ] Implement `data_profile`, `basic_stats_plot`, `qpcr_template`, `ppt_from_outline`, and `markdown_report`.
- [ ] Reuse runtime validation from `script_runner`.
- [ ] Run coding runtime tests until green.

### Task 3: Workflow Execution Service

**Files:**
- Create: `backend/researchos/integration/workflow_execution_service.py`
- Modify: `skills/researchos_skill_library/pipeline_registry.json`
- Modify: `backend/researchos/skills/pipeline_registry.py`
- Modify: `backend/research_agent_runtime/scripts/research_agent_api.py`
- Test: `tests/test_workflow_execution_service.py`
- Test: `tests/test_nature_workflow_registry.py`
- Test: `tests/test_workspace_execute_real_skill.py`
- Test: `tests/test_chat_workflow_routing.py`
- Test: `tests/test_no_fake_success.py`

- [ ] Add failing tests for machine-readable definitions and honest workflow statuses.
- [ ] Implement service run creation, handler dispatch, artifacts, memory candidates, and developer diagnostics.
- [ ] Connect nature-like workflows and Markdown fallbacks.
- [ ] Expose plan, execute, and chat-route endpoints.
- [ ] Run workflow tests until green.

### Task 4: Product UI

**Files:**
- Create: `web_client/components/artifact_card.js`
- Create: `web_client/components/workflow_card.js`
- Create: `web_client/components/developer_details.js`
- Create: `web_client/components/project_status_card.js`
- Modify: `web_client/api.js`
- Modify: `web_client/user_workflows.js`
- Modify: `web_client/views/workspace.js`
- Modify: `web_client/views/simplified_library.js`
- Modify: `web_client/components/workflow_result.js`
- Modify: `scripts/check_web_client.py`
- Test: `tests/test_library_artifact_ui.py`
- Test: `tests/test_researchos_web_client.py`
- Test: `tests/test_frontend_developer_mode_visibility.py`
- Test: `tests/test_enter_to_send_chat.py`
- Test: `tests/test_artifact_cards_render.py`

- [ ] Add failing static and Node tests for normal-mode visibility and artifact cards.
- [ ] Route confirmed workspace tasks to the real workflow execution endpoint.
- [ ] Render readable registry-backed library categories and preview hints.
- [ ] Keep raw pipeline and artifact JSON developer-only.
- [ ] Run frontend checks and tests until green.

### Task 5: Verification

- [ ] Run targeted backend tests.
- [ ] Run `npm run client:check`.
- [ ] Run `py -m unittest discover -s tests -p "test_*.py"`.
- [ ] Perform a local client smoke test for project, workflow, artifact, and developer-mode visibility.
- [ ] Remove local test caches and audit every prompt requirement.
