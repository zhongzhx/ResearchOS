# ResearchOS Linear Client Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Tkinter desktop client as a lower-density Linear-inspired research operations workbench while preserving existing backend functions.

**Architecture:** Keep `researchos_local_client.pyw` as the main client module so existing tests continue to import it directly. Add a small theme/layout helper layer inside the file, then replace the shell, overview, task, library, Agent, memory, and developer navigation surfaces with larger low-density panels mapped to existing backend methods.

**Tech Stack:** Python 3, Tkinter/ttk, existing local ResearchOS HTTP API, `unittest`.

---

## File Structure

- Modify `researchos_local_client.pyw`
  - Replace old green/animated dock visual system with Linear-inspired `WorkbenchTheme` constants.
  - Add low-density shell helpers for section panels, rows, action bars, status pills, and empty states.
  - Rebuild sidebar, top command bar, overview, task stream, library, Agent, memory, and developer surfaces.
  - Reuse existing backend action methods wherever possible.
- Modify `tests/test_local_client_boot.py`
  - Add structural tests for the new theme, view grouping, and client construction.
- Modify `tests/test_researchos_local_client_project_actions.py`
  - Keep existing project action tests green; add a small non-GUI helper test only if needed.
- Use existing design spec at `docs/superpowers/specs/2026-05-13-researchos-linear-client-redesign-design.md`.

## Task 1: Add Client Structure Tests

**Files:**
- Modify: `tests/test_local_client_boot.py`
- Modify later: `researchos_local_client.pyw`

- [ ] **Step 1: Add failing tests for the workbench design contract**

Append these tests to `LocalClientBootTests` in `tests/test_local_client_boot.py`:

```python
    def test_workbench_theme_exposes_linear_surface_tokens(self) -> None:
        client_module = load_client_module()

        self.assertEqual(client_module.WorkbenchTheme.CANVAS, "#010102")
        self.assertEqual(client_module.WorkbenchTheme.ACCENT, "#5e6ad2")
        self.assertEqual(client_module.WorkbenchTheme.PANEL_RADIUS_NOTE, "8-12px")

    def test_primary_workspace_keys_are_low_density_user_workflows(self) -> None:
        client_module = load_client_module()

        self.assertEqual(
            [key for key, _label in client_module.PRIMARY_WORKSPACES],
            ["overview", "tasks_user", "library_user", "agent", "memory"],
        )

    def test_developer_workspace_keys_are_separate_from_primary_workflows(self) -> None:
        client_module = load_client_module()

        primary_keys = {key for key, _label in client_module.PRIMARY_WORKSPACES}
        developer_keys = {key for key, _label in client_module.DEVELOPER_WORKSPACES}

        self.assertFalse(primary_keys & developer_keys)
        self.assertIn("skills", developer_keys)
        self.assertIn("api", developer_keys)
```

- [ ] **Step 2: Run the tests and verify they fail for missing symbols**

Run:

```powershell
py -m unittest tests.test_local_client_boot -v
```

Expected: FAIL with `AttributeError` for `WorkbenchTheme` or `PRIMARY_WORKSPACES`.

- [ ] **Step 3: Add minimal exported symbols**

In `researchos_local_client.pyw`, add this after `TASK_FILTERS`:

```python
class WorkbenchTheme:
    CANVAS = "#010102"
    SURFACE_1 = "#0f1011"
    SURFACE_2 = "#141516"
    SURFACE_3 = "#18191a"
    HAIRLINE = "#23252a"
    HAIRLINE_STRONG = "#34343a"
    INK = "#f7f8f8"
    MUTED = "#d0d6e0"
    SUBTLE = "#8a8f98"
    ACCENT = "#5e6ad2"
    ACCENT_HOVER = "#828fff"
    SUCCESS = "#27a644"
    WARNING = "#ffc533"
    DANGER = "#ff6161"
    PANEL_RADIUS_NOTE = "8-12px"


PRIMARY_WORKSPACES = [
    ("overview", "总览"),
    ("tasks_user", "任务流"),
    ("library_user", "资料库"),
    ("agent", "AURA"),
    ("memory", "项目记忆"),
]


DEVELOPER_WORKSPACES = [
    ("skills", "技能注册表"),
    ("projects", "项目/文件调试"),
    ("data", "数据调试"),
    ("experiments", "实验调试"),
    ("samples", "样品调试"),
    ("feed", "任务原始状态"),
    ("functions", "开发者控制台"),
    ("api", "API 调试"),
]
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
py -m unittest tests.test_local_client_boot -v
```

