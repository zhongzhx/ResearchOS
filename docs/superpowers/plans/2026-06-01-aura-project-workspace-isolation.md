# AURA Research Project Workspace Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build canonical project workspaces, truthful status APIs, destructive clear/purge semantics, and one consistent active-project client context.

**Architecture:** Put filesystem ownership in `backend/researchos/workspace/project_workspace.py`, keep SQLite ownership in the MVP runtime, and expose composed status through the existing HTTP handler. Remove ordinary-client default-project fallbacks and invalidate stale browser caches once.

**Tech Stack:** Python standard library, SQLite, vanilla JavaScript, unittest, Electron local HTTP proxy.

---

### Task 1: Canonical Project Workspace

**Files:**
- Modify: `backend/researchos/workspace/project_workspace.py`
- Modify: `backend/researchos/workspace/__init__.py`
- Modify: `backend/research_agent_runtime/scripts/research_os_mvp.py`
- Create: `tests/test_project_workspace_isolation.py`

- [ ] Write failing tests for exact canonical paths, all required directories, manifest fields, and A/B file and artifact isolation.
- [ ] Run `py -m unittest tests.test_project_workspace_isolation -v` and confirm the old layout fails.
- [ ] Implement `ProjectWorkspace`, compatibility aliases, manifest refresh, and project-scoped archive paths.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Clear And Purge

**Files:**
- Modify: `backend/research_agent_runtime/scripts/research_os_mvp.py`
- Modify: `backend/research_agent_runtime/scripts/research_agent_api.py`
- Create: `tests/test_project_clear_purge.py`

- [ ] Write failing tests proving clear rebuilds an empty project shell and purge removes the project directory only when `confirm=true`.
- [ ] Run `py -m unittest tests.test_project_clear_purge -v` and confirm failures.
- [ ] Expand project-scoped deletion tables, recreate the workspace after clear, and require boolean purge confirmation.
- [ ] Re-run focused clear/purge tests and related legacy project-management tests.

### Task 3: Status And Paths API

**Files:**
- Modify: `backend/research_agent_runtime/scripts/research_os_mvp.py`
- Modify: `backend/research_agent_runtime/scripts/research_agent_api.py`
- Create: `tests/test_project_status_api.py`

- [ ] Write failing HTTP tests for status, paths, real counts, recent workflow run, A/B isolation, and missing-project errors.
- [ ] Run `py -m unittest tests.test_project_status_api -v` and confirm failures.
- [ ] Implement composed project status, path response, and explicit-scope read behavior.
- [ ] Re-run focused API tests.

### Task 4: Client Project Context

**Files:**
- Modify: `web_client/api.js`
- Modify: `web_client/state.js`
- Modify: `web_client/artifact_types.js`
- Modify: `web_client/user_workflows.js`
- Modify: `web_client/views/chat.js`
- Modify: `web_client/views/workspace.js`
- Modify: `web_client/views/projects.js`
- Modify: `web_client/views/simplified_library.js`
- Modify: `web_client/views/settings.js`
- Modify: `web_client/components/project_switcher.js`
- Modify: `web_client/styles.css`
- Create: `tests/test_web_client_project_status.py`

- [ ] Write failing source-contract tests for status cards, developer-only diagnostics, cache reset, and absence of silent `default` fallback.
- [ ] Run `py -m unittest tests.test_web_client_project_status -v` and confirm failures.
- [ ] Add API helpers, cache invalidation, strict project guards, project-switch events, and normal/developer status rendering.
- [ ] Re-run focused client tests and `npm run client:check`.

### Task 5: Regression Verification

**Files:**
- Modify only files required by failures.

- [ ] Run new tests and related legacy project, isolation, chat, and client tests.
- [ ] Run `npm run client:check`.
- [ ] Run `py -m unittest discover -s tests -p "test_*.py"`.
- [ ] Inspect `git diff --stat` and report changed files, design, verification evidence, and any remaining failures.
