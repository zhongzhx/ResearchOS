# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


WORKSPACE_ROOT = Path(__file__).resolve().parent
LEGACY_API_SCRIPT = WORKSPACE_ROOT / "research-agent-runtime" / "scripts" / "research_agent_api.py"
CANONICAL_API_SCRIPT = WORKSPACE_ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts" / "research_agent_api.py"
API_SCRIPT = LEGACY_API_SCRIPT if LEGACY_API_SCRIPT.exists() else CANONICAL_API_SCRIPT
AGENT_ROOT = Path(os.environ.get("RESEARCHOS_AGENT_ROOT", str(WORKSPACE_ROOT / "agent_data")))
HOST = os.environ.get("RESEARCHOS_HOST", "127.0.0.1")
PORT = int(os.environ.get("RESEARCHOS_PORT", "8765"))
BASE_URL = f"http://{HOST}:{PORT}"
LOG_ROOT = AGENT_ROOT / "logs"
API_LOG_PATH = LOG_ROOT / "researchos_api.log"
CLIENT_CACHE_PATH = AGENT_ROOT / "researchos_client_cache.json"
APP_NAME = "AURA Research"
API_PROCESS_NAME = "AURA Research.exe"
API_PYTHON_HOME = ""
DESTRUCTIVE_CONFIRMATION_WORD = "确定"

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
    ("literature", "文献采集调试"),
    ("knowledge", "知识库调试"),
    ("api", "API 调试"),
]


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
FONT_UI = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

USER_NAV = PRIMARY_WORKSPACES
DEV_NAV = DEVELOPER_WORKSPACES

CAPABILITY_PROMPTS = {
    "文献采集": "请围绕当前项目关键词采集开放文献，并把结果整理进资料库。",
    "实验分析": "请帮我分析实验数据或实验记录，并指出缺失信息。",
    "方案提取": "请从实验方法或文档中提取实验方案草案。",
    "证据核查": "请核查当前项目结论是否有证据支撑，并指出冲突或不足。",
    "生成周报": "请根据当前项目记忆、任务和资料库生成本周项目周报。",
}

SMALLTALK_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "你好",
    "嗨",
    "在吗",
    "早上好",
    "晚上好",
    "你是谁",
    "你能做什么",
    "怎么用",
    "help",
    "帮助",
}

TASK_VERBS = [
    "文献采集",
    "采集文献",
    "查文献",
    "下载文献",
    "实验分析",
    "分析数据",
    "上传数据",
    "报告生成",
    "生成报告",
    "写周报",
    "方案提取",
    "提取方案",
    "设计实验",
    "证据核查",
    "核查证据",
    "整理实验记录",
    "创建项目",
    "导入pdf",
    "导入 pdf",
    "解析文件",
]

TASK_TYPE_LABELS = {
    "kb_summary": "知识库摘要生成",
    "experiment_plan": "实验方案规划",
    "memory_consolidation": "项目记忆整理",
    "Manage Agent Memory": "项目记忆整理",
    "manage_agent_memory": "项目记忆整理",
    "diagnose_research_bottleneck": "研究瓶颈诊断",
    "Diagnose Research Bottleneck": "研究瓶颈诊断",
    "literature_harvest": "文献采集",
    "pdf_ingest": "PDF 入库解析",
    "data_analysis": "数据分析",
    "report_generation": "报告生成",
    "protocol_search": "方案检索",
    "protocol_extraction": "方案提取",
    "skill_learning": "流程学习",
    "weekly_report": "生成周报",
}

TASK_STATUS_LABELS = {
    "pending": "等待处理",
    "running": "运行中",
    "waiting_for_user": "待确认",
    "waiting_approval": "待确认",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
    "created": "已创建",
    "active": "进行中",
    "archived": "已归档",
}

TASK_FILTERS = {
    "全部": "",
    "运行中": "running",
    "待确认": "waiting_for_user",
    "已完成": "completed",
    "失败": "failed",
}

USER_FEATURE_MAP = {
    "问 AURA": "首页",
    "项目管理": "工作区",
    "项目记忆": "工作区",
    "资料库问答": "资料库",
    "文献采集": "资料库",
    "PDF 导入": "资料库",
    "数据上传": "资料库",
    "实验记录": "资料库",
    "任务进度": "任务",
    "技能注册表": "开发者模式",
    "API 调试": "开发者模式",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def python_for_api() -> str:
    global API_PYTHON_HOME
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        candidate = exe.with_name("python.exe")
        if candidate.exists():
            exe = candidate
    API_PYTHON_HOME = str(exe.parent)
    named = exe.with_name(API_PROCESS_NAME)
    try:
        if not named.exists():
            shutil.copy2(exe, named)
        return str(named)
    except Exception:
        try:
            runtime_dir = WORKSPACE_ROOT / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            runtime_named = runtime_dir / API_PROCESS_NAME
            if not runtime_named.exists():
                shutil.copy2(exe, runtime_named)
            return str(runtime_named)
        except Exception:
            return str(exe)


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, object]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return exc.code, {"error": raw}

    def get(self, path: str, timeout: int = 30) -> tuple[int, object]:
        return self.request("GET", path, timeout=timeout)

    def post(self, path: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, object]:
        return self.request("POST", path, payload or {}, timeout=timeout)

    def put(self, path: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, object]:
        return self.request("PUT", path, payload or {}, timeout=timeout)

    def delete(self, path: str, timeout: int = 30) -> tuple[int, object]:
        return self.request("DELETE", path, timeout=timeout)


class ResearchOSClientApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} 本地科研工作台")
        self.root.geometry("1560x960")
        self.root.minsize(390, 640)
        self.root.configure(bg=BG_DEEP)

        self.api = ApiClient(BASE_URL)
        self.backend_process: subprocess.Popen | None = None
        self.project_cache: list[dict] = []
        self.project_label_to_id: dict[str, str] = {}
        self.project_id_to_label: dict[str, str] = {}
        self.skill_cache: list[dict] = []
        self.active_view = ""
        self.views: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.active_lit_task_id = ""
        self.active_lit_polling = False
        self.lit_download_paths: dict[str, str] = {}
        self.client_cache = self.load_client_cache()
        dev_requested = any(arg.lower() in {"--dev", "/dev", "?dev=1", "dev=1"} for arg in sys.argv[1:])
        self.developer_mode = tk.BooleanVar(value=bool(self.client_cache.get("developer_mode")) or dev_requested)

        self.status_text = tk.StringVar(value="正在连接本地服务")
        self.model_text = tk.StringVar(value="后端模型由本地服务管理")
        self.model_status_text = tk.StringVar(value="模型检测中")
        self.workspace_title = tk.StringVar(value=APP_NAME)
        self.workspace_subtitle = tk.StringVar(value="本地科研 AI 工作台")

        self.project_choice = tk.StringVar()
        self.lit_project = tk.StringVar()
        self.lit_keywords = tk.StringVar()
        self.lit_provider = tk.StringVar(value="all")
        self.lit_max_results = tk.StringVar(value="")
        self.lit_use_agent = tk.BooleanVar(value=False)
        self.exp_project = tk.StringVar()
        self.sample_project = tk.StringVar()
        self.memory_project = tk.StringVar()
        self.rag_project = tk.StringVar()
        self.skill_project = tk.StringVar()
        self.file_project = tk.StringVar()
        self.api_method = tk.StringVar(value="GET")
        self.api_path = tk.StringVar(value="/health")
        self.data_project = tk.StringVar()
        self.data_search = tk.StringVar()
        self.conclusion_text = tk.StringVar()
        self.failure_text = tk.StringVar()
        self.decision_text = tk.StringVar()
        self.agent_project = tk.StringVar()
        self.agent_save_to_memory = tk.BooleanVar(value=False)
        self.agent_context_visible = tk.BooleanVar(value=False)
        self.agent_last_intent = ""
        self.agent_conversation_id = clean(self.client_cache.get("agent_conversation_id"))
        self.feed_items: list[dict] = []
        self.active_feed_item_id = ""
        self.agent_tasks: list[dict] = []
        self.active_agent_task_id = ""
        self.command_text = tk.StringVar()
        self.task_project = tk.StringVar()
        self.task_keywords = tk.StringVar()
        self.task_followup = tk.StringVar()
        self.task_status = tk.StringVar(value="等待开始")
        self.task_title_text = tk.StringVar(value="科研任务")
        self.task_step_state: dict[str, str] = {}
        self.task_outcome_vars: dict[str, tk.StringVar] = {}
        self.task_outcome_labels: dict[str, tk.Label] = {}
        self.task_result_tabs: dict[str, ScrolledText] = {}
        self.task_literature_task_id = ""
        self.task_harvest_started = False
        self.user_task_filter = tk.StringVar(value="全部")
        self.user_task_cache: list[dict] = []
        self.library_reference_cache: list[dict] = []
        self.library_data_cache: list[dict] = []
        self.workspace_memory_cache: list[dict] = []
        self.dock_expanded = True
        self.dock_hide_after = ""
        self.sidebar_animation_after = ""
        self.sidebar_target_width = 230
        self.reference_cache: list[dict] = []
        self._project_syncing = False
        self.agent_citations: dict[str, dict] = {}
        self.workspace_state_cache: dict = {}
        self.settings_health_status = tk.StringVar(value="正在连接")
        self.settings_dual_status = tk.StringVar(value="检测中")
        self.settings_data_dir = tk.StringVar(value=str(AGENT_ROOT))

        self._build_style()
        self._build_ui()
        self.hydrate_from_client_cache()
        self.root.after(120, self.bootstrap)

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=(FONT_UI, 10), background=BG_BASE, foreground=TEXT_1)
        style.configure("App.TFrame", background=BG_DEEP)
        style.configure("Workspace.TFrame", background=BG_BASE)
        style.configure("Panel.TFrame", background=BG_SURFACE)
        style.configure("Card.TFrame", background=BG_SURFACE)
        style.configure("TLabel", background=BG_BASE, foreground=TEXT_1)
        style.configure("Panel.TLabel", background=BG_SURFACE, foreground=TEXT_1)
        style.configure("Muted.TLabel", background=BG_BASE, foreground=TEXT_2)
        style.configure("PanelMuted.TLabel", background=BG_SURFACE, foreground=TEXT_2)
        style.configure("Title.TLabel", background=BG_BASE, foreground=TEXT_1, font=(FONT_UI, 18, "bold"))
        style.configure("PanelTitle.TLabel", background=BG_SURFACE, foreground=TEXT_1, font=(FONT_UI, 11, "bold"))
        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=TEXT_1, insertcolor=TEXT_1, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=(12, 9))
        style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=TEXT_1, arrowcolor=TEXT_2, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=(10, 8))
        style.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)], foreground=[("readonly", TEXT_1)])
        style.configure("Treeview", rowheight=38, background=BG_INPUT, fieldbackground=BG_INPUT, foreground=TEXT_1, bordercolor=BORDER_SUBTLE, lightcolor=BORDER_SUBTLE, darkcolor=BORDER_SUBTLE)
        style.configure("Treeview.Heading", background=BG_SURFACE, foreground=TEXT_2, font=(FONT_UI, 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", ACCENT_DIM)], foreground=[("selected", TEXT_1)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT, focusthickness=0, padding=(16, 10), font=(FONT_UI, 10, "bold"))
        style.map("Accent.TButton", background=[("active", WorkbenchTheme.ACCENT_HOVER), ("pressed", ACCENT)], foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
        style.configure("Secondary.TButton", background=BG_SURFACE, foreground=TEXT_1, bordercolor=BORDER, focusthickness=0, padding=(14, 9))
        style.map("Secondary.TButton", background=[("active", BG_HOVER)])
        style.configure("Ghost.TButton", background=BG_BASE, foreground=TEXT_2, bordercolor=BG_BASE, focusthickness=0, padding=(10, 8))
        style.map("Ghost.TButton", background=[("active", BG_HOVER)], foreground=[("active", TEXT_1)])
        style.configure("TCheckbutton", background=BG_SURFACE, foreground=TEXT_2, focuscolor=BG_SURFACE)
        style.map("TCheckbutton", background=[("active", BG_SURFACE)], foreground=[("active", TEXT_1)])
        style.configure("TNotebook", background=BG_BASE, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_SURFACE, foreground=TEXT_2, padding=(14, 8), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", BG_ELEVATED), ("active", BG_HOVER)], foreground=[("selected", TEXT_1), ("active", TEXT_1)])

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(self.root, bg=BG_DEEP, width=230, highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.bind("<Enter>", self.expand_sidebar)
        self.sidebar.bind("<Leave>", self.collapse_sidebar)

        self.workspace = ttk.Frame(self.root, style="Workspace.TFrame", padding=(0, 0, 0, 0))
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)

        self.statusbar = tk.Frame(self.root, bg=BG_DEEP, height=1)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.statusbar.grid_propagate(False)
        self.statusbar.grid_remove()
        tk.Label(self.statusbar, textvariable=self.status_text, bg=BG_DEEP, fg=TEXT_2, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=16)
        self.status_model_label = tk.Label(self.statusbar, textvariable=self.model_status_text, bg=BG_DEEP, fg=TEXT_3, font=("Microsoft YaHei UI", 9))
        self.status_model_label.pack(side="right", padx=12)
        if not self.developer_mode.get():
            self.status_model_label.pack_forget()

        self._build_sidebar()
        self._build_workspace_shell()
        self._build_views()
        self.show_view("overview")
        self.root.bind("<Configure>", self.handle_responsive_shell)

    def handle_responsive_shell(self, _event=None) -> None:
        if not hasattr(self, "sidebar"):
            return
        width = self.root.winfo_width()
        if width and width < 760:
            if self.sidebar.winfo_ismapped():
                self.sidebar.grid_remove()
        else:
            if not self.sidebar.winfo_ismapped():
                self.sidebar.grid(row=0, column=0, sticky="nsew")

    def _build_sidebar(self) -> None:
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        brand = tk.Frame(self.sidebar, bg=BG_DEEP, cursor="hand2")
        brand.grid(row=0, column=0, sticky="ew", padx=14, pady=(22, 24))
        brand.bind("<Enter>", self.expand_sidebar)
        brand.bind("<Leave>", self.collapse_sidebar)
        brand.bind("<Button-1>", lambda _event: self.show_view("overview"))
        self.status_dot = tk.Canvas(brand, width=0, height=0, bg=BG_DEEP, highlightthickness=0)
        self.status_dot_id = self.status_dot.create_oval(0, 0, 0, 0, fill=WARN, outline=WARN)
        self.brand_mark = tk.Label(
            brand,
            text="A",
            width=3,
            height=2,
            bg=ACCENT,
            fg="#07110c",
            font=("Microsoft YaHei UI", 14, "bold"),
            cursor="hand2",
        )
        self.brand_mark.pack(side="left")
        self.brand_mark.bind("<Button-1>", lambda _event: self.show_view("overview"))
        self.brand_text = tk.Frame(brand, bg=BG_DEEP, cursor="hand2")
        tk.Label(self.brand_text, text="AURA Research", bg=BG_DEEP, fg=TEXT_1, font=("Microsoft YaHei UI", 12, "bold"), cursor="hand2").pack(anchor="w")
        tk.Label(self.brand_text, text="科研任务工作台", bg=BG_DEEP, fg=TEXT_3, font=("Microsoft YaHei UI", 8), cursor="hand2").pack(anchor="w", pady=(2, 0))
        self.brand_text.bind("<Button-1>", lambda _event: self.show_view("overview"))

        self.dock = tk.Frame(self.sidebar, bg=BG_DEEP)
        self.dock.grid(row=1, column=0, sticky="nsew", padx=14)
        self.dock.bind("<Enter>", self.expand_sidebar)
        self.dock.bind("<Leave>", self.collapse_sidebar)
        self.render_sidebar_nav()

        bottom = tk.Frame(self.sidebar, bg=BG_DEEP)
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 20))
        bottom.bind("<Enter>", self.expand_sidebar)
        bottom.bind("<Leave>", self.collapse_sidebar)
        mini = tk.Frame(bottom, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1, cursor="hand2")
        mini.pack(fill="x", ipady=10)
        mini.bind("<Enter>", self.expand_sidebar)
        mini.bind("<Leave>", self.collapse_sidebar)
        mini.bind("<Button-1>", lambda _event: self.show_view("workspace_user"))
        self.mini_project_dot = tk.Label(mini, text="●", bg=BG_SURFACE, fg=ACCENT, font=("Microsoft YaHei UI", 13, "bold"), cursor="hand2")
        self.mini_project_dot.pack(side="left", padx=(12, 9))
        self.mini_project_text = tk.Frame(mini, bg=BG_SURFACE, cursor="hand2")
        tk.Label(self.mini_project_text, text="肉桂渣免疫调节", bg=BG_SURFACE, fg=TEXT_1, font=("Microsoft YaHei UI", 9, "bold"), cursor="hand2").pack(anchor="w")
        tk.Label(self.mini_project_text, text="当前项目 · 68% 已整理", bg=BG_SURFACE, fg=TEXT_3, font=("Microsoft YaHei UI", 8), cursor="hand2").pack(anchor="w", pady=(2, 0))
        self.mini_project_dot.bind("<Button-1>", lambda _event: self.show_view("workspace_user"))
        self.mini_project_text.bind("<Button-1>", lambda _event: self.show_view("workspace_user"))
        self._sync_sidebar_labels()

    def render_sidebar_nav(self) -> None:
        if not hasattr(self, "dock"):
            return
        for child in self.dock.winfo_children():
            child.destroy()
        self.nav_buttons = {}
        user_items = [
            ("overview", "总览", "⌁"),
            ("tasks_user", "任务流", "●"),
            ("library_user", "资料库", "◫"),
            ("agent", "AURA", "AI"),
            ("memory", "项目记忆", "◎"),
        ]
        for key, title, icon in user_items:
            self._nav_button(self.dock, key, title, title, icon)
        if self.developer_mode.get():
            tk.Label(self.dock, text="开发者工具", bg=BG_DEEP, fg=TEXT_3, anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x", padx=14, pady=(14, 4))
            for key, title in DEV_NAV:
                self._nav_button(self.dock, key, title, title, "·")
        self._sync_sidebar_labels()

    def toggle_developer_mode(self) -> None:
        self.developer_mode.set(not self.developer_mode.get())
        self.client_cache["developer_mode"] = bool(self.developer_mode.get())
        self.save_client_cache()
        self.render_sidebar_nav()
        if hasattr(self, "dev_command_button"):
            if self.developer_mode.get():
                self.dev_command_button.grid()
                self.dev_demo_button.grid()
                if hasattr(self, "status_model_label"):
                    self.status_model_label.pack(side="right", padx=12)
            else:
                self.dev_command_button.grid_remove()
                self.dev_demo_button.grid_remove()
                if hasattr(self, "status_model_label"):
                    self.status_model_label.pack_forget()
        self.update_settings_developer_visibility()
        self.status_text.set("开发者模式已开启" if self.developer_mode.get() else "开发者模式已关闭")
        if not self.developer_mode.get() and self.active_view not in {key for key, _title in USER_NAV}:
            self.show_view("overview")

    def _small_button(self, parent, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=BG_SURFACE, fg=TEXT_2, activebackground=BG_HOVER, activeforeground=TEXT_1, relief="flat", bd=0, padx=12, pady=9, cursor="hand2", font=("Microsoft YaHei UI", 9))

    def _nav_button(self, parent, key: str, title: str, subtitle: str, icon: str = "") -> None:
        label = f"{icon}  {title}" if icon else title
        button = tk.Button(parent, text=label, command=lambda: self.show_view(key), bg=BG_DEEP, fg=TEXT_2, activebackground=BG_HOVER, activeforeground=TEXT_1, relief="flat", bd=0, padx=13, pady=13, anchor="w", justify="left", cursor="hand2", font=("Microsoft YaHei UI", 10, "bold"), wraplength=180)
        button.pack(fill="x", pady=4)
        button._aura_icon = icon
        button._aura_title = title
        button.bind("<Enter>", self.expand_sidebar)
        button.bind("<Leave>", self.collapse_sidebar)
        self.nav_buttons[key] = button

    def _sync_sidebar_labels(self) -> None:
        expanded = getattr(self, "dock_expanded", False)
        if hasattr(self, "brand_text"):
            if expanded:
                self.brand_text.pack(side="left", padx=(12, 0))
            else:
                self.brand_text.pack_forget()
        if hasattr(self, "mini_project_text"):
            if expanded:
                self.mini_project_text.pack(side="left")
            else:
                self.mini_project_text.pack_forget()
        for button in getattr(self, "nav_buttons", {}).values():
            icon = getattr(button, "_aura_icon", "")
            title = getattr(button, "_aura_title", "")
            button.configure(text=f"{icon}  {title}" if expanded else icon)

    def animate_sidebar_width(self, target: int) -> None:
        if getattr(self, "sidebar_target_width", None) == target and int(self.sidebar.cget("width")) == target:
            return
        self.sidebar_target_width = target
        if self.sidebar_animation_after:
            try:
                self.root.after_cancel(self.sidebar_animation_after)
            except Exception:
                pass
            self.sidebar_animation_after = ""
        current = int(self.sidebar.cget("width"))
        if current == target:
            self._sync_sidebar_labels()
            return
        step = 18 if target > current else -18
        next_width = current + step
        if (step > 0 and next_width > target) or (step < 0 and next_width < target):
            next_width = target
        self.sidebar.configure(width=next_width)
        if next_width != target:
            self.sidebar_animation_after = self.root.after(16, lambda: self.animate_sidebar_width(target))
        else:
            self.sidebar_animation_after = ""
            self._sync_sidebar_labels()

    def expand_sidebar(self, _event=None) -> None:
        if self.dock_expanded and int(self.sidebar.cget("width")) >= 260:
            return
        self.dock_expanded = True
        self._sync_sidebar_labels()
        if hasattr(self, "sidebar"):
            self.animate_sidebar_width(260)

    def collapse_sidebar(self, _event=None) -> None:
        if self.root.winfo_width() >= 760:
            self.dock_expanded = True
            self._sync_sidebar_labels()
            if hasattr(self, "sidebar"):
                self.sidebar.configure(width=230)
            return
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        target = self.root.winfo_containing(x, y)
        widget = target
        while widget is not None:
            if widget is self.sidebar:
                return
            widget = getattr(widget, "master", None)
        if not self.dock_expanded and int(self.sidebar.cget("width")) <= 88:
            return
        self.dock_expanded = False
        self._sync_sidebar_labels()
        if hasattr(self, "sidebar"):
            self.animate_sidebar_width(88)

    def show_dock(self, _event=None) -> None:
        if self.dock_hide_after:
            try:
                self.root.after_cancel(self.dock_hide_after)
            except Exception:
                pass
            self.dock_hide_after = ""
        self.expand_sidebar()

    def schedule_hide_dock(self, _event=None) -> None:
        if self.dock_hide_after:
            try:
                self.root.after_cancel(self.dock_hide_after)
            except Exception:
                pass
        self.dock_hide_after = self.root.after(420, self.hide_dock)

    def hide_dock(self) -> None:
        self.dock_expanded = False
        self._sync_sidebar_labels()
        if hasattr(self, "sidebar"):
            self.animate_sidebar_width(88)

    def toggle_dock(self) -> None:
        if self.dock_expanded:
            self.hide_dock()
        else:
            self.show_dock()

    def _build_workspace_shell(self) -> None:
        header = ttk.Frame(self.workspace, style="Workspace.TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(18, 0))
        header.grid_columnconfigure(0, weight=1)

        self.shell_title_block = ttk.Frame(header, style="Workspace.TFrame")
        self.shell_title_block.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Label(self.shell_title_block, textvariable=self.workspace_title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.shell_title_block, textvariable=self.workspace_subtitle, style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

        self.global_command = tk.Entry(
            header,
            bg=BG_INPUT,
            fg=TEXT_3,
            insertbackground=TEXT_1,
            relief="flat",
            bd=0,
            font=(FONT_UI, 11),
        )
        self.global_command_placeholder = "搜索项目、文献、任务，或输入科研命令"
        self.global_command.insert(0, self.global_command_placeholder)
        self.global_command.grid(row=0, column=0, sticky="ew", ipady=12, padx=(0, 12))
        self.global_command.bind("<Return>", self.run_global_command)
        self.global_command.bind("<FocusIn>", self.clear_global_command_placeholder)
        self.global_command.bind("<FocusOut>", self.restore_global_command_placeholder)

        ttk.Button(header, text="新建任务", style="Accent.TButton", command=lambda: self.show_view("tasks_user")).grid(row=0, column=1, sticky="e")
        self.dual_status_pill = tk.Label(header, text="本地服务检测中", bg=BG_SURFACE, fg=TEXT_2, padx=13, pady=10, font=(FONT_UI, 9, "bold"), cursor="hand2")
        self.dual_status_pill.grid(row=0, column=2, sticky="e", padx=(10, 0))
        self.dual_status_pill.bind("<Button-1>", lambda _event: self.show_view("settings"))
        self.task_count_pill = tk.Label(header, text="任务流", bg=BG_SURFACE, fg=TEXT_2, padx=13, pady=10, font=(FONT_UI, 9, "bold"), cursor="hand2")
        self.task_count_pill.grid(row=0, column=3, sticky="e", padx=(10, 0))
        self.task_count_pill.bind("<Button-1>", lambda _event: self.show_view("tasks_user"))
        self.profile_pill = tk.Label(header, text="设置", bg=BG_SURFACE, fg=TEXT_2, padx=13, pady=10, font=(FONT_UI, 9, "bold"), cursor="hand2")
        self.profile_pill.grid(row=0, column=4, sticky="e", padx=(10, 0))
        self.profile_pill.bind("<Button-1>", lambda _event: self.show_view("settings"))
        self.dev_command_button = ttk.Button(header, text="开发者控制台", style="Secondary.TButton", command=lambda: self.show_view("functions"))
        self.dev_command_button.grid(row=1, column=3, sticky="e", padx=(10, 0), pady=(8, 0))
        self.dev_demo_button = ttk.Button(header, text="开发者演示", style="Accent.TButton", command=self.run_dual_agent_demo)
        self.dev_demo_button.grid(row=1, column=4, sticky="e", padx=(10, 0), pady=(8, 0))
        if not self.developer_mode.get():
            self.dev_command_button.grid_remove()
            self.dev_demo_button.grid_remove()

        self.content_host = ttk.Frame(self.workspace, style="Workspace.TFrame")
        self.content_host.grid(row=1, column=0, sticky="nsew")
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

    def _build_right_panel(self) -> None:
        self.latest_context = {}

    def _build_views(self) -> None:
        self._build_overview()
        self._build_workspace_user()
        self._build_library_user()
        self._build_tasks_user()
        self._build_settings()
        self._build_task_workspace()
        self._build_functions()
        self._build_literature()
        self._build_projects()
        self._build_data()
        self._build_experiments()
        self._build_samples()
        self._build_knowledge()
        self._build_agent()
        self._build_research_feed()
        self._build_memory()
        self._build_skills()
        self._build_api_console()

    def _view(self, key: str, title: str, subtitle: str) -> ttk.Frame:
        frame = ttk.Frame(self.content_host, style="Workspace.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        self.views[key] = frame
        setattr(frame, "_view_title", title)
        setattr(frame, "_view_subtitle", subtitle)
        return frame

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
            ttk.Button(bar, text=label, style=style, command=command).pack(side="left", padx=(0, 8), pady=(0, 4))
        return bar

    def _set_text(self, widget: ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _panel(self, parent, title: str, subtitle: str = "") -> ttk.Frame:
        return self._workbench_section(parent, title, subtitle)

    def _text(self, parent, height: int = 12) -> ScrolledText:
        box = ScrolledText(parent, height=height, bg=BG_INPUT, fg=TEXT_1, insertbackground=TEXT_1, selectbackground=ACCENT_DIM, relief="flat", bd=0, padx=13, pady=13, font=(FONT_MONO, 10), wrap="word")
        return box

    def _reading_text(self, parent, height: int = 12) -> ScrolledText:
        box = ScrolledText(parent, height=height, bg=BG_INPUT, fg=TEXT_1, insertbackground=TEXT_1, selectbackground=ACCENT_DIM, relief="flat", bd=0, padx=16, pady=16, font=(FONT_UI, 10), wrap="word")
        return box

    def _action_button(self, parent, text: str, command, *, kind: str = "secondary") -> tk.Button:
        primary = kind == "primary"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=ACCENT if primary else BG_ELEVATED,
            fg="#07110c" if primary else TEXT_1,
            activebackground="#2fd6a1" if primary else BG_HOVER,
            activeforeground="#07110c" if primary else TEXT_1,
            relief="flat",
            bd=0,
            padx=14,
            pady=9,
            cursor="hand2",
            font=(FONT_UI, 9, "bold"),
        )

    def _entry(self, parent, label: str, var: tk.StringVar) -> ttk.Entry:
        ttk.Label(parent, text=label, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(parent, textvariable=var)
        entry.pack(fill="x", pady=(0, 10))
        return entry

    def _combo(self, parent, label: str, var: tk.StringVar, values: list[str] | None = None) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        combo = ttk.Combobox(parent, textvariable=var, values=values or [], state="readonly")
        combo.pack(fill="x", pady=(0, 10))
        return combo

    def default_client_cache(self) -> dict:
        return {
            "projects": [],
            "last_project_id": "",
            "hidden_projects": [],
            "hidden_literature_tasks": [],
            "hidden_references": [],
            "hidden_tasks": [],
            "hidden_memory": [],
            "hidden_files": [],
            "agent_conversation_id": "",
            "developer_mode": False,
            "active_user_tab": "overview",
        }

    def load_client_cache(self) -> dict:
        try:
            if CLIENT_CACHE_PATH.exists():
                cached = json.loads(CLIENT_CACHE_PATH.read_text(encoding="utf-8"))
                if isinstance(cached, dict):
                    base = self.default_client_cache()
                    base.update(cached)
                    return base
        except Exception:
            pass
        return self.default_client_cache()

    def save_client_cache(self) -> None:
        try:
            CLIENT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CLIENT_CACHE_PATH.write_text(json.dumps(self.client_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def hidden_ids(self, key: str) -> set[str]:
        return {clean(item) for item in self.client_cache.get(key, []) if clean(item)}

    def hide_client_item(self, key: str, item_id: str) -> None:
        item_id = clean(item_id)
        if not item_id:
            return
        values = self.hidden_ids(key)
        values.add(item_id)
        self.client_cache[key] = sorted(values)
        self.save_client_cache()

    def is_client_hidden(self, key: str, item_id: str) -> bool:
        return clean(item_id) in self.hidden_ids(key)

    def hydrate_from_client_cache(self) -> None:
        cached_projects = self.client_cache.get("projects") or []
        if isinstance(cached_projects, list) and cached_projects:
            self.render_projects(cached_projects, from_cache=True)

    def _build_overview(self) -> None:
        view = self._view("overview", "首页", "从一句话开始和 AURA 对话。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(0, weight=1)

        shell = tk.Frame(view, bg=BG_BASE)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        bg = tk.Canvas(shell, bg=BG_BASE, highlightthickness=0)
        bg.grid(row=0, column=0, sticky="nsew")

        content = tk.Frame(bg, bg=BG_BASE)
        content.grid_columnconfigure(0, weight=1)
        bg_window = bg.create_window(0, 0, window=content, anchor="nw")

        def redraw_background(_event=None) -> None:
            width = max(bg.winfo_width(), 1)
            height = max(bg.winfo_height(), 1)
            size_key = (width // 24, height // 24)
            if getattr(bg, "_aura_bg_size_key", None) == size_key:
                return
            bg._aura_bg_size_key = size_key
            bg.delete("aura-bg")
            bands = [
                "#0f1411", "#101612", "#111713", "#121814", "#131b16",
                "#151d18", "#17201b", "#19231d", "#1b251f", "#1d2922",
            ]
            band_h = max(height // len(bands), 1)
            for idx, color in enumerate(bands):
                bg.create_rectangle(0, idx * band_h, width, (idx + 1) * band_h + 2, fill=color, outline=color, tags="aura-bg")
            bg.create_oval(int(width * 0.70), -120, int(width * 1.05), int(height * 0.36), fill="#173d31", outline="", tags="aura-bg")
            bg.create_oval(-100, int(height * 0.65), int(width * 0.30), int(height * 1.16), fill="#152d25", outline="", tags="aura-bg")
            bg.create_line(0, int(height * 0.80), width, int(height * 0.56), fill="#20352d", width=1, tags="aura-bg")
            bg.tag_lower("aura-bg")
            bg.itemconfigure(bg_window, width=width, height=height)

        bg.bind("<Configure>", redraw_background)

        hero = tk.Frame(content, bg=BG_BASE)
        hero.grid(row=0, column=0, sticky="nsew", padx=30, pady=(86, 72))
        hero.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        headline = tk.Canvas(hero, width=980, height=68, bg=BG_BASE, highlightthickness=0)
        headline.grid(row=0, column=0, pady=(0, 28))

        def draw_headline(_event=None) -> None:
            width_key = headline.winfo_width() // 24
            if getattr(headline, "_aura_headline_width_key", None) == width_key:
                return
            headline._aura_headline_width_key = width_key
            headline.delete("all")
            canvas_width = max(headline.winfo_width(), 980)
            cn_font = tkfont.Font(family="Microsoft YaHei UI", size=30, weight="bold")
            aura_font = tkfont.Font(family="Fraunces", size=36, slant="italic", weight="bold")
            left_text = "欢迎使用"
            aura_text = "Aura Research"
            right_text = "，有什么可以帮忙的？"
            total = cn_font.measure(left_text) + aura_font.measure(aura_text) + cn_font.measure(right_text) + 22
            x = max((canvas_width - total) // 2, 8)
            y = 34
            headline.create_text(x, y, text=left_text, anchor="w", fill=TEXT_1, font=cn_font)
            x += cn_font.measure(left_text) + 10
            aura_width = aura_font.measure(aura_text)
            headline.create_rectangle(x + 2, y + 13, x + aura_width - 2, y + 21, fill="#173d31", outline="")
            try:
                headline.create_text(x, y + 1, text=aura_text, anchor="w", fill="#1b4d3b", font=aura_font, angle=-1)
                headline.create_text(x, y, text=aura_text, anchor="w", fill=ACCENT, font=aura_font, angle=-1)
            except tk.TclError:
                headline.create_text(x, y + 1, text=aura_text, anchor="w", fill="#1b4d3b", font=aura_font)
                headline.create_text(x, y, text=aura_text, anchor="w", fill=ACCENT, font=aura_font)
            x += aura_width + 12
            headline.create_text(x, y, text=right_text, anchor="w", fill=TEXT_1, font=cn_font)

        headline.bind("<Configure>", draw_headline)

        composer = tk.Frame(hero, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1)
        composer.grid(row=1, column=0, sticky="ew", padx=150)
        composer.grid_columnconfigure(0, weight=1)
        self.command_entry = tk.Text(
            composer,
            height=3,
            bg=BG_SURFACE,
            fg=TEXT_1,
            insertbackground=TEXT_1,
            relief="flat",
            bd=0,
            padx=20,
            pady=16,
            font=("Microsoft YaHei UI", 12),
            wrap="word",
        )
        self.command_entry.grid(row=0, column=0, columnspan=2, sticky="ew")
        placeholder = "输入关键词、实验问题、文献方向或数据分析需求，例如：肉桂渣 免疫调节 文献采集"
        self.command_entry.insert("1.0", placeholder)
        self.command_entry.configure(fg="#9aa692")

        def clear_placeholder(_event=None) -> None:
            if self.command_entry.get("1.0", "end-1c") == placeholder:
                self.command_entry.delete("1.0", tk.END)
                self.command_entry.configure(fg=TEXT_1)

        def restore_placeholder(_event=None) -> None:
            if not self.command_entry.get("1.0", "end-1c").strip():
                self.command_entry.insert("1.0", placeholder)
                self.command_entry.configure(fg="#9aa692")

        def sync_command_text() -> None:
            value = self.command_entry.get("1.0", "end-1c")
            self.command_text.set("" if value == placeholder else value)

        def current_home_text() -> str:
            sync_command_text()
            return self.command_text.get().strip()

        def send_from_home() -> None:
            value = current_home_text()
            if not value:
                self.show_aura_toast("先输入一个科研目标或关键词")
                return
            self.command_entry.delete("1.0", tk.END)
            restore_placeholder()
            self.command_text.set("")
            self.open_chat_with_message(value)

        def home_keydown(event) -> str | None:
            if event.keysym == "Return" and not (event.state & 0x0001):
                send_from_home()
                return "break"
            return None

        self.command_entry.bind("<FocusIn>", clear_placeholder)
        self.command_entry.bind("<FocusOut>", restore_placeholder)
        self.command_entry.bind("<KeyRelease>", lambda _event: sync_command_text())
        self.command_entry.bind("<Return>", home_keydown)

        actions = tk.Frame(composer, bg=BG_SURFACE)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 14))
        actions.grid_columnconfigure(0, weight=1)
        tool_row = tk.Frame(actions, bg=BG_SURFACE)
        tool_row.grid(row=0, column=0, sticky="w")

        def run_context_tool(default_prompt: str, with_topic) -> None:
            value = current_home_text()
            if value:
                self.command_entry.delete("1.0", tk.END)
                restore_placeholder()
                self.command_text.set("")
                self.open_chat_with_message(with_topic(value))
            else:
                fill_quick(default_prompt)

        tool_actions = [
            ("＋ 上传", self.home_upload_file),
            ("文献", lambda: run_context_tool("请围绕当前项目关键词采集开放文献，并把结果整理进资料库。", lambda topic: f"请围绕“{topic}”采集开放文献，并把结果整理进当前项目资料库。")),
            ("实验", lambda: run_context_tool("请根据当前项目设计下一步实验方案，包括分组、指标、方法和验证路径。", lambda topic: f"请根据“{topic}”设计下一步实验方案，包括分组、指标、方法和验证路径。")),
            ("数据", self.home_upload_data_file),
            ("写作", lambda: run_context_tool("请根据当前项目记忆生成一页式科研进展汇报。", lambda topic: f"请围绕“{topic}”并结合当前项目记忆生成科研写作草稿。")),
        ]
        for label, command in tool_actions:
            tk.Button(tool_row, text=label, command=command, bg=BG_SURFACE, fg=TEXT_2, activebackground=BG_HOVER, activeforeground=ACCENT, relief="flat", bd=0, padx=11, pady=8, cursor="hand2", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(0, 8))
        send = tk.Button(actions, text="→", command=send_from_home, bg=ACCENT, fg="#07110c", activebackground="#2fd6a1", activeforeground="#07110c", relief="flat", bd=0, padx=17, pady=10, cursor="hand2", font=("Microsoft YaHei UI", 15, "bold"))
        send.grid(row=0, column=1, sticky="e")

        cards = tk.Frame(hero, bg=BG_BASE)
        cards.grid(row=2, column=0, sticky="ew", padx=150, pady=(18, 0))
        for idx in range(4):
            cards.grid_columnconfigure(idx, weight=1, uniform="quick")
        quick_prompts = [
            ("文献采集", "输入 1 到 3 个关键词，自动检索、筛选、入库。", "帮我采集肉桂渣免疫调节相关文献，并整理成项目知识库"),
            ("实验设计", "把研究目标转成分组、指标、方法和验证路径。", "根据我的项目设计下一步 RAW264.7 免疫调节实验方案"),
            ("数据分析", "上传表格后自动判断统计路线和可视化方案。", "分析我上传的数据表，找出差异结果并生成图表建议"),
            ("项目复盘", "从文献、实验、数据和失败记录生成汇报。", "根据当前项目记忆生成一页式科研进展汇报"),
        ]

        def fill_quick(text: str) -> None:
            self.command_entry.configure(fg=TEXT_1)
            self.command_entry.delete("1.0", tk.END)
            self.command_entry.insert("1.0", text)
            self.command_text.set(text)
            self.command_entry.focus_set()
            self.show_aura_toast("已放入输入框，可继续修改后发送")

        for idx, (title, desc, text) in enumerate(quick_prompts):
            card = tk.Frame(cards, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1, cursor="hand2")
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0 if idx == 3 else 6), ipady=10)
            card.bind("<Button-1>", lambda _event, value=text: fill_quick(value))
            title_label = tk.Label(card, text=title, bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2")
            title_label.pack(fill="x", padx=16, pady=(12, 5))
            desc_label = tk.Label(card, text=desc, bg=BG_SURFACE, fg=TEXT_3, anchor="w", justify="left", wraplength=160, font=("Microsoft YaHei UI", 9), cursor="hand2")
            desc_label.pack(fill="x", padx=16, pady=(0, 12))
            title_label.bind("<Button-1>", lambda _event, value=text: fill_quick(value))
            desc_label.bind("<Button-1>", lambda _event, value=text: fill_quick(value))

        self.home_project_summary = tk.Label(shell, text="当前项目：等待连接本地工作区", bg=BG_BASE, fg=TEXT_3, font=("Microsoft YaHei UI", 1))
        self.home_status_line = tk.Label(shell, text="本地连接检测中 · 模型检测中", bg=BG_BASE, fg=TEXT_3, font=("Microsoft YaHei UI", 1))
        self.aura_toast = tk.Label(view, text="", bg=BG_SURFACE, fg=ACCENT, padx=16, pady=12, font=("Microsoft YaHei UI", 9, "bold"), highlightbackground=BORDER, highlightthickness=1)

        def responsive(_event=None) -> None:
            width = view.winfo_width()
            if width and width < 760:
                headline.configure(width=max(width - 36, 320))
                cards.grid_configure(padx=18)
                composer.grid_configure(padx=18)
                for idx, child in enumerate(cards.winfo_children()):
                    child.grid_configure(row=idx, column=0, sticky="ew", padx=0, pady=(0, 12))
            else:
                headline.configure(width=980)
                cards.grid_configure(padx=150)
                composer.grid_configure(padx=150)
                for idx, child in enumerate(cards.winfo_children()):
                    child.grid_configure(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0 if idx == 3 else 6), pady=0)

        view.bind("<Configure>", responsive)

    def _build_workspace_user(self) -> None:
        view = self._view("workspace_user", "工作区", "当前项目、项目记忆和下一步建议。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        header = self._panel(view, "当前项目", "选择项目后，AURA 会围绕这个项目读取资料库、记忆和任务状态。")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_body = ttk.Frame(header, style="Panel.TFrame")
        header_body.pack(fill="x")
        self.user_project_box = ttk.Combobox(header_body, textvariable=self.project_choice, values=[], state="readonly", width=44)
        self.user_project_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.user_project_box.bind("<<ComboboxSelected>>", lambda _event: (self.activate_project(self.current_project_id(self.project_choice)), self.load_workspace_summary()))
        ttk.Button(header_body, text="刷新", style="Secondary.TButton", command=self.load_workspace_summary).pack(side="left")
        ttk.Button(header_body, text="项目设置", style="Secondary.TButton", command=self.rename_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(header_body, text="归档", style="Secondary.TButton", command=self.archive_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(header_body, text="取消归档", style="Secondary.TButton", command=self.unarchive_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(header_body, text="清空记忆", style="Secondary.TButton", command=self.clear_workspace_memory).pack(side="left", padx=(8, 0))
        ttk.Button(header_body, text="清空项目内容", style="Secondary.TButton", command=self.clear_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(header_body, text="删除项目", style="Secondary.TButton", command=self.delete_workspace_project).pack(side="left", padx=(8, 0))
        self.workspace_project_summary = tk.Label(header, text="正在读取项目资料。", bg=BG_SURFACE, fg=TEXT_2, anchor="w", justify="left", font=("Microsoft YaHei UI", 10))
        self.workspace_project_summary.pack(fill="x", pady=(12, 0))

        stats = tk.Frame(view, bg=BG_ELEVATED, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        stats.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for idx in range(6):
            stats.grid_columnconfigure(idx, weight=1)
        self.workspace_stat_vars: dict[str, tk.StringVar] = {}
        for idx, (key, label) in enumerate([
            ("pdf", "PDF"),
            ("refs", "文献"),
            ("chunks", "证据片段"),
            ("experiments", "实验"),
            ("samples", "样品"),
            ("tasks", "运行任务"),
        ]):
            value = tk.StringVar(value="0")
            self.workspace_stat_vars[key] = value
            cell = tk.Frame(stats, bg=BG_ELEVATED)
            cell.grid(row=0, column=idx, sticky="ew", padx=8, pady=10)
            tk.Label(cell, textvariable=value, bg=BG_ELEVATED, fg=TEXT_1, font=("Microsoft YaHei UI", 15, "bold")).pack()
            tk.Label(cell, text=label, bg=BG_ELEVATED, fg=TEXT_2, font=("Microsoft YaHei UI", 9)).pack()

        body = ttk.Frame(view, style="Workspace.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        memory = self._panel(body, "项目记忆摘要", "只展示用户可理解的当前状态，不显示原始 JSON。")
        memory.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.workspace_memory_box = self._reading_text(memory, 10)
        self.workspace_memory_box.pack(fill="both", expand=True, pady=(0, 8))
        self.workspace_memory_list = tk.Listbox(memory, height=6, bg=BG_INPUT, fg=TEXT_1, highlightthickness=1, highlightbackground=BORDER, relief="flat", selectbackground=ACCENT_DIM, selectforeground=TEXT_1, font=("Microsoft YaHei UI", 10))
        self.workspace_memory_list.pack(fill="x", pady=(0, 8))
        memory_actions = ttk.Frame(memory, style="Panel.TFrame")
        memory_actions.pack(fill="x")
        ttk.Button(memory_actions, text="重新整理记忆", style="Secondary.TButton", command=self.rebuild_workspace_memory).pack(side="left")
        ttk.Button(memory_actions, text="标记错误", style="Secondary.TButton", command=self.mark_selected_memory_wrong).pack(side="left", padx=(8, 0))
        ttk.Button(memory_actions, text="隐藏记忆", style="Secondary.TButton", command=self.hide_selected_memory_entry).pack(side="left", padx=(8, 0))
        next_steps = self._panel(body, "下一步建议", "最多展示 5 条，可点击后进入聊天。")
        next_steps.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.workspace_next_box = self._reading_text(next_steps, 8)
        self.workspace_next_box.pack(fill="both", expand=True, pady=(0, 10))
        self.workspace_suggestion_frame = ttk.Frame(next_steps, style="Panel.TFrame")
        self.workspace_suggestion_frame.pack(fill="x")

    def _build_library_user(self) -> None:
        view = self._view("library_user", "资料库", "统一管理文献、PDF、数据文件、实验方案和实验记录。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(0, weight=1)
        notebook = ttk.Notebook(view)
        notebook.grid(row=0, column=0, sticky="nsew")

        literature = ttk.Frame(notebook, style="Workspace.TFrame", padding=(14, 14, 14, 14))
        literature.grid_columnconfigure(0, weight=1)
        literature.grid_rowconfigure(1, weight=1)
        lit_panel = self._panel(literature, "文献采集", "输入 1-3 个关键词，AURA 会调用文献采集能力。")
        lit_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.library_keywords = tk.StringVar()
        ttk.Entry(lit_panel, textvariable=self.library_keywords).pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=7)
        ttk.Button(lit_panel, text="开始采集", style="Accent.TButton", command=self.run_library_literature_harvest).pack(side="left")
        ttk.Button(lit_panel, text="刷新", style="Secondary.TButton", command=self.load_literature_tasks).pack(side="left", padx=(8, 0))
        lit_list = self._panel(literature, "采集进度")
        lit_list.grid(row=1, column=0, sticky="nsew")
        self.library_literature_box = self._reading_text(lit_list, 18)
        self.library_literature_box.pack(fill="both", expand=True)
        notebook.add(literature, text="文献")

        pdf = ttk.Frame(notebook, style="Workspace.TFrame", padding=(14, 14, 14, 14))
        pdf.grid_columnconfigure(0, weight=1)
        pdf.grid_rowconfigure(1, weight=1)
        pdf_actions = self._panel(pdf, "添加文献", "导入 PDF 后会登记文件并启动解析。")
        pdf_actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(pdf_actions, text="添加 PDF", style="Accent.TButton", command=self.quick_pdf_import).pack(side="left")
        ttk.Button(pdf_actions, text="构建知识库", style="Secondary.TButton", command=self.build_kb).pack(side="left", padx=(8, 0))
        ttk.Button(pdf_actions, text="加载文献列表", style="Secondary.TButton", command=self.load_references).pack(side="left", padx=(8, 0))
        ttk.Button(pdf_actions, text="查看", style="Secondary.TButton", command=self.show_library_reference_detail).pack(side="left", padx=(8, 0))
        ttk.Button(pdf_actions, text="重新解析", style="Secondary.TButton", command=self.reparse_selected_library_reference).pack(side="left", padx=(8, 0))
        ttk.Button(pdf_actions, text="从项目移除", style="Secondary.TButton", command=self.remove_selected_library_reference_from_project).pack(side="left", padx=(8, 0))
        ttk.Button(pdf_actions, text="删除", style="Secondary.TButton", command=self.delete_selected_library_reference).pack(side="left", padx=(8, 0))
        pdf_list = self._panel(pdf, "文献列表")
        pdf_list.grid(row=1, column=0, sticky="nsew")
        self.library_reference_list = tk.Listbox(pdf_list, height=9, bg=BG_INPUT, fg=TEXT_1, highlightthickness=1, highlightbackground=BORDER, relief="flat", selectbackground=ACCENT_DIM, selectforeground=TEXT_1, font=("Microsoft YaHei UI", 10))
        self.library_reference_list.pack(fill="x", pady=(0, 8))
        self.library_reference_list.bind("<<ListboxSelect>>", lambda _event: self.show_library_reference_detail())
        self.library_reference_box = self._reading_text(pdf_list, 11)
        self.library_reference_box.pack(fill="both", expand=True)
        notebook.add(pdf, text="PDF")

        data = ttk.Frame(notebook, style="Workspace.TFrame", padding=(14, 14, 14, 14))
        data.grid_columnconfigure(0, weight=1)
        data.grid_rowconfigure(1, weight=1)
        data_actions = self._panel(data, "分析数据", "上传 CSV、Excel 或仪器导出文件。")
        data_actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.library_data_search = tk.StringVar()
        ttk.Entry(data_actions, textvariable=self.library_data_search).pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=7)
        ttk.Button(data_actions, text="上传数据", style="Accent.TButton", command=self.quick_data_upload).pack(side="left")
        ttk.Button(data_actions, text="搜索", style="Secondary.TButton", command=self.run_library_data_search).pack(side="left", padx=(8, 0))
        ttk.Button(data_actions, text="查看", style="Secondary.TButton", command=self.show_library_data_detail).pack(side="left", padx=(8, 0))
        ttk.Button(data_actions, text="从项目移除", style="Secondary.TButton", command=self.hide_selected_library_data).pack(side="left", padx=(8, 0))
        ttk.Button(data_actions, text="删除记录", style="Secondary.TButton", command=self.hide_selected_library_data).pack(side="left", padx=(8, 0))
        data_list = self._panel(data, "数据与实验对象")
        data_list.grid(row=1, column=0, sticky="nsew")
        self.library_data_list = tk.Listbox(data_list, height=9, bg=BG_INPUT, fg=TEXT_1, highlightthickness=1, highlightbackground=BORDER, relief="flat", selectbackground=ACCENT_DIM, selectforeground=TEXT_1, font=("Microsoft YaHei UI", 10))
        self.library_data_list.pack(fill="x", pady=(0, 8))
        self.library_data_list.bind("<<ListboxSelect>>", lambda _event: self.show_library_data_detail())
        self.library_data_box = self._reading_text(data_list, 11)
        self.library_data_box.pack(fill="both", expand=True)
        notebook.add(data, text="数据")

        protocol = ttk.Frame(notebook, style="Workspace.TFrame", padding=(14, 14, 14, 14))
        protocol.grid_columnconfigure(0, weight=1)
        protocol.grid_rowconfigure(1, weight=1)
        protocol_actions = self._panel(protocol, "方案提取", "粘贴方法学或实验流程，提取实验方案草案。")
        protocol_actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(protocol_actions, text="提取方案", style="Accent.TButton", command=self.run_library_protocol_extract).pack(side="left")
        self.library_protocol_input = self._reading_text(protocol, 7)
        self.library_protocol_input.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        protocol_result = self._panel(protocol, "方案结果")
        protocol_result.grid(row=2, column=0, sticky="nsew")
        self.library_protocol_box = self._reading_text(protocol_result, 12)
        self.library_protocol_box.pack(fill="both", expand=True)
        notebook.add(protocol, text="方案")

        records = ttk.Frame(notebook, style="Workspace.TFrame", padding=(14, 14, 14, 14))
        records.grid_columnconfigure(0, weight=1)
        records.grid_rowconfigure(1, weight=1)
        record_actions = self._panel(records, "实验记录", "粘贴今天的实验记录，AURA 会提取结构化记忆。")
        record_actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(record_actions, text="保存记录", style="Accent.TButton", command=self.run_library_experiment_extract).pack(side="left")
        self.library_record_input = self._reading_text(records, 7)
        self.library_record_input.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        record_result = self._panel(records, "记录结果")
        record_result.grid(row=2, column=0, sticky="nsew")
        self.library_record_box = self._reading_text(record_result, 12)
        self.library_record_box.pack(fill="both", expand=True)
        notebook.add(records, text="记录")

    def _build_tasks_user(self) -> None:
        view = self._view("tasks_user", "任务", "正在运行、已完成、失败和待确认的科研任务。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)
        top = self._panel(view, "任务操作")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(top, text="刷新任务", style="Accent.TButton", command=self.load_user_tasks_summary).pack(side="left")
        ttk.Label(top, text="筛选", style="PanelMuted.TLabel").pack(side="left", padx=(14, 6))
        self.user_task_filter_box = ttk.Combobox(top, textvariable=self.user_task_filter, values=list(TASK_FILTERS.keys()), state="readonly", width=10)
        self.user_task_filter_box.pack(side="left")
        self.user_task_filter_box.bind("<<ComboboxSelected>>", lambda _event: self.render_user_task_list())
        ttk.Button(top, text="自动推进任务", style="Secondary.TButton", command=self.run_agent_heartbeat).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="扫描项目", style="Secondary.TButton", command=self.run_research_watcher).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="查看结果", style="Secondary.TButton", command=self.show_selected_user_task_detail).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="继续", style="Secondary.TButton", command=self.continue_selected_user_task).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="重试", style="Secondary.TButton", command=self.retry_selected_user_task).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="取消", style="Secondary.TButton", command=self.cancel_selected_user_task).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="删除记录", style="Secondary.TButton", command=self.hide_selected_user_task).pack(side="right")
        body = ttk.Frame(view, style="Workspace.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        left = self._panel(body, "任务列表", "轻量展示任务状态；技术详情在开发者模式查看。")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.user_tasks_list = tk.Listbox(left, bg=BG_INPUT, fg=TEXT_1, highlightthickness=1, highlightbackground=BORDER, relief="flat", selectbackground=ACCENT_DIM, selectforeground=TEXT_1, font=("Microsoft YaHei UI", 10))
        self.user_tasks_list.pack(fill="both", expand=True)
        self.user_tasks_list.bind("<<ListboxSelect>>", lambda _event: self.show_selected_user_task_detail())
        self.user_tasks_box = self.user_tasks_list
        right = self._panel(body, "任务详情")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.user_activity_box = self._reading_text(right, 22)
        self.user_activity_box.pack(fill="both", expand=True)

    def _build_settings(self) -> None:
        view = self._view("settings", "设置", "本地运行状态、模型和开发者模式。")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(0, weight=1)
        panel = self._panel(view, "本地设置", "敏感信息只显示状态，不在界面明文展示完整密钥。")
        panel.grid(row=0, column=0, sticky="nsew")
        status_grid = ttk.Frame(panel, style="Panel.TFrame")
        status_grid.pack(fill="x", pady=(0, 14))
        for idx in range(2):
            status_grid.grid_columnconfigure(idx, weight=1)
        for idx, (title, var) in enumerate([("本地服务", self.settings_health_status), ("AURA 能力", self.settings_dual_status)]):
            cell = tk.Frame(status_grid, bg=BG_ELEVATED, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
            cell.grid(row=0, column=idx, sticky="ew", padx=6, pady=4)
            tk.Label(cell, text=title, bg=BG_ELEVATED, fg=TEXT_2, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(cell, textvariable=var, bg=BG_ELEVATED, fg=TEXT_1, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=14, pady=(0, 10))
        ttk.Label(panel, text="模型服务", style="PanelMuted.TLabel").pack(anchor="w", pady=(6, 4))
        self.settings_model_status_label = tk.Label(panel, textvariable=self.model_status_text, bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=("Microsoft YaHei UI", 10))
        self.settings_model_status_label.pack(fill="x", pady=(0, 8))
        self.settings_model_raw_label = ttk.Label(panel, text="后端模型详情", style="PanelMuted.TLabel")
        self.settings_model_raw_entry = ttk.Entry(panel, textvariable=self.model_text)
        ttk.Label(panel, text="数据目录", style="PanelMuted.TLabel").pack(anchor="w", pady=(6, 4))
        self.settings_data_status_label = tk.Label(panel, text="本地资料目录已配置", bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=("Microsoft YaHei UI", 10))
        self.settings_data_status_label.pack(fill="x", pady=(0, 8))
        self.settings_data_raw_label = ttk.Label(panel, text="本地路径详情", style="PanelMuted.TLabel")
        self.settings_data_raw_entry = ttk.Entry(panel, textvariable=self.settings_data_dir)
        settings_actions = ttk.Frame(panel, style="Panel.TFrame")
        settings_actions.pack(fill="x", pady=(2, 16))
        ttk.Button(settings_actions, text="打开数据目录", style="Secondary.TButton", command=self.open_data_dir).pack(side="left")
        ttk.Button(settings_actions, text="重新连接", style="Accent.TButton", command=self.reconnect_api).pack(side="left", padx=(8, 0))
        ttk.Label(panel, text="新建项目", style="PanelMuted.TLabel").pack(anchor="w", pady=(6, 4))
        self.settings_project_title = tk.StringVar()
        self.settings_project_area = tk.StringVar()
        ttk.Label(panel, text="项目名称", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Entry(panel, textvariable=self.settings_project_title).pack(fill="x", pady=(0, 8))
        ttk.Label(panel, text="研究方向", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Entry(panel, textvariable=self.settings_project_area).pack(fill="x", pady=(0, 8))
        ttk.Button(panel, text="创建项目", style="Secondary.TButton", command=self.create_project_from_settings).pack(anchor="w", pady=(0, 14))
        tk.Checkbutton(panel, text="开发者模式：显示技能注册表、API 调试和原始状态", variable=self.developer_mode, command=self.on_developer_mode_changed, bg=BG_SURFACE, fg=TEXT_2, activebackground=BG_SURFACE, activeforeground=TEXT_1, selectcolor=BG_INPUT, relief="flat", anchor="w", cursor="hand2").pack(fill="x", pady=(0, 10))
        self.settings_hint = self._reading_text(panel, 8)
        self.settings_hint.pack(fill="both", expand=True)
        self.settings_hint.insert("1.0", "API Key：已由后端环境变量或 .env 管理，客户端不会显示完整密钥。\n\n开发者模式默认关闭，开启后可访问技能注册表、开发者控制台、API 调试和后端日志。")
        self.update_settings_developer_visibility()

    def on_developer_mode_changed(self) -> None:
        self.client_cache["developer_mode"] = bool(self.developer_mode.get())
        self.save_client_cache()
        self.render_sidebar_nav()
        if hasattr(self, "dev_command_button"):
            if self.developer_mode.get():
                self.dev_command_button.grid()
                self.dev_demo_button.grid()
                if hasattr(self, "status_model_label"):
                    self.status_model_label.pack(side="right", padx=12)
            else:
                self.dev_command_button.grid_remove()
                self.dev_demo_button.grid_remove()
                if hasattr(self, "status_model_label"):
                    self.status_model_label.pack_forget()
        self.update_settings_developer_visibility()
        if not self.developer_mode.get() and self.active_view not in {key for key, _title in USER_NAV}:
            self.show_view("overview")

    def update_settings_developer_visibility(self) -> None:
        if not hasattr(self, "settings_model_raw_label"):
            return
        if self.developer_mode.get():
            self.settings_model_raw_label.pack(anchor="w", pady=(0, 4))
            self.settings_model_raw_entry.pack(fill="x", pady=(0, 10))
            self.settings_data_raw_label.pack(anchor="w", pady=(0, 4))
            self.settings_data_raw_entry.pack(fill="x", pady=(0, 10))
        else:
            self.settings_model_raw_label.pack_forget()
            self.settings_model_raw_entry.pack_forget()
            self.settings_data_raw_label.pack_forget()
            self.settings_data_raw_entry.pack_forget()

    def format_user_error(self, message: str) -> str:
        text = str(message or "")
        for marker in ["Traceback", "File \"", "RuntimeError:", "Exception:", "{", "}", "stack"]:
            if marker in text:
                return "操作失败。请检查本地服务是否启动，或在设置中开启开发者模式查看详情。"
        return clean(text) or "操作失败，请稍后重试。"

    def format_user_answer(self, body: dict) -> str:
        answer = clean(body.get("answer") or body.get("summary") or body.get("message"))
        if answer:
            return answer
        result = body.get("execution_result") or {}
        if result:
            return clean(result.get("summary")) or "AURA 已完成任务。"
        return "AURA 已返回结果。"

    def format_task_item(self, task: dict) -> str:
        name = self.user_task_name(task)
        status = self.user_status_label(clean(task.get("status") or "未知"))
        progress = task.get("progress") or task.get("progress_json") or {}
        if isinstance(progress, str):
            try:
                progress = json.loads(progress)
            except Exception:
                progress = {}
        bits = []
        for key, label in [("downloaded", "下载"), ("parsed", "解析"), ("indexed", "入库"), ("failed", "失败")]:
            if isinstance(progress, dict) and progress.get(key) is not None:
                bits.append(f"{label} {progress.get(key)}")
        suffix = f" · {' / '.join(bits)}" if bits else ""
        return f"{name} · {status}{suffix}"

    def user_task_name(self, task: dict) -> str:
        raw = clean(task.get("title") or task.get("task_type") or task.get("skill_name") or task.get("name") or "科研任务")
        if raw in TASK_TYPE_LABELS:
            return TASK_TYPE_LABELS[raw]
        lowered = raw.lower()
        if "keyword" in lowered and "harvest" in lowered:
            return "文献采集"
        if "memory" in lowered:
            return "项目记忆整理"
        if "bottleneck" in lowered or "gap" in lowered:
            return "研究缺口分析"
        if "protocol" in lowered or "sop" in lowered:
            return "方案提取"
        if "report" in lowered or "digest" in lowered:
            return "报告生成"
        if "analysis" in lowered or "data" in lowered:
            return "数据分析"
        if "core_" in lowered or "handler" in lowered:
            return "科研任务"
        return raw.replace("_", " ").strip().title() if raw.islower() else raw

    def user_status_label(self, status: str) -> str:
        return TASK_STATUS_LABELS.get(clean(status), clean(status) or "未知")

    def user_project_name_for_item(self, item: dict) -> str:
        project_id = clean(item.get("project_id"))
        return self.project_label_from_id(project_id) if project_id else (self.project_choice.get() or "当前项目")

    def parse_maybe_json(self, value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    def load_workspace_summary(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            if hasattr(self, "workspace_memory_box"):
                self.workspace_memory_box.delete("1.0", tk.END)
                self.workspace_memory_box.insert("1.0", "还没有项目。请在设置里创建项目。")
            return

        def task():
            state_status, state = self.api.get("/research-os/workspace-state?" + urllib.parse.urlencode({"project_id": project_id}), timeout=60)
            memory_status, memory = self.api.post("/research-os/memory/context", {"project_id": project_id, "query": "当前项目状态和下一步建议"}, timeout=60)
            entries_status, entries = self.api.get("/research-os/agent-memory?" + urllib.parse.urlencode({"project_id": project_id, "limit": 60}), timeout=60)
            inbox_status, inbox = self.api.get("/research-os/agent/inbox?" + urllib.parse.urlencode({"project_id": project_id, "limit": 20}), timeout=60)
            return {"state_status": state_status, "state": state, "memory_status": memory_status, "memory": memory, "entries_status": entries_status, "entries": entries, "inbox_status": inbox_status, "inbox": inbox}

        def done(result):
            state = result.get("state") if result.get("state_status") == 200 else {}
            self.workspace_state_cache = state if isinstance(state, dict) else {}
            self.render_workspace_summary(result)

        self.run_async(task, done, lambda message: self.render_workspace_error(message))

    def render_workspace_error(self, message: str) -> None:
        if hasattr(self, "workspace_memory_box"):
            self.workspace_memory_box.delete("1.0", tk.END)
            self.workspace_memory_box.insert("1.0", self.format_user_error(message))

    def render_workspace_summary(self, result: dict) -> None:
        state = result.get("state") if isinstance(result.get("state"), dict) else {}
        project = state.get("project") or {}
        literature = state.get("literature") or {}
        data = state.get("data") or {}
        tasks = state.get("tasks") or {}
        memory = result.get("memory") if isinstance(result.get("memory"), dict) else {}
        entries_payload = result.get("entries") if isinstance(result.get("entries"), dict) else {}
        inbox = result.get("inbox") if isinstance(result.get("inbox"), dict) else {}
        stats = {
            "pdf": literature.get("pdf_files_found", 0),
            "refs": literature.get("references_count", 0),
            "chunks": literature.get("chunks_count", 0),
            "experiments": data.get("experiments_count", 0),
            "samples": data.get("samples_count", 0),
            "tasks": len(tasks.get("running") or []),
        }
        for key, value in stats.items():
            if hasattr(self, "workspace_stat_vars") and key in self.workspace_stat_vars:
                self.workspace_stat_vars[key].set(str(value))
        title = clean(project.get("title")) or self.project_label_from_id(self.default_project_id()) or "当前项目"
        if hasattr(self, "workspace_project_summary"):
            direction = clean(project.get("research_area") or project.get("research_direction")) or "未填写"
            stage = clean(project.get("status")) or "active"
            updated = clean(project.get("updated_at") or project.get("created_at")) or "暂无"
            self.workspace_project_summary.configure(text=f"研究方向：{direction}    当前阶段：{self.user_status_label(stage)}    最近更新：{updated}")
        if hasattr(self, "home_project_summary"):
            self.home_project_summary.configure(text=f"当前项目：{title} · PDF {stats['pdf']} · 文献 {stats['refs']} · 运行任务 {stats['tasks']}")
        if hasattr(self, "workspace_memory_box"):
            lines = [f"项目：{title}", "", f"PDF {stats['pdf']} 篇，文献记录 {stats['refs']} 条，可检索证据片段 {stats['chunks']} 个。", f"实验 {stats['experiments']} 条，样品 {stats['samples']} 个。", ""]
            context = clean(memory.get("compiled_context") or memory.get("context") or memory.get("answer"))
            lines.append(context[:1600] if context else "暂无项目记忆摘要。可以先导入文献、上传实验记录，或在首页询问 AURA。")
            self.workspace_memory_box.delete("1.0", tk.END)
            self.workspace_memory_box.insert("1.0", "\n".join(lines))
        if hasattr(self, "workspace_memory_list"):
            entries = entries_payload.get("memory") or entries_payload.get("entries") or []
            self.workspace_memory_cache = [
                item for item in entries
                if isinstance(item, dict) and not self.is_client_hidden("hidden_memory", clean(item.get("id")))
            ]
            self.workspace_memory_list.delete(0, tk.END)
            for item in self.workspace_memory_cache[:30]:
                label = clean(item.get("title") or item.get("memory_type") or item.get("content") or item.get("summary") or "记忆条目")
                self.workspace_memory_list.insert(tk.END, label[:120])
            if not self.workspace_memory_cache:
                self.workspace_memory_list.insert(tk.END, "暂无可管理的记忆条目。")
        if hasattr(self, "workspace_next_box"):
            items = inbox.get("items") or inbox.get("inbox_items") or []
            lines = []
            suggestions: list[str] = []
            for item in items[:8]:
                if isinstance(item, dict):
                    title_text = clean(item.get('title')) or clean(item.get('type'))
                    message_text = clean(item.get('message'))[:180]
                    lines.append(f"- {title_text}: {message_text}")
                    if title_text:
                        suggestions.append(title_text)
            if not lines:
                suggestions = ["请基于当前项目生成文献缺口分析", "请整理当前项目的证据链", "请生成下一步实验方案"]
                lines = ["暂无主动建议。可以点击下面的建议，让 AURA 继续推进。"]
            self.workspace_next_box.delete("1.0", tk.END)
            self.workspace_next_box.insert("1.0", "\n".join(lines[:5]))
            if hasattr(self, "workspace_suggestion_frame"):
                for child in self.workspace_suggestion_frame.winfo_children():
                    child.destroy()
                for suggestion in suggestions[:5]:
                    tk.Button(self.workspace_suggestion_frame, text=suggestion, command=lambda value=suggestion: self.open_chat_with_message(value), bg=ACCENT_DIM, fg=ACCENT, activebackground=BG_HOVER, activeforeground=ACCENT, relief="flat", bd=0, padx=12, pady=7, cursor="hand2", font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=(0, 6))

    def load_library_summary(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            return
        if hasattr(self, "library_literature_box"):
            self.library_literature_box.delete("1.0", tk.END)
            self.library_literature_box.insert("1.0", "输入关键词后点击“开始采集”。下载和入库进度会显示在这里。")
        self.load_references()

    def run_library_literature_harvest(self) -> None:
        keywords = clean(self.library_keywords.get())
        if not keywords:
            self._show_error("请输入 1-3 个关键词。")
            return
        self.lit_keywords.set(keywords)
        self.set_project_var(self.lit_project, self.default_project_id())
        if hasattr(self, "library_literature_box"):
            self.library_literature_box.delete("1.0", tk.END)
            self.library_literature_box.insert("1.0", "正在提交文献采集任务。")
        self.run_literature_harvest()

    def run_library_data_search(self) -> None:
        self.data_search.set(self.library_data_search.get())
        self.set_project_var(self.data_project, self.default_project_id())
        self.search_data_objects()

    def run_library_protocol_extract(self) -> None:
        text = self.library_protocol_input.get("1.0", tk.END).strip()
        project_id = self.default_project_id()
        if not text:
            self._show_error("请先粘贴 Methods 或实验流程。")
            return

        def task():
            status, body = self.api.post("/research-os/protocols/parse", {"project_id": project_id, "text": text}, timeout=90)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.library_protocol_box.delete("1.0", tk.END)
            self.library_protocol_box.insert("1.0", self.format_user_answer(body) + "\n\n" + self.safe_summary_lines(body))
            self.status_text.set("方案已提取")

        self.run_async(task, done, self._show_error)

    def run_library_experiment_extract(self) -> None:
        text = self.library_record_input.get("1.0", tk.END).strip()
        project_id = self.default_project_id()
        if not text:
            self._show_error("请先粘贴实验记录。")
            return

        def task():
            status, body = self.api.post("/research-os/memory/extract-experiment", {"project_id": project_id, "text": text}, timeout=90)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.library_record_box.delete("1.0", tk.END)
            self.library_record_box.insert("1.0", self.safe_summary_lines(body))
            self.status_text.set("实验记录已整理")

        self.run_async(task, done, self._show_error)

    def safe_summary_lines(self, body: object) -> str:
        if not isinstance(body, dict):
            return clean(body)
        lines = []
        for key, label in [("status", "状态"), ("message", "结果"), ("summary", "摘要"), ("id", "记录"), ("error", "错误")]:
            value = clean(body.get(key))
            if value and key != "error":
                lines.append(f"{label}：{value}")
            elif value:
                lines.append(f"{label}：{self.format_user_error(value)}")
        if not lines:
            for key, value in list(body.items())[:8]:
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"{key}：{clean(value)}")
        return "\n".join(lines) or "已完成。"

    def create_project_from_settings(self) -> None:
        title = clean(self.settings_project_title.get())
        area = clean(self.settings_project_area.get())
        if not title:
            self._show_error("请输入项目名称。")
            return
        payload = {"title": title, "research_area": area, "owner": "local_user", "status": "active"}

        def task():
            status, body = self.api.post("/research-os/projects", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body.get("project") or body

        def done(project):
            self.settings_project_title.set("")
            self.settings_project_area.set("")
            self.status_text.set(f"项目已创建：{self.project_label(project)}")
            self.client_cache["last_project_id"] = clean(project.get("id"))
            self.save_client_cache()
            self.load_projects()
            self.show_view("workspace_user")

        self.run_async(task, done, self._show_error)

    def rename_workspace_project(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return
        current = self.project_label_from_id(project_id)
        title = clean(simpledialog.askstring("项目设置", "输入新的项目名称：", initialvalue=current))
        if not title:
            return

        def task():
            status, body = self.api.put(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}", {"title": title})
            if status != 200:
                raise RuntimeError(pretty(body))
            return body.get("project") or body

        def done(_project):
            self.status_text.set("项目名称已更新")
            self.load_projects()

        self.run_async(task, done, self._show_error)

    def archive_workspace_project(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return
        if not messagebox.askyesno("归档项目", "归档后普通界面将隐藏这个项目；资料和记忆不会被物理删除。确认归档？"):
            return
        self.hide_client_item("hidden_projects", project_id)

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/archive", {})
            if status != 200:
                return {"warning": body}
            return body

        def done(_body):
            self.status_text.set("项目已归档并从普通界面隐藏")
            self.load_projects()
            self.show_view("overview")

        self.run_async(task, done, self._show_error)

    def unarchive_workspace_project(self) -> None:
        project_id = self.selected_project_id() or self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/unarchive", {}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(_body):
            self.status_text.set("项目已取消归档")
            self.load_projects()

        self.run_async(task, done, self._show_error)

    def _deletion_plan_text(self, plan: dict) -> str:
        tables = plan.get("affected_tables") if isinstance(plan.get("affected_tables"), dict) else {}
        table_text = "，".join(f"{key}:{value}" for key, value in list(tables.items())[:8]) or "无记录"
        dirs = plan.get("affected_dirs") if isinstance(plan.get("affected_dirs"), list) else []
        return (
            f"项目：{clean((plan.get('project') or {}).get('display_name'))}\n"
            f"范围：{clean(plan.get('scope'))}\n"
            f"目录：{'; '.join(dirs[:4]) or '无'}\n"
            f"记录数：{int(plan.get('record_count') or 0)}\n"
            f"文件数：{int(plan.get('file_count') or 0)}\n"
            f"预计释放：{float(plan.get('estimated_free_mb') or 0):.3f} MB\n"
            f"表：{table_text}"
        )

    def clear_workspace_memory(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/clear", {"scope": "memory", "dry_run": True}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(result):
            plan = result.get("deletion_plan") or {}
            phrase = clean(plan.get("confirmation_phrase"))
            if not phrase:
                display = clean((plan.get("project") or {}).get("display_name")) or self.project_label_from_id(project_id)
                phrase = f"确认清空 {display}"
            if not messagebox.askyesno("清空项目记忆", self._deletion_plan_text(plan) + f"\n\n该操作只清空项目记忆，不会删除文献、文件或任务；如需执行，请在下一步输入：{DESTRUCTIVE_CONFIRMATION_WORD}"):
                return
            confirmation = clean(simpledialog.askstring("确认清空项目记忆", f"请输入：{DESTRUCTIVE_CONFIRMATION_WORD}"))
            if confirmation != DESTRUCTIVE_CONFIRMATION_WORD:
                self.status_text.set("确认词不匹配，未清空项目记忆")
                return

            def execute():
                status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/clear", {"scope": "memory", "confirmation": phrase}, timeout=120)
                if status != 200 or not (isinstance(body, dict) and body.get("executed")):
                    raise RuntimeError(pretty(body))
                return body

            self.run_async(execute, lambda _body: (self.status_text.set("项目记忆已清空"), self.load_workspace_summary()), self._show_error)

        self.run_async(task, done, self._show_error)

    def clear_workspace_project(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/clear", {"scope": "all", "dry_run": True}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(result):
            plan = result.get("deletion_plan") or {}
            phrase = clean(plan.get("confirmation_phrase"))
            if not phrase:
                display = clean((plan.get("project") or {}).get("display_name")) or self.project_label_from_id(project_id)
                phrase = f"确认清空 {display}"
            if not messagebox.askyesno("清空项目", self._deletion_plan_text(plan) + f"\n\n如需执行，请在下一步输入：{DESTRUCTIVE_CONFIRMATION_WORD}"):
                return
            confirmation = clean(simpledialog.askstring("确认清空项目", f"请输入：{DESTRUCTIVE_CONFIRMATION_WORD}"))
            if confirmation != DESTRUCTIVE_CONFIRMATION_WORD:
                self.status_text.set("确认词不匹配，未清空项目")
                return

            def execute():
                status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/clear", {"scope": "all", "confirmation": phrase}, timeout=120)
                if status != 200 or not (isinstance(body, dict) and body.get("executed")):
                    raise RuntimeError(pretty(body))
                return body

            self.run_async(execute, lambda _body: (self.status_text.set("项目已清空，项目本身仍保留"), self.load_projects(), self.load_workspace_summary()), self._show_error)

        self.run_async(task, done, self._show_error)

    def delete_workspace_project(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/purge", {"dry_run": True}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(result):
            plan = result.get("deletion_plan") or {}
            display = clean((plan.get("project") or {}).get("display_name"))
            phrase = clean(plan.get("confirmation_phrase")) or f"CONFIRM PURGE {display}"
            if not messagebox.askyesno("彻底删除项目", self._deletion_plan_text(plan) + f"\n\n该操作会删除项目内容和项目对象；如需执行，请在下一步输入：{DESTRUCTIVE_CONFIRMATION_WORD}"):
                return
            confirmation = clean(simpledialog.askstring("确认彻底删除项目", f"请输入：{DESTRUCTIVE_CONFIRMATION_WORD}"))
            if confirmation != DESTRUCTIVE_CONFIRMATION_WORD:
                self.status_text.set("确认词不匹配，未删除项目")
                return

            def execute():
                status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/purge", {"confirmation": phrase}, timeout=120)
                if status != 200 or not (isinstance(body, dict) and body.get("executed")):
                    raise RuntimeError(pretty(body))
                return body

            def deleted(_body):
                self.forget_project_selection(project_id)
                self.status_text.set("项目已彻底删除")
                self.load_projects()
                self.show_view("overview")

            self.run_async(execute, deleted, self._show_error)

        self.run_async(task, done, self._show_error)

    def selected_workspace_memory(self) -> dict:
        if not hasattr(self, "workspace_memory_list"):
            return {}
        selection = self.workspace_memory_list.curselection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.workspace_memory_cache):
            return {}
        return self.workspace_memory_cache[index]

    def mark_selected_memory_wrong(self) -> None:
        memory = self.selected_workspace_memory()
        memory_id = clean(memory.get("id"))
        if not memory_id:
            self._show_error("请先选择一条记忆。")
            return
        if not messagebox.askyesno("标记错误", "标记后 AURA 会降低这条记忆的优先级，并记录一条用户纠正。"):
            return

        def task():
            put_status, put_body = self.api.put(f"/research-os/agent-memory/{urllib.parse.quote(memory_id, safe='')}", {"status": "rejected", "disabled": True, "note": "Marked wrong from client"}, timeout=60)
            correction_status, correction_body = self.api.post("/research-os/memory/user-correction", {"project_id": self.default_project_id(), "memory_id": memory_id, "correction": "这条记忆被用户标记为错误。"}, timeout=60)
            return {"memory": put_body if put_status == 200 else {"warning": put_body}, "correction": correction_body if correction_status == 200 else {"warning": correction_body}}

        def done(_body):
            self.hide_client_item("hidden_memory", memory_id)
            self.status_text.set("记忆已标记为错误，并从普通界面隐藏")
            self.load_workspace_summary()

        self.run_async(task, done, self._show_error)

    def hide_selected_memory_entry(self) -> None:
        memory = self.selected_workspace_memory()
        memory_id = clean(memory.get("id"))
        if not memory_id:
            self._show_error("请先选择一条记忆。")
            return
        if not messagebox.askyesno("隐藏记忆", "从当前客户端隐藏这条记忆？后端数据不会被物理删除。"):
            return
        self.hide_client_item("hidden_memory", memory_id)
        self.status_text.set("记忆已从客户端隐藏")
        self.load_workspace_summary()

    def rebuild_workspace_memory(self) -> None:
        self.open_chat_with_message("请重新整理当前项目记忆，标出可靠结论、待确认信息和下一步建议。")

    def load_user_tasks_summary(self) -> None:
        project_id = self.default_project_id()
        if not project_id:
            return

        def task():
            task_status, tasks = self.api.get("/research-os/tasks?" + urllib.parse.urlencode({"project_id": project_id, "limit": 80}), timeout=60)
            run_status, runs = self.api.get("/research-os/skill-runs?limit=50", timeout=60)
            lit_status, lit = self.api.get("/research-os/literature/search-tasks?" + urllib.parse.urlencode({"project_id": project_id, "limit": 20}), timeout=60)
            inbox_status, inbox = self.api.get("/research-os/agent/inbox?" + urllib.parse.urlencode({"project_id": project_id, "limit": 40}), timeout=60)
            return {"tasks": tasks if task_status == 200 else {}, "runs": runs if run_status == 200 else {}, "lit": lit if lit_status == 200 else {}, "inbox": inbox if inbox_status == 200 else {}}

        def done(result):
            tasks = result.get("tasks", {}).get("tasks", [])
            runs = result.get("runs", {}).get("skill_runs", [])
            lit = result.get("lit", {}).get("tasks") or result.get("lit", {}).get("literature_search_tasks") or []
            inbox = result.get("inbox", {}).get("items", [])
            combined: list[dict] = []
            for item in tasks or []:
                if isinstance(item, dict):
                    row = dict(item)
                    row["_kind"] = "task"
                    combined.append(row)
            for item in lit or []:
                if isinstance(item, dict):
                    row = dict(item)
                    row["_kind"] = "literature"
                    row.setdefault("task_type", "literature_harvest")
                    row.setdefault("title", f"文献采集：{clean(row.get('query'))[:80]}")
                    combined.append(row)
            self.user_task_cache = [item for item in combined if not self.is_client_hidden("hidden_tasks", clean(item.get("task_id") or item.get("id")))]
            self.render_user_task_list()
            if hasattr(self, "user_activity_box"):
                lines = ["最近活动", ""]
                for item in (runs or [])[:12]:
                    lines.append(f"- {self.user_task_name(item)} · {self.user_status_label(clean(item.get('status')))} · {clean(item.get('updated_at'))}")
                for item in (inbox or [])[:8]:
                    lines.append(f"- {clean(item.get('title')) or clean(item.get('type'))}: {clean(item.get('message'))[:120]}")
                if len(lines) == 2:
                    lines.append("暂无活动。")
                self.user_activity_box.delete("1.0", tk.END)
                self.user_activity_box.insert("1.0", "\n".join(lines))
            has_running = any(clean(item.get("status")) in {"running", "pending"} for item in self.user_task_cache)
            if self.active_view == "tasks_user" and has_running:
                self.root.after(6000, self.load_user_tasks_summary)

        self.run_async(task, done, self._show_error)

    def render_user_task_list(self) -> None:
        if not hasattr(self, "user_tasks_list"):
            return
        selected_filter = TASK_FILTERS.get(self.user_task_filter.get(), "")
        self.user_tasks_list.delete(0, tk.END)
        shown = []
        for item in self.user_task_cache:
            status = clean(item.get("status"))
            if selected_filter:
                if selected_filter == "waiting_for_user" and status not in {"waiting_for_user", "waiting_approval"}:
                    continue
                if selected_filter != "waiting_for_user" and status != selected_filter:
                    continue
            shown.append(item)
            updated = clean(item.get("updated_at") or item.get("created_at"))
            project = self.user_project_name_for_item(item)
            self.user_tasks_list.insert(tk.END, f"{self.format_task_item(item)} · {project} · {updated}")
        if not shown:
            self.user_tasks_list.insert(tk.END, "暂无符合条件的任务。")
        self.user_task_visible_cache = shown

    def selected_user_task(self) -> dict:
        if not hasattr(self, "user_tasks_list"):
            return {}
        selection = self.user_tasks_list.curselection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(getattr(self, "user_task_visible_cache", [])):
            return {}
        return self.user_task_visible_cache[index]

    def show_selected_user_task_detail(self) -> None:
        item = self.selected_user_task()
        if not hasattr(self, "user_activity_box"):
            return
        self.user_activity_box.delete("1.0", tk.END)
        if not item:
            self.user_activity_box.insert("1.0", "请选择一个任务查看详情。")
            return
        lines = [
            f"任务：{self.user_task_name(item)}",
            f"状态：{self.user_status_label(clean(item.get('status')))}",
            f"项目：{self.user_project_name_for_item(item)}",
            f"时间：{clean(item.get('updated_at') or item.get('created_at')) or '暂无'}",
            "",
            f"摘要：{clean(item.get('summary') or item.get('next_action') or item.get('message')) or '暂无摘要。'}",
        ]
        progress = self.parse_maybe_json(item.get("progress") or item.get("progress_json"))
        if isinstance(progress, dict):
            readable = []
            for key, label in [("downloaded", "已下载"), ("parsed", "已解析"), ("indexed", "已入库"), ("failed", "失败")]:
                if progress.get(key) is not None:
                    readable.append(f"{label} {progress.get(key)}")
            if readable:
                lines.extend(["", "进度：" + " / ".join(readable)])
        error = clean(item.get("error"))
        if error:
            lines.extend(["", f"错误：{self.format_user_error(error)}"])
        lines.extend(["", "可执行操作：查看结果、继续、重试、取消或删除记录。"])
        if self.developer_mode.get():
            lines.extend(["", "开发者详情", pretty(item)])
        self.user_activity_box.insert("1.0", "\n".join(lines))

    def continue_selected_user_task(self) -> None:
        item = self.selected_user_task()
        if not item:
            self._show_error("请先选择一个任务。")
            return
        self.open_chat_with_message(f"继续处理这个任务：{self.user_task_name(item)}。请告诉我当前结果和下一步。")

    def retry_selected_user_task(self) -> None:
        item = self.selected_user_task()
        task_id = clean(item.get("task_id") or item.get("id"))
        if not task_id:
            self._show_error("这个任务没有可重试的后端记录。")
            return
        if not messagebox.askyesno("重试任务", "重新运行这个任务？"):
            return

        def task():
            if item.get("_kind") == "literature":
                query = clean(item.get("query") or item.get("title"))
                status, body = self.api.post("/research-os/literature/search-tasks", {"project_id": self.default_project_id(), "query": query, "keywords": query, "provider": "all"}, timeout=120)
            else:
                status, body = self.api.post(f"/research-os/tasks/{urllib.parse.quote(task_id)}/run", {"approved": True}, timeout=120)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(_body):
            self.status_text.set("任务已重新提交")
            self.load_user_tasks_summary()

        self.run_async(task, done, self._show_error)

    def cancel_selected_user_task(self) -> None:
        item = self.selected_user_task()
        task_id = clean(item.get("task_id") or item.get("id"))
        if not task_id:
            self._show_error("这个任务没有可取消的后端记录。")
            return
        if not messagebox.askyesno("取消任务", "取消这个任务？已经产生的文件不会被删除。"):
            return

        def task():
            if item.get("_kind") == "literature":
                status, body = self.api.post(f"/research-os/literature/search-tasks/{urllib.parse.quote(task_id)}/cancel", {"reason": "cancelled from client"}, timeout=90)
            else:
                status, body = self.api.post(f"/research-os/tasks/{urllib.parse.quote(task_id)}/cancel", {"reason": "cancelled from client"}, timeout=90)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(_body):
            self.status_text.set("任务已取消")
            self.load_user_tasks_summary()

        self.run_async(task, done, self._show_error)

    def hide_selected_user_task(self) -> None:
        item = self.selected_user_task()
        task_id = clean(item.get("task_id") or item.get("id"))
        if not task_id:
            self._show_error("请先选择一个任务。")
            return
        if not messagebox.askyesno("删除任务记录", "普通删除会先从客户端隐藏这条记录；不会删除已经产生的资料。"):
            return
        self.hide_client_item("hidden_tasks", task_id)
        self.status_text.set("任务记录已从客户端隐藏")
        self.load_user_tasks_summary()

    def _build_task_workspace(self) -> None:
        view = self._view("task_workspace", "任务工作区", "从关键词进入文献、知识库、记忆和 Agent 编排流程。")
        view.grid_columnconfigure(0, weight=2)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(view, style="Workspace.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)
        ttk.Label(header, textvariable=self.task_title_text, style="Title.TLabel", font=("Microsoft YaHei UI", 18)).grid(row=0, column=0, sticky="w")
        self.task_project_box = ttk.Combobox(header, textvariable=self.task_project, values=[], state="readonly", width=34)
        self.task_project_box.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Label(header, textvariable=self.task_status, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        flow = self._panel(view, "Agent 任务流", "前端复用现有 Agent、RAG、文献采集、记忆和 Skill 接口。")
        flow.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.task_step_labels: dict[str, tk.Label] = {}
        steps = [
            ("understand", "理解研究方向"),
            ("plan", "生成任务计划"),
            ("search", "检索文献与知识库"),
            ("extract", "整理结构化证据"),
            ("suggest", "生成下一步建议"),
            ("memory", "项目记忆更新"),
        ]
        for key, label in steps:
            row = tk.Frame(flow, bg=BG_SURFACE)
            row.pack(fill="x", pady=5)
            dot = tk.Label(row, text="o", bg=BG_SURFACE, fg=TEXT_3, font=("Microsoft YaHei UI", 13), width=2)
            dot.pack(side="left")
            text = tk.Label(row, text=label, bg=BG_SURFACE, fg=TEXT_2, font=("Microsoft YaHei UI", 10), anchor="w")
            text.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.task_step_labels[key] = dot
            self.task_step_state[key] = "pending"

        outcome = self._panel(flow, "任务产出", "只展示后端真实返回或可从结果中推导的数量。")
        outcome.pack(fill="x", pady=(18, 0))
        metrics = [
            ("papers", "检索文献"),
            ("pdfs", "PDF"),
            ("evidence", "证据项"),
            ("tables", "表格"),
            ("memory", "记忆"),
            ("suggestions", "建议"),
        ]
        grid = ttk.Frame(outcome, style="Panel.TFrame")
        grid.pack(fill="x")
        for index, (key, label) in enumerate(metrics):
            cell = tk.Frame(grid, bg=BG_INPUT, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=5)
            grid.grid_columnconfigure(index % 2, weight=1)
            value = tk.StringVar(value="等待")
            self.task_outcome_vars[key] = value
            tk.Label(cell, textvariable=value, bg=BG_INPUT, fg=ACCENT, font=("Microsoft YaHei UI", 18)).pack(anchor="w", padx=12, pady=(10, 0))
            tk.Label(cell, text=label, bg=BG_INPUT, fg=TEXT_2, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=12, pady=(0, 10))

        actions = ttk.Frame(flow, style="Panel.TFrame")
        actions.pack(fill="x", pady=(16, 0))
        ttk.Button(actions, text="运行文献采集", style="Accent.TButton", command=self.start_task_literature_harvest).pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="打开资料库", style="Secondary.TButton", command=lambda: self.show_view("library_user")).pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="查看任务", style="Secondary.TButton", command=lambda: self.show_view("tasks_user")).pack(fill="x")

        output = self._panel(view, "研究输出", "按科研资产组织结果，避免直接暴露大段原始 JSON。")
        output.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        output.grid_rowconfigure(0, weight=1)
        notebook = ttk.Notebook(output)
        notebook.pack(fill="both", expand=True)
        for key, title in [
            ("overview", "概览"),
            ("literature", "文献证据"),
            ("kb", "资料库"),
            ("protocol", "方案 / 实验计划"),
            ("data", "数据分析"),
            ("memory", "项目记忆"),
        ]:
            tab = ttk.Frame(notebook, style="Panel.TFrame", padding=(8, 8, 8, 8))
            box = self._text(tab, 18)
            box.pack(fill="both", expand=True)
            box.insert("1.0", self.task_empty_text(title))
            self.task_result_tabs[key] = box
            notebook.add(tab, text=title)

        bottom = ttk.Frame(view, style="Workspace.TFrame")
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bottom.grid_columnconfigure(0, weight=1)
        ttk.Entry(bottom, textvariable=self.task_followup).grid(row=0, column=0, sticky="ew", ipady=6)
        ttk.Button(bottom, text="继续询问 Agent", style="Accent.TButton", command=self.send_task_followup).grid(row=0, column=1, sticky="e", padx=(8, 0))

    def task_empty_text(self, title: str) -> str:
        return (
            f"{title}\n\n"
            "当前任务还没有生成这一类结果。\n"
            "你可以继续和 Agent 对话，或运行左侧对应模块来生成真实数据。"
        )

    def fill_command_chip(self, value: str) -> None:
        self.open_chat_with_message(CAPABILITY_PROMPTS.get(value, f"请帮我进行{value}。"))

    def show_aura_toast(self, message: str) -> None:
        toast = getattr(self, "aura_toast", None)
        if toast is None:
            return
        toast.configure(text=message)
        toast.place(relx=0.5, rely=1.0, anchor="s", y=-28)
        if getattr(self, "aura_toast_after", ""):
            try:
                self.root.after_cancel(self.aura_toast_after)
            except Exception:
                pass
        self.aura_toast_after = self.root.after(1600, toast.place_forget)

    def home_upload_file(self) -> None:
        self.set_project_var(self.agent_project, self.default_project_id())
        self.show_view("agent")
        self.chat_upload_file()

    def home_upload_data_file(self) -> None:
        self.set_project_var(self.data_project, self.default_project_id())
        if self.quick_data_upload():
            self.show_aura_toast("数据文件已交给资料库解析，可继续向 AURA 提问")

    def normalize_intent_guard_text(self, message: str) -> str:
        text = clean(message).lower()
        text = re.sub(r"[\s,，。.!！?？、;；:：]+", "", text)
        return text

    def is_smalltalk_message(self, message: str) -> bool:
        text = self.normalize_intent_guard_text(message)
        if not text:
            return True
        smalltalk = {self.normalize_intent_guard_text(item) for item in SMALLTALK_MESSAGES}
        return text in smalltalk

    def has_explicit_task_verb(self, message: str) -> bool:
        text = self.normalize_intent_guard_text(message)
        return any(self.normalize_intent_guard_text(verb) in text for verb in TASK_VERBS)

    def should_try_dual_agent_route(self, message: str) -> bool:
        return False

    def open_chat_with_message(self, message: str) -> None:
        message = clean(message)
        if not message:
            return
        self.set_project_var(self.agent_project, self.default_project_id())
        self.show_view("agent")
        if hasattr(self, "agent_message"):
            self.agent_message.delete("1.0", tk.END)
            self.agent_message.insert("1.0", message)
            self.send_agent_message()

    def build_local_task_plan(self, keywords: str) -> str:
        return (
            f"科研任务：{keywords}\n\n"
            "任务已创建，当前不会等待大模型返回才继续。\n\n"
            "建议执行顺序：\n"
            "1. 文献采集：用关键词检索 PubMed/PMC、EuropePMC、Crossref、OpenAlex，并下载可公开访问全文。\n"
            "2. 知识库整理：将已下载 PDF / HTML / XML 解析为本地 KB 和证据片段。\n"
            "3. 证据抽取：整理研究对象、实验模型、处理条件、检测指标和关键结论。\n"
            "4. 实验转化：根据证据生成实验分组、Protocol 草案和下一步验证建议。\n"
            "5. 项目记忆：人工确认后写入项目记忆，避免把未证实结论当成事实。\n\n"
            "下一步：点击左侧“运行文献采集”，或在底部继续询问 Agent。"
        )

    def reset_task_workspace(self, keywords: str) -> None:
        self.task_title_text.set(f"科研任务：{keywords}")
        self.task_status.set("正在创建任务计划")
        self.task_harvest_started = False
        self.task_literature_task_id = ""
        for key in self.task_step_state:
            self.update_task_step(key, "pending")
        for key, var in self.task_outcome_vars.items():
            var.set("0" if key in {"papers", "pdfs", "evidence", "tables", "memory", "suggestions"} else "waiting")
        for key, box in self.task_result_tabs.items():
            box.delete("1.0", tk.END)
            box.insert("1.0", self.task_empty_text(key))

    def update_task_step(self, key: str, state: str) -> None:
        self.task_step_state[key] = state
        label = getattr(self, "task_step_labels", {}).get(key)
        if not label:
            return
        mapping = {
            "pending": ("o", TEXT_3),
            "running": ("*", WARN),
            "completed": ("*", ACCENT),
            "failed": ("!", BAD),
        }
        text, color = mapping.get(state, mapping["pending"])
        label.configure(text=text, fg=color)

    def set_task_tab(self, key: str, text: str) -> None:
        box = self.task_result_tabs.get(key)
        if not box:
            return
        box.delete("1.0", tk.END)
        box.insert("1.0", text.strip() or self.task_empty_text(key))

    def clear_global_command_placeholder(self, _event=None) -> None:
        if not hasattr(self, "global_command"):
            return
        if self.global_command.get() == getattr(self, "global_command_placeholder", ""):
            self.global_command.delete(0, tk.END)
            self.global_command.configure(fg=TEXT_1)

    def restore_global_command_placeholder(self, _event=None) -> None:
        if not hasattr(self, "global_command"):
            return
        if not self.global_command.get().strip():
            self.global_command.insert(0, getattr(self, "global_command_placeholder", ""))
            self.global_command.configure(fg=TEXT_3)

    def run_global_command(self, _event=None) -> str:
        value = clean(self.global_command.get() if hasattr(self, "global_command") else "")
        if not value or value == getattr(self, "global_command_placeholder", ""):
            self.show_aura_toast("先输入一个科研命令")
            return "break"
        self.open_chat_with_message(value)
        if hasattr(self, "global_command"):
            self.global_command.delete(0, tk.END)
            self.restore_global_command_placeholder()
        return "break"

    def start_command_task(self) -> None:
        message = clean(self.command_text.get())
        if not message:
            self._show_error("请输入想问 AURA 的内容。")
            return
        self.command_text.set("")
        self.open_chat_with_message(message)

    def count_suggestions(self, text: str) -> int:
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        candidates = [line for line in lines if "建议" in line or "下一" in line or line.startswith(("-", "1.", "2.", "3.", "4.", "5."))]
        return min(len(candidates), 9)

    def format_sources_for_task(self, body: dict) -> str:
        sources = body.get("sources") or body.get("retrieved_chunks") or []
        if not sources:
            return "资料库来源\n\n当前回答没有返回资料库来源。你可以在“资料库”添加文献、构建知识库，或继续询问 AURA。"
        lines = ["资料库来源", ""]
        for index, item in enumerate(sources[:20], start=1):
            if isinstance(item, dict):
                title = clean(item.get("title") or item.get("source") or item.get("file") or item.get("id"))
                snippet = clean(item.get("snippet") or item.get("text") or item.get("content"))
                lines.append(f"{index}. {title}")
                if snippet:
                    lines.append(f"   {snippet[:260]}")
            else:
                lines.append(f"{index}. {clean(item)}")
        return "\n".join(lines)

    def format_memory_for_task(self, body: dict) -> str:
        memories = body.get("memory_used") or body.get("memory") or []
        if not memories:
            return "项目记忆\n\n当前任务还没有返回项目记忆。你可以在“工作区”查看已有记忆，或继续让 AURA 整理项目背景。"
        lines = ["本次使用的项目记忆", ""]
        for index, item in enumerate(memories[:20], start=1):
            if isinstance(item, dict):
                title = clean(item.get("title") or item.get("memory_type") or item.get("entity_type") or item.get("id"))
                content = clean(item.get("content") or item.get("summary") or item.get("text"))
                lines.append(f"{index}. {title}")
                if content:
                    lines.append(f"   {content[:260]}")
            else:
                lines.append(f"{index}. {clean(item)}")
        return "\n".join(lines)

    def start_task_literature_harvest(self) -> None:
        if self.task_harvest_started and self.active_lit_polling:
            self.task_status.set("文献采集已经在运行。")
            return
        self.task_harvest_started = True
        self.lit_use_agent.set(False)
        keywords = self.task_keywords.get() or self.command_text.get()
        if keywords:
            self.lit_keywords.set(keywords)
        if self.task_project.get():
            self.lit_project.set(self.task_project.get())
        self.update_task_step("search", "running")
        self.task_status.set("正在启动文献采集。下载进度会同步到任务工作区和文献模块。")
        self.run_literature_harvest()

    def send_task_followup(self) -> None:
        message = clean(self.task_followup.get())
        if not message:
            self._show_error("请输入要继续询问 Agent 的内容。")
            return
        self.task_followup.set("")
        project_id = self.current_project_id(self.task_project) or self.default_project_id()
        self.task_status.set("正在继续询问 AURA")

        def task():
            status, body = self.api.post("/research-os/agent/chat", {"project_id": project_id, "message": message}, timeout=120)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.task_status.set("AURA 已回复")
            self.set_task_tab("overview", self.format_user_answer(body))
            self.set_task_tab("kb", self.format_sources_for_task(body))
            self.set_task_tab("memory", self.format_memory_for_task(body))
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def _build_functions(self) -> None:
        view = self._view("functions", "开发者控制台", "高级工具仅在开发者模式中显示。")
        view.grid_columnconfigure((0, 1, 2), weight=1)
        actions = [
            ("文献采集调试", "调用文献采集能力检索并下载开放全文。", lambda: self.show_view("literature")),
            ("添加文献", "登记本地 PDF 并触发解析。", self.quick_pdf_import),
            ("实验记录", "粘贴自然语言实验记录并提取结构化信息。", lambda: self.show_view("experiments")),
            ("分析数据", "上传或选择数据文件并运行解析接口。", lambda: self.show_view("data")),
            ("问资料库", "检索文献、知识库和项目记忆。", lambda: self.show_view("knowledge")),
            ("写作辅助", "基于项目记忆和资料库生成写作草稿。", self.run_writing_assistant),
            ("生成周报", "运行周报或项目摘要能力。", self.run_weekly_report),
            ("找研究缺口", "检查当前项目的研究缺口。", self.run_gap_analysis),
            ("核查证据冲突", "检查结论与证据是否冲突。", self.run_conflict_detection),
            ("整理项目记忆", "构建上下文并整理项目记忆摘要。", self.organize_project_memory),
            ("问 AURA", "回到主聊天入口。", lambda: self.show_view("agent")),
            ("研究动态", "查看主动建议、文献请求和缺口提醒。", lambda: self.show_view("feed")),
        ]
        for index, (title, desc, command) in enumerate(actions):
            card = tk.Frame(view, bg=BG_SURFACE, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=8)
            tk.Label(card, text=title, bg=BG_SURFACE, fg=TEXT_1, font=("Microsoft YaHei UI", 13)).pack(anchor="w", padx=14, pady=(14, 5))
            tk.Label(card, text=desc, bg=BG_SURFACE, fg=TEXT_2, font=("Microsoft YaHei UI", 10), wraplength=280, justify="left").pack(anchor="w", padx=14)
            tk.Button(card, text="进入", command=command, bg=BG_ELEVATED, fg=TEXT_1, activebackground=BG_HOVER, activeforeground=TEXT_1, relief="flat", bd=0, padx=12, pady=8, cursor="hand2").pack(anchor="w", padx=14, pady=14)

    def _build_literature(self) -> None:
        view = self._view("literature", "文献采集调试", "用反斜杠分隔关键词；下载结果会逐篇显示。")
        view.grid_columnconfigure(0, weight=2)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(1, weight=1)
        controls = self._panel(view, "采集参数", "全部来源会使用 PubMed/PMC、EuropePMC、Crossref 和 OpenAlex。")
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 10))
        self.lit_project_box = self._combo(controls, "项目", self.lit_project)
        self._entry(controls, "Keywords separated by backslash", self.lit_keywords)
        self.lit_provider_box = self._combo(controls, "Provider", self.lit_provider, ["all", "pubmed", "openalex", "crossref", "europepmc"])
        self._entry(controls, "Limit per provider per keyword, blank means long run", self.lit_max_results)
        tk.Checkbutton(controls, text="Use Agent to expand query first", variable=self.lit_use_agent, bg=BG_SURFACE, fg=TEXT_2, activebackground=BG_SURFACE, activeforeground=TEXT_1, selectcolor=BG_INPUT, relief="flat", anchor="w", cursor="hand2").pack(fill="x", pady=(0, 10))
        row = ttk.Frame(controls, style="Panel.TFrame")
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="停止", style="Secondary.TButton", command=self.stop_literature_harvest).pack(side="right", padx=(8, 0))
        ttk.Button(row, text="开始采集", style="Accent.TButton", command=self.run_literature_harvest).pack(side="left")
        ttk.Button(row, text="刷新", style="Secondary.TButton", command=self.load_literature_tasks).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="打开目录", style="Secondary.TButton", command=self.open_literature_run_dir).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="打开 PDF 目录", style="Secondary.TButton", command=self.open_literature_pdf_dir).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="隐藏任务", style="Secondary.TButton", command=self.hide_selected_literature_task).pack(side="left", padx=(8, 0))
        tasks = self._panel(view, "采集任务", "任务状态来自后端进度。")
        tasks.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.lit_task_tree = ttk.Treeview(tasks, columns=("query", "provider", "status"), show="headings")
        for key, label, width in [("query", "Query", 250), ("provider", "Provider", 90), ("status", "Status", 90)]:
            self.lit_task_tree.heading(key, text=label)
            self.lit_task_tree.column(key, width=width, anchor="w")
        self.lit_task_tree.pack(fill="both", expand=True)
        self.lit_task_tree.bind("<<TreeviewSelect>>", self.on_literature_task_selected)
        progress = self._panel(view, "Download Progress", "Each successful download appears here.")
        progress.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        self.lit_progress_box = self._text(progress, 9)
        self.lit_progress_box.pack(fill="x", pady=(0, 10))
        self.lit_download_tree = ttk.Treeview(progress, columns=("title", "file", "format", "time"), show="headings")
        for key, label, width in [("title", "Literature", 330), ("file", "File", 240), ("format", "Format", 70), ("time", "Time", 140)]:
            self.lit_download_tree.heading(key, text=label)
            self.lit_download_tree.column(key, width=width, anchor="w")
        self.lit_download_tree.pack(fill="both", expand=True)
        self.lit_download_tree.bind("<Double-1>", self.open_selected_literature_pdf)
        ttk.Button(progress, text="打开选中文献 PDF", style="Accent.TButton", command=self.open_selected_literature_pdf).pack(fill="x", pady=(10, 0))

    def _build_projects(self) -> None:
        view = self._view("projects", "项目 / 文件", "项目名称由用户自定义；内部 ID 只在后端保存。")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "项目列表", "先创建或选择一个项目，后续文献、实验、记忆都会写入这个项目。")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.project_tree = ttk.Treeview(left, columns=("title", "area", "status"), show="headings")
        for key, label, width in [("title", "项目名", 260), ("area", "方向", 220), ("status", "状态", 90)]:
            self.project_tree.heading(key, text=label)
            self.project_tree.column(key, width=width, anchor="w")
        self.project_tree.pack(fill="both", expand=True)
        self.project_tree.bind("<<TreeviewSelect>>", self.on_project_selected)
        actions = ttk.Frame(left, style="Panel.TFrame")
        actions.pack(anchor="w", pady=(10, 0))
        ttk.Button(actions, text="归档", style="Secondary.TButton", command=self.hide_selected_project).pack(side="left")
        ttk.Button(actions, text="取消归档", style="Secondary.TButton", command=self.unarchive_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="清空项目", style="Secondary.TButton", command=self.clear_workspace_project).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="彻底删除", style="Secondary.TButton", command=self.delete_workspace_project).pack(side="left", padx=(8, 0))
        right = self._panel(view, "新建 / 修改项目", "用户只需要看到项目名，系统会在后台维护稳定 ID。")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.new_project_title = tk.StringVar()
        self.new_project_area = tk.StringVar()
        self.new_project_owner = tk.StringVar(value="local_user")
        self._entry(right, "项目名称", self.new_project_title)
        self._entry(right, "研究方向", self.new_project_area)
        self._entry(right, "负责人", self.new_project_owner)
        ttk.Button(right, text="创建项目", style="Accent.TButton", command=self.create_project).pack(fill="x", pady=(0, 8))
        ttk.Button(right, text="用上方名称重命名当前项目", style="Secondary.TButton", command=self.rename_current_project).pack(fill="x", pady=(0, 12))
        self.file_project_box = self._combo(right, "文件所属项目", self.file_project)
        self.file_path_text = tk.StringVar()
        self._entry(right, "Local File Path", self.file_path_text)
        ttk.Button(right, text="Choose File", style="Secondary.TButton", command=self.choose_file).pack(fill="x", pady=(0, 8))
        ttk.Button(right, text="Register and Extract", style="Accent.TButton", command=self.register_selected_file).pack(fill="x")

    def _build_data(self) -> None:
        view = self._view("data", "Data", "Search experiments, samples, files; save conclusions, failures, and decisions.")
        view.grid_columnconfigure(0, weight=2)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Data Actions", "Upload files, search objects, and save research records.")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.data_project_box = self._combo(left, "项目", self.data_project)
        self._entry(left, "Search", self.data_search)
        action_row = ttk.Frame(left, style="Panel.TFrame")
        action_row.pack(fill="x", pady=(0, 10))
        ttk.Button(action_row, text="Search", style="Accent.TButton", command=self.search_data_objects).pack(side="left")
        ttk.Button(action_row, text="Upload Data File", style="Secondary.TButton", command=self.quick_data_upload).pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text="New Experiment", style="Secondary.TButton", command=lambda: self.show_view("experiments")).pack(side="left", padx=(8, 0))
        ttk.Label(left, text="Conclusion", style="PanelMuted.TLabel").pack(anchor="w", pady=(8, 4))
        ttk.Entry(left, textvariable=self.conclusion_text).pack(fill="x", pady=(0, 8))
        ttk.Button(left, text="Save Conclusion", style="Secondary.TButton", command=self.save_conclusion).pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="Failure", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Entry(left, textvariable=self.failure_text).pack(fill="x", pady=(0, 8))
        ttk.Button(left, text="Save Failure", style="Secondary.TButton", command=self.save_failure).pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="Decision", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Entry(left, textvariable=self.decision_text).pack(fill="x", pady=(0, 8))
        ttk.Button(left, text="Save Decision", style="Secondary.TButton", command=self.save_decision).pack(fill="x")
        right = self._panel(view, "Results / Detail", "Results appear here.")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.data_result = self._text(right, 25)
        self.data_result.pack(fill="both", expand=True)

    def _build_experiments(self) -> None:
        view = self._view("experiments", "Experiments", "Create structured experiment records or extract from text logs.")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Experiment List")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        top = ttk.Frame(left, style="Panel.TFrame")
        top.pack(fill="x", pady=(0, 8))
        self.exp_project_box = self._combo(top, "项目", self.exp_project)
        ttk.Button(top, text="Load Experiments", style="Secondary.TButton", command=self.load_experiments).pack(anchor="w")
        self.exp_tree = ttk.Treeview(left, columns=("title", "type", "date", "status"), show="headings")
        for key, label, width in [("title", "Title", 260), ("type", "Type", 120), ("date", "Date", 110), ("status", "Status", 90)]:
            self.exp_tree.heading(key, text=label)
            self.exp_tree.column(key, width=width, anchor="w")
        self.exp_tree.pack(fill="both", expand=True)
        self.exp_tree.bind("<<TreeviewSelect>>", self.show_experiment_detail)
        right = self._panel(view, "Create / Extract")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.exp_title = tk.StringVar()
        self.exp_type = tk.StringVar(value="experiment")
        self.exp_date = tk.StringVar()
        self.exp_operator = tk.StringVar(value="local_user")
        self._entry(right, "Experiment Title", self.exp_title)
        self._entry(right, "Experiment Type", self.exp_type)
        self._entry(right, "Date", self.exp_date)
        self._entry(right, "Operator", self.exp_operator)
        self.exp_text = self._text(right, 9)
        self.exp_text.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Button(right, text="Create Experiment", style="Accent.TButton", command=self.create_experiment).pack(fill="x", pady=(0, 8))
        ttk.Button(right, text="Extract Experiment Memory", style="Secondary.TButton", command=self.extract_experiment_memory).pack(fill="x")

    def _build_samples(self) -> None:
        view = self._view("samples", "Samples", "Sample IDs, batches, and status.")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Sample List")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.sample_project_box = self._combo(left, "项目", self.sample_project)
        ttk.Button(left, text="Load Samples", style="Secondary.TButton", command=self.load_samples).pack(anchor="w", pady=(0, 8))
        self.sample_tree = ttk.Treeview(left, columns=("code", "type", "batch", "status"), show="headings")
        for key, label, width in [("code", "Code", 170), ("type", "Type", 120), ("batch", "Batch", 110), ("status", "Status", 90)]:
            self.sample_tree.heading(key, text=label)
            self.sample_tree.column(key, width=width, anchor="w")
        self.sample_tree.pack(fill="both", expand=True)
        right = self._panel(view, "New Sample")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.sample_code = tk.StringVar()
        self.sample_type = tk.StringVar()
        self.sample_batch = tk.StringVar()
        self.sample_status = tk.StringVar(value="active")
        self._entry(right, "Sample Code", self.sample_code)
        self._entry(right, "Sample Type", self.sample_type)
        self._entry(right, "Batch", self.sample_batch)
        self._entry(right, "Status", self.sample_status)
        ttk.Button(right, text="Create Sample", style="Accent.TButton", command=self.create_sample).pack(fill="x")

    def _build_knowledge(self) -> None:
        view = self._view("knowledge", "知识库调试", "文献、资料库和检索调试。")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "References / PDF", "Import PDFs, run literature harvest, and build KB.")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.rag_project_box = self._combo(left, "项目", self.rag_project)
        row = ttk.Frame(left, style="Panel.TFrame")
        row.pack(fill="x", pady=(0, 8))
        ttk.Button(row, text="Import PDF", style="Secondary.TButton", command=self.quick_pdf_import).pack(side="left")
        ttk.Button(row, text="Literature Harvest", style="Secondary.TButton", command=lambda: self.show_view("literature")).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Build KB", style="Accent.TButton", command=self.build_kb).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Reparse PDF", style="Secondary.TButton", command=self.reparse_selected_reference).pack(side="left", padx=(8, 0))
        self.reference_tree = ttk.Treeview(left, columns=("title", "provider", "status"), show="headings")
        for key, label, width in [("title", "Title", 360), ("provider", "Source", 120), ("status", "Status", 100)]:
            self.reference_tree.heading(key, text=label)
            self.reference_tree.column(key, width=width, anchor="w")
        self.reference_tree.pack(fill="both", expand=True)
        self.reference_tree.bind("<<TreeviewSelect>>", self.show_reference_detail)
        ref_actions = ttk.Frame(left, style="Panel.TFrame")
        ref_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(ref_actions, text="Load References", style="Secondary.TButton", command=self.load_references).pack(side="left")
        ttk.Button(ref_actions, text="Hide Selected", style="Secondary.TButton", command=self.hide_selected_reference).pack(side="left", padx=(8, 0))
        right = self._panel(view, "KB Question")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.rag_question = self._text(right, 5)
        self.rag_question.pack(fill="x", pady=(0, 10))
        ttk.Button(right, text="Query KB", style="Accent.TButton", command=self.query_rag).pack(fill="x", pady=(0, 10))
        self.rag_answer = self._text(right, 15)
        self.rag_answer.pack(fill="both", expand=True)

    def _build_agent(self) -> None:
        view = self._view("agent", "问 AURA", "像聊天一样提出问题；需要启动任务时，AURA 会先说明并等待确认或返回任务卡片。")
        view.grid_columnconfigure(0, weight=5)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)

        chat = tk.Frame(view, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=16)
        chat.grid(row=0, column=0, sticky="nsew", padx=(26, 10), pady=(14, 24))
        chat.grid_columnconfigure(0, weight=1)
        chat.grid_rowconfigure(2, weight=1)

        top = tk.Frame(chat, bg=BG_SURFACE)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(2, weight=1)
        tk.Label(top, text="AURA Agent", bg=BG_SURFACE, fg=TEXT_1, font=(FONT_UI, 15, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(top, text="项目", bg=BG_SURFACE, fg=TEXT_3, font=(FONT_UI, 9)).grid(row=0, column=1, sticky="w", padx=(18, 8))
        self.agent_project_box = ttk.Combobox(top, textvariable=self.agent_project, values=[], state="readonly", width=28)
        self.agent_project_box.grid(row=0, column=2, sticky="w")
        self._action_button(top, "上下文", self.toggle_agent_context_panel).grid(row=0, column=3, sticky="e", padx=(8, 0))
        self._action_button(top, "清空", self.clear_agent_chat).grid(row=0, column=4, sticky="e", padx=(8, 0))

        shortcut = tk.Frame(chat, bg=BG_SURFACE)
        shortcut.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        shortcut_prompts = [
            ("采文献", "请围绕当前项目关键词采集开放文献，并整理证据链。"),
            ("设计实验", "请根据当前项目设计下一步实验方案。"),
            ("查资料库", "请检索当前项目资料库并总结可用证据。"),
            ("写进展", "请根据当前项目记忆生成科研进展汇报。"),
        ]
        for label, prompt in shortcut_prompts:
            self._action_button(shortcut, label, lambda value=prompt: self.insert_agent_prompt(value)).pack(side="left", padx=(0, 8))

        self.agent_transcript = self._reading_text(chat, 21)
        self.agent_transcript.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self.agent_transcript.insert("1.0", "AURA 已准备好。\n\n你可以直接打招呼、提问，或让 AURA 帮你采集文献、分析数据、整理实验记录。\n\n")

        self.agent_inline_actions = tk.Frame(chat, bg=BG_SURFACE)
        self.agent_inline_actions.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        composer = tk.Frame(chat, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1, padx=10, pady=10)
        composer.grid(row=4, column=0, sticky="ew")
        composer.grid_columnconfigure(0, weight=1)
        self.agent_message = self._reading_text(composer, 4)
        self.agent_message.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.agent_message.bind("<Control-Return>", lambda _event: self.send_agent_message())
        self._action_button(composer, "上传", self.chat_upload_file).grid(row=0, column=1, sticky="se", padx=(0, 8))
        self._action_button(composer, "发送", self.send_agent_message, kind="primary").grid(row=0, column=2, sticky="se")

        right = tk.Frame(view, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=16)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 26), pady=(14, 24))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)
        tk.Label(right, text="上下文", bg=BG_SURFACE, fg=TEXT_1, anchor="w", font=(FONT_UI, 13, "bold")).grid(row=0, column=0, sticky="ew")
        tk.Label(right, text="本次回答使用的来源、任务和项目摘要。", bg=BG_SURFACE, fg=TEXT_3, anchor="w", justify="left", wraplength=320, font=(FONT_UI, 9)).grid(row=1, column=0, sticky="ew", pady=(2, 12))
        self.agent_context_panel = right
        self.agent_actions_frame = tk.Frame(right, bg=BG_SURFACE)
        self.agent_actions_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        context_state = tk.Frame(right, bg=BG_SURFACE)
        context_state.grid(row=3, column=0, sticky="new", pady=(0, 10))
        self.agent_workspace_label = tk.Label(context_state, text="项目：未选择", bg=BG_ELEVATED, fg=TEXT_2, anchor="w", padx=12, pady=8, font=(FONT_UI, 9))
        self.agent_workspace_label.pack(fill="x", pady=(0, 6))
        self.agent_evidence_label = tk.Label(context_state, text="资料：等待检索", bg=BG_ELEVATED, fg=TEXT_2, anchor="w", padx=12, pady=8, font=(FONT_UI, 9))
        self.agent_evidence_label.pack(fill="x", pady=(0, 6))
        self.agent_task_label = tk.Label(context_state, text="任务：暂无", bg=BG_ELEVATED, fg=TEXT_2, anchor="w", padx=12, pady=8, font=(FONT_UI, 9))
        self.agent_task_label.pack(fill="x")
        self.agent_detail = self._reading_text(right, 18)
        self.agent_detail.grid(row=4, column=0, sticky="nsew")
        self.agent_answer = self.agent_detail
        self.agent_context_panel.grid_remove()

    def insert_agent_prompt(self, text: str) -> None:
        if not hasattr(self, "agent_message"):
            return
        self.agent_message.delete("1.0", tk.END)
        self.agent_message.insert("1.0", text)
        self.agent_message.focus_set()

    def _build_research_feed(self) -> None:
        view = self._view("feed", "Research Feed", "Agent 主动观察当前项目后的建议、缺口和待处理文献。")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(1, weight=1)

        top = self._panel(view, "Agent Inbox", "不把主动建议塞进聊天框；这里集中处理文献提醒、缺口提示和下一步动作。")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        actions = ttk.Frame(top, style="Panel.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="扫描当前项目", style="Accent.TButton", command=self.run_research_watcher).pack(side="left")
        ttk.Button(actions, text="Agent Heartbeat", style="Secondary.TButton", command=self.run_agent_heartbeat).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="运行调度+联网 Scout", style="Secondary.TButton", command=self.run_scheduler_once).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="调度状态", style="Secondary.TButton", command=self.load_scheduler_status).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="刷新 Feed", style="Secondary.TButton", command=self.load_agent_inbox).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="标记已读", style="Secondary.TButton", command=lambda: self.update_selected_feed_item("read")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="忽略", style="Secondary.TButton", command=lambda: self.update_selected_feed_item("ignored")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="运行选中任务", style="Secondary.TButton", command=self.run_selected_agent_task).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="取消选中任务", style="Secondary.TButton", command=self.cancel_selected_agent_task).pack(side="right", padx=(8, 0))

        left = self._panel(view, "Suggestions")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left_body = ttk.Frame(left, style="Panel.TFrame")
        left_body.pack(fill="both", expand=True)
        left_body.grid_rowconfigure(0, weight=2)
        left_body.grid_rowconfigure(2, weight=1)
        left_body.grid_columnconfigure(0, weight=1)
        self.feed_tree = ttk.Treeview(left_body, columns=("type", "priority", "status", "title"), show="headings", height=12)
        for column, label, width in [("type", "类型", 120), ("priority", "优先级", 90), ("status", "状态", 90), ("title", "标题", 520)]:
            self.feed_tree.heading(column, text=label)
            self.feed_tree.column(column, width=width, anchor="w")
        self.feed_tree.grid(row=0, column=0, sticky="nsew")
        self.feed_tree.bind("<<TreeviewSelect>>", self.on_feed_selected)
        ttk.Label(left_body, text="Agent Task Queue", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 4))
        self.agent_task_tree = ttk.Treeview(left_body, columns=("type", "status", "priority", "next"), show="headings", height=7)
        for column, label, width in [("type", "任务", 150), ("status", "状态", 95), ("priority", "优先级", 80), ("next", "下一步", 440)]:
            self.agent_task_tree.heading(column, text=label)
            self.agent_task_tree.column(column, width=width, anchor="w")
        self.agent_task_tree.grid(row=2, column=0, sticky="nsew")
        self.agent_task_tree.bind("<<TreeviewSelect>>", self.on_agent_task_selected)

        right = self._panel(view, "详情 / 动作")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self.feed_action_frame = tk.Frame(right, bg=BG_SURFACE)
        self.feed_action_frame.pack(fill="x", pady=(0, 10))
        self.feed_detail = self._reading_text(right, 22)
        self.feed_detail.pack(fill="both", expand=True)
        self.feed_detail.insert("1.0", f"点击“扫描当前项目”，{APP_NAME} 会读取 workspace-state、文献、任务、记忆和 KB 状态，生成主动建议。")

    def _build_memory(self) -> None:
        view = self._view("memory", "Memory", "Build Research Memory Context and view Agent Memory.")
        view.grid_columnconfigure(0, weight=2)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Query")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.memory_project_box = self._combo(left, "项目", self.memory_project)
        self.memory_query = self._text(left, 8)
        self.memory_query.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Button(left, text="Build Memory Context", style="Accent.TButton", command=self.build_memory_context).pack(fill="x", pady=(0, 8))
        ttk.Button(left, text="Load Agent Memory", style="Secondary.TButton", command=self.load_agent_memory).pack(fill="x")
        right = self._panel(view, "Memory Context")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.memory_result = self._text(right, 24)
        self.memory_result.pack(fill="both", expand=True)

    def _build_skills(self) -> None:
        view = self._view("skills", "Skills", "Skill Library, pipelines, and run history.")
        view.grid_columnconfigure(0, weight=3)
        view.grid_columnconfigure(1, weight=2)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Skill Library")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ttk.Label(left, text="Runtime Registry").pack(anchor="w", pady=(0, 6))
        self.skill_tree = ttk.Treeview(left, columns=("name", "handler", "status"), show="headings", height=7)
        for key, label, width in [("name", "Skill", 230), ("handler", "Handler", 220), ("status", "Status", 80)]:
            self.skill_tree.heading(key, text=label)
            self.skill_tree.column(key, width=width, anchor="w")
        self.skill_tree.pack(fill="x", expand=False)
        button_row = tk.Frame(left, bg=BG_SURFACE)
        button_row.pack(fill="x", pady=(8, 10))
        ttk.Button(button_row, text="Load Runtime", style="Secondary.TButton", command=self.load_skills).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Load Library", style="Secondary.TButton", command=self.load_skill_library).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Load Pipelines", style="Secondary.TButton", command=self.load_pipeline_registry).pack(side="left")

        ttk.Label(left, text="Canonical Skill Library").pack(anchor="w", pady=(4, 6))
        self.skill_catalog_tree = ttk.Treeview(left, columns=("skill", "category", "status"), show="headings", height=8)
        for key, label, width in [("skill", "Skill", 220), ("category", "Category", 230), ("status", "Status", 90)]:
            self.skill_catalog_tree.heading(key, text=label)
            self.skill_catalog_tree.column(key, width=width, anchor="w")
        self.skill_catalog_tree.pack(fill="x", expand=False)

        ttk.Label(left, text="Research Pipelines").pack(anchor="w", pady=(10, 6))
        self.pipeline_tree = ttk.Treeview(left, columns=("pipeline", "skills", "auth"), show="headings", height=7)
        for key, label, width in [("pipeline", "Pipeline", 220), ("skills", "Execution Skills", 250), ("auth", "Auth", 80)]:
            self.pipeline_tree.heading(key, text=label)
            self.pipeline_tree.column(key, width=width, anchor="w")
        self.pipeline_tree.pack(fill="both", expand=True)

        right = self._panel(view, "运行能力")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.skill_project_box = self._combo(right, "项目", self.skill_project)
        self.skill_payload = self._text(right, 9)
        self.skill_payload.pack(fill="x", pady=(0, 10))
        self.skill_payload.insert("1.0", '{\n  "project_id": "",\n  "query": "generate weekly project report"\n}')
        ttk.Button(right, text="运行所选能力", style="Accent.TButton", command=self.run_selected_skill).pack(fill="x", pady=(0, 10))
        ttk.Button(right, text="测试路由", style="Secondary.TButton", command=self.route_skill_query).pack(fill="x", pady=(0, 10))
        self.skill_run_box = self._text(right, 14)
        self.skill_run_box.pack(fill="both", expand=True)

    def _build_api_console(self) -> None:
        view = self._view("api", "API Console", "Local debug only. Hidden from the customer demo path.")
        view.grid_columnconfigure(0, weight=2)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(0, weight=1)
        left = self._panel(view, "Request")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._combo(left, "Method", self.api_method, ["GET", "POST"])
        self._entry(left, "Path", self.api_path)
        self.api_payload = self._text(left, 13)
        self.api_payload.pack(fill="both", expand=True, pady=(0, 10))
        self.api_payload.insert("1.0", "{}")
        ttk.Button(left, text="Send Request", style="Accent.TButton", command=self.send_api_request).pack(fill="x")
        right = self._panel(view, "Response")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.api_response = self._text(right, 25)
        self.api_response.pack(fill="both", expand=True)

    def show_view(self, key: str) -> None:
        aura_home_allowed = {item[0] for item in USER_NAV} | {"data", "knowledge"}
        if not self.developer_mode.get() and key not in aura_home_allowed:
            key = "settings"
        for name, frame in self.views.items():
            frame.grid() if name == key else frame.grid_remove()
        for name, button in self.nav_buttons.items():
            if name == key:
                button.configure(bg=BG_SURFACE, fg=TEXT_1)
            else:
                button.configure(bg=BG_DEEP, fg=TEXT_2)
        self.active_view = key
        self.client_cache["active_user_tab"] = key
        self.save_client_cache()
        frame = self.views[key]
        self.workspace_title.set(getattr(frame, "_view_title"))
        self.workspace_subtitle.set(getattr(frame, "_view_subtitle"))
        if hasattr(self, "shell_title_block"):
            if key == "overview":
                self.shell_title_block.grid_remove()
            else:
                self.shell_title_block.grid()
        if key == "feed":
            self.load_agent_inbox()
        if key == "workspace_user":
            self.load_workspace_summary()
        if key == "tasks_user":
            self.load_user_tasks_summary()
        if key == "library_user":
            self.load_library_summary()
        if key == "settings":
            self.refresh_health()

    def set_context(self, value: object) -> None:
        self.latest_context = value
        if not hasattr(self, "context_box"):
            return
        self.context_box.configure(state="normal")
        self.context_box.delete("1.0", tk.END)
        self.context_box.insert("1.0", value if isinstance(value, str) else pretty(value))
        self.context_box.configure(state="disabled")

    def run_async(self, func, on_success=None, on_error=None) -> None:
        def worker() -> None:
            try:
                result = func()
                if on_success:
                    self.root.after(0, lambda: on_success(result))
            except Exception as exc:  # noqa: BLE001
                if on_error:
                    message = str(exc)
                    self.root.after(0, lambda message=message: on_error(message))
        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, message: str) -> None:
        self.status_text.set("操作失败")
        shown = message if self.developer_mode.get() else self.format_user_error(message)
        messagebox.showerror(APP_NAME, shown)

    def _log_tail(self, path: Path, limit: int = 5000) -> str:
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        return text[-limit:]

    def _backend_ready(self) -> bool:
        try:
            status, _ = self.api.get("/health", timeout=5)
            return status == 200
        except Exception:
            return False

    def _stop_existing_api_processes(self) -> None:
        script = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -notin @('powershell.exe','pwsh.exe') -and $_.CommandLine -like '*research_agent_api.py*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except Exception:
            pass

    def bootstrap(self) -> None:
        def task() -> str:
            if self._backend_ready():
                return "Local API connected"
            self._stop_existing_api_processes()
            AGENT_ROOT.mkdir(parents=True, exist_ok=True)
            LOG_ROOT.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["RESEARCHOS_AGENT_ROOT"] = str(AGENT_ROOT)
            env["RESEARCHOS_HOST"] = HOST
            env["RESEARCHOS_PORT"] = str(PORT)
            env.setdefault("RESEARCHOS_DUAL_AGENT_API_ENABLED", "true")
            env_file = WORKSPACE_ROOT / ".env"
            if env_file.exists():
                env["RESEARCHOS_ENV_FILE"] = str(env_file)
            api_exe = python_for_api()
            if API_PYTHON_HOME and Path(api_exe).parent != Path(API_PYTHON_HOME):
                env["PYTHONHOME"] = API_PYTHON_HOME
            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            log_handle = API_LOG_PATH.open("a", encoding="utf-8", buffering=1)
            log_handle.write(f"\n--- starting API at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            self.backend_process = subprocess.Popen(
                [api_exe, str(API_SCRIPT), "--agent-root", str(AGENT_ROOT), "--host", HOST, "--port", str(PORT)],
                cwd=str(API_SCRIPT.parent),
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            log_handle.close()
            deadline = time.time() + 30
            while time.time() < deadline:
                if self._backend_ready():
                    return "Local API started"
                if self.backend_process and self.backend_process.poll() is not None:
                    tail = self._log_tail(API_LOG_PATH)
                    raise RuntimeError(f"Local API exited early.\n\n{tail}")
                time.sleep(0.8)
            tail = self._log_tail(API_LOG_PATH)
            raise RuntimeError(f"Local API startup timed out.\n\n{tail}")

        def done(message: str) -> None:
            self.status_dot.itemconfig(self.status_dot_id, fill=ACCENT, outline=ACCENT)
            self.status_text.set(message)
            self.refresh_health()
            self.load_projects()
            self.load_skills()
            self.load_skill_library()
            self.load_pipeline_registry()
            self.load_recent_skill_runs()

        self.run_async(task, done, self._show_error)

    def reconnect_api(self) -> None:
        self.status_text.set("Reconnecting local API")
        self.status_dot.itemconfig(self.status_dot_id, fill=WARN, outline=WARN)
        if self.backend_process and self.backend_process.poll() is None:
            try:
                self.backend_process.terminate()
            except Exception:
                pass
        self.backend_process = None
        self.bootstrap()

    def refresh_health(self) -> None:
        def task():
            health = self.api.get("/health")
            dual = self.api.get("/api/skills/resolver/check", timeout=8)
            return {"health": health, "dual": dual}

        def done(result):
            status, payload = result["health"]
            dual_status, _dual_payload = result["dual"]
            state_db = clean(payload.get("state_db")) if isinstance(payload, dict) else ""
            self.status_text.set("本地科研 Agent 已连接" if status == 200 else "本地服务连接异常")
            self.update_dual_status("本地已连接" if status == 200 else "本地未连接", ACCENT if status == 200 else WARN)
            self.settings_health_status.set("已连接" if status == 200 else "未连接")
            self.settings_dual_status.set("已就绪" if dual_status == 200 else "未启用")
            self.model_status_text.set("模型已就绪" if status == 200 else "模型待配置")
            if hasattr(self, "home_status_line"):
                model_state = "模型就绪" if status == 200 else "模型待配置"
                self.home_status_line.configure(text=f"{'本地已连接' if status == 200 else '本地未连接'} · {model_state}")
            if hasattr(self, "health_box"):
                self.health_box.delete("1.0", tk.END)
                lines = [
                    "AURA 本地服务已连接。" if status == 200 else "AURA 本地服务暂不可用。",
                    f"模型：{self.model_text.get()}",
                    "双 Agent 开发接口：已启用" if dual_status == 200 else "双 Agent 开发接口：未启用",
                ]
                if state_db:
                    lines.append("项目记忆和本地知识库可用。")
                self.health_box.insert("1.0", "\n".join(lines))
            if self.developer_mode.get():
                self.set_context({"status": status, "model": self.model_text.get()})

        self.run_async(task, done, self._show_error)

    def open_data_dir(self) -> None:
        AGENT_ROOT.mkdir(parents=True, exist_ok=True)
        os.startfile(str(AGENT_ROOT))

    def open_backend_log(self) -> None:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        if not API_LOG_PATH.exists():
            API_LOG_PATH.write_text("", encoding="utf-8")
        os.startfile(str(API_LOG_PATH))

    def project_label(self, project: dict) -> str:
        title = clean(project.get("display_name") or project.get("project_name") or project.get("title")) or "未命名项目"
        area = clean(project.get("research_area"))
        if area:
            return f"{title} · {area}"
        return title

    def project_id_from_value(self, value: str) -> str:
        value = clean(value)
        if not value:
            return ""
        if value in self.project_label_to_id:
            return self.project_label_to_id[value]
        if value in self.project_id_to_label:
            return value
        for project in self.project_cache:
            if clean(project.get("title")) == value:
                return clean(project.get("id"))
        return value

    def project_label_from_id(self, project_id: str) -> str:
        project_id = clean(project_id)
        return self.project_id_to_label.get(project_id, project_id)

    def current_project_id(self, var: tk.StringVar) -> str:
        return self.project_id_from_value(var.get())

    def set_project_var(self, var: tk.StringVar, project_id: str) -> None:
        label = self.project_label_from_id(project_id)
        if label:
            var.set(label)

    def forget_project_selection(self, project_id: str) -> None:
        project_id = clean(project_id)
        if not project_id:
            return
        if clean(self.client_cache.get("last_project_id")) == project_id:
            self.client_cache["last_project_id"] = ""
            self.save_client_cache()
        for var_name in [
            "project_choice",
            "lit_project",
            "file_project",
            "data_project",
            "exp_project",
            "sample_project",
            "memory_project",
            "rag_project",
            "skill_project",
            "agent_project",
            "task_project",
        ]:
            if not hasattr(self, var_name):
                continue
            var = getattr(self, var_name)
            if self.current_project_id(var) == project_id:
                var.set("")

    def activate_project(self, project_id: str, *, persist: bool = True) -> None:
        project_id = clean(project_id)
        if not project_id:
            return
        if self.project_id_to_label and project_id not in self.project_id_to_label:
            return
        if self._project_syncing:
            return
        self._project_syncing = True
        try:
            for var in [
                self.project_choice,
                self.lit_project,
                self.file_project,
                self.data_project,
                self.exp_project,
                self.sample_project,
                self.memory_project,
                self.rag_project,
                self.skill_project,
                self.agent_project,
                self.task_project,
            ]:
                self.set_project_var(var, project_id)
            if hasattr(self, "project_tree") and project_id in self.project_tree.get_children():
                current_selection = set(self.project_tree.selection())
                if current_selection != {project_id}:
                    self.project_tree.selection_set(project_id)
                self.project_tree.focus(project_id)
            if persist:
                self.client_cache["last_project_id"] = project_id
                self.save_client_cache()
        finally:
            self._project_syncing = False

    def on_project_selected(self, _event=None) -> None:
        if self._project_syncing:
            return
        project_id = self.selected_project_id(fallback=False)
        if project_id:
            self.activate_project(project_id)
            self.status_text.set(f"当前项目：{self.project_label_from_id(project_id)}")

    def render_projects(self, projects: list[dict], from_cache: bool = False) -> None:
        all_projects = [project for project in projects if clean(project.get("status")) != "purged" and not self.is_client_hidden("hidden_projects", clean(project.get("id")))]
        active_projects = [project for project in all_projects if clean(project.get("status")) != "archived"]
        archived_projects = [project for project in all_projects if clean(project.get("status")) == "archived"]
        visible_projects = active_projects + archived_projects
        self.project_cache = visible_projects
        self.project_label_to_id = {}
        self.project_id_to_label = {}
        labels: list[str] = []
        for project in active_projects:
            base = self.project_label(project)
            label = base
            suffix = 2
            while label in self.project_label_to_id:
                label = f"{base} ({suffix})"
                suffix += 1
            project_id = clean(project.get("id"))
            if project_id:
                self.project_label_to_id[label] = project_id
                self.project_id_to_label[project_id] = label
                labels.append(label)
        if hasattr(self, "project_tree"):
            self.project_tree.delete(*self.project_tree.get_children())
            for project in active_projects + archived_projects:
                status = clean(project.get("status")) or "active"
                title = clean(project.get("display_name") or project.get("title"))
                title = f"[archived] {title}" if status == "archived" else f"[active] {title}"
                self.project_tree.insert("", tk.END, iid=project["id"], values=(title, project.get("research_area"), status))
        for box_name in ["user_project_box", "lit_project_box", "file_project_box", "data_project_box", "exp_project_box", "sample_project_box", "memory_project_box", "rag_project_box", "skill_project_box", "agent_project_box", "task_project_box"]:
            if hasattr(self, box_name):
                getattr(self, box_name)["values"] = labels
        preferred_id = clean(self.client_cache.get("last_project_id"))
        if preferred_id not in self.project_id_to_label:
            preferred_id = clean(active_projects[0].get("id")) if active_projects else ""
            if not preferred_id and clean(self.client_cache.get("last_project_id")):
                self.client_cache["last_project_id"] = ""
                self.save_client_cache()
        for var in [self.project_choice, self.lit_project, self.file_project, self.data_project, self.exp_project, self.sample_project, self.memory_project, self.rag_project, self.skill_project, self.agent_project, self.task_project]:
            if not labels:
                var.set("")
                continue
            current_id = preferred_id if preferred_id else self.project_id_from_value(var.get())
            var.set(self.project_label_from_id(current_id) if current_id in self.project_id_to_label else labels[0])
        if labels:
            self.client_cache["last_project_id"] = self.project_id_from_value(self.project_choice.get()) or self.project_cache[0]["id"]
            self.activate_project(self.client_cache["last_project_id"], persist=False)
        if from_cache:
            self.status_text.set("已加载客户端缓存；连接后会自动刷新")

    def load_projects(self) -> None:
        def task():
            status, payload = self.api.get("/research-os/projects")
            if status == 200:
                return {"projects": payload.get("projects", []), "from_cache": False}
            cached_projects = self.client_cache.get("projects") or []
            if cached_projects:
                return {"projects": cached_projects, "from_cache": True}
            raise RuntimeError(pretty(payload))

        def done(result):
            projects = result.get("projects", [])
            if not result.get("from_cache"):
                self.client_cache["projects"] = projects
                self.save_client_cache()
            self.render_projects(projects, from_cache=bool(result.get("from_cache")))
            if self.active_view == "literature":
                self.load_literature_tasks()
            if hasattr(self, "home_project_summary"):
                project_id = self.default_project_id()
                label = self.project_label_from_id(project_id) if project_id else "未选择项目"
                self.home_project_summary.configure(text=f"当前项目：{label}")
            if self.active_view in {"overview", "workspace_user"}:
                self.load_workspace_summary()

        self.run_async(task, done, self._show_error)

    def create_project(self) -> None:
        payload = {"title": self.new_project_title.get(), "research_area": self.new_project_area.get(), "owner": self.new_project_owner.get(), "status": "active"}

        def task():
            status, body = self.api.post("/research-os/projects", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body["project"]

        def done(project):
            label = self.project_label(project)
            self.status_text.set(f"项目已创建：{label}")
            if self.developer_mode.get():
                self.set_context(project)
            self.client_cache["last_project_id"] = clean(project.get("id"))
            self.save_client_cache()
            self.project_cache = [project] + [item for item in self.project_cache if clean(item.get("id")) != clean(project.get("id"))]
            self.project_id_to_label[clean(project.get("id"))] = label
            self.project_label_to_id[label] = clean(project.get("id"))
            self.activate_project(clean(project.get("id")))
            self.new_project_title.set("")
            self.new_project_area.set("")
            self.load_projects()

        self.run_async(task, done, self._show_error)

    def selected_project_id(self, fallback: bool = True) -> str:
        selected = ""
        if hasattr(self, "project_tree"):
            rows = self.project_tree.selection()
            if rows:
                selected = clean(rows[0])
        if selected in {"active_projects", "archived_projects"}:
            selected = ""
        return selected or (self.default_project_id() if fallback else "")

    def rename_current_project(self) -> None:
        project_id = self.selected_project_id()
        title = clean(self.new_project_title.get())
        area = clean(self.new_project_area.get())
        if not project_id:
            self._show_error("请先选择或创建一个项目。")
            return
        if not title:
            self._show_error("请在“项目名称”里输入新的项目名。")
            return
        payload = {"title": title}
        if area:
            payload["research_area"] = area

        def task():
            status, body = self.api.put(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body["project"]

        def done(project):
            self.status_text.set(f"项目已重命名：{self.project_label(project)}")
            if self.developer_mode.get():
                self.set_context(project)
            self.load_projects()

        self.run_async(task, done, self._show_error)

    def hide_selected_project(self) -> None:
        project_id = self.selected_project_id()
        if not project_id:
            self._show_error("请先选择一个项目。")
            return
        if not messagebox.askyesno("隐藏项目", "从客户端隐藏这个项目？后端会把项目标记为 archived，已下载文件不会被删除。"):
            return
        self.hide_client_item("hidden_projects", project_id)

        def task():
            status, body = self.api.post(f"/research-os/projects/{urllib.parse.quote(project_id, safe='')}/archive", {})
            if status != 200:
                return {"warning": body}
            return body

        def done(body):
            self.status_text.set("项目已从客户端隐藏")
            if self.developer_mode.get():
                self.set_context(body)
            self.load_projects()

        self.run_async(task, done, self._show_error)

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(title="选择科研文件")
        if path:
            self.file_path_text.set(path)

    def register_selected_file(self) -> None:
        project_id = self.current_project_id(self.file_project)
        file_path = Path(self.file_path_text.get())
        if not project_id or not file_path.exists():
            self._show_error("Select a project and a valid local file first.")
            return

        def task():
            content = ""
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = f"Binary or unreadable text file: {file_path.name}"
            status, body = self.api.post("/research-os/files", {"project_id": project_id, "filename": file_path.name, "content": content, "source_path": str(file_path)})
            if status != 200:
                raise RuntimeError(pretty(body))
            file_id = body.get("file", {}).get("id")
            if file_id:
                self.api.post("/research-os/extraction", {"file_id": file_id})
            return body

        def done(body):
            self.status_text.set("文件已登记并提交解析")
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def load_skills(self) -> None:
        def task():
            status, payload = self.api.get("/research-os/skills?include_disabled=1")
            if status != 200:
                raise RuntimeError(pretty(payload))
            return payload.get("skills", [])

        def done(skills):
            self.skill_cache = skills
            if hasattr(self, "skill_tree"):
                self.skill_tree.delete(*self.skill_tree.get_children())
                for skill in skills:
                    self.skill_tree.insert("", tk.END, iid=skill["skill_id"], values=(skill.get("skill_name") or skill.get("skill_id"), skill.get("handler"), skill.get("status")))

        self.run_async(task, done, self._show_error)

    def load_skill_library(self) -> None:
        def task():
            status, payload = self.api.get("/api/skills/catalog", timeout=12)
            if status != 200:
                return {"disabled": True, "payload": payload}
            return payload

        def done(payload):
            if payload.get("disabled"):
                self.skill_run_box.delete("1.0", tk.END)
                self.skill_run_box.insert("1.0", "双 Agent 开发接口未启用。请从 AURA 客户端重启本地服务，或设置 RESEARCHOS_DUAL_AGENT_API_ENABLED=true。")
                return
            skills = payload.get("skills", [])
            if hasattr(self, "skill_catalog_tree"):
                self.skill_catalog_tree.delete(*self.skill_catalog_tree.get_children())
                for row in skills:
                    skill_id = clean(row.get("skill_id") or row.get("name"))
                    category = clean(row.get("category"))
                    status = clean(row.get("status"))
                    if skill_id:
                        self.skill_catalog_tree.insert("", tk.END, iid=skill_id, values=(skill_id, category, status))
            self.status_text.set(f"Loaded {len(skills)} canonical skills")

        self.run_async(task, done, self._show_error)

    def load_pipeline_registry(self) -> None:
        def task():
            status, payload = self.api.get("/api/skills/pipelines", timeout=12)
            if status != 200:
                return {"disabled": True, "payload": payload}
            return payload

        def done(payload):
            if payload.get("disabled"):
                self.skill_run_box.delete("1.0", tk.END)
                self.skill_run_box.insert("1.0", "双 Agent 开发接口未启用。请从 AURA 客户端重启本地服务，或设置 RESEARCHOS_DUAL_AGENT_API_ENABLED=true。")
                return
            pipelines = payload.get("pipelines", [])
            if hasattr(self, "pipeline_tree"):
                self.pipeline_tree.delete(*self.pipeline_tree.get_children())
                for row in pipelines:
                    name = clean(row.get("pipeline_name"))
                    skills = ", ".join(row.get("execution_skills") or [])
                    auth = "required" if row.get("requires_user_authorization") else "auto"
                    if name:
                        self.pipeline_tree.insert("", tk.END, iid=name, values=(name, skills, auth))
            self.status_text.set(f"Loaded {len(pipelines)} research pipelines")

        self.run_async(task, done, self._show_error)

    def route_skill_query(self) -> None:
        try:
            payload = json.loads(self.skill_payload.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as exc:
            self._show_error(f"Invalid JSON: {exc}")
            return
        query = clean(payload.get("user_query") or payload.get("query") or payload.get("message"))
        if not query:
            self._show_error("Add a query field first.")
            return

        def task():
            status, body = self.api.post("/api/skills/route", {"user_query": query}, timeout=15)
            if status != 200:
                return {"disabled": True, "payload": body}
            return body

        def done(body):
            self.skill_run_box.delete("1.0", tk.END)
            if body.get("disabled"):
                self.skill_run_box.insert("1.0", "双 Agent 开发接口未启用。请从 AURA 客户端重启本地服务，或设置 RESEARCHOS_DUAL_AGENT_API_ENABLED=true。")
                return
            pipeline = body.get("pipeline") or {}
            lines = [
                f"Selected pipeline: {pipeline.get('pipeline_name')}",
                f"Intent: {pipeline.get('intent')}",
                f"Execution skills: {', '.join(pipeline.get('execution_skills') or [])}",
                f"Authorization: {'required' if pipeline.get('requires_user_authorization') else 'not required'}",
                "",
                pretty(body),
            ]
            self.skill_run_box.insert("1.0", "\n".join(lines))
            self.status_text.set("Query routed to research pipeline")

        self.run_async(task, done, self._show_error)

    def load_recent_skill_runs(self) -> None:
        def task():
            status, payload = self.api.get("/research-os/skill-runs?limit=50")
            if status != 200:
                raise RuntimeError(pretty(payload))
            return payload.get("skill_runs", [])

        def done(runs):
            if hasattr(self, "recent_runs_tree"):
                self.recent_runs_tree.delete(*self.recent_runs_tree.get_children())
                for run in runs:
                    self.recent_runs_tree.insert("", tk.END, iid=run["id"], values=(run.get("skill_name"), run.get("status"), run.get("updated_at")))

        self.run_async(task, done, lambda _msg: None)

    def _find_skill_id(self, *needles: str) -> str:
        lowered = [needle.lower() for needle in needles]
        for skill in self.skill_cache:
            text = " ".join(str(skill.get(key) or "") for key in ["skill_id", "skill_name", "handler", "source_path"]).lower()
            if all(needle in text for needle in lowered):
                return clean(skill.get("skill_id"))
        return ""

    def _known_project_ids(self) -> list[str]:
        return [clean(project.get("id")) for project in self.project_cache if clean(project.get("id"))]

    def _valid_project_id(self, value: str) -> str:
        project_id = self.project_id_from_value(value)
        known = self._known_project_ids()
        if project_id in known:
            return project_id
        return ""

    def run_literature_harvest(self) -> None:
        project_id = self._valid_project_id(self.lit_project.get())
        raw_keywords = self.lit_keywords.get()
        keywords = [clean(item) for item in re.split(r"[\\/,，、;；\n]+", raw_keywords) if clean(item)]
        if not project_id:
            self._show_error("Please select a project first.")
            return
        if not keywords:
            self._show_error("Please enter keywords separated by backslash.")
            return
        provider = self.lit_provider.get().strip() or "all"
        payload = {"project_id": project_id, "keywords": keywords, "folder_keywords": keywords, "query": ", ".join(keywords), "provider": provider}
        max_results = clean(self.lit_max_results.get())
        if max_results:
            try:
                payload["max_results_per_query"] = max(1, int(max_results))
            except ValueError:
                self._show_error("Limit must be a number.")
                return
        self.lit_progress_box.delete("1.0", tk.END)
        self.lit_progress_box.insert("1.0", "正在提交文献采集任务...\n")
        self.lit_download_tree.delete(*self.lit_download_tree.get_children())
        self.status_text.set("正在提交文献采集任务")

        def task():
            if not self._backend_ready():
                raise RuntimeError(f"本地服务暂时不可用。请确认 AURA 后端已经启动。")
            expansion = None
            if self.lit_use_agent.get():
                expand_status, expansion = self.api.post("/research-os/literature/expand-query", payload, timeout=120)
                if expand_status != 200:
                    raise RuntimeError(pretty(expansion))
                expanded_keywords = expansion.get("expanded_keywords") or []
                expanded_query = clean(expansion.get("query"))
                if expanded_keywords:
                    payload["keywords"] = [clean(item) for item in expanded_keywords if clean(item)]
                if expanded_query:
                    payload["query"] = expanded_query
            skill_id = "core_keyword_research_harvest"
            status, body = self.api.post(f"/research-os/skills/{urllib.parse.quote(skill_id, safe='')}/run", payload, timeout=45)
            if status != 200:
                raise RuntimeError(pretty(body))
            return skill_id, body, expansion

        def done(result):
            skill_id, body, expansion = result
            output = body.get("output") or {}
            search = output.get("literature_search") or {}
            task_obj = search.get("task") or {}
            task_id = clean(task_obj.get("id"))
            self.status_text.set("文献采集已启动，正在下载")
            if self.developer_mode.get():
                self.set_context({"skill_id": skill_id, "skill_run_id": body.get("skill_run_id"), "agent_expansion": expansion, "task": task_obj})
            self.load_literature_tasks()
            if task_id:
                self.active_lit_task_id = task_id
                self.active_lit_polling = True
                self.poll_literature_progress()

        self.run_async(task, done, self._show_error)

    def stop_literature_harvest(self) -> None:
        task_id = self.active_lit_task_id
        if not task_id and hasattr(self, "lit_task_tree"):
            selected = self.lit_task_tree.selection()
            if selected:
                task_id = selected[0]
        if not task_id:
            self._show_error("No selected or active harvest task.")
            return
        self.status_text.set("正在停止文献采集")

        def task():
            status, body = self.api.post(
                f"/research-os/literature/search-tasks/{urllib.parse.quote(task_id, safe='')}/cancel",
                {"reason": "User stopped harvest from local client."},
                timeout=30,
            )
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.active_lit_polling = False
            self.status_text.set("文献采集已停止，已下载文件会保留")
            self.render_literature_progress(body)
            self.load_literature_tasks()
            self.load_recent_skill_runs()

        self.run_async(task, done, self._show_error)

    def load_literature_tasks(self) -> None:
        project_id = self.current_project_id(self.lit_project)
        if not project_id or not hasattr(self, "lit_task_tree"):
            return

        def task():
            path = "/research-os/literature/search-tasks?" + urllib.parse.urlencode({"project_id": project_id, "limit": 50})
            status, payload = self.api.get(path)
            if status == 200:
                return payload.get("literature_search_tasks", [])
            cached = self.client_cache.get(f"literature_tasks:{project_id}") or []
            if cached:
                return cached
            raise RuntimeError(pretty(payload))

        def done(tasks):
            self.lit_task_tree.delete(*self.lit_task_tree.get_children())
            for item in tasks:
                task_id = clean(item.get("id"))
                if self.is_client_hidden("hidden_literature_tasks", task_id):
                    continue
                if task_id:
                    self.lit_task_tree.insert("", tk.END, iid=task_id, values=(item.get("query"), item.get("provider"), item.get("status")))
            if hasattr(self, "library_literature_box") and tasks:
                lines = ["最近文献采集任务", ""]
                for item in tasks[:12]:
                    if self.is_client_hidden("hidden_literature_tasks", clean(item.get("id"))):
                        continue
                    lines.append(f"- {clean(item.get('query'))[:120]} · {clean(item.get('status'))} · {clean(item.get('provider'))}")
                self.library_literature_box.delete("1.0", tk.END)
                self.library_literature_box.insert("1.0", "\n".join(lines) if len(lines) > 2 else "暂无文献采集任务。")
            self.client_cache[f"literature_tasks:{project_id}"] = tasks
            self.save_client_cache()

        self.run_async(task, done, self._show_error)

    def on_literature_task_selected(self, _event=None) -> None:
        selected = self.lit_task_tree.selection()
        if selected:
            self.active_lit_task_id = selected[0]
            self.active_lit_polling = True
            self.poll_literature_progress()

    def hide_selected_literature_task(self) -> None:
        selected = self.lit_task_tree.selection() if hasattr(self, "lit_task_tree") else []
        if not selected:
            self._show_error("请先选择一个文献采集任务。")
            return
        task_id = selected[0]
        if not messagebox.askyesno("隐藏任务", "从客户端隐藏这个文献任务？已下载 PDF 不会删除。"):
            return
        self.hide_client_item("hidden_literature_tasks", task_id)
        self.active_lit_polling = False
        self.load_literature_tasks()
        self.status_text.set("文献任务已从客户端隐藏")

    def poll_literature_progress(self) -> None:
        task_id = self.active_lit_task_id
        if not task_id:
            return

        def task():
            status, payload = self.api.get(f"/research-os/literature/search-tasks/{urllib.parse.quote(task_id, safe='')}/progress", timeout=20)
            if status != 200:
                raise RuntimeError(pretty(payload))
            return payload

        def done(payload):
            self.render_literature_progress(payload)
            task_obj = payload.get("task") or {}
            status = clean(task_obj.get("status"))
            if status not in {"completed", "failed"} and self.active_lit_polling and task_id == self.active_lit_task_id:
                self.root.after(1800, self.poll_literature_progress)
            else:
                self.active_lit_polling = False
                self.load_literature_tasks()
                self.load_recent_skill_runs()

        self.run_async(task, done, self._show_error)

    def render_literature_progress(self, payload: dict) -> None:
        task_obj = payload.get("task") or {}
        progress = payload.get("progress") or {}
        items = progress.get("downloaded_items") or []
        lines = [
            f"任务：{task_obj.get('id')}",
            f"状态：{self.user_status_label(clean(task_obj.get('status')))} | 阶段：{progress.get('phase')}",
            f"候选：{progress.get('candidate_count', 0)} | 已下载：{progress.get('downloaded_count', 0)} | PDF：{progress.get('pdf_count', 0)} | HTML/XML：{progress.get('fulltext_count', 0)}",
            f"入库：已解析 {progress.get('parsed_count', 0)} | 已索引 {progress.get('indexed_count', 0)} | 失败 {progress.get('ingest_failed_count', 0)} | 当前阶段 {progress.get('current_stage', '')}",
            f"下载目录：{progress.get('run_root', '')}",
        ]
        if progress.get("current_title"):
            lines.append(f"当前文献：{progress.get('current_title')}")
        lines.append(f"最终 PDF：{progress.get('final_pdf_count', 0)} | PDF 目录：{progress.get('final_pdf_dir', '')}")
        if progress.get("log_path"):
            lines.append(f"Harvest log: {progress.get('log_path')}")
        if progress.get("error"):
            lines.append(f"Error: {progress.get('error')}")
        log_tail = str(progress.get("log_tail") or "").strip()
        if log_tail:
            lines.extend(["", "Recent log", log_tail[-1200:]])
        self.lit_progress_box.delete("1.0", tk.END)
        self.lit_progress_box.insert("1.0", "\n".join(lines))
        if hasattr(self, "library_literature_box"):
            self.library_literature_box.delete("1.0", tk.END)
            self.library_literature_box.insert("1.0", self.format_literature_assets(task_obj, progress, items))
        self.lit_download_tree.delete(*self.lit_download_tree.get_children())
        self.lit_download_paths = {}
        for index, item in enumerate(items, start=1):
            title = clean(item.get("title"))[:120]
            filename = clean(item.get("filename"))
            fmt = clean(item.get("content_format"))
            ingest = clean(item.get("ingest_status"))
            fmt_text = f"{fmt} / {ingest}" if ingest else fmt
            row_id = str(index)
            self.lit_download_tree.insert("", tk.END, iid=row_id, values=(title, filename, fmt_text, item.get("modified_at")))
            path_value = self.resolve_literature_item_path(item, progress)
            if path_value:
                self.lit_download_paths[row_id] = path_value
        self.latest_literature_progress = progress
        if self.developer_mode.get():
            self.set_context({"literature_progress": progress, "latest_downloads": items[-5:]})
        if hasattr(self, "task_outcome_vars"):
            self.task_outcome_vars.get("papers", tk.StringVar()).set(str(progress.get("candidate_count", 0) or len(items)))
            self.task_outcome_vars.get("pdfs", tk.StringVar()).set(str(progress.get("final_pdf_count", progress.get("pdf_count", 0)) or 0))
            self.task_outcome_vars.get("evidence", tk.StringVar()).set(str(progress.get("indexed_count", 0) or progress.get("parsed_count", 0) or 0))
            if items:
                self.update_task_step("search", "completed")
                self.update_task_step("extract", "completed" if progress.get("indexed_count", 0) else ("running" if progress.get("pdf_count", 0) else "pending"))
            if clean(task_obj.get("status")) == "completed":
                self.update_task_step("extract", "completed")
                self.task_status.set("文献采集已完成。可以继续构建知识库或询问 AURA。")
            elif clean(task_obj.get("status")) == "failed":
                self.update_task_step("search", "failed")
                self.task_status.set("文献采集失败。可以稍后重试，开发者模式可查看日志。")
            self.set_task_tab("literature", self.format_literature_assets(task_obj, progress, items))

    def format_literature_assets(self, task_obj: dict, progress: dict, items: list[dict]) -> str:
        lines = [
            "文献采集结果",
            "",
            f"状态：{self.user_status_label(clean(task_obj.get('status')))} | 阶段：{clean(progress.get('phase')) or '处理中'}",
            f"候选文献：{progress.get('candidate_count', 0)} | PDF：{progress.get('final_pdf_count', progress.get('pdf_count', 0))}",
            f"已解析：{progress.get('parsed_count', 0)} | 已入库：{progress.get('indexed_count', 0)} | 失败：{progress.get('ingest_failed_count', 0)}",
            "",
        ]
        if self.developer_mode.get():
            lines.append(f"目录：{progress.get('final_pdf_dir') or progress.get('run_root') or ''}")
            lines.append("")
        if progress.get("current_title"):
            lines.extend(["正在处理", f"{progress.get('current_stage', '')}: {progress.get('current_title')}", ""])
        if not items:
            lines.append("等待下载结果。成功下载或入库的文献会逐篇显示。")
            return "\n".join(lines)
        for index, item in enumerate(items[-30:], start=1):
            title = clean(item.get("title") or item.get("filename") or "Untitled")
            filename = clean(item.get("filename"))
            fmt = clean(item.get("content_format") or item.get("format"))
            lines.append(f"{index}. {title}")
            if filename or fmt:
                lines.append(f"   {fmt} | {filename}")
        return "\n".join(lines)

    def open_literature_run_dir(self) -> None:
        progress = getattr(self, "latest_literature_progress", {}) or {}
        for key in ("final_pdf_dir", "run_root"):
            path_value = clean(progress.get(key))
            if path_value:
                path = Path(path_value)
                if path.exists():
                    os.startfile(str(path))
                    return
        text = self.lit_progress_box.get("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith("下载目录："):
                path = Path(line.split("：", 1)[1].strip())
                if path.exists():
                    os.startfile(str(path))
                    return
        os.startfile(str(data_literature_root()))

    def open_literature_pdf_dir(self) -> None:
        progress = getattr(self, "latest_literature_progress", {}) or {}
        for key in ("final_pdf_dir", "run_root"):
            path_value = clean(progress.get(key))
            if not path_value:
                continue
            path = Path(path_value)
            if path.exists():
                if path.is_file():
                    path = path.parent
                os.startfile(str(path))
                return
        self.open_literature_run_dir()

    def resolve_literature_item_path(self, item: dict, progress: dict) -> str:
        direct_keys = ["path", "file_path", "pdf_path", "local_path", "saved_path", "final_path"]
        for key in direct_keys:
            value = clean(item.get(key))
            if value and Path(value).exists():
                return str(Path(value))
        filename = clean(item.get("filename"))
        if not filename:
            return ""
        roots = []
        for key in ("final_pdf_dir", "run_root"):
            value = clean(progress.get(key))
            if value:
                roots.append(Path(value))
        for root in roots:
            if not root.exists():
                continue
            candidate = root / filename
            if candidate.exists():
                return str(candidate)
            try:
                matches = list(root.rglob(filename))
            except Exception:
                matches = []
            if matches:
                return str(matches[0])
            if not filename.lower().endswith(".pdf"):
                stem = Path(filename).stem
                try:
                    pdf_matches = [path for path in root.rglob("*.pdf") if path.stem == stem]
                except Exception:
                    pdf_matches = []
                if pdf_matches:
                    return str(pdf_matches[0])
        return ""

    def open_selected_literature_pdf(self, _event=None) -> None:
        if not hasattr(self, "lit_download_tree"):
            return
        selected = self.lit_download_tree.selection()
        if not selected:
            self._show_error("请先在下载列表里选择一篇文献。")
            return
        path_value = self.lit_download_paths.get(selected[0], "")
        if not path_value or not Path(path_value).exists():
            self._show_error("没有找到这篇文献的本地文件。可以先在开发者模式打开 PDF 目录查看下载结果。")
            return
        os.startfile(str(Path(path_value)))

    def quick_pdf_import(self) -> bool:
        project_id = self.current_project_id(self.rag_project) or self.current_project_id(self.file_project) or self.default_project_id()
        path = filedialog.askopenfilename(title="添加文献 PDF", filetypes=[("PDF", "*.pdf"), ("All files", "*.*")])
        if not path:
            return False
        self._register_file_path(Path(path), project_id, category="paper")
        return True

    def quick_data_upload(self) -> bool:
        project_id = self.current_project_id(self.data_project) or self.current_project_id(self.file_project) or self.default_project_id()
        path = filedialog.askopenfilename(title="上传科研资料", filetypes=[("Research files", "*.csv *.tsv *.xlsx *.xls *.txt *.docx *.doc *.pdf *.png *.jpg *.jpeg *.tif *.tiff"), ("All files", "*.*")])
        if not path:
            return False
        self._register_file_path(Path(path), project_id, category="instrument export")
        return True

    def _register_file_path(self, file_path: Path, project_id: str, category: str = "") -> None:
        if not project_id or not file_path.exists():
            self._show_error("请先选择项目，并选择一个存在的本地文件。")
            return
        self.status_text.set("正在上传并解析文件")

        def task():
            content = ""
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:200000]
            except Exception:
                content = f"Binary or unreadable text file: {file_path.name}"
            status, body = self.api.post(
                "/research-os/files",
                {"project_id": project_id, "filename": file_path.name, "content": content, "source_path": str(file_path), "category": category},
                timeout=45,
            )
            if status != 200:
                raise RuntimeError(pretty(body))
            file_id = body.get("file", {}).get("id")
            extraction = {}
            if file_id:
                ex_status, extraction = self.api.post("/research-os/extraction", {"file_id": file_id}, timeout=45)
                if ex_status != 200:
                    extraction = {"error": extraction}
            return {"file_result": body, "extraction": extraction}

        def done(body):
            self.status_text.set("文件已上传并开始解析")
            if self.developer_mode.get():
                self.set_context(body)
            if hasattr(self, "data_result"):
                self.data_result.delete("1.0", tk.END)
                self.data_result.insert("1.0", pretty(body))
            target_box = self.library_reference_box if category == "paper" and hasattr(self, "library_reference_box") else (self.library_data_box if hasattr(self, "library_data_box") else None)
            if target_box:
                target_box.delete("1.0", tk.END)
                target_box.insert("1.0", f"文件已上传：{file_path.name}\n状态：登记中 / 解析中\n\n解析完成后会进入当前项目资料库。")
            self.load_references()
            if hasattr(self, "library_data_search"):
                self.search_data_objects()

        self.run_async(task, done, self._show_error)

    def search_data_objects(self) -> None:
        project_id = self.current_project_id(self.data_project) or self.default_project_id()
        query = self.data_search.get()
        self.status_text.set("正在搜索实验 / 样品 / 文件")

        def task():
            results = {}
            for key, path in {
                "experiments": "/research-os/experiments",
                "samples": "/research-os/samples",
                "files": "/research-os/files",
                "conclusions": "/research-os/conclusions",
                "decisions": "/research-os/decisions",
                "failures": "/research-os/failures",
            }.items():
                url = path + "?" + urllib.parse.urlencode({"project_id": project_id})
                status, body = self.api.get(url)
                if status != 200:
                    results[key] = {"error": body}
                    continue
                value = body.get(key) or body.get("files") or body
                if query:
                    value = [item for item in value if query.lower() in json.dumps(item, ensure_ascii=False).lower()]
                results[key] = value
            return results

        def done(results):
            self.status_text.set("搜索完成")
            self.data_result.delete("1.0", tk.END)
            self.data_result.insert("1.0", self.safe_summary_lines({"summary": "搜索完成", "status": "可使用"}))
            if hasattr(self, "library_data_box"):
                lines = ["数据与实验对象", ""]
                self.library_data_cache = []
                for key, label in [("experiments", "实验"), ("samples", "样品"), ("files", "文件"), ("conclusions", "结论"), ("decisions", "决策"), ("failures", "失败记录")]:
                    rows = results.get(key) or []
                    lines.append(f"{label}：{len(rows) if isinstance(rows, list) else 0}")
                    if isinstance(rows, list):
                        for item in rows[:5]:
                            if isinstance(item, dict):
                                row = dict(item)
                                row["_kind"] = key
                                item_id = clean(row.get("id") or row.get("file_id") or row.get("sample_id"))
                                if item_id and self.is_client_hidden("hidden_files", item_id):
                                    continue
                                self.library_data_cache.append(row)
                                lines.append(f"  - {clean(item.get('title') or item.get('name') or item.get('filename') or item.get('sample_code') or item.get('decision_text') or item.get('conclusion_text'))[:120]}")
                if hasattr(self, "library_data_list"):
                    self.library_data_list.delete(0, tk.END)
                    for item in self.library_data_cache[:120]:
                        label = clean(item.get("title") or item.get("name") or item.get("filename") or item.get("sample_code") or item.get("decision_text") or item.get("conclusion_text") or item.get("failure_description") or "资料")
                        self.library_data_list.insert(tk.END, f"{label[:120]} · {self.library_item_kind_label(clean(item.get('_kind')))}")
                    if not self.library_data_cache:
                        self.library_data_list.insert(tk.END, "暂无数据。请上传文件或保存实验记录。")
                self.library_data_box.delete("1.0", tk.END)
                self.library_data_box.insert("1.0", "\n".join(lines))
            if self.developer_mode.get():
                self.set_context(results)

        self.run_async(task, done, self._show_error)

    def library_item_kind_label(self, kind: str) -> str:
        return {
            "experiments": "实验记录",
            "samples": "样品",
            "files": "数据文件",
            "conclusions": "结论",
            "decisions": "决策",
            "failures": "失败记录",
        }.get(kind, "资料")

    def selected_library_data_item(self) -> dict:
        if not hasattr(self, "library_data_list"):
            return {}
        selection = self.library_data_list.curselection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.library_data_cache):
            return {}
        return self.library_data_cache[index]

    def show_library_data_detail(self) -> None:
        item = self.selected_library_data_item()
        if not hasattr(self, "library_data_box"):
            return
        self.library_data_box.delete("1.0", tk.END)
        if not item:
            self.library_data_box.insert("1.0", "请选择一条数据、实验记录或样品。")
            return
        title = clean(item.get("title") or item.get("name") or item.get("filename") or item.get("sample_code") or item.get("decision_text") or item.get("conclusion_text") or item.get("failure_description") or "资料")
        lines = [
            f"标题：{title}",
            f"类型：{self.library_item_kind_label(clean(item.get('_kind')))}",
            f"状态：{self.user_status_label(clean(item.get('status') or item.get('current_status') or item.get('analysis_status') or 'active'))}",
            f"所属项目：{self.project_label_from_id(clean(item.get('project_id'))) or self.project_choice.get() or '当前项目'}",
            f"更新时间：{clean(item.get('updated_at') or item.get('created_at') or item.get('upload_time')) or '暂无'}",
        ]
        summary = clean(item.get("summary") or item.get("result_summary") or item.get("parsed_summary") or item.get("reason") or item.get("likely_reason"))
        if summary:
            lines.extend(["", summary[:900]])
        if self.developer_mode.get():
            lines.extend(["", "开发者详情", pretty(item)])
        self.library_data_box.insert("1.0", "\n".join(lines))

    def hide_selected_library_data(self) -> None:
        item = self.selected_library_data_item()
        item_id = clean(item.get("id") or item.get("file_id") or item.get("sample_id"))
        if not item_id:
            self._show_error("请先选择一条资料。")
            return
        if not messagebox.askyesno("删除记录", "当前普通删除会从客户端隐藏这条记录；不会物理删除本地文件。"):
            return
        self.hide_client_item("hidden_files", item_id)
        self.status_text.set("记录已从客户端隐藏")
        self.search_data_objects()

    def save_conclusion(self) -> None:
        payload = {"project_id": self.current_project_id(self.data_project) or self.default_project_id(), "conclusion_text": self.conclusion_text.get(), "status": "draft", "evidence_strength": "preliminary", "confidence": 0.45}
        self._post_data_record("/research-os/conclusions", payload, "结论已保存")

    def save_failure(self) -> None:
        payload = {"project_id": self.current_project_id(self.data_project) or self.default_project_id(), "title": self.failure_text.get()[:80] or "Failure record", "failure_description": self.failure_text.get(), "observed_failure": self.failure_text.get()}
        self._post_data_record("/research-os/failures", payload, "失败记录已保存")

    def save_decision(self) -> None:
        payload = {"project_id": self.current_project_id(self.data_project) or self.default_project_id(), "decision_text": self.decision_text.get(), "reason": "Saved from local client", "status": "active", "confidence": 0.6}
        self._post_data_record("/research-os/decisions", payload, "决策已保存")

    def _post_data_record(self, path: str, payload: dict, ok_message: str) -> None:
        if not payload.get("project_id"):
            self._show_error("请先选择项目。")
            return
        if not clean(payload.get("conclusion_text") or payload.get("failure_description") or payload.get("decision_text")):
            self._show_error("内容不能为空。")
            return

        def task():
            status, body = self.api.post(path, payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set(ok_message)
            self.data_result.delete("1.0", tk.END)
            self.data_result.insert("1.0", self.safe_summary_lines(body))
            if self.developer_mode.get():
                self.set_context(body)
            if hasattr(self, "library_data_search"):
                self.search_data_objects()

        self.run_async(task, done, self._show_error)

    def load_experiments(self) -> None:
        project_id = self.current_project_id(self.exp_project)
        if not project_id:
            return
        def task():
            status, payload = self.api.get("/research-os/experiments?" + urllib.parse.urlencode({"project_id": project_id}))
            if status != 200:
                raise RuntimeError(pretty(payload))
            return payload.get("experiments", [])
        def done(rows):
            self.exp_tree.delete(*self.exp_tree.get_children())
            for exp in rows:
                self.exp_tree.insert("", tk.END, iid=exp["id"], values=(exp.get("title"), exp.get("experiment_type"), exp.get("experiment_date"), exp.get("status")))
        self.run_async(task, done, self._show_error)

    def show_experiment_detail(self, _event=None) -> None:
        selected = self.exp_tree.selection()
        if not selected:
            return
        experiment_id = selected[0]
        project_id = self.current_project_id(self.exp_project)

        def task():
            status, payload = self.api.get("/research-os/experiments?" + urllib.parse.urlencode({"project_id": project_id}))
            if status != 200:
                raise RuntimeError(pretty(payload))
            for item in payload.get("experiments", []):
                if item.get("id") == experiment_id:
                    return item
            return {"id": experiment_id, "error": "not found"}

        def done(item):
            self.set_context(item)
            if hasattr(self, "data_result"):
                self.data_result.delete("1.0", tk.END)
                self.data_result.insert("1.0", pretty(item))

        self.run_async(task, done, self._show_error)

    def create_experiment(self) -> None:
        payload = {"project_id": self.current_project_id(self.exp_project), "title": self.exp_title.get(), "experiment_type": self.exp_type.get(), "experiment_date": self.exp_date.get(), "operator": self.exp_operator.get(), "result_summary": self.exp_text.get("1.0", tk.END).strip(), "status": "completed"}
        def task():
            status, body = self.api.post("/research-os/experiments", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body["experiment"]
        def done(exp):
            self.status_text.set("实验记录已写入")
            if self.developer_mode.get():
                self.set_context(exp)
            self.load_experiments()
        self.run_async(task, done, self._show_error)

    def extract_experiment_memory(self) -> None:
        payload = {"project_id": self.current_project_id(self.exp_project), "text": self.exp_text.get("1.0", tk.END).strip()}
        def task():
            status, body = self.api.post("/research-os/memory/extract-experiment", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.status_text.set("实验记忆已提取")
            if self.developer_mode.get():
                self.set_context(body)
            self.load_experiments()
        self.run_async(task, done, self._show_error)

    def load_samples(self) -> None:
        project_id = self.current_project_id(self.sample_project)
        if not project_id:
            return
        def task():
            status, payload = self.api.get("/research-os/samples?" + urllib.parse.urlencode({"project_id": project_id}))
            if status != 200:
                raise RuntimeError(pretty(payload))
            return payload.get("samples", [])
        def done(rows):
            self.sample_tree.delete(*self.sample_tree.get_children())
            for sample in rows:
                self.sample_tree.insert("", tk.END, iid=sample["id"], values=(sample.get("sample_code") or sample.get("sample_id"), sample.get("sample_type"), sample.get("batch"), sample.get("current_status")))
        self.run_async(task, done, self._show_error)

    def create_sample(self) -> None:
        payload = {"project_id": self.current_project_id(self.sample_project), "sample_code": self.sample_code.get(), "sample_type": self.sample_type.get(), "batch": self.sample_batch.get(), "current_status": self.sample_status.get()}
        def task():
            status, body = self.api.post("/research-os/samples", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body["sample"]
        def done(sample):
            self.status_text.set("样品已写入")
            if self.developer_mode.get():
                self.set_context(sample)
            self.load_samples()
        self.run_async(task, done, self._show_error)

    def load_references(self) -> None:
        project_id = self.current_project_id(self.rag_project)
        def task():
            status, payload = self.api.get("/research-os/references?" + urllib.parse.urlencode({"project_id": project_id, "limit": 200}))
            if status == 200:
                return payload.get("references", [])
            cached = self.client_cache.get(f"references:{project_id}") or []
            if cached:
                return cached
            raise RuntimeError(pretty(payload))
        def done(rows):
            self.reference_cache = [row for row in rows if not self.is_client_hidden("hidden_references", clean(row.get("id")))]
            self.library_reference_cache = self.reference_cache
            self.reference_tree.delete(*self.reference_tree.get_children())
            for ref in self.reference_cache:
                self.reference_tree.insert("", tk.END, iid=ref["id"], values=(ref.get("title"), ref.get("source_provider"), ref.get("access_status")))
            if hasattr(self, "library_reference_list"):
                self.library_reference_list.delete(0, tk.END)
                for ref in self.library_reference_cache[:200]:
                    title = clean(ref.get("title") or ref.get("filename") or "未命名文献")
                    status = clean(ref.get("access_status") or ref.get("status") or ref.get("source_provider")) or "可使用"
                    self.library_reference_list.insert(tk.END, f"{title[:120]} · {status}")
                if not self.library_reference_cache:
                    self.library_reference_list.insert(tk.END, "暂无文献。请添加 PDF 或启动文献采集。")
            if hasattr(self, "library_reference_box"):
                lines = ["已入库文献", ""]
                for ref in self.reference_cache[:40]:
                    title = clean(ref.get("title") or ref.get("filename") or "未命名文献")
                    status = clean(ref.get("access_status") or ref.get("status") or ref.get("source_provider")) or "可使用"
                    lines.append(f"- {title[:150]} · {status}")
                if len(lines) == 2:
                    lines.append("暂无文献。请添加 PDF 或启动文献采集。")
                self.library_reference_box.delete("1.0", tk.END)
                self.library_reference_box.insert("1.0", "\n".join(lines))
            self.client_cache[f"references:{project_id}"] = rows
            self.save_client_cache()
        self.run_async(task, done, self._show_error)

    def show_reference_detail(self, _event=None) -> None:
        selected = self.reference_tree.selection()
        if not selected:
            return
        reference_id = selected[0]
        for ref in self.reference_cache:
            if ref.get("id") == reference_id:
                if self.developer_mode.get():
                    self.set_context(ref)
                return

    def reparse_selected_reference(self) -> None:
        selected = self.reference_tree.selection()
        if not selected:
            self._show_error("Please select a reference or PDF record first.")
            return
        reference_id = selected[0]
        ref = next((item for item in self.reference_cache if item.get("id") == reference_id), {})
        path = clean(ref.get("full_text_path") or ref.get("source_path"))
        if not path or not Path(path).exists():
            self._show_error("Selected reference has no local file to parse.")
            return
        self._register_file_path(Path(path), self.current_project_id(self.rag_project) or self.default_project_id(), category="paper")

    def hide_selected_reference(self) -> None:
        selected = self.reference_tree.selection() if hasattr(self, "reference_tree") else []
        if not selected:
            self._show_error("请先选择一条文献记录。")
            return
        reference_id = selected[0]
        if not messagebox.askyesno("隐藏文献", "从客户端隐藏这条文献记录？本地 PDF 和数据库不会被删除。"):
            return
        self.hide_client_item("hidden_references", reference_id)
        self.load_references()
        self.status_text.set("文献记录已从客户端隐藏")

    def selected_library_reference(self) -> dict:
        if not hasattr(self, "library_reference_list"):
            return {}
        selection = self.library_reference_list.curselection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.library_reference_cache):
            return {}
        return self.library_reference_cache[index]

    def show_library_reference_detail(self) -> None:
        ref = self.selected_library_reference()
        if not hasattr(self, "library_reference_box"):
            return
        self.library_reference_box.delete("1.0", tk.END)
        if not ref:
            self.library_reference_box.insert("1.0", "请选择一条文献或 PDF。")
            return
        lines = [
            f"标题：{clean(ref.get('title') or ref.get('filename') or '未命名文献')}",
            f"类型：{clean(ref.get('source_provider') or ref.get('file_type') or '文献')}",
            f"状态：{clean(ref.get('access_status') or ref.get('status')) or '可使用'}",
            f"所属项目：{self.project_label_from_id(clean(ref.get('project_id'))) or self.project_choice.get() or '当前项目'}",
            f"更新时间：{clean(ref.get('updated_at') or ref.get('created_at')) or '暂无'}",
        ]
        abstract = clean(ref.get("abstract") or ref.get("summary") or ref.get("note"))
        if abstract:
            lines.extend(["", abstract[:900]])
        if self.developer_mode.get():
            lines.extend(["", "开发者详情", pretty(ref)])
        self.library_reference_box.insert("1.0", "\n".join(lines))

    def reparse_selected_library_reference(self) -> None:
        ref = self.selected_library_reference()
        if not ref:
            self._show_error("请先选择一条文献或 PDF。")
            return
        path = clean(ref.get("full_text_path") or ref.get("source_path") or ref.get("path"))
        if not path or not Path(path).exists():
            self._show_error("这条记录没有可重新解析的本地文件。")
            return
        self._register_file_path(Path(path), self.default_project_id(), category="paper")

    def remove_selected_library_reference_from_project(self) -> None:
        ref = self.selected_library_reference()
        reference_id = clean(ref.get("id"))
        if not reference_id:
            self._show_error("请先选择一条文献。")
            return
        if not messagebox.askyesno("从项目移除", "只从当前项目移除这条资料；本地库记录会保留。"):
            return

        def task():
            status, body = self.api.post(f"/research-os/references/{urllib.parse.quote(reference_id, safe='')}/exclude", {"project_id": self.default_project_id(), "reason": "removed from project in client"}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(_body):
            self.hide_client_item("hidden_references", reference_id)
            self.status_text.set("资料已从当前项目移除")
            self.load_references()

        self.run_async(task, done, self._show_error)

    def delete_selected_library_reference(self) -> None:
        ref = self.selected_library_reference()
        reference_id = clean(ref.get("id"))
        if not reference_id:
            self._show_error("请先选择一条文献。")
            return
        if not messagebox.askyesno("删除资料", "当前后端没有确认的物理删除接口。确认后会把资料标记为删除/排除，并从客户端隐藏。"):
            return

        def task():
            put_status, put_body = self.api.put(f"/research-os/references/{urllib.parse.quote(reference_id, safe='')}", {"status": "deleted", "excluded": True}, timeout=60)
            if put_status == 200:
                return put_body
            post_status, post_body = self.api.post(f"/research-os/references/{urllib.parse.quote(reference_id, safe='')}/exclude", {"project_id": self.default_project_id(), "reason": "deleted from client"}, timeout=60)
            return post_body if post_status == 200 else {"warning": post_body}

        def done(_body):
            self.hide_client_item("hidden_references", reference_id)
            self.status_text.set("资料已从客户端删除/隐藏")
            self.load_references()

        self.run_async(task, done, self._show_error)

    def build_kb(self) -> None:
        payload = {"project_id": self.current_project_id(self.rag_project)}
        def task():
            status, body = self.api.post("/research-os/knowledge-base/build", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.status_text.set("知识库已构建")
            if hasattr(self, "library_reference_box"):
                self.library_reference_box.delete("1.0", tk.END)
                self.library_reference_box.insert("1.0", "知识库已构建。现在可以在聊天或资料库问答中检索这些文献。")
            if self.developer_mode.get():
                self.set_context(body)
        self.run_async(task, done, self._show_error)

    def query_rag(self) -> None:
        payload = {"project_id": self.current_project_id(self.rag_project), "question": self.rag_question.get("1.0", tk.END).strip()}
        def task():
            status, body = self.api.post("/research-os/rag/query", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.rag_answer.delete("1.0", tk.END)
            if isinstance(body, dict) and clean(body.get("answer")):
                citations = body.get("citations") or []
                self.insert_answer_with_citations(self.rag_answer, clean(body.get("answer")), citations)
                if citations:
                    self.rag_answer.insert(tk.END, f"\n\n本回答使用了 {len(citations)} 个来源。点击正文上标查看详情。")
            else:
                self.rag_answer.insert("1.0", pretty(body))
            if self.developer_mode.get():
                self.set_context(body)
        self.run_async(task, done, self._show_error)

    def build_memory_context(self) -> None:
        payload = {"project_id": self.current_project_id(self.memory_project), "query": self.memory_query.get("1.0", tk.END).strip(), "limit": 20}
        def task():
            status, body = self.api.post("/research-os/memory/context", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.memory_result.delete("1.0", tk.END)
            self.memory_result.insert("1.0", pretty(body))
            self.set_context(body)
        self.run_async(task, done, self._show_error)

    def load_agent_memory(self) -> None:
        project_id = self.current_project_id(self.memory_project)
        def task():
            status, body = self.api.get("/research-os/agent-memory?" + urllib.parse.urlencode({"project_id": project_id, "limit": 100}))
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.memory_result.delete("1.0", tk.END)
            self.memory_result.insert("1.0", pretty(body))
            self.set_context(body)
        self.run_async(task, done, self._show_error)

    def clear_agent_chat(self) -> None:
        self.agent_transcript.delete("1.0", tk.END)
        self.agent_detail.delete("1.0", tk.END)
        self.agent_citations = {}
        self.agent_conversation_id = ""
        self.client_cache["agent_conversation_id"] = ""
        self.save_client_cache()
        self.agent_transcript.insert("1.0", "AURA 已准备好。\n\n你可以直接打招呼、提问，或让 AURA 帮你采集文献、分析数据、整理实验记录。\n\n")

    def toggle_agent_context_panel(self) -> None:
        if not hasattr(self, "agent_context_panel"):
            return
        if self.agent_context_visible.get():
            self.agent_context_panel.grid_remove()
            self.agent_context_visible.set(False)
        else:
            self.agent_context_panel.grid()
            self.agent_context_visible.set(True)

    def chat_upload_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择要交给 AURA 的文件",
            filetypes=[
                ("Research files", "*.pdf *.csv *.xlsx *.xls *.docx *.txt *.md *.png *.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._register_file_path(Path(path), self.default_project_id(), category="chat upload")
        filename = Path(path).name
        self.append_agent_chat("你", f"已上传文件：{filename}")
        self.agent_message.delete("1.0", tk.END)
        self.agent_message.insert("1.0", f"请读取并整理我刚上传的文件：{filename}")

    def update_dual_status(self, text: str, color: str = TEXT_2) -> None:
        if hasattr(self, "dual_status_pill"):
            label = "● 本地知识库已连接" if "已连接" in text or "就绪" in text else "● 本地知识库待连接"
            self.dual_status_pill.configure(text=label, fg=color)

    def summarize_dual_agent_response(self, body: dict) -> str:
        result = body.get("execution_result") or {}
        processing = body.get("post_task_processing") or {}
        memory = processing.get("memory_write") or {}
        pending = processing.get("pending_skill") or {}
        memory_pages = len(memory.get("written") or [])
        pending_name = clean(pending.get("name"))
        status = self.user_status_label(clean(result.get("status") or "completed"))
        summary = clean(result.get("summary")) or "AURA 已完成这次处理。"
        lines = [summary]
        facts = [f"状态：{status}", f"记忆页：{memory_pages}"]
        if pending_name:
            facts.append(f"待审核技能：{pending_name}")
        lines.append(" | ".join(facts))
        lines.append("需要查看来源和任务细节时，可以打开右侧上下文。")
        return "\n".join(lines)

    def format_dual_agent_detail(self, body: dict) -> str:
        task_spec = body.get("task_spec") or {}
        result = body.get("execution_result") or {}
        decision = body.get("brain_decision") or {}
        processing = body.get("post_task_processing") or {}
        resolver = body.get("resolver_health") or {}
        memory = processing.get("memory_write") or {}
        pending = processing.get("pending_skill") or {}
        lines = [
            "Dual Agent Result",
            "",
            f"Task type: {clean(task_spec.get('task_type'))}",
            f"Intent: {clean(task_spec.get('intent'))}",
            f"Status: {clean(result.get('status'))}",
            f"SkillRun: {clean(result.get('skillrun_id'))}",
            "",
            "Badges",
            f"- Memory Pages: {len(memory.get('written') or [])}",
            f"- Pending Skill: {clean(pending.get('name')) or 'none'}",
            f"- Resolver Entries: {resolver.get('resolver_entries', 0)}",
            "",
            "Task Plan",
            clean(task_spec.get("user_query")),
            "",
            "Execution Summary",
            clean(result.get("summary")),
            "",
            "Brain Decision",
            clean(decision.get("decision_type")) or "n/a",
            clean(decision.get("reason")),
            "",
            "Raw JSON is intentionally folded into this context panel.",
            pretty(body),
        ]
        return "\n".join(lines)

    def format_chat_context_summary(self, body: dict) -> str:
        if not isinstance(body, dict):
            return "本次回答没有返回可展示的上下文。"
        result = body.get("execution_result") or {}
        processing = body.get("post_task_processing") or {}
        memory = processing.get("memory_write") or {}
        pending = processing.get("pending_skill") or {}
        task_spec = body.get("task_spec") or {}
        workspace = body.get("workspace_state") or (body.get("debug") or {}).get("workspace_state") or {}
        literature = workspace.get("literature") or {}
        data = workspace.get("data") or {}
        task_status = body.get("task_status") or []
        citations = body.get("citations") or []
        sources = body.get("sources") or []
        memory_used = body.get("memory_used") or []
        intent = self.user_task_label(clean(body.get("intent_type") or body.get("intent") or task_spec.get("intent")))
        status = self.user_status_label(clean(result.get("status") or body.get("status") or ""))
        lines = ["本次回答摘要", ""]
        if intent:
            lines.append(f"识别意图：{intent}")
        if status:
            lines.append(f"处理状态：{status}")
        if workspace:
            lines.extend([
                "",
                "当前项目概况",
                f"文献：{literature.get('references_count', 0)} | PDF：{literature.get('pdf_files_found', 0)} | 可检索片段：{literature.get('chunks_count', 0)}",
                f"实验：{data.get('experiments_count', 0)} | 样品：{data.get('samples_count', 0)} | 数据文件：{data.get('data_files_count', 0)}",
            ])
        lines.extend([
            "",
            "本次使用",
            f"来源：{len(citations) or len(sources)} 个",
            f"项目记忆：{len(memory_used)} 条",
            f"相关任务：{len(task_status)} 条",
        ])
        written_pages = len(memory.get("written") or [])
        if written_pages or pending:
            lines.extend(["", "任务产物"])
            if written_pages:
                lines.append(f"更新记忆页：{written_pages}")
            if clean(pending.get("name")):
                lines.append(f"待审核能力：{clean(pending.get('name'))}")
        if citations:
            lines.extend(["", "来源说明", "正文上标可以点击查看来源详情。"])
        return "\n".join(lines)

    def run_dual_agent_demo(self) -> None:
        project_id = self.default_project_id() or "demo_project"
        self.status_text.set("正在运行 scaffold 开发者演示")
        self.show_view("agent")
        if hasattr(self, "agent_detail"):
            self.agent_detail.delete("1.0", tk.END)
            self.agent_detail.insert("1.0", "这是 backend/researchos scaffold 开发者演示，不属于默认 demo 可用能力。")

        def task():
            path = "/api/demo/dual-agent?" + urllib.parse.urlencode({"project_id": project_id})
            status, body = self.api.get(path, timeout=180)
            if status != 200:
                raise RuntimeError("开发者演示接口未启用或不可用。请启用 RESEARCHOS_DUAL_AGENT_API_ENABLED=true 后重启本地服务。")
            return body

        def done(body):
            self.status_text.set("scaffold 开发者演示已完成")
            self.update_dual_status("Scaffold Developer Demo", ACCENT)
            self.append_agent_chat(APP_NAME, self.summarize_dual_agent_response(body.get("details") or body))
            self.agent_detail.delete("1.0", tk.END)
            self.agent_detail.insert("1.0", self.format_dual_agent_detail(body.get("details") or body))
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def append_agent_chat(self, speaker: str, text: str, citations: list[dict] | None = None) -> None:
        label = "你" if speaker.lower() in {"you", "user", "你"} else (speaker if speaker == "任务" else APP_NAME)
        self.agent_transcript.insert(tk.END, f"\n{label}：\n")
        if citations and label == APP_NAME:
            self.insert_answer_with_citations(self.agent_transcript, text.strip(), citations)
            self.agent_transcript.insert(tk.END, "\n")
        else:
            self.agent_transcript.insert(tk.END, f"{text.strip()}\n")
        self.agent_transcript.see(tk.END)

    def citation_marker_to_number(self, marker: str) -> str:
        table = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
        return clean(marker.translate(table))

    def insert_answer_with_citations(self, box: ScrolledText, text: str, citations: list[dict]) -> None:
        by_id = {str(item.get("citation_id")): item for item in citations if item.get("citation_id")}
        for key, value in by_id.items():
            self.agent_citations[key] = value
        pattern = re.compile(r"([¹²³⁴⁵⁶⁷⁸⁹⁰]+)")
        pos = 0
        for match in pattern.finditer(text):
            if match.start() > pos:
                box.insert(tk.END, text[pos:match.start()])
            marker = match.group(1)
            citation_id = self.citation_marker_to_number(marker)
            tag = f"citation_{citation_id}"
            box.insert(tk.END, marker, (tag,))
            box.tag_config(tag, foreground=ACCENT, underline=True)
            box.tag_bind(tag, "<Button-1>", lambda _event, cid=citation_id: self.show_citation_detail(cid))
            box.tag_bind(tag, "<Enter>", lambda _event: box.configure(cursor="hand2"))
            box.tag_bind(tag, "<Leave>", lambda _event: box.configure(cursor=""))
            pos = match.end()
        if pos < len(text):
            box.insert(tk.END, text[pos:])

    def open_citation_file(self, citation: dict) -> None:
        path = clean(citation.get("file_path"))
        if not path:
            self._show_error("这个来源没有可打开的本地文件。")
            return
        target = Path(path)
        if not target.exists():
            self._show_error(f"本地文件不存在：{path}")
            return
        os.startfile(str(target))

    def show_citation_detail(self, citation_id: str) -> None:
        citation = self.agent_citations.get(str(citation_id))
        if not citation:
            return
        self.agent_detail.delete("1.0", tk.END)
        excerpts = citation.get("excerpts") or ([citation.get("excerpt")] if citation.get("excerpt") else [])
        lines = [
            f"来源 {citation_id}",
            clean(citation.get("display_title")) or clean(citation.get("pdf_filename")) or "未命名来源",
            "",
        ]
        meta = []
        for key, label in [("year", "年份"), ("journal", "期刊"), ("doi", "DOI"), ("pmid", "PMID"), ("pdf_filename", "PDF")]:
            value = clean(citation.get(key))
            if value:
                meta.append(f"{label}：{value}")
        if meta:
            lines.extend(meta)
            lines.append("")
        if citation.get("page"):
            lines.append(f"页码：{citation.get('page')}")
        lines.append(f"类型：{clean(citation.get('source_type'))}")
        if clean(citation.get("file_path")):
            lines.append(f"本地文件：{clean(citation.get('file_path'))}")
        lines.append("")
        lines.append("证据片段")
        for index, excerpt in enumerate(excerpts[:5], start=1):
            lines.append(f"{index}. {clean(excerpt)[:700]}")
        lines.append("")
        lines.append("技术 ID 默认隐藏；需要排查时可在 API / 调试页查看。")
        self.agent_detail.insert("1.0", "\n".join(lines))
        if hasattr(self, "agent_actions_frame"):
            for child in self.agent_actions_frame.winfo_children():
                child.destroy()
            tk.Label(self.agent_actions_frame, text=f"来源 {citation_id}", bg=BG_SURFACE, fg=TEXT_2, anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=(0, 6))
            if citation.get("openable") and clean(citation.get("file_path")):
                tk.Button(
                    self.agent_actions_frame,
                    text="打开 PDF / 文件",
                    command=lambda item=citation: self.open_citation_file(item),
                    bg=BG_ELEVATED,
                    fg=TEXT_1,
                    activebackground=BG_HOVER,
                    activeforeground=TEXT_1,
                    relief="flat",
                    bd=0,
                    padx=10,
                    pady=8,
                    cursor="hand2",
                    anchor="w",
                ).pack(fill="x", pady=(0, 6))

    def set_agent_message_and_send(self, message: str) -> None:
        self.agent_message.delete("1.0", tk.END)
        self.agent_message.insert("1.0", message)
        self.send_agent_message()

    def run_agent_action(self, action: dict) -> None:
        if clean(action.get("action")):
            self.run_feed_action(action)
            return
        intent = clean(action.get("intent"))
        if intent == "refresh_task_status":
            self.set_agent_message_and_send("现在下载、解析和入库进度怎么样？")
        elif intent == "summarize_literature":
            self.set_agent_message_and_send("总结当前项目已入库文献，按研究对象、实验模型、方法、指标和主要发现归纳。")
        elif intent == "start_literature_harvest":
            keywords = clean(self.lit_keywords.get() or self.command_text.get())
            self.set_agent_message_and_send(f"帮我用 {keywords} 下载文献" if keywords else "我要启动文献采集，请先告诉我需要哪些关键词。")
        elif intent == "next_experiment":
            self.set_agent_message_and_send("基于当前证据和缺口，给我下一步可执行实验建议。")
        elif intent == "save_to_memory":
            self.agent_save_to_memory.set(True)
            self.set_agent_message_and_send("把刚才确认的信息整理成项目记忆。")
        elif intent == "workspace_diagnostics":
            self.set_agent_message_and_send("检查当前项目和文献归属是否一致。")
        else:
            self.set_agent_message_and_send(clean(action.get("description")) or clean(action.get("label")) or "继续。")

    def update_agent_workspace_cards(self, body: dict) -> None:
        workspace = body.get("workspace_state") or (body.get("debug") or {}).get("workspace_state") or {}
        project = workspace.get("project") or {}
        literature = workspace.get("literature") or {}
        tasks = workspace.get("tasks") or {}
        diagnostics = workspace.get("workspace_diagnostics") or {}
        project_title = clean(project.get("title")) or self.agent_project.get() or "未选择"
        self.agent_workspace_label.configure(text=f"当前项目：{project_title}")
        self.agent_evidence_label.configure(
            text=f"资料：PDF {literature.get('pdf_files_found', 0)} / 文献 {literature.get('references_count', 0)} / 证据片段 {literature.get('chunks_count', 0)}"
        )
        self.agent_task_label.configure(text=f"任务：运行 {len(tasks.get('running') or [])} / 完成 {len(tasks.get('completed') or [])}")
        if diagnostics.get("warnings"):
            self.agent_evidence_label.configure(fg=WARN)
        else:
            self.agent_evidence_label.configure(fg=TEXT_1)

        if hasattr(self, "agent_actions_frame"):
            for child in self.agent_actions_frame.winfo_children():
                child.destroy()
            actions = body.get("next_actions") or []
            if actions:
                tk.Label(self.agent_actions_frame, text="下一步", bg=BG_SURFACE, fg=TEXT_2, anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=(0, 6))
                for action in actions[:4]:
                    tk.Button(
                        self.agent_actions_frame,
                        text=clean(action.get("label")),
                        command=lambda item=action: self.run_agent_action(item),
                        bg=BG_ELEVATED,
                        fg=TEXT_1,
                        activebackground=BG_HOVER,
                        activeforeground=TEXT_1,
                        relief="flat",
                        bd=0,
                        padx=10,
                        pady=8,
                        cursor="hand2",
                        anchor="w",
                    ).pack(fill="x", pady=(0, 6))
            else:
                tk.Label(self.agent_actions_frame, text="Agent 会在回答后给出下一步动作。", bg=BG_SURFACE, fg=TEXT_2, anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x")

    def format_agent_detail(self, body: dict) -> str:
        routing = body.get("prompt_routing") or {}
        llm = body.get("llm") or {}
        skill = clean(body.get("matched_skill") or body.get("_resolved_skill_name") or routing.get("resolved_skill_name") or "自动选择")
        model = clean(llm.get("model") or self.model_text.get())
        tool_calls = body.get("tool_calls") or []
        memory_used = body.get("memory_used") or []
        sources = body.get("sources") or []
        citations = body.get("citations") or []
        task_status = body.get("task_status") or []
        workspace = body.get("workspace_state") or (body.get("debug") or {}).get("workspace_state") or {}
        literature = workspace.get("literature") or {}
        data = workspace.get("data") or {}
        rag = workspace.get("rag") or {}
        lines = [
            "本次处理",
            f"识别任务：{clean(body.get('intent') or 'research_task')}",
            f"调用能力：{skill}",
            "",
            "当前 Workspace",
            f"项目：{clean((workspace.get('project') or {}).get('title')) or self.agent_project.get()}",
            f"PDF：{literature.get('pdf_files_found', 0)} | 已入库文献：{literature.get('references_count', 0)} | Chunks：{literature.get('chunks_count', 0)} | KB：{literature.get('kb_entries_count', 0)}",
            f"未入库 PDF：{literature.get('discovered_not_ingested', 0)} | 已注册未切块：{literature.get('registered_not_chunked', 0)} | 已切块未入 KB：{literature.get('chunked_not_indexed', 0)}",
            f"实验：{data.get('experiments_count', 0)} | 样品：{data.get('samples_count', 0)} | 数据文件：{data.get('data_files_count', 0)} | RAG 可用：{rag.get('available', False)}",
            "",
            f"工具调用：{len(tool_calls)}",
            f"任务状态：{len(task_status)} 条",
            f"使用项目记忆：{len(memory_used)} 条",
            f"本回答来源：{len(citations) or len(sources)} 个",
            f"回答检查：{clean(body.get('validation_status') or '未返回')}",
        ]
        diagnostics = workspace.get("workspace_diagnostics") or {}
        if diagnostics.get("warnings"):
            lines.extend(["", "需要注意"])
            for item in diagnostics.get("possible_misassigned_literature", [])[:3]:
                lines.append(f"可能有文献挂在其他项目：{clean(item.get('project_title'))} | PDF {item.get('pdf_files_found', 0)} | 文献 {item.get('references_count', 0)} | Chunks {item.get('chunks_count', 0)}")
        if task_status:
            lines.extend(["", "任务状态"])
            for index, item in enumerate(task_status[:6], start=1):
                progress = item.get("progress") if isinstance(item, dict) else {}
                if not isinstance(progress, dict):
                    progress = {}
                lines.append(f"{index}. {clean(item.get('task_name') or item.get('task_type'))} | {clean(item.get('status'))} | {clean(item.get('skill_id'))}")
                if progress:
                    lines.append(f"   total={progress.get('total', 0)} downloaded={progress.get('downloaded', 0)} parsed={progress.get('parsed', 0)} indexed={progress.get('indexed', 0)} failed={progress.get('failed', 0)}")
                    if clean(progress.get("current_title")):
                        lines.append(f"   current: {clean(progress.get('current_title'))[:140]}")
        feed = body.get("research_feed") or []
        watcher = body.get("watcher_result") or {}
        if watcher or feed:
            lines.extend(["", "Research Feed"])
            if clean(watcher.get("project_state_summary")):
                lines.append(clean(watcher.get("project_state_summary")))
            for item in feed[:5]:
                if isinstance(item, dict):
                    lines.append(f"- {clean(item.get('title'))}: {clean(item.get('message'))[:120]}")
        if citations:
            lines.extend(["", "来源默认折叠"])
            lines.append("点击正文里的上标编号查看 PDF、文献和证据片段。")
            for item in citations[:5]:
                lines.append(f"{item.get('citation_id')}. {clean(item.get('display_title') or item.get('pdf_filename'))[:120]}")
        if memory_used:
            lines.extend(["", "项目记忆"])
            for index, item in enumerate(memory_used[:8], start=1):
                title = clean(item.get("title") or item.get("memory_type") or item.get("id")) if isinstance(item, dict) else clean(item)
                lines.append(f"{index}. {title}")
        artifacts = workspace.get("artifacts") or []
        if artifacts:
            lines.extend(["", "最近资产"])
            for index, item in enumerate(artifacts[:8], start=1):
                if isinstance(item, dict):
                    lines.append(f"{index}. {clean(item.get('type'))}: {clean(item.get('title'))[:120]}")
        return "\n".join(lines)

    def format_workspace_state(self, state: dict) -> str:
        project = state.get("project") or {}
        literature = state.get("literature") or {}
        data = state.get("data") or {}
        memory = state.get("memory") or {}
        rag = state.get("rag") or {}
        tasks = state.get("tasks") or {}
        lines = [
            "工作区状态",
            f"项目：{clean(project.get('title')) or clean(state.get('active_project_id'))}",
            "",
            f"PDF：{literature.get('pdf_files_found', 0)}",
            f"已入库文献：{literature.get('references_count', 0)}",
            f"证据片段：{literature.get('chunks_count', 0)}",
            f"知识条目：{literature.get('kb_entries_count', 0)}",
            f"已下载未入库：{literature.get('discovered_not_ingested', 0)}",
            f"已注册未切块：{literature.get('registered_not_chunked', 0)}",
            f"已切块未入 KB：{literature.get('chunked_not_indexed', 0)}",
            "",
            f"实验：{data.get('experiments_count', 0)} | 样品：{data.get('samples_count', 0)} | 数据文件：{data.get('data_files_count', 0)}",
            f"项目记忆：{memory.get('project_memory_count', 0)} | Agent 记忆：{memory.get('agent_memory_count', 0)} | 执行记忆：{memory.get('execution_memory_count', 0)}",
            f"资料检索：{'可用' if rag.get('available') else '暂无'} | 可检索片段：{rag.get('queryable_chunks', 0)}",
            f"任务：运行 {len(tasks.get('running') or [])} / 完成 {len(tasks.get('completed') or [])} / 失败 {len(tasks.get('failed') or [])}",
            "",
            "最近文献",
        ]
        for ref in (literature.get("recent_references") or [])[:8]:
            lines.append(f"- {clean(ref.get('title'))[:160]}")
        artifacts = state.get("artifacts") or []
        if artifacts:
            lines.extend(["", "最近资产"])
            for item in artifacts[:10]:
                lines.append(f"- {clean(item.get('type'))}: {clean(item.get('title'))[:140]}")
        return "\n".join(lines)

    def refresh_workspace_state(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return

        def task():
            status, body = self.api.get("/research-os/workspace-state?" + urllib.parse.urlencode({"project_id": project_id}), timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("工作区状态已加载")
            self.update_agent_workspace_cards({"workspace_state": body, "next_actions": []})
            self.agent_detail.delete("1.0", tk.END)
            self.agent_detail.insert("1.0", self.format_workspace_state(body))
            if self.developer_mode.get():
                self.set_context({"workspace_state": body})

        self.run_async(task, done, self._show_error)

    def render_agent_inbox(self, items: list[dict]) -> None:
        if not hasattr(self, "feed_tree"):
            return
        self.feed_items = items
        self.feed_tree.delete(*self.feed_tree.get_children())
        for item in items:
            item_id = clean(item.get("id"))
            if not item_id:
                continue
            self.feed_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(clean(item.get("type")), clean(item.get("priority")), clean(item.get("status")), clean(item.get("title"))),
            )
        if hasattr(self, "feed_detail") and not items:
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", "当前没有待处理建议。点击“扫描当前项目”让 Agent 主动检查文献、任务、记忆和缺口。")

    def load_agent_inbox(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            return

        def task():
            status, body = self.api.get("/research-os/agent/inbox?" + urllib.parse.urlencode({"project_id": project_id, "limit": 80}), timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body.get("items", []) if isinstance(body, dict) else []

        def done(items):
            self.render_agent_inbox(items)
            self.load_agent_tasks()
            self.status_text.set(f"Research Feed：{len(items)} 条")

        self.run_async(task, done, self._show_error)

    def render_agent_tasks(self, tasks: list[dict]) -> None:
        if not hasattr(self, "agent_task_tree"):
            return
        self.agent_tasks = tasks
        self.agent_task_tree.delete(*self.agent_task_tree.get_children())
        for task in tasks:
            task_id = clean(task.get("task_id") or task.get("id"))
            if not task_id:
                continue
            self.agent_task_tree.insert(
                "",
                tk.END,
                iid=task_id,
                values=(clean(task.get("task_type")), clean(task.get("status")), clean(task.get("priority")), clean(task.get("next_action"))[:120]),
            )

    def load_agent_tasks(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            return

        def task():
            status, body = self.api.get("/research-os/tasks?" + urllib.parse.urlencode({"project_id": project_id, "limit": 80}), timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body.get("tasks", []) if isinstance(body, dict) else []

        def done(tasks):
            self.render_agent_tasks(tasks)

        self.run_async(task, done, self._show_error)

    def selected_agent_task(self) -> dict:
        if not hasattr(self, "agent_task_tree"):
            return {}
        selection = self.agent_task_tree.selection()
        if not selection:
            return {}
        task_id = clean(selection[0])
        return next((task for task in self.agent_tasks if clean(task.get("task_id") or task.get("id")) == task_id), {})

    def on_agent_task_selected(self, _event=None) -> None:
        task = self.selected_agent_task()
        if not task:
            return
        self.active_agent_task_id = clean(task.get("task_id") or task.get("id"))
        self.feed_detail.delete("1.0", tk.END)
        self.feed_detail.insert("1.0", self.format_agent_task(task))

    def format_agent_task(self, task: dict) -> str:
        return "\n".join(
            [
                f"任务：{clean(task.get('task_type'))}",
                f"状态：{clean(task.get('status'))} | 优先级：{clean(task.get('priority'))}",
                f"ID：{clean(task.get('task_id') or task.get('id'))}",
                "",
                f"下一步：{clean(task.get('next_action')) or '等待 Agent 判断'}",
                "",
                "输入",
                pretty(task.get("input") or {}),
                "",
                "进度",
                pretty(task.get("progress") or {}),
                "",
                "产物",
                pretty(task.get("artifacts") or []),
                "",
                f"错误：{clean(task.get('error')) or '无'}",
            ]
        )

    def run_selected_agent_task(self) -> None:
        task = self.selected_agent_task()
        task_id = clean(task.get("task_id") or task.get("id"))
        if not task_id:
            self._show_error("请先选择一个 Agent Task。")
            return
        self.status_text.set("正在运行选中任务")

        def work():
            status, body = self.api.post(f"/research-os/tasks/{urllib.parse.quote(task_id)}/run", {"approved": True}, timeout=180)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("任务已推进")
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", pretty(body))
            self.load_agent_tasks()
            self.load_agent_inbox()

        self.run_async(work, done, self._show_error)

    def cancel_selected_agent_task(self) -> None:
        task = self.selected_agent_task()
        task_id = clean(task.get("task_id") or task.get("id"))
        if not task_id:
            self._show_error("请先选择一个 Agent Task。")
            return
        if not messagebox.askyesno("取消任务", "取消选中的 Agent Task？不会删除已经产生的文件。"):
            return

        def work():
            status, body = self.api.post(f"/research-os/tasks/{urllib.parse.quote(task_id)}/cancel", {"reason": "cancelled from client"}, timeout=90)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("任务已取消")
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", pretty(body))
            self.load_agent_tasks()

        self.run_async(work, done, self._show_error)

    def run_agent_heartbeat(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return
        self.status_text.set("正在自动推进任务")
        if hasattr(self, "feed_detail"):
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", "正在观察 workspace、规划任务、自动推进低风险任务，并更新 Research Feed。")

        def task():
            status, body = self.api.post("/research-os/agent/heartbeat", {"project_id": project_id, "trigger": "manual", "auto_run_low_risk": True}, timeout=180)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("自动推进任务完成")
            if hasattr(self, "feed_detail"):
                self.feed_detail.delete("1.0", tk.END)
                self.feed_detail.insert("1.0", self.format_heartbeat_result(body))
            self.render_agent_inbox(body.get("research_feed") or [])
            self.load_agent_tasks()
            self.update_agent_workspace_cards({"workspace_state": body.get("workspace_state", {}), "next_actions": []})
            if self.developer_mode.get():
                self.set_context({"agent_heartbeat": body})

        self.run_async(task, done, self._show_error)

    def run_research_watcher(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return
        self.status_text.set("正在扫描当前项目")
        if hasattr(self, "feed_detail"):
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", "正在读取 workspace-state、文献、KB、任务、记忆和失败记录。")

        def task():
            status, body = self.api.post("/research-os/agent/watch-project", {"project_id": project_id, "trigger": "manual"}, timeout=120)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            items = body.get("inbox_items", []) if isinstance(body, dict) else []
            self.render_agent_inbox(items)
            self.update_agent_workspace_cards({"workspace_state": body.get("workspace_state", {}), "next_actions": body.get("recommended_actions", [])})
            if hasattr(self, "feed_detail"):
                self.feed_detail.delete("1.0", tk.END)
                self.feed_detail.insert("1.0", self.format_watcher_result(body))
            self.set_context({"watcher_result": body})
            self.status_text.set(f"项目扫描完成：{len(items)} 条建议")

        self.run_async(task, done, self._show_error)

    def run_scheduler_once(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()
        if not project_id:
            self._show_error("请先选择项目。")
            return
        self.status_text.set("正在运行调度和联网 Scout")
        if hasattr(self, "feed_detail"):
            self.feed_detail.delete("1.0", tk.END)
            self.feed_detail.insert("1.0", "正在触发一次自动观察；如项目具备关键词且没有运行中文献任务，会启动受限数量的联网文献 Scout。")

        def task():
            status, body = self.api.post("/research-os/agent/scheduler/run", {"project_id": project_id, "force": True}, timeout=120)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("调度运行完成")
            if hasattr(self, "feed_detail"):
                self.feed_detail.delete("1.0", tk.END)
                self.feed_detail.insert("1.0", self.format_scheduler_result(body))
            self.load_agent_inbox()
            self.set_context({"scheduler_run": body})

        self.run_async(task, done, self._show_error)

    def load_scheduler_status(self) -> None:
        project_id = self.current_project_id(self.agent_project) or self.default_project_id()

        def task():
            query = {"project_id": project_id} if project_id else {}
            suffix = "?" + urllib.parse.urlencode(query) if query else ""
            status, body = self.api.get("/research-os/agent/scheduler/status" + suffix, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("调度状态已读取")
            if hasattr(self, "feed_detail"):
                self.feed_detail.delete("1.0", tk.END)
                self.feed_detail.insert("1.0", self.format_scheduler_status(body))
            self.set_context({"scheduler_status": body})

        self.run_async(task, done, self._show_error)

    def format_scheduler_result(self, body: dict) -> str:
        lines = [f"调度完成：检查项目 {body.get('checked_projects', 0)} 个。"]
        for outcome in body.get("outcomes") or []:
            watcher = outcome.get("watcher") or {}
            scout = outcome.get("literature_scout") or {}
            lines.append("")
            lines.append(clean(watcher.get("project_state_summary")) or f"项目：{clean(outcome.get('project_id'))}")
            lines.append("联网 Scout：" + ("已启动" if scout.get("started") else clean(scout.get("reason") or scout.get("error") or "未启动")))
            if scout.get("keywords"):
                lines.append("关键词：" + " / ".join(clean(item) for item in scout.get("keywords") or []))
            if scout.get("skill_run_id"):
                lines.append(f"SkillRun：{clean(scout.get('skill_run_id'))}")
        return "\n".join(lines)

    def format_heartbeat_result(self, body: dict) -> str:
        lines = [
            "Agent Heartbeat",
            "",
            f"新建任务：{len(body.get('created_tasks') or [])}",
            f"自动推进：{len(body.get('auto_run_results') or [])}",
            f"等待用户确认：{len(body.get('waiting_for_user') or [])}",
            f"Research Feed：{len(body.get('research_feed') or [])}",
        ]
        safety = body.get("safety_policy") or {}
        lines.extend(["", "自动任务", ", ".join(safety.get("auto_executable") or []) or "无"])
        lines.extend(["", "需要确认", ", ".join(safety.get("requires_user_confirmation") or []) or "无"])
        if body.get("created_tasks"):
            lines.append("")
            lines.append("创建的任务")
            for task in body.get("created_tasks") or []:
                lines.append(f"- {clean(task.get('task_type'))}: {clean(task.get('status'))} | {clean(task.get('next_action'))}")
        if body.get("auto_run_results"):
            lines.append("")
            lines.append("自动推进结果")
            for item in body.get("auto_run_results") or []:
                task = item.get("task") or {}
                lines.append(f"- {clean(task.get('task_type'))}: {'完成' if item.get('ok') else '失败'} {clean(item.get('error'))}")
        return "\n".join(lines)

    def format_scheduler_status(self, body: dict) -> str:
        lines = [
            f"后台调度：{'开启' if body.get('enabled') else '关闭'}",
            f"线程：{'运行中' if body.get('thread_alive') else '未运行'}",
        ]
        last = body.get("last_run") or {}
        lines.append(f"最近运行：{clean(last.get('last_run_at')) or '暂无'} | {clean(last.get('status')) or 'unknown'}")
        if clean(last.get("last_error")):
            lines.append(f"错误：{clean(last.get('last_error'))}")
        states = body.get("watch_states") or []
        if states:
            lines.append("")
            lines.append("项目观察配置：")
            for state in states[:8]:
                lines.append(
                    f"- {clean(state.get('project_id'))}: enabled={state.get('enabled')} scout={state.get('auto_literature_scout')} "
                    f"watch={state.get('watch_interval_minutes')}min scout={state.get('literature_scout_interval_minutes')}min "
                    f"last_watch={clean(state.get('last_watch_at')) or 'never'}"
                )
        return "\n".join(lines)

    def selected_feed_item(self) -> dict:
        if not hasattr(self, "feed_tree"):
            return {}
        selection = self.feed_tree.selection()
        if not selection:
            return {}
        item_id = clean(selection[0])
        return next((item for item in self.feed_items if clean(item.get("id")) == item_id), {})

    def format_feed_item(self, item: dict) -> str:
        sources = item.get("related_sources") or []
        actions = item.get("actions") or []
        lines = [
            clean(item.get("title")),
            "",
            clean(item.get("message")),
            "",
            f"类型：{clean(item.get('type'))}    优先级：{clean(item.get('priority'))}    状态：{clean(item.get('status'))}",
        ]
        if sources:
            lines.append("")
            lines.append("来源：")
            for source in sources[:8]:
                title = clean(source.get("title") or source.get("source_type") or source.get("id"))
                reason = clean(source.get("reason"))
                lines.append(f"- {title}" + (f"：{reason}" if reason else ""))
        if actions:
            lines.append("")
            lines.append("可执行动作：")
            for action in actions:
                lines.append(f"- {clean(action.get('label')) or clean(action.get('action'))}")
        return "\n".join(lines)

    def format_watcher_result(self, body: dict) -> str:
        lines = [clean(body.get("project_state_summary")) or "项目扫描完成。"]
        tags = body.get("project_state_tags") or []
        if tags:
            lines.append("")
            lines.append("状态标签：" + " / ".join(clean(item) for item in tags if clean(item)))
        gaps = body.get("knowledge_gaps") or []
        if gaps:
            lines.append("")
            lines.append("主要缺口：")
            for gap in gaps[:5]:
                lines.append(f"- {clean(gap.get('gap'))}")
        papers = body.get("papers_to_read") or []
        if papers:
            lines.append("")
            lines.append("优先阅读：")
            for paper in papers[:5]:
                lines.append(f"- {clean(paper.get('title'))}")
        questions = body.get("questions_for_user") or []
        if questions:
            lines.append("")
            lines.append("需要你确认：")
            for question in questions[:3]:
                lines.append(f"- {clean(question)}")
        return "\n".join(lines)

    def on_feed_selected(self, _event=None) -> None:
        item = self.selected_feed_item()
        if not item:
            return
        self.active_feed_item_id = clean(item.get("id"))
        self.feed_detail.delete("1.0", tk.END)
        self.feed_detail.insert("1.0", self.format_feed_item(item))
        for child in self.feed_action_frame.winfo_children():
            child.destroy()
        for action in (item.get("actions") or [])[:4]:
            label = clean(action.get("label")) or clean(action.get("action")) or "执行"
            tk.Button(
                self.feed_action_frame,
                text=label,
                command=lambda item_action=action: self.run_feed_action(item_action),
                bg=BG_ELEVATED,
                fg=TEXT_1,
                activebackground=BG_HOVER,
                activeforeground=TEXT_1,
                relief="flat",
                bd=0,
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(fill="x", pady=(0, 6))

    def update_selected_feed_item(self, status_value: str) -> None:
        item = self.selected_feed_item()
        item_id = clean(item.get("id"))
        if not item_id:
            self._show_error("请先选择一条 Feed。")
            return

        def task():
            status, body = self.api.put(f"/research-os/agent/inbox/{urllib.parse.quote(item_id)}", {"status": status_value}, timeout=60)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body.get("item", {}) if isinstance(body, dict) else {}

        def done(_item):
            self.status_text.set("Research Feed 已更新")
            self.load_agent_inbox()

        self.run_async(task, done, self._show_error)

    def run_feed_action(self, action: dict) -> None:
        action_name = clean(action.get("action"))
        skill_id = clean(action.get("skill_id"))
        if action_name == "run_skill" and skill_id == "core_keyword_research_harvest":
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            keywords = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
            if keywords:
                self.lit_keywords.set("\\".join(clean(item) for item in keywords if clean(item)))
            self.show_view("literature")
            return
        if action_name == "run_skill" and skill_id:
            if "kb" in skill_id.lower() or "research-kb" in skill_id.lower():
                self.show_view("knowledge")
                self.build_kb()
            else:
                self.show_view("skills")
                self.skill_payload.delete("1.0", tk.END)
                self.skill_payload.insert("1.0", pretty({"project_id": self.current_project_id(self.agent_project) or self.default_project_id()}))
            return
        if action_name == "ask_agent":
            message = clean(action.get("message")) or clean(action.get("label"))
            self.show_view("agent")
            self.set_agent_message_and_send(message or "解释这条 Research Feed。")
            return
        if action_name == "open_watched_folder":
            os.startfile(str(AGENT_ROOT / "research_os_files"))
            return
        if action_name == "open_reference":
            self.show_view("knowledge")
            return
        if action_name == "watch_project":
            self.run_research_watcher()
            return
        self.show_view("agent")
        self.set_agent_message_and_send(clean(action.get("message")) or clean(action.get("label")) or "继续。")

    def chat_response_intent(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        task_spec = body.get("task_spec") if isinstance(body.get("task_spec"), dict) else {}
        return clean(body.get("intent_type") or body.get("intent") or task_spec.get("intent"))

    def chat_response_text(self, body: dict) -> str:
        if not isinstance(body, dict):
            return "我暂时没有收到有效回复。"
        if body.get("_client_route") == "dual_agent":
            return self.summarize_dual_agent_response(body)
        return clean(body.get("assistant_text") or body.get("answer") or body.get("message") or self.format_user_answer(body))

    def chat_task_created(self, body: dict) -> bool:
        if not isinstance(body, dict):
            return False
        if body.get("task_created") is True:
            return True
        if body.get("task") or body.get("task_id"):
            return True
        if body.get("_client_route") == "dual_agent":
            result = body.get("execution_result") or {}
            return bool(clean(result.get("skillrun_id")) or clean(result.get("task_id")))
        return False

    def chat_task_card_text(self, body: dict) -> str:
        if body.get("_client_route") == "dual_agent":
            task_spec = body.get("task_spec") or {}
            result = body.get("execution_result") or {}
            title = clean(task_spec.get("user_query")) or "AURA 任务"
            status = self.user_status_label(clean(result.get("status")) or "created")
            return f"任务卡片\n任务：{title}\n状态：{status}\n你可以在“任务”页查看进度。"
        task = body.get("task") if isinstance(body.get("task"), dict) else {}
        title = clean(task.get("title") or body.get("task_title") or body.get("title")) or "AURA 任务"
        status = self.user_status_label(clean(task.get("status") or body.get("task_status")) or "created")
        return f"任务卡片\n任务：{title}\n状态：{status}\n你可以在“任务”页查看进度。"

    def render_chat_response(self, body: dict) -> None:
        if hasattr(self, "agent_inline_actions"):
            for child in self.agent_inline_actions.winfo_children():
                child.destroy()
        intent = self.chat_response_intent(body)
        text = self.chat_response_text(body)
        if text:
            self.append_agent_chat(APP_NAME, text, body.get("citations") or [])
        if self.chat_task_created(body):
            self.append_agent_chat("任务", self.chat_task_card_text(body))
            self.load_user_tasks_summary()
        elif intent in {"research_task", "start_skill_request"}:
            actions = body.get("suggested_actions") or body.get("actions") or []
            labels: list[str] = []
            for item in actions[:4]:
                if isinstance(item, dict):
                    labels.append(clean(item.get("label") or item.get("title") or item.get("action")))
                else:
                    labels.append(clean(item))
            labels = [label for label in labels if label]
            if labels:
                self.append_agent_chat("AURA", "可以继续选择：" + "、".join(labels))
                if hasattr(self, "agent_inline_actions"):
                    for label in labels:
                        tk.Button(
                            self.agent_inline_actions,
                            text=label,
                            command=lambda value=label: self.set_agent_message_and_send(value),
                            bg=ACCENT_DIM,
                            fg=ACCENT,
                            activebackground=BG_HOVER,
                            activeforeground=ACCENT,
                            relief="flat",
                            bd=0,
                            padx=12,
                            pady=6,
                            cursor="hand2",
                            font=("Microsoft YaHei UI", 9),
                        ).pack(side="left", padx=(0, 8))
            if body.get("requires_confirmation") or body.get("needs_confirmation"):
                self.append_agent_chat("AURA", "这个任务需要你确认后再启动。")
                if hasattr(self, "agent_inline_actions"):
                    tk.Button(
                        self.agent_inline_actions,
                        text="确认启动任务",
                        command=lambda: self.set_agent_message_and_send("确认启动任务。"),
                        bg=ACCENT,
                        fg="white",
                        activebackground="#5f7f68",
                        activeforeground="white",
                        relief="flat",
                        bd=0,
                        padx=14,
                        pady=6,
                        cursor="hand2",
                        font=("Microsoft YaHei UI", 9, "bold"),
                    ).pack(side="left", padx=(0, 8))
        elif intent == "file_required":
            self.append_agent_chat("AURA", "这一步需要文件。你可以点击底部“上传”，或把数据内容粘贴到对话里。")
        elif intent == "project_required":
            self.append_agent_chat("AURA", "这一步需要先选择或创建项目。我不会把刚才的输入自动改成项目名。")

    def send_agent_message(self) -> None:
        message = self.agent_message.get("1.0", tk.END).strip()
        payload = {
            "conversation_id": self.agent_conversation_id,
            "project_id": self.current_project_id(self.agent_project) or self.default_project_id(),
            "message": message,
            "save_to_memory": bool(self.agent_save_to_memory.get()),
            "previous_intent": self.agent_last_intent,
        }
        if not payload["message"]:
            self._show_error("请输入要发送给 AURA 的内容。")
            return
        self.status_text.set("AURA 正在回复")
        self.append_agent_chat("你", message)
        self.agent_message.delete("1.0", tk.END)
        self.agent_detail.delete("1.0", tk.END)
        self.agent_detail.insert("1.0", "正在检索项目记录、资料库和任务状态。")

        def task():
            status, body = self.api.post("/research-os/agent/chat", payload, timeout=180)
            if status != 200:
                raise RuntimeError(self.format_user_error(pretty(body)))
            return body

        def done(body):
            if body.get("_client_route") == "dual_agent":
                self.status_text.set("AURA 已完成任务处理")
                self.render_chat_response(body)
                self.agent_detail.delete("1.0", tk.END)
                detail = self.format_dual_agent_detail(body) if self.developer_mode.get() else self.format_chat_context_summary(body)
                self.agent_detail.insert("1.0", detail)
                if self.developer_mode.get():
                    self.set_context(body)
                self.update_dual_status("Dual Agent Ready", ACCENT)
                return
            matched_skill = body.get("matched_skill") or body.get("_resolved_skill_name") or ""
            if self.developer_mode.get():
                self.status_text.set(f"AURA 已回复 | {body.get('llm', {}).get('model', '')} | {matched_skill} | validation: {body.get('validation_status')}")
            else:
                self.status_text.set("AURA 已回复")
            self.render_chat_response(body)
            self.agent_conversation_id = clean(body.get("conversation_id")) or self.agent_conversation_id
            if self.agent_conversation_id:
                self.client_cache["agent_conversation_id"] = self.agent_conversation_id
                self.save_client_cache()
            self.agent_last_intent = self.chat_response_intent(body)
            if body.get("research_feed"):
                self.render_agent_inbox(body.get("research_feed") or [])
            self.update_agent_workspace_cards(body)
            self.agent_detail.delete("1.0", tk.END)
            detail = self.format_agent_detail(body) if self.developer_mode.get() else self.format_chat_context_summary(body)
            self.agent_detail.insert("1.0", detail)
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def agent_retrieve_context(self) -> None:
        payload = {"project_id": self.current_project_id(self.agent_project) or self.default_project_id(), "query": self.agent_message.get("1.0", tk.END).strip() or "current project status", "limit": 20}

        def task():
            status, body = self.api.post("/research-os/memory/context", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("项目上下文已读取")
            self.agent_answer.delete("1.0", tk.END)
            context_text = clean(body.get("context_text") if isinstance(body, dict) else "")
            self.agent_answer.insert("1.0", context_text or self.format_memory_for_task(body if isinstance(body, dict) else {}))
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def agent_rag_memory(self) -> None:
        payload = {"project_id": self.current_project_id(self.agent_project) or self.default_project_id(), "question": self.agent_message.get("1.0", tk.END).strip() or "当前项目最相关的知识是什么？"}

        def task():
            status, body = self.api.post("/research-os/rag/query", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body

        def done(body):
            self.status_text.set("资料库已返回回答")
            self.agent_answer.delete("1.0", tk.END)
            answer = clean(body.get("answer") if isinstance(body, dict) else "")
            self.agent_answer.insert("1.0", answer or self.format_sources_for_task(body if isinstance(body, dict) else {}))
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def run_selected_skill(self) -> None:
        selected = self.skill_tree.selection()
        if not selected:
            self._show_error("请先选择一个 Skill。")
            return
        skill_id = selected[0]
        try:
            payload = json.loads(self.skill_payload.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as exc:
            self._show_error(f"JSON 格式错误：{exc}")
            return
        if self.current_project_id(self.skill_project) and not payload.get("project_id"):
            payload["project_id"] = self.current_project_id(self.skill_project)
        def task():
            status, body = self.api.post(f"/research-os/skills/{urllib.parse.quote(skill_id, safe='')}/run", payload, timeout=45)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.skill_run_box.delete("1.0", tk.END)
            self.skill_run_box.insert("1.0", pretty(body))
            self.set_context(body)
            self.load_recent_skill_runs()
        self.run_async(task, done, self._show_error)

    def run_skill_by_handler(self, handler_text: str, payload: dict) -> None:
        skill_id = self._find_skill_id(handler_text) or self._find_skill_id(handler_text.lower())
        if not skill_id:
            self._show_error(f"未找到对应 Skill：{handler_text}")
            return
        def task():
            status, body = self.api.post(f"/research-os/skills/{urllib.parse.quote(skill_id, safe='')}/run", payload, timeout=45)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.status_text.set(f"Skill 已运行：{skill_id}")
            self.set_context(body)
            self.load_recent_skill_runs()
        self.run_async(task, done, self._show_error)

    def run_weekly_report(self) -> None:
        self.run_skill_by_handler("WeeklyReportSkill", {"project_id": self.default_project_id(), "report_type": "weekly_report"})

    def run_gap_analysis(self) -> None:
        self.run_skill_by_handler("ProjectGapAnalysisSkill", {"project_id": self.default_project_id()})

    def run_conflict_detection(self) -> None:
        self.run_skill_by_handler("ConflictDetectionSkill", {"project_id": self.default_project_id()})

    def run_writing_assistant(self) -> None:
        payload = {"project_id": self.default_project_id(), "writing_task": "基于当前项目记忆生成一段写作草稿。"}
        def task():
            status, body = self.api.post("/research-os/writing/assist", payload)
            if status != 200:
                raise RuntimeError(pretty(body))
            return body
        def done(body):
            self.status_text.set("写作辅助已完成")
            if self.developer_mode.get():
                self.set_context(body)
        self.run_async(task, done, self._show_error)

    def organize_project_memory(self) -> None:
        payload = {"project_id": self.default_project_id(), "query": "整理当前项目记忆、结论、失败记录、决策和下一步建议", "limit": 30}
        if not payload["project_id"]:
            self._show_error("请先创建或选择一个项目。")
            return

        def task():
            status, context = self.api.post("/research-os/memory/context", payload)
            if status != 200:
                raise RuntimeError(pretty(context))
            memory_payload = {
                "memory_scope": "project",
                "project_id": payload["project_id"],
                "memory_type": "project_memory_summary",
                "title": "项目记忆整理",
                "content": context.get("context_text") or pretty(context),
                "structured_content": context,
                "source_type": "local_client",
                "trust_level": "raw_extracted",
            }
            mem_status, memory = self.api.post("/research-os/agent-memory", memory_payload)
            if mem_status != 200:
                raise RuntimeError(pretty(memory))
            return {"context": context, "memory": memory}

        def done(body):
            self.status_text.set("项目记忆已整理")
            if self.developer_mode.get():
                self.set_context(body)

        self.run_async(task, done, self._show_error)

    def default_project_id(self) -> str:
        cached = clean(self.client_cache.get("last_project_id"))
        if cached and (not self.project_id_to_label or cached in self.project_id_to_label):
            return cached
        for var in [self.project_choice, self.task_project, self.lit_project, self.file_project, self.data_project, self.exp_project, self.sample_project, self.memory_project, self.rag_project, self.skill_project, self.agent_project]:
            project_id = self.current_project_id(var)
            if project_id and (not self.project_id_to_label or project_id in self.project_id_to_label):
                return project_id
        return clean(self.project_cache[0].get("id")) if self.project_cache else ""

    def send_api_request(self) -> None:
        method = self.api_method.get().upper()
        path = self.api_path.get().strip() or "/health"
        try:
            payload = json.loads(self.api_payload.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as exc:
            self._show_error(f"JSON 格式错误：{exc}")
            return
        def task():
            return self.api.get(path) if method == "GET" else self.api.post(path, payload)
        def done(result):
            status, body = result
            self.api_response.delete("1.0", tk.END)
            self.api_response.insert("1.0", pretty({"status": status, "body": body}))
            self.set_context(body)
        self.run_async(task, done, self._show_error)

    def run(self) -> None:
        self.root.mainloop()


def data_literature_root() -> Path:
    path = AGENT_ROOT / "research_os_files" / "literature_harvest"
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    ResearchOSClientApp().run()