Expected: all tests in `test_local_client_boot.py` pass.

- [ ] **Step 5: Commit**

```powershell
git add researchos_local_client.pyw tests/test_local_client_boot.py
git commit -m "test: define workbench client structure"
```

## Task 2: Replace Theme Constants and ttk Styling

**Files:**
- Modify: `researchos_local_client.pyw`

- [ ] **Step 1: Add a focused style test if Task 1 passes too broadly**

If Task 1 already covers theme symbols, no new test is needed here. The existing boot test instantiates the app and will catch ttk layout/style errors.

- [ ] **Step 2: Replace top-level color aliases with Linear-inspired values**

Change the existing constants near the top of `researchos_local_client.pyw`:

```python
BG_DEEP = WorkbenchTheme.CANVAS
BG_BASE = WorkbenchTheme.CANVAS
BG_SURFACE = WorkbenchTheme.SURFACE_1
BG_ELEVATED = WorkbenchTheme.SURFACE_2
BG_HOVER = WorkbenchTheme.SURFACE_3
BG_INPUT = "#090a0b"
BORDER = WorkbenchTheme.HAIRLINE
BORDER_SUBTLE = WorkbenchTheme.HAIRLINE
TEXT_1 = WorkbenchTheme.INK
TEXT_2 = WorkbenchTheme.MUTED
TEXT_3 = WorkbenchTheme.SUBTLE
ACCENT = WorkbenchTheme.ACCENT
ACCENT_DIM = "#171b35"
BLUE = WorkbenchTheme.ACCENT_HOVER
WARN = WorkbenchTheme.WARNING
BAD = WorkbenchTheme.DANGER
CARD_RADIUS_NOTE = WorkbenchTheme.PANEL_RADIUS_NOTE
```

- [ ] **Step 3: Update `_build_style` for lower-density controls**

In `ResearchOSClientApp._build_style`, keep the `clam` theme but change these style values:

```python
style.configure(".", font=(FONT_UI, 10), background=BG_BASE, foreground=TEXT_1)
style.configure("Title.TLabel", background=BG_BASE, foreground=TEXT_1, font=(FONT_UI, 18, "bold"))
style.configure("PanelTitle.TLabel", background=BG_SURFACE, foreground=TEXT_1, font=(FONT_UI, 11, "bold"))
style.configure("TEntry", fieldbackground=BG_INPUT, foreground=TEXT_1, insertcolor=TEXT_1, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=(12, 9))
style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=TEXT_1, arrowcolor=TEXT_2, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=(10, 8))
style.configure("Treeview", rowheight=38, background=BG_INPUT, fieldbackground=BG_INPUT, foreground=TEXT_1, bordercolor=BORDER_SUBTLE, lightcolor=BORDER_SUBTLE, darkcolor=BORDER_SUBTLE)
style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT, focusthickness=0, padding=(16, 10), font=(FONT_UI, 10, "bold"))
style.map("Accent.TButton", background=[("active", WorkbenchTheme.ACCENT_HOVER), ("pressed", ACCENT)], foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
style.configure("Secondary.TButton", background=BG_SURFACE, foreground=TEXT_1, bordercolor=BORDER, focusthickness=0, padding=(14, 9))
```

