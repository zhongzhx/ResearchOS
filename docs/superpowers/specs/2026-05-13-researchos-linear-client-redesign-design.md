# ResearchOS Linear Client Redesign Design

## Context

ResearchOS currently ships a Windows Tkinter desktop client in `researchos_local_client.pyw`. The existing client already connects to the local backend and exposes project management, tasks, literature harvest, PDF/RAG, data, experiments, samples, memory, Agent chat, feed, skills, and API debugging. The problem is not backend capability coverage; it is that the front end reads as a dense collection of pages and buttons rather than a coherent research workbench.

The redesign will follow `awesome-design-md` with the selected reference direction: Linear's product-focused dark operations console. The user approved this direction with one important adjustment: reduce visual density and use fewer card/grid blocks than the preview. The final UI should feel like a focused research operating system, not a dashboard made of many boxes.

## Goals

- Rebuild the client around a Linear-inspired dark workbench visual system.
- Reduce page count and interaction noise by making workflow areas clearer.
- Preserve existing backend capabilities and reconnect them into the new layout.
- Keep changes pragmatic for Tkinter: large structural refactor, but no technology rewrite.
- Add only minimal extra UI for functions missed by the first visual design.
- Run a focused smoke test and existing local-client tests.

## Non-Goals

- Do not rewrite the client as a web app.
- Do not redesign backend APIs unless the UI cannot map an existing capability.
- Do not remove developer/debug functions; place them behind developer mode.
- Do not add decorative gradients, dense KPI grids, or marketing-style hero sections.
- Do not make every backend object a separate visible card.

## Visual Direction

The visual system is based on Linear:

- Canvas: near-black, using a small surface ladder for hierarchy.
- Panels: low-count, large panels with 1px hairline borders.
- Accent: Linear lavender used sparingly for primary actions, focus, active navigation, and running-state emphasis.
- Typography: restrained system font stack, medium-weight titles, readable body text.
- Density: lower than the preview. The default screen should have 2-3 major regions, not many small cards.
- Spacing: more breathing room around section groups; avoid nested cards.
- Shape: 8-12px radius for controls and panels.

The revised density rule is:

- Use one broad summary band instead of four or more metric cards.
- Use one main task stream and one contextual side panel rather than multiple equal grids.
- Use lists and sections for resources instead of card grids.
- Use whitespace, headings, and subtle dividers as the primary organization tools.

## Information Architecture

The client will be reorganized into five primary user workspaces:

1. **总览**
   - Current project summary.
   - Backend connection status.
   - Active task stream.
   - Top-level command entry for search, task creation, and quick routing.

2. **任务流**
   - Running, waiting, completed, failed tasks.
   - Continue, retry, cancel, hide, inspect result.
   - Agent heartbeat and project watcher actions.

3. **资料库**
   - Literature harvest.
   - PDF references and knowledge base build/query.
   - Data files.
   - Protocol extraction and experiment record extraction.

4. **AURA**
   - Agent chat.
   - Citations and context visibility controls.
   - Suggested follow-up actions.

5. **项目记忆**
   - Project memory summary.
   - Evidence and claim review surfaces when available.
   - User correction, hide, and rebuild actions.

Developer mode adds:

- 技能注册表
- 项目/文件调试
- 数据/实验/样品调试
- Feed 原始状态
- API 调试日志

## Layout

The shell will use:

- Left navigation: stable, not animated by default. It should show labels clearly and avoid hover-expand behavior as the primary navigation model.
- Top command bar: global command/search field plus one primary action.
- Main content: a single large work area for the active workspace.
- Right context rail: optional context rail for current project, selected task, selected reference, or Agent response. It can collapse on narrow windows.

The total visible layout should avoid more than three major columns. On narrow windows:

- Hide the right context rail first.
- Keep navigation compact but understandable.
- Stack content vertically when needed.

## Component Model

Add a small set of local UI helpers inside `researchos_local_client.pyw` before splitting files, because the current client is a single-file app and tests load it directly.

Core helpers:

- `WorkbenchTheme`: color, spacing, and font constants.
- `WorkbenchShell`: methods for building nav, command bar, main area, and context rail.
- `section(...)`: large low-density bordered panel.
- `status_row(...)`: compact text row with a small status pill.
- `resource_row(...)`: list row for references, files, data, and experiments.
- `action_bar(...)`: grouped primary/secondary actions.
- `empty_state(...)`: readable empty/error state.

These helpers should reduce repeated manual `tk.Frame` and `ttk` styling without trying to create a full component framework.

## Backend Mapping

Existing backend methods and API calls remain the source of truth:

- Projects: `/research-os/projects`, project status, archive, clear, purge.
- Workspace summary: `/research-os/workspace-state`, project status endpoints.
- Tasks: `/research-os/tasks`, task run/cancel, Agent heartbeat, watcher.
- Literature: `/research-os/literature/search-tasks`, progress, cancel, searches.
- References/RAG: `/research-os/references`, `/research-os/knowledge-base/build`, `/research-os/rag/query`.
- Data and experiment objects: `/research-os/data-files`, `/research-os/experiments`, `/research-os/samples`.
- Memory: `/research-os/memory/context`, `/research-os/agent-memory`, review/correction endpoints.
- Agent: `/research-os/agent/chat`, Agent feed, scheduler.
- Skills/dev: `/api/skills/*`, `/research-os/skills`, `/research-os/skill-runs`, API console.

The implementation should map old functions into new surfaces rather than replacing backend behavior.

## Interaction Changes

- Replace the current hero-like home page with a low-density operations overview.
- The command bar should accept natural language task input and route to existing `open_chat_with_message`, task creation, literature harvest, or skill route behavior where practical.
- Task actions should be grouped next to the task stream, not scattered across multiple pages.
- Resource lists should use selection-driven details in the context rail or lower detail panel.
- Developer mode should remain off by default and should visibly separate debug tools from user workflows.
- Dangerous actions such as project purge and memory clear keep current confirmation flow.

## Error Handling

- Backend offline: show a single clear offline state in the top status and overview body.
- Empty project: show a create/select project prompt.
- Empty lists: show concise empty states with one action.
- Failed backend call: keep current error plumbing but display it in the active workspace, not only status text.
- Long task: show running status and keep refresh/polling behavior.

## Testing

Minimum verification:

- Run the existing local client boot tests.
- Run local client project action tests.
- Import the client module to ensure no syntax/runtime import failures.
- If possible, instantiate `ResearchOSClientApp` in tests.
- Do one manual smoke launch or equivalent script check if the desktop environment supports it.

Target commands:

```powershell
py -m unittest tests.test_local_client_boot tests.test_researchos_local_client_project_actions
```

If broader changes touch task or backend mapping code, also run:

```powershell
py -m unittest discover -s tests
```

## Scope Control

This is a large UI refactor but should remain one client-focused change:

- Modify `researchos_local_client.pyw`.
- Add focused tests only where feasible.
- Avoid changing backend modules unless the client reveals a missing endpoint or broken contract.
- Do not commit `.superpowers/` visual companion files.

## Open Decisions Resolved

- Primary visual reference: Linear.
- Density: lower than the preview; fewer panels and no broad grid of boxes.
- Technology: keep Tkinter desktop client.
- Backend: reconnect existing capabilities to the redesigned surfaces.