- [ ] **Step 4: Run boot tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add researchos_local_client.pyw
git commit -m "style: apply linear workbench theme"
```

## Task 3: Build Low-Density Workbench Shell Helpers

**Files:**
- Modify: `researchos_local_client.pyw`

- [ ] **Step 1: Add helper methods after `_view`**

Add these methods to `ResearchOSClientApp` after `_view`:

```python
    def _workbench_section(self, parent, title: str, subtitle: str = "") -> tk.Frame:
        outer = tk.Frame(parent, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=16)
        if title:
            tk.Label(outer, text=title, bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=(FONT_UI, 12, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(outer, text=subtitle, bg=BG_SURFACE, fg=TEXT_3, anchor="w", justify="left", wraplength=760, font=(FONT_UI, 9)).pack(anchor="w", pady=(4, 14))
        else:
            tk.Frame(outer, bg=BG_SURFACE, height=10).pack()
        return outer

    def _status_pill(self, parent, text: str, tone: str = "neutral") -> tk.Label:
        colors = {
            "neutral": (BG_ELEVATED, TEXT_2),
            "active": ("#171b35", WorkbenchTheme.ACCENT_HOVER),
            "success": ("#102016", WorkbenchTheme.SUCCESS),
            "warning": ("#241f0d", WorkbenchTheme.WARNING),
            "danger": ("#241214", WorkbenchTheme.DANGER),
        }
        bg, fg = colors.get(tone, colors["neutral"])
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=10, pady=4, font=(FONT_UI, 9, "bold"))

    def _resource_row(self, parent, title: str, subtitle: str, meta: str = "", tone: str = "neutral", command=None) -> tk.Frame:
        row = tk.Frame(parent, bg=BG_SURFACE, cursor="hand2" if command else "")
        row.pack(fill="x", pady=(0, 1))
        body = tk.Frame(row, bg=BG_SURFACE)
        body.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)
        tk.Label(body, text=title, bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=(FONT_UI, 10, "bold")).pack(fill="x")
        tk.Label(body, text=subtitle, bg=BG_SURFACE, fg=TEXT_3, anchor="w", justify="left", wraplength=520, font=(FONT_UI, 9)).pack(fill="x", pady=(3, 0))
        if meta:
            self._status_pill(row, meta, tone).pack(side="right", pady=10)
        if command:
            row.bind("<Button-1>", lambda _event: command())
            body.bind("<Button-1>", lambda _event: command())
        return row

    def _action_bar(self, parent, actions: list[tuple[str, object, str]]) -> tk.Frame:
        bar = tk.Frame(parent, bg=BG_SURFACE)
        for label, command, kind in actions:
            style = "Accent.TButton" if kind == "primary" else "Secondary.TButton"
            ttk.Button(bar, text=label, style=style, command=command).pack(side="left", padx=(0, 8))
        return bar

    def _set_text(self, widget: ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state="disabled")
```

- [ ] **Step 2: Alias `_panel` to the new section helper**

Replace the body of `_panel` with:

```python
        return self._workbench_section(parent, title, subtitle)
```

This preserves existing callers while letting new screens use the lower-density section style.

- [ ] **Step 3: Run boot tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add researchos_local_client.pyw
git commit -m "refactor: add workbench layout helpers"
```

## Task 4: Rebuild Navigation and Shell

**Files:**
- Modify: `researchos_local_client.pyw`

- [ ] **Step 1: Replace `USER_NAV` and developer nav references**

Change `USER_NAV` to use the new primary workspaces:

```python
USER_NAV = PRIMARY_WORKSPACES
DEV_NAV = DEVELOPER_WORKSPACES
```

Place this after `PRIMARY_WORKSPACES` and `DEVELOPER_WORKSPACES` are defined.

- [ ] **Step 2: Replace `render_sidebar_nav` item lists**

In `render_sidebar_nav`, use:

```python
        user_items = [
            ("overview", "总览", "⌁"),
            ("tasks_user", "任务流", "●"),
            ("library_user", "资料库", "◫"),
            ("agent", "AURA", "AI"),
            ("memory", "项目记忆", "◎"),
        ]
```

Keep developer items conditional on `self.developer_mode.get()`, using `DEVELOPER_WORKSPACES`.

- [ ] **Step 3: Make the sidebar stable instead of hover-primary**

In `_build_ui`, set sidebar width to `230` and remove reliance on hover expansion as the primary behavior:

```python
self.sidebar = tk.Frame(self.root, bg=BG_DEEP, width=230, highlightthickness=1, highlightbackground=BORDER)
```

In `__init__`, set:

```python
self.dock_expanded = True
self.sidebar_target_width = 230
```

Keep old hover methods present for compatibility, but they should not hide labels in normal desktop mode.

- [ ] **Step 4: Simplify `_build_workspace_shell`**

Replace the title-heavy header with a top command row:

```python
        header = ttk.Frame(self.workspace, style="Workspace.TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(18, 0))
        header.grid_columnconfigure(0, weight=1)

        self.global_command = tk.Entry(header, bg=BG_INPUT, fg=TEXT_1, insertbackground=TEXT_1, relief="flat", bd=0, font=(FONT_UI, 11))
        self.global_command.insert(0, "搜索项目、文献、任务，或输入科研命令")
        self.global_command.grid(row=0, column=0, sticky="ew", ipady=12, padx=(0, 12))
        self.global_command.bind("<Return>", self.run_global_command)

        ttk.Button(header, text="新建任务", style="Accent.TButton", command=self.start_command_task).grid(row=0, column=1, sticky="e")
        self.dual_status_pill = tk.Label(header, text="本地服务检测中", bg=BG_SURFACE, fg=TEXT_2, padx=13, pady=10, font=(FONT_UI, 9, "bold"))
        self.dual_status_pill.grid(row=0, column=2, sticky="e", padx=(10, 0))
```

- [ ] **Step 5: Add `run_global_command`**

Add this method near `start_command_task`:

```python
    def run_global_command(self, _event=None) -> str | None:
        value = clean(getattr(self, "global_command", None).get() if hasattr(self, "global_command") else "")
        if not value or value == "搜索项目、文献、任务，或输入科研命令":
            self.show_aura_toast("先输入一个科研命令")
            return "break"
        self.open_chat_with_message(value)
        if hasattr(self, "global_command"):
            self.global_command.delete(0, tk.END)
        return "break"
```

- [ ] **Step 6: Run boot tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add researchos_local_client.pyw
git commit -m "refactor: rebuild workbench shell"
```

## Task 5: Rebuild Low-Density Overview

**Files:**
- Modify: `researchos_local_client.pyw`

- [ ] **Step 1: Replace `_build_overview` with an operations overview**

Replace the current hero/composer implementation with a layout containing:

- one project summary section
- one task stream section
- one resource map section
- one next-action section

The implementation skeleton:

```python
    def _build_overview(self) -> None:
        view = self._view("overview", "总览", "项目状态、任务流和资料库概览。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        summary = self._workbench_section(view, "当前项目", "ResearchOS 会围绕当前项目读取资料库、任务和记忆。")
        summary.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 14))
        self.home_project_summary = tk.Label(summary, text="等待连接本地工作区", bg=BG_SURFACE, fg=TEXT_1, anchor="w", justify="left", font=(FONT_UI, 11))
        self.home_project_summary.pack(fill="x")
        self.home_status_line = tk.Label(summary, text="本地服务检测中", bg=BG_SURFACE, fg=TEXT_3, anchor="w", font=(FONT_UI, 9))
        self.home_status_line.pack(fill="x", pady=(6, 0))

        body = ttk.Frame(view, style="Workspace.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=26, pady=(0, 22))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        tasks = self._workbench_section(body, "任务流", "运行中、待确认、失败和最近完成的任务。")
        tasks.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.overview_task_rows = tk.Frame(tasks, bg=BG_SURFACE)
        self.overview_task_rows.pack(fill="both", expand=True)
        self._action_bar(tasks, [
            ("刷新任务", self.load_user_tasks_summary, "primary"),
            ("自动推进", self.run_agent_heartbeat, "secondary"),
            ("扫描项目", self.run_research_watcher, "secondary"),
        ]).pack(fill="x", pady=(12, 0))

        side = ttk.Frame(body, style="Workspace.TFrame")
        side.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        side.grid_columnconfigure(0, weight=1)

        resources = self._workbench_section(side, "资料库", "文献、PDF、知识库、数据和实验对象。")
        resources.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.overview_resource_rows = tk.Frame(resources, bg=BG_SURFACE)
        self.overview_resource_rows.pack(fill="x")

        next_actions = self._workbench_section(side, "下一步", "少量关键动作，而不是铺满快捷卡片。")
        next_actions.grid(row=1, column=0, sticky="ew")
        self._action_bar(next_actions, [
            ("问 AURA", lambda: self.show_view("agent"), "primary"),
            ("采集文献", lambda: self.show_view("library_user"), "secondary"),
            ("打开任务流", lambda: self.show_view("tasks_user"), "secondary"),
        ]).pack(fill="x")

        self.aura_toast = tk.Label(view, text="", bg=BG_SURFACE, fg=WorkbenchTheme.ACCENT_HOVER, padx=16, pady=12, font=(FONT_UI, 9, "bold"), highlightbackground=BORDER, highlightthickness=1)
```

- [ ] **Step 2: Add overview rendering helpers**

Add:

```python
    def render_overview_task_rows(self) -> None:
        if not hasattr(self, "overview_task_rows"):
            return
        for child in self.overview_task_rows.winfo_children():
            child.destroy()
        tasks = self.user_task_cache[:5]
        if not tasks:
            self._resource_row(self.overview_task_rows, "暂无任务", "创建任务或刷新后，这里会显示任务流。", "empty")
            return
        for task in tasks:
            title = clean(task.get("title") or TASK_TYPE_LABELS.get(clean(task.get("type")), clean(task.get("type")) or "科研任务"))
            status = clean(task.get("status") or "pending")
            tone = "active" if status == "running" else "success" if status == "completed" else "warning" if "waiting" in status else "danger" if status == "failed" else "neutral"
            self._resource_row(self.overview_task_rows, title, clean(task.get("summary") or task.get("message") or task.get("task_id")), TASK_STATUS_LABELS.get(status, status), tone, command=lambda: self.show_view("tasks_user"))

    def render_overview_resource_rows(self) -> None:
        if not hasattr(self, "overview_resource_rows"):
            return
        for child in self.overview_resource_rows.winfo_children():
            child.destroy()
        self._resource_row(self.overview_resource_rows, "文献与 PDF", "采集、导入、重解析和构建知识库。", "资料库", command=lambda: self.show_view("library_user"))
        self._resource_row(self.overview_resource_rows, "数据与实验", "上传数据，管理实验、样品、结论和失败记录。", "数据", command=lambda: self.show_view("data"))
        self._resource_row(self.overview_resource_rows, "项目记忆", "查看摘要、证据和下一步建议。", "记忆", command=lambda: self.show_view("memory"))
```

- [ ] **Step 3: Call overview renderers after task/project updates**

At the end of `render_user_task_list`, add:

```python
        self.render_overview_task_rows()
```

At the end of `render_workspace_summary`, add:

```python
        self.render_overview_resource_rows()
```

- [ ] **Step 4: Run local client tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot tests.test_researchos_local_client_project_actions -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add researchos_local_client.pyw
git commit -m "refactor: rebuild low density overview"
```

## Task 6: Reorganize Tasks, Library, Agent, and Memory Surfaces

**Files:**
- Modify: `researchos_local_client.pyw`

- [ ] **Step 1: Keep existing backend action methods unchanged**

Do not rename these methods:

```python
load_user_tasks_summary
render_user_task_list
show_selected_user_task_detail
continue_selected_user_task
retry_selected_user_task
cancel_selected_user_task
run_library_literature_harvest
quick_pdf_import
build_kb
query_rag
send_agent_message
render_chat_response
build_memory_context
load_agent_memory
```

- [ ] **Step 2: Lower density in `_build_tasks_user`**

Keep one task list and one detail panel. Remove extra button crowding by grouping actions into two rows:

```python
primary_actions = [
    ("刷新任务", self.load_user_tasks_summary, "primary"),
    ("自动推进", self.run_agent_heartbeat, "secondary"),
    ("扫描项目", self.run_research_watcher, "secondary"),
]
selected_actions = [
    ("查看结果", self.show_selected_user_task_detail, "primary"),
    ("继续", self.continue_selected_user_task, "secondary"),
    ("重试", self.retry_selected_user_task, "secondary"),
    ("取消", self.cancel_selected_user_task, "secondary"),
    ("隐藏", self.hide_selected_user_task, "secondary"),
]
```

Use `_action_bar` for both groups instead of packing all buttons into one line.

- [ ] **Step 3: Lower density in `_build_library_user`**

Keep the notebook if rewriting all tabs is too risky, but reduce each tab to:

- one action section
- one list/detail region

For literature, PDF, and data, avoid placing more than four buttons in one row. Move secondary destructive actions to the end of the detail panel.

- [ ] **Step 4: Make `_build_agent` visually consistent**

Keep existing chat backend methods. Wrap chat input, response, citations, and actions in workbench sections. Use a single primary send button and secondary clear/context toggles.

- [ ] **Step 5: Make `_build_memory` the project-memory workspace**

Expose:

- build memory context
- load agent memory
- memory result text
- review queue/evidence actions if already present

Do not add new backend behavior in this task.

- [ ] **Step 6: Run tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot tests.test_researchos_local_client_project_actions -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add researchos_local_client.pyw
git commit -m "refactor: reorganize client workspaces"
```

## Task 7: Developer Mode and Compatibility Pass

**Files:**
- Modify: `researchos_local_client.pyw`
- Modify if needed: `tests/test_researchos_local_client_project_actions.py`

- [ ] **Step 1: Verify developer views still build**

Confirm `_build_views` still calls all developer builders:

```python
self._build_functions()
self._build_projects()
self._build_data()
self._build_experiments()
self._build_samples()
self._build_research_feed()
self._build_skills()
self._build_api_console()
```

- [ ] **Step 2: Ensure `toggle_developer_mode` uses developer workspace keys**

Update the hiding condition:

```python
        if not self.developer_mode.get() and self.active_view not in {key for key, _title in PRIMARY_WORKSPACES}:
            self.show_view("overview")
```

- [ ] **Step 3: Keep dangerous confirmation tests green**

Do not alter the confirmation phrase behavior in:

```python
clear_workspace_memory
clear_workspace_project
delete_workspace_project
```

If UI text changes break tests, update tests only for display copy. Do not change backend payload expectations.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot tests.test_researchos_local_client_project_actions -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add researchos_local_client.pyw tests/test_researchos_local_client_project_actions.py
git commit -m "refactor: preserve developer mode compatibility"
```

## Task 8: Final Verification

**Files:**
- No planned edits unless verification reveals failures.

- [ ] **Step 1: Run focused client tests**

Run:

```powershell
py -m unittest tests.test_local_client_boot tests.test_researchos_local_client_project_actions -v
```

Expected: all tests pass.

- [ ] **Step 2: Run broad tests if focused tests pass and time allows**

Run:

```powershell
py -m unittest discover -s tests
```

Expected: pass, or report exact failures if existing unrelated tests fail.

- [ ] **Step 3: Check git status and diff summary**

Run:

```powershell
git status --short --branch
git diff --stat HEAD
```

Expected: clean status after final commit, or only intentional uncommitted changes before commit.

- [ ] **Step 4: Manual smoke launch**

Run:

```powershell
py -m unittest tests.test_local_client_boot.LocalClientBootTests.test_client_boots_without_tcl_layout_conflict -v
```

Expected: pass, confirming `ResearchOSClientApp()` can construct and destroy the Tk root without Tcl layout conflict.

- [ ] **Step 5: Commit verification fixes if any**

If edits were required:

```powershell
git add researchos_local_client.pyw tests/test_local_client_boot.py tests/test_researchos_local_client_project_actions.py
git commit -m "fix: stabilize redesigned client tests"
```

If no edits were required, do not create an empty commit.

## Self-Review

Spec coverage:

- Visual direction: covered by Tasks 2-5.
- Lower density/fewer boxes: covered by Tasks 3, 5, and 6.
- Interaction restructuring: covered by Tasks 4-6.
- Backend mapping: covered by Tasks 5-7 through existing action methods.
- Minimal extra UI: covered by Tasks 5-6, with no backend rewrites.
- Testing: covered by Tasks 1, 2, 5, 6, 7, and 8.

Placeholder scan:

- No unresolved placeholders are intentionally left in this plan.

Type consistency:

- `WorkbenchTheme`, `PRIMARY_WORKSPACES`, `DEVELOPER_WORKSPACES`, `_workbench_section`, `_status_pill`, `_resource_row`, `_action_bar`, `_set_text`, `run_global_command`, `render_overview_task_rows`, and `render_overview_resource_rows` are consistently named.
