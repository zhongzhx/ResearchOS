from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


explicit_env = os.environ.get("RESEARCHOS_ENV_FILE", "").strip()
if explicit_env:
    load_env_file(Path(explicit_env))
def resolve_workspace_root(script_path: Path) -> Path:
    for candidate in [script_path.parent, *script_path.parents]:
        if (candidate / "researchos_local_client.pyw").exists() and (candidate / "skills" / "researchos_skill_library").exists():
            return candidate
    return script_path.parents[2]


workspace_root = resolve_workspace_root(Path(__file__).resolve())
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))
load_env_file(workspace_root / ".env")
load_env_file(Path(__file__).resolve().parent / ".env")

from answer_kb import answer
from agent_memory import api as memory_api
from lab_agent_features import (
    add_research_interest,
    create_failure_record,
    delete_failure_record,
    delete_research_interest,
    extract_protocol,
    generate_sop,
    generate_weekly_digest,
    ingest_downloaded_pdfs_to_rag,
    ingest_rag_document,
    list_research_interests,
    list_weekly_digests,
    match_failure_records,
    parse_scientific_data,
    peer_review_simulation,
    query_rag,
    result_narrative,
    search_failure_records,
    update_failure_record,
    update_research_interest,
)
import research_memory_canonical as canonical_memory
import research_os_mvp as research_os
from researchos_agent_prompt import build_researchos_messages, researchos_prompt_info
from runtime_common import (
    article_detail,
    article_rows,
    browser_learning_rows,
    create_or_update_job,
    job_events,
    job_row,
    project_kb_root,
    stable_id,
    state_db,
    write_feedback,
)


class RuntimeConfig:
    def __init__(self, agent_root: Path) -> None:
        self.agent_root = agent_root.resolve()


CONFIG: RuntimeConfig
SCHEDULER_THREAD: threading.Thread | None = None
SCHEDULER_STOP = threading.Event()
SCHEDULER_LAST_RUN: dict[str, Any] = {"status": "not_started", "last_run_at": "", "last_error": ""}


def api_log_path() -> Path:
    path = CONFIG.agent_root / "logs" / "researchos_api.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def api_log(message: str) -> None:
    try:
        with api_log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def scheduler_enabled() -> bool:
    return os.environ.get("RESEARCHOS_WATCHER_SCHEDULER", "1").strip().lower() not in {"0", "false", "no", "off"}


def dual_agent_api_enabled() -> bool:
    return os.environ.get("RESEARCHOS_DUAL_AGENT_API_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def run_dual_agent_api(callback: Any) -> Any:
    previous = os.environ.get("RESEARCHOS_AGENT_ROOT")
    os.environ["RESEARCHOS_AGENT_ROOT"] = str(CONFIG.agent_root)
    try:
        return callback()
    finally:
        if previous is None:
            os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        else:
            os.environ["RESEARCHOS_AGENT_ROOT"] = previous


def scheduler_loop() -> None:
    global SCHEDULER_LAST_RUN
    initial_delay = int(os.environ.get("RESEARCHOS_WATCHER_INITIAL_DELAY_SECONDS", "10") or 10)
    poll_seconds = max(30, int(os.environ.get("RESEARCHOS_WATCHER_POLL_SECONDS", "300") or 300))
    if SCHEDULER_STOP.wait(initial_delay):
        return
    while not SCHEDULER_STOP.is_set():
        try:
            if scheduler_enabled():
                result = research_os.run_scheduled_research_watch(CONFIG.agent_root, force=False)
                SCHEDULER_LAST_RUN = {"status": "ok", "last_run_at": datetime.now().isoformat(timespec="seconds"), "last_error": "", "result": result}
                api_log(f"watcher scheduler run: checked={result.get('checked_projects')} outcomes={len(result.get('outcomes') or [])}")
            else:
                SCHEDULER_LAST_RUN = {"status": "disabled", "last_run_at": datetime.now().isoformat(timespec="seconds"), "last_error": ""}
        except Exception as exc:
            SCHEDULER_LAST_RUN = {"status": "error", "last_run_at": datetime.now().isoformat(timespec="seconds"), "last_error": str(exc)}
            api_log(f"watcher scheduler failed: {exc}\n{traceback.format_exc()}")
        SCHEDULER_STOP.wait(poll_seconds)


def start_scheduler_once() -> None:
    global SCHEDULER_THREAD
    if SCHEDULER_THREAD and SCHEDULER_THREAD.is_alive():
        return
    SCHEDULER_STOP.clear()
    SCHEDULER_THREAD = threading.Thread(target=scheduler_loop, name="researchos-watcher-scheduler", daemon=True)
    SCHEDULER_THREAD.start()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any] | list[Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_error(handler: BaseHTTPRequestHandler, exc: Exception) -> None:
    try:
        api_log(f"{handler.command} {handler.path} failed: {exc}\n{traceback.format_exc()}")
    except Exception:
        pass
    if isinstance(exc, KeyError):
        json_response(handler, 404, {"error": str(exc).strip("'")})
    elif isinstance(exc, (ValueError, FileNotFoundError, json.JSONDecodeError)):
        json_response(handler, 400, {"error": str(exc)})
    else:
        json_response(handler, 500, {"error": str(exc)})


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body or "{}")


def run_job_background(payload: dict[str, Any], job_id: str) -> None:
    script = Path(__file__).resolve().parent / "run_research_job.py"
    command = [
        sys.executable,
        str(script),
        "--project-name",
        payload["project_name"],
        "--query",
        payload["query"],
        "--agent-root",
        str(CONFIG.agent_root),
        "--max-results",
        str(int(payload.get("max_results", 20))),
        "--source",
        payload.get("source", "both"),
        "--job-id",
        job_id,
    ]
    if payload.get("email"):
        command.extend(["--email", payload["email"]])
    if payload.get("also_open_access"):
        command.append("--also-open-access")
    if payload.get("no_article_analysis"):
        command.append("--no-article-analysis")
    if payload.get("browser_fallback"):
        command.append("--browser-fallback")
    if payload.get("browser_learning"):
        command.append("--browser-learning")
    if payload.get("browser_learning_max_pages"):
        command.extend(["--browser-learning-max-pages", str(payload["browser_learning_max_pages"])])
    browser_learning_sites = payload.get("browser_learning_site") or payload.get("browser_learning_sites") or []
    if isinstance(browser_learning_sites, str):
        browser_learning_sites = [browser_learning_sites]
    for site in browser_learning_sites:
        command.extend(["--browser-learning-site", str(site)])
    if payload.get("browser_learning_session"):
        command.extend(["--browser-learning-session", payload["browser_learning_session"]])
    if payload.get("browser_profile"):
        command.extend(["--browser-profile", payload["browser_profile"]])
    if payload.get("browser_headed"):
        command.append("--browser-headed")
    if payload.get("browser_session"):
        command.extend(["--browser-session", payload["browser_session"]])
    if payload.get("browser_cdp_url"):
        command.extend(["--browser-cdp-url", payload["browser_cdp_url"]])
    if payload.get("from_year"):
        command.extend(["--from-year", str(payload["from_year"])])
    if payload.get("until_year"):
        command.extend(["--until-year", str(payload["until_year"])])
    if payload.get("memory_root"):
        command.extend(["--memory-root", payload["memory_root"]])
    if payload.get("memory_max_shard_bytes"):
        command.extend(["--memory-max-shard-bytes", str(payload["memory_max_shard_bytes"])])
    if payload.get("memory_max_entry_bytes"):
        command.extend(["--memory-max-entry-bytes", str(payload["memory_max_entry_bytes"])])
    subprocess.run(command, text=True, check=False)


class Handler(BaseHTTPRequestHandler):
    server_version = "ResearchAgentRuntime/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            json_response(self, 200, {"status": "ok", "state_db": str(state_db(CONFIG.agent_root)), "log_path": str(api_log_path())})
            return

        if path == "/research-os/runtime/status":
            try:
                json_response(self, 200, research_os.get_demo_runtime_status(CONFIG.agent_root, query.get("project_id", [""])[0]))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/demo/dual-agent":
            try:
                from backend.researchos.api import dual_agent_routes

                project_id = query.get("project_id", ["demo_project"])[0] or "demo_project"
                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.demo_dual_agent(project_id=project_id)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/self-evolution/pending-skills":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(dual_agent_routes.pending_skills))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/skills/resolver/check":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(dual_agent_routes.resolver_check))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/skills/catalog":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(dual_agent_routes.skill_catalog))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/skills/pipelines":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(dual_agent_routes.pipeline_registry))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/dashboard":
            try:
                json_response(self, 200, research_os.dashboard(CONFIG.agent_root))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/workflow-templates":
            json_response(self, 200, {"templates": research_os.workflow_templates()})
            return

        if path == "/research-os/agents":
            json_response(self, 200, {"agents": research_os.agent_registry()})
            return

        if path == "/research-os/skills":
            try:
                include_disabled = query.get("include_disabled", ["0"])[0].lower() in {"1", "true", "yes"}
                json_response(self, 200, {"skills": research_os.list_skills(CONFIG.agent_root, include_disabled=include_disabled)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/skill-runs":
            try:
                json_response(
                    self,
                    200,
                    {
                        "skill_runs": research_os.list_skill_runs(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            skill_id=query.get("skill_id", [""])[0],
                            status=query.get("status", [""])[0],
                            limit=int(query.get("limit", ["50"])[0] or 50),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/core-skills/integration-summary":
            try:
                json_response(self, 200, research_os.core_skill_integration_summary(CONFIG.agent_root))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/skill-deduplication-report":
            try:
                json_response(self, 200, research_os.imported_skill_deduplication_report(CONFIG.agent_root))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/tool-capabilities":
            try:
                json_response(self, 200, {"tool_capabilities": research_os.list_tool_capabilities(CONFIG.agent_root)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/execution-memory":
            try:
                json_response(
                    self,
                    200,
                    {
                        "execution_memory": research_os.list_execution_memory(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            skill_id=query.get("skill_id", [""])[0],
                            status=query.get("status", [""])[0],
                            limit=int(query.get("limit", ["100"])[0] or 100),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/search-tasks":
            try:
                json_response(self, 200, {"literature_search_tasks": research_os.list_literature_search_tasks(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["50"])[0] or 50))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/paper-requests":
            try:
                json_response(
                    self,
                    200,
                    {
                        "paper_requests": research_os.list_paper_requests(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            task_id=query.get("task_id", [""])[0],
                            status=query.get("status", [""])[0],
                            limit=int(query.get("limit", ["50"])[0] or 50),
                        ),
                        "watch_folder": str(research_os.paper_request_watch_folder(CONFIG.agent_root, query.get("project_id", [""])[0])),
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/unmatched-pdfs":
            try:
                json_response(
                    self,
                    200,
                    {
                        "unmatched_pdfs": research_os.list_unmatched_pdfs(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            status=query.get("status", [""])[0],
                            limit=int(query.get("limit", ["50"])[0] or 50),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/literature/search-tasks/") and path.endswith("/progress"):
            task_id = urllib.parse.unquote(path.split("/")[4])
            try:
                json_response(self, 200, research_os.get_literature_search_task_detail(CONFIG.agent_root, task_id))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/literature/search-tasks/"):
            task_id = urllib.parse.unquote(path.split("/")[4])
            try:
                json_response(self, 200, research_os.get_literature_search_task_detail(CONFIG.agent_root, task_id))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/searches":
            try:
                json_response(self, 200, {"literature_search_tasks": research_os.list_literature_search_tasks(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["50"])[0] or 50))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/references":
            try:
                json_response(
                    self,
                    200,
                    {
                        "references": research_os.list_references(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            search=query.get("search", [""])[0],
                            limit=int(query.get("limit", ["100"])[0] or 100),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/reference-chunks":
            try:
                json_response(
                    self,
                    200,
                    {
                        "reference_chunks": research_os.list_reference_chunks(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            reference_id=query.get("reference_id", [""])[0],
                            limit=int(query.get("limit", ["100"])[0] or 100),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/knowledge-base-entries":
            try:
                json_response(self, 200, {"knowledge_base_entries": research_os.list_knowledge_base_entries(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["100"])[0] or 100))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/rag-queries":
            try:
                json_response(self, 200, {"rag_queries": research_os.list_rag_queries(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["50"])[0] or 50))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/failure-logs":
            try:
                json_response(
                    self,
                    200,
                    {
                        "failure_logs": research_os.list_failure_logs(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            search=query.get("search", [""])[0],
                            limit=int(query.get("limit", ["100"])[0] or 100),
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/experiment-logs":
            try:
                json_response(self, 200, {"experiment_logs": research_os.list_experiment_logs(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["100"])[0] or 100))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/weekly-digest/configs":
            try:
                json_response(self, 200, {"weekly_digest_configs": research_os.list_weekly_digest_configs(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/weekly-digest/reports":
            try:
                json_response(self, 200, {"weekly_digest_reports": research_os.list_weekly_digest_reports(CONFIG.agent_root, query.get("project_id", [""])[0], int(query.get("limit", ["50"])[0] or 50))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/skill-runs/"):
            skill_run_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"skill_run": research_os.get_skill_run(CONFIG.agent_root, skill_run_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent-memory":
            try:
                include_disabled = query.get("include_disabled", ["0"])[0].lower() in {"1", "true", "yes"}
                json_response(
                    self,
                    200,
                    research_os.list_agent_memory(
                        CONFIG.agent_root,
                        scope=query.get("scope", [""])[0],
                        project_id=query.get("project_id", [""])[0],
                        include_disabled=include_disabled,
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/kit-templates":
            try:
                json_response(self, 200, {"kit_templates": research_os.list_kit_templates(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/data-contexts":
            try:
                status = query.get("status", query.get("context_status", [""]))[0]
                json_response(
                    self,
                    200,
                    {
                        "data_contexts": research_os.list_data_contexts(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            context_status=status,
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/under-contextualized-files":
            try:
                json_response(self, 200, {"files": research_os.list_under_contextualized_files(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/workflow-board":
            try:
                json_response(self, 200, research_os.workflow_board(CONFIG.agent_root, query.get("project_id", [""])[0]))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/projects":
            try:
                json_response(self, 200, {"projects": research_os.list_projects(CONFIG.agent_root), "grouped": research_os.list_projects_grouped(CONFIG.agent_root)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/workspace-state":
            try:
                json_response(self, 200, research_os.workspace_state(CONFIG.agent_root, query.get("project_id", [""])[0]))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/tasks":
            try:
                json_response(
                    self,
                    200,
                    research_os.list_agent_tasks(
                        CONFIG.agent_root,
                        project_id=query.get("project_id", [""])[0],
                        status=query.get("status", [""])[0],
                        task_type=query.get("task_type", [""])[0],
                        limit=int(query.get("limit", ["100"])[0] or 100),
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/tasks/"):
            task_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"task": research_os.get_agent_task(CONFIG.agent_root, task_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path in {"/research-os/agent/inbox", "/research-os/agent-feed"}:
            try:
                json_response(
                    self,
                    200,
                    research_os.list_agent_inbox(
                        CONFIG.agent_root,
                        query.get("project_id", [""])[0],
                        query.get("status", [""])[0],
                        int(query.get("limit", ["50"])[0] or 50),
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent/scheduler/status":
            try:
                payload = {
                    "enabled": scheduler_enabled(),
                    "thread_alive": bool(SCHEDULER_THREAD and SCHEDULER_THREAD.is_alive()),
                    "last_run": SCHEDULER_LAST_RUN,
                    "watch_states": research_os.watcher_scheduler_status(CONFIG.agent_root, query.get("project_id", [""])[0]).get("watch_states", []),
                }
                json_response(self, 200, payload)
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/experiments":
            try:
                json_response(self, 200, {"experiments": canonical_memory.list_experiments(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/samples":
            try:
                json_response(self, 200, {"samples": canonical_memory.list_samples(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/data-files":
            try:
                json_response(self, 200, {"data_files": canonical_memory.list_data_files(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/conclusions":
            try:
                json_response(
                    self,
                    200,
                    {"conclusions": canonical_memory.list_conclusions(CONFIG.agent_root, query.get("project_id", [""])[0], query.get("status", [""])[0])},
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/decisions":
            try:
                json_response(
                    self,
                    200,
                    {"decisions": canonical_memory.list_decisions(CONFIG.agent_root, query.get("project_id", [""])[0], query.get("status", [""])[0])},
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/failures":
            try:
                json_response(
                    self,
                    200,
                    {"failures": canonical_memory.list_failures(CONFIG.agent_root, query.get("project_id", [""])[0])},
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/context":
            try:
                json_response(
                    self,
                    200,
                    canonical_memory.build_research_memory_context(
                        CONFIG.agent_root,
                        {
                            "project_id": query.get("project_id", [""])[0],
                            "query": query.get("query", query.get("question", [""]))[0],
                            "memory_view_version": query.get("memory_view_version", [""])[0],
                            "limit": query.get("limit", ["30"])[0],
                        },
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/review-queue":
            try:
                json_response(
                    self,
                    200,
                    {
                        "review_queue": canonical_memory.list_memory_review_items(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            status=query.get("status", ["pending"])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/evidence-review"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(
                    self,
                    200,
                    research_os.list_evidence_review_items(
                        CONFIG.agent_root,
                        project_id,
                        {
                            "evidence_type": query.get("evidence_type", [""])[0],
                            "label": query.get("label", [""])[0],
                            "can_support_confirmed_claim": query.get("can_support_confirmed_claim", [""])[0],
                            "trust_level": query.get("trust_level", [""])[0],
                            "source_provider": query.get("source_provider", [""])[0],
                            "linked": query.get("linked", [""])[0],
                            "search": query.get("search", [""])[0],
                            "date_from": query.get("date_from", [""])[0],
                            "date_to": query.get("date_to", [""])[0],
                        },
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/claims/review"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(
                    self,
                    200,
                    research_os.list_claim_review_queue(
                        CONFIG.agent_root,
                        project_id,
                        status=query.get("status", [""])[0],
                        claim_type=query.get("claim_type", [""])[0],
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/status"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"project_status": research_os.get_project_status(CONFIG.agent_root, project_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/evidence/"):
            evidence_id = urllib.parse.unquote(path.removeprefix("/research-os/evidence/"))
            try:
                json_response(self, 200, {"evidence": research_os.get_evidence_item(CONFIG.agent_root, evidence_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"project": research_os.get_project_detail(CONFIG.agent_root, project_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/files":
            try:
                json_response(self, 200, {"files": research_os.list_files(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/files/") and path.endswith("/samples"):
            file_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.file_samples(CONFIG.agent_root, file_id))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/files/"):
            file_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"file": research_os.read_file_record(CONFIG.agent_root, file_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory":
            try:
                json_response(
                    self,
                    200,
                    research_os.search_memory(
                        CONFIG.agent_root,
                        {
                            "project_id": query.get("project_id", [""])[0],
                            "query": query.get("query", [""])[0],
                            "entity_type": query.get("entity_type", [""])[0],
                            "trust_level": query.get("trust_level", [""])[0],
                            "limit": query.get("limit", ["100"])[0],
                        },
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/protocols":
            try:
                json_response(self, 200, {"protocols": research_os.list_protocols(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/protocols/"):
            protocol_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"protocol": research_os.get_protocol(CONFIG.agent_root, protocol_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/workflows":
            try:
                json_response(self, 200, {"workflows": research_os.list_workflows(CONFIG.agent_root, query.get("project_id", [""])[0])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/conflicts":
            try:
                json_response(
                    self,
                    200,
                    {
                        "conflicts": research_os.list_conflicts(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            status=query.get("status", [""])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/reports":
            try:
                json_response(
                    self,
                    200,
                    {
                        "reports": research_os.list_reports(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            report_type=query.get("report_type", [""])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/claims":
            try:
                json_response(
                    self,
                    200,
                    {
                        "claims": research_os.list_claims(
                            CONFIG.agent_root,
                            project_id=query.get("project_id", [""])[0],
                            status=query.get("status", [""])[0],
                            claim_type=query.get("claim_type", [""])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"claim": research_os.get_claim_with_evidence(CONFIG.agent_root, claim_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/relationships":
            try:
                json_response(
                    self,
                    200,
                    research_os.relationship_query(
                        CONFIG.agent_root,
                        {
                            "project_id": query.get("project_id", [""])[0],
                            "source_type": query.get("source_type", [""])[0],
                            "source_id": query.get("source_id", [""])[0],
                            "target_type": query.get("target_type", [""])[0],
                            "relation": query.get("relation", [""])[0],
                        },
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/agent/system-prompt":
            include_prompt = query.get("include_prompt", ["0"])[0].lower() in {"1", "true", "yes"}
            prompt_language = query.get("prompt_language", ["en"])[0]
            prompt_policy = query.get("prompt_policy", [""])[0]
            try:
                json_response(
                    self,
                    200,
                    researchos_prompt_info(
                        include_prompt=include_prompt,
                        prompt_language=prompt_language,
                        prompt_policy=prompt_policy,
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/review-queue":
            try:
                json_response(
                    self,
                    200,
                    {
                        "review_queue": memory_api.list_review_queue(
                            CONFIG.agent_root,
                            user_id=query.get("user_id", [""])[0],
                            group_id=query.get("group_id", [""])[0],
                            status=query.get("status", ["pending"])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/memory/projects/") and path.endswith("/memory"):
            project_id = path.split("/")[3]
            include_archived = query.get("include_archived", ["0"])[0].lower() in {"1", "true", "yes"}
            try:
                json_response(self, 200, {"memory": memory_api.list_project_memory(CONFIG.agent_root, project_id, include_archived)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/memory/projects/") and path.endswith("/view"):
            project_id = path.split("/")[3]
            try:
                view = memory_api.get_current_project_view(CONFIG.agent_root, project_id)
                json_response(self, 200, {"project_view": view})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/memory/experiments/") and path.endswith("/memory"):
            experiment_id = path.split("/")[3]
            include_archived = query.get("include_archived", ["0"])[0].lower() in {"1", "true", "yes"}
            try:
                json_response(self, 200, {"memory": memory_api.list_experiment_memory(CONFIG.agent_root, experiment_id, include_archived)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-interests":
            project_name = query.get("project_name", [""])[0]
            try:
                json_response(self, 200, {"research_interests": list_research_interests(CONFIG.agent_root, project_name)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/weekly-digest":
            project_name = query.get("project_name", [""])[0]
            limit = int(query.get("limit", ["50"])[0] or 50)
            try:
                json_response(self, 200, {"digests": list_weekly_digests(CONFIG.agent_root, project_name, limit)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/failure-records":
            try:
                json_response(
                    self,
                    200,
                    {
                        "failure_records": search_failure_records(
                            CONFIG.agent_root,
                            query=query.get("search", [""])[0],
                            project=query.get("project", [""])[0],
                            research_field=query.get("research_field", [""])[0],
                            experiment_type=query.get("experiment_type", [""])[0],
                            tags=query.get("tags", [""])[0],
                        )
                    },
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/jobs/") and path.endswith("/events"):
            job_id = path.split("/")[2]
            json_response(self, 200, {"job_id": job_id, "events": job_events(CONFIG.agent_root, job_id)})
            return

        if path.startswith("/jobs/"):
            job_id = path.split("/")[2]
            row = job_row(CONFIG.agent_root, job_id)
            if not row:
                json_response(self, 404, {"error": "job not found"})
                return
            json_response(self, 200, row)
            return

        if path == "/articles":
            project_name = query.get("project_name", [""])[0]
            search = query.get("search", [""])[0]
            if not project_name:
                json_response(self, 400, {"error": "project_name is required"})
                return
            rows = article_rows(project_kb_root(CONFIG.agent_root, project_name), search=search)
            json_response(self, 200, {"articles": rows})
            return

        if path == "/browser-learning":
            project_name = query.get("project_name", [""])[0]
            search = query.get("search", [""])[0]
            if not project_name:
                json_response(self, 400, {"error": "project_name is required"})
                return
            rows = browser_learning_rows(project_kb_root(CONFIG.agent_root, project_name), search=search)
            json_response(self, 200, {"browser_learning_pages": rows})
            return

        if path.startswith("/articles/"):
            project_name = query.get("project_name", [""])[0]
            article_id = path.split("/")[2]
            if not project_name:
                json_response(self, 400, {"error": "project_name is required"})
                return
            detail = article_detail(project_kb_root(CONFIG.agent_root, project_name), article_id)
            if not detail:
                json_response(self, 404, {"error": "article not found"})
                return
            json_response(self, 200, detail)
            return

        json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            payload = read_json(self)
        except json.JSONDecodeError as exc:
            json_response(self, 400, {"error": f"invalid json: {exc}"})
            return

        if dual_agent_api_enabled() and path == "/api/agents/coordinator/run":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.coordinator_run(payload)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path.startswith("/api/brain/skillrun/") and path.endswith("/process"):
            try:
                from backend.researchos.api import dual_agent_routes

                skillrun_id = urllib.parse.unquote(path.removeprefix("/api/brain/skillrun/").removesuffix("/process").strip("/"))
                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.process_skillrun(skillrun_id)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path.startswith("/api/self-evolution/skills/") and path.endswith("/activate"):
            try:
                from backend.researchos.api import dual_agent_routes

                skill_name = urllib.parse.unquote(path.removeprefix("/api/self-evolution/skills/").removesuffix("/activate").strip("/"))
                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.activate_generated_skill(skill_name)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path.startswith("/api/self-evolution/skills/") and path.endswith("/reject"):
            try:
                from backend.researchos.api import dual_agent_routes

                skill_name = urllib.parse.unquote(path.removeprefix("/api/self-evolution/skills/").removesuffix("/reject").strip("/"))
                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.reject_generated_skill(skill_name, payload)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if dual_agent_api_enabled() and path == "/api/skills/route":
            try:
                from backend.researchos.api import dual_agent_routes

                json_response(self, 200, run_dual_agent_api(lambda: dual_agent_routes.route_skill_query(payload)))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/seed-demo":
            try:
                json_response(self, 200, research_os.seed_demo(CONFIG.agent_root))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/projects":
            try:
                json_response(self, 200, {"project": research_os.create_project(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/tasks":
            try:
                json_response(self, 200, {"task": research_os.create_agent_task(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/tasks/") and path.endswith("/run"):
            task_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.run_agent_task(CONFIG.agent_root, task_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/tasks/") and path.endswith("/cancel"):
            task_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"task": research_os.cancel_agent_task(CONFIG.agent_root, task_id, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent/heartbeat":
            try:
                json_response(self, 200, research_os.agent_heartbeat(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/experiments":
            try:
                json_response(self, 200, {"experiment": research_os.upsert_experiment(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/samples":
            try:
                json_response(self, 200, {"sample": research_os.upsert_sample(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/export-context"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            template = urllib.parse.parse_qs(parsed.query).get("template", [payload.get("template", "agent_handoff")])[0]
            try:
                json_response(self, 200, research_os.export_project_context(CONFIG.agent_root, project_id, template=template))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/archive"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"project": research_os.archive_project(CONFIG.agent_root, project_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/unarchive"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"project": research_os.unarchive_project(CONFIG.agent_root, project_id)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/clear"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(
                    self,
                    200,
                    research_os.clear_project(
                        CONFIG.agent_root,
                        project_id,
                        str(payload.get("scope") or "").strip() or "all",
                        dry_run=bool(payload.get("dry_run")),
                        confirmation=str(payload.get("confirmation") or "").strip(),
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/projects/") and path.endswith("/purge"):
            project_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(
                    self,
                    200,
                    research_os.purge_project(
                        CONFIG.agent_root,
                        project_id,
                        dry_run=bool(payload.get("dry_run")),
                        confirmation=str(payload.get("confirmation") or "").strip(),
                        confirmed_by_user=str(payload.get("confirmed_by_user") or "").strip(),
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/evidence/") and path.endswith("/mark-reviewed"):
            evidence_id = urllib.parse.unquote(path.removeprefix("/research-os/evidence/").removesuffix("/mark-reviewed").rstrip("/"))
            try:
                json_response(self, 200, research_os.mark_evidence_reviewed(CONFIG.agent_root, evidence_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/evidence/") and path.endswith("/link-claim"):
            evidence_id = urllib.parse.unquote(path.removeprefix("/research-os/evidence/").removesuffix("/link-claim").rstrip("/"))
            try:
                json_response(self, 200, research_os.link_evidence_item_to_claim(CONFIG.agent_root, evidence_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/files":
            try:
                json_response(self, 200, {"file": research_os.register_file(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/extraction":
            try:
                json_response(self, 200, research_os.run_extraction(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/search":
            try:
                json_response(self, 200, research_os.search_memory(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/merge":
            try:
                json_response(self, 200, {"memory": research_os.merge_memory_entities(CONFIG.agent_root, payload["target_id"], payload.get("source_ids") or [])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/protocols/parse":
            try:
                json_response(self, 200, research_os.parse_protocol_text(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/protocols":
            try:
                json_response(self, 200, {"protocol": research_os.store_protocol(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/protocol-execution-package":
            try:
                json_response(self, 200, {"execution_package": research_os.generate_execution_package(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/calculator":
            try:
                json_response(self, 200, {"result": research_os.run_reagent_calculator(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/workflows":
            try:
                json_response(self, 200, {"workflow": research_os.create_workflow(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/workflows/") and path.endswith("/run"):
            workflow_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.run_workflow(CONFIG.agent_root, workflow_id))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/workflow-steps/") and path.endswith("/approve"):
            step_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.approve_workflow_step(CONFIG.agent_root, step_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/conflicts/detect":
            try:
                json_response(self, 200, {"conflicts": research_os.detect_conflicts(CONFIG.agent_root, payload["project_id"])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/reports":
            try:
                json_response(self, 200, {"report": research_os.generate_report(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/reports/") and path.endswith("/claims"):
            report_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.generate_claims_from_report(CONFIG.agent_root, report_id))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/claims":
            try:
                json_response(self, 200, {"claim": research_os.create_claim(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/confirm"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.confirm_claim(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/reject"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.reject_claim(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/needs-more-evidence"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.mark_claim_needs_more_evidence(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/link-evidence"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.link_claim_evidence_from_payload(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/unlink-evidence"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.unlink_claim_evidence(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/claims/") and path.endswith("/supersede"):
            claim_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.supersede_claim(CONFIG.agent_root, claim_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/relationships/query":
            try:
                json_response(self, 200, research_os.relationship_query(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/skills":
            try:
                json_response(self, 200, {"skill": research_os.upsert_skill(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/prompt-routing/simulate":
            try:
                json_response(self, 200, research_os.simulate_prompt_routing(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/skills/") and path.endswith("/run"):
            skill_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.run_skill_example(CONFIG.agent_root, skill_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/execution-memory/") and path.endswith("/promote"):
            memory_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, research_os.promote_execution_memory_to_skill_draft(CONFIG.agent_root, memory_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/search-tasks":
            try:
                json_response(self, 200, research_os.create_literature_search_task(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/paper-requests":
            try:
                json_response(self, 200, {"paper_request": research_os.create_paper_request(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/paper-requests/generate":
            try:
                json_response(self, 200, research_os.generate_paper_requests_for_task(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/paper-requests/process-watch-folder":
            try:
                json_response(self, 200, research_os.process_user_downloaded_pdfs(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/literature/search-tasks/") and path.endswith("/cancel"):
            task_id = urllib.parse.unquote(path.split("/")[4])
            try:
                json_response(self, 200, research_os.cancel_literature_search_task(CONFIG.agent_root, task_id, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/expand-query":
            try:
                json_response(self, 200, research_os.expand_literature_query(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/keyword-mine":
            try:
                json_response(self, 200, research_os.keyword_mine(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/literature/search":
            try:
                json_response(self, 200, research_os.search_literature(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/references":
            try:
                json_response(self, 200, {"reference": research_os.import_reference(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/references/") and (path.endswith("/tag") or path.endswith("/tags")):
            reference_id = urllib.parse.unquote(path.split("/")[3])
            try:
                tags = payload.get("tags")
                reference = None
                if isinstance(tags, list):
                    for tag in tags:
                        reference = research_os.add_reference_tag(CONFIG.agent_root, reference_id, str(tag))
                else:
                    reference = research_os.add_reference_tag(CONFIG.agent_root, reference_id, str(payload.get("tag") or payload.get("name") or ""))
                json_response(self, 200, {"reference": reference})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/references/") and (path.endswith("/note") or path.endswith("/notes")):
            reference_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"reference": research_os.add_reference_note(CONFIG.agent_root, reference_id, str(payload.get("note") or payload.get("content") or ""))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/references/") and path.endswith("/mark-important"):
            reference_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"reference": research_os.mark_reference_important(CONFIG.agent_root, reference_id, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/references/") and path.endswith("/exclude"):
            reference_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"reference": research_os.exclude_reference(CONFIG.agent_root, reference_id, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/references/") and path.endswith("/link"):
            reference_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"link": research_os.link_reference_to_object(CONFIG.agent_root, reference_id, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/knowledge-base/build":
            try:
                json_response(self, 200, research_os.build_project_research_kb(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/rag/query":
            try:
                json_response(self, 200, research_os.query_research_rag(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/research-context/query":
            try:
                json_response(self, 200, canonical_memory.query_research_context(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/context":
            try:
                json_response(self, 200, canonical_memory.build_research_memory_context(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/extract-experiment":
            try:
                json_response(self, 200, canonical_memory.extract_experiment_memory(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/validator":
            try:
                json_response(self, 200, canonical_memory.validate_research_answer(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/claim-reference-links":
            try:
                json_response(self, 200, {"claim_reference_link": research_os.link_claim_reference(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/conclusions":
            try:
                json_response(self, 200, {"conclusion": research_os.upsert_conclusion(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/decisions":
            try:
                json_response(self, 200, {"decision": research_os.upsert_decision(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/failure-logs":
            try:
                json_response(self, 200, {"failure_log": research_os.create_failure_log(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/failures":
            try:
                json_response(self, 200, {"failure": research_os.create_failure_log(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/tasks/parse-natural-language":
            try:
                json_response(self, 200, research_os.parse_natural_language_task(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/tasks/create-from-natural-language":
            try:
                json_response(self, 200, research_os.create_task_from_natural_language(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/experiment-logs/ingest":
            try:
                json_response(self, 200, research_os.ingest_experiment_log(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/retrospectives/generate":
            try:
                json_response(self, 200, research_os.generate_retrospective(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/writing/assist":
            try:
                json_response(self, 200, research_os.writing_assistant(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path in {"/research-os/agent/chat", "/api/llm/chat"}:
            try:
                json_response(self, 200, research_os.agent_chat(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent/watch-project":
            try:
                json_response(self, 200, research_os.run_research_watcher(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/memory/user-correction":
            try:
                json_response(self, 200, research_os.record_user_correction(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/agent-feed/") and path.endswith("/accept"):
            item_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"item": research_os.update_agent_inbox_item(CONFIG.agent_root, item_id, {"status": "accepted"})})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path.startswith("/research-os/agent-feed/") and path.endswith("/dismiss"):
            item_id = urllib.parse.unquote(path.split("/")[3])
            try:
                json_response(self, 200, {"item": research_os.update_agent_inbox_item(CONFIG.agent_root, item_id, {"status": "dismissed"})})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent/scheduler/run":
            try:
                json_response(
                    self,
                    200,
                    research_os.run_scheduled_research_watch(
                        CONFIG.agent_root,
                        force=bool(payload.get("force", True)),
                        project_id=str(payload.get("project_id") or ""),
                    ),
                )
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/weekly-digest/configs":
            try:
                json_response(self, 200, {"weekly_digest_config": research_os.upsert_weekly_digest_config(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/weekly-digest/generate":
            try:
                json_response(self, 200, research_os.generate_weekly_project_digest(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/agent-memory":
            try:
                json_response(self, 200, {"memory": research_os.create_agent_memory_entry(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-os/kit-templates/parse":
            try:
                json_response(self, 200, {"kit_template": research_os.parse_kit_template(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/projects":
            project_name = payload.get("project_name")
            if not project_name:
                json_response(self, 400, {"error": "project_name is required"})
                return
            kb_root = project_kb_root(CONFIG.agent_root, project_name)
            kb_root.mkdir(parents=True, exist_ok=True)
            json_response(self, 200, {"project_name": project_name, "kb_root": str(kb_root)})
            return

        if path == "/agent/messages":
            try:
                json_response(self, 200, {"messages": build_researchos_messages(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/create":
            try:
                json_response(self, 200, {"memory": memory_api.create_memory(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/retrieve":
            try:
                json_response(self, 200, {"memory": memory_api.retrieve_memory(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/context":
            try:
                json_response(self, 200, {"memory_context": memory_api.build_memory_context(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/consolidate":
            try:
                json_response(self, 200, memory_api.consolidate_memory(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/extract":
            try:
                json_response(self, 200, memory_api.extract_and_queue_if_needed(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/archive":
            try:
                memory_id = payload.get("memory_id") or payload.get("id")
                if not memory_id:
                    raise ValueError("memory_id is required")
                json_response(self, 200, {"memory": memory_api.archive_memory(CONFIG.agent_root, str(memory_id))})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/groups":
            try:
                json_response(self, 200, {"group": memory_api.create_group(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/projects":
            try:
                json_response(self, 200, {"project": memory_api.create_project(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/experiments":
            try:
                json_response(self, 200, {"experiment": memory_api.create_experiment(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/samples":
            try:
                json_response(self, 200, {"sample": memory_api.create_sample(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/protocols":
            try:
                json_response(self, 200, {"protocol": memory_api.create_protocol(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/data-files":
            try:
                json_response(self, 200, {"data_file": memory_api.register_data_file(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/data-files/link-project":
            try:
                json_response(self, 200, {"data_file": memory_api.link_file_to_project(CONFIG.agent_root, payload["file_id"], payload["project_id"])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/memory/data-files/link-experiment":
            try:
                json_response(self, 200, {"data_file": memory_api.link_file_to_experiment(CONFIG.agent_root, payload["file_id"], payload["experiment_id"])})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/research-interests":
            try:
                json_response(self, 200, {"research_interest": add_research_interest(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/weekly-digest":
            try:
                json_response(self, 200, {"digest": generate_weekly_digest(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/protocol-extract":
            try:
                json_response(self, 200, {"protocol": extract_protocol(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/sop-generate":
            try:
                json_response(self, 200, {"sop": generate_sop(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/failure-records":
            try:
                json_response(self, 200, {"failure_record": create_failure_record(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/failure-records/match":
            try:
                json_response(self, 200, match_failure_records(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/peer-review":
            try:
                json_response(self, 200, {"review": peer_review_simulation(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/data-parse":
            try:
                json_response(self, 200, {"parsed_table": parse_scientific_data(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/result-narrative":
            try:
                json_response(self, 200, {"narrative": result_narrative(payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/rag/documents":
            try:
                json_response(self, 200, {"document": ingest_rag_document(CONFIG.agent_root, payload)})
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/rag/ingest-pdfs":
            try:
                json_response(self, 200, ingest_downloaded_pdfs_to_rag(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/rag/query":
            try:
                json_response(self, 200, query_rag(CONFIG.agent_root, payload))
            except Exception as exc:
                handle_error(self, exc)
            return

        if path == "/search-jobs":
            project_name = payload.get("project_name")
            query = payload.get("query")
            if not project_name or not query:
                json_response(self, 400, {"error": "project_name and query are required"})
                return
            job_id = payload.get("job_id") or f"job_{stable_id(project_name, query)}"
            agent_root = CONFIG.agent_root
            job_root = agent_root / "jobs" / job_id
            kb_root = project_kb_root(agent_root, project_name)
            create_or_update_job(
                agent_root,
                job_id,
                project_name,
                query,
                "queued",
                job_root,
                kb_root,
                int(payload.get("max_results", 20)),
                payload.get("source", "both"),
            )
            thread = threading.Thread(target=run_job_background, args=(payload, job_id), daemon=True)
            thread.start()
            json_response(self, 202, {"job_id": job_id, "status": "queued"})
            return

        if path == "/kb/query":
            project_name = payload.get("project_name")
            question = payload.get("question") or payload.get("search")
            if not project_name or not question:
                json_response(self, 400, {"error": "project_name and question are required"})
                return
            text = answer(project_kb_root(CONFIG.agent_root, project_name), question, int(payload.get("limit", 8)))
            json_response(self, 200, {"answer": text})
            return

        if path == "/feedback":
            if not payload.get("project_name"):
                json_response(self, 400, {"error": "project_name is required"})
                return
            row = write_feedback(CONFIG.agent_root, payload)
            json_response(self, 200, {"feedback": row})
            return

        json_response(self, 404, {"error": "not found"})

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            payload = read_json(self)
            if path.startswith("/research-os/projects/"):
                project_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"project": research_os.update_project(CONFIG.agent_root, project_id, payload)})
                return
            if path.startswith("/research-os/memory/"):
                memory_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"memory": research_os.update_memory_entity(CONFIG.agent_root, memory_id, payload)})
                return
            if path.startswith("/research-os/data-contexts/"):
                context_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"data_context": research_os.update_data_context(CONFIG.agent_root, context_id, payload)})
                return
            if path.startswith("/research-os/skills/"):
                skill_id = urllib.parse.unquote(path.split("/")[3])
                status = payload.get("status")
                if status:
                    json_response(self, 200, {"skill": research_os.update_skill_status(CONFIG.agent_root, skill_id, str(status))})
                else:
                    payload["skill_id"] = skill_id
                    json_response(self, 200, {"skill": research_os.upsert_skill(CONFIG.agent_root, payload)})
                return
            if path.startswith("/research-os/references/"):
                reference_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"reference": research_os.update_reference(CONFIG.agent_root, reference_id, payload)})
                return
            if path.startswith("/research-os/agent-memory/"):
                entry_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"memory": research_os.update_agent_memory_entry(CONFIG.agent_root, entry_id, payload)})
                return
            if path.startswith("/research-os/agent/inbox/"):
                item_id = urllib.parse.unquote(path.split("/")[4])
                json_response(self, 200, {"item": research_os.update_agent_inbox_item(CONFIG.agent_root, item_id, payload)})
                return
            if path.startswith("/research-os/agent-feed/"):
                item_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"item": research_os.update_agent_inbox_item(CONFIG.agent_root, item_id, payload)})
                return
            if path.startswith("/research-os/agent/watch-state/"):
                project_id = urllib.parse.unquote(path.split("/")[4])
                json_response(self, 200, {"watch_state": research_os.configure_project_watch(CONFIG.agent_root, project_id, payload)})
                return
            if path.startswith("/research-os/kit-templates/"):
                template_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"kit_template": research_os.update_kit_template(CONFIG.agent_root, template_id, payload)})
                return
            if path.startswith("/research-os/conflicts/"):
                conflict_id = urllib.parse.unquote(path.split("/")[3])
                json_response(self, 200, {"conflict": research_os.resolve_conflict(CONFIG.agent_root, conflict_id, payload)})
                return
            if path.startswith("/memory/projects/"):
                project_id = path.split("/")[3]
                json_response(self, 200, {"project": memory_api.update_project(CONFIG.agent_root, project_id, payload)})
                return
            if path.startswith("/memory/experiments/"):
                experiment_id = path.split("/")[3]
                json_response(self, 200, {"experiment": memory_api.update_experiment(CONFIG.agent_root, experiment_id, payload)})
                return
            if path.startswith("/memory/samples/"):
                sample_id = path.split("/")[3]
                json_response(self, 200, {"sample": memory_api.update_sample(CONFIG.agent_root, sample_id, payload)})
                return
            if path.startswith("/memory/protocols/"):
                protocol_id = path.split("/")[3]
                json_response(self, 200, {"protocol": memory_api.update_protocol(CONFIG.agent_root, protocol_id, payload)})
                return
            if path.startswith("/memory/"):
                memory_id = path.split("/")[2]
                json_response(self, 200, {"memory": memory_api.update_memory(CONFIG.agent_root, memory_id, payload)})
                return
            if path.startswith("/research-interests/"):
                interest_id = path.split("/")[2]
                json_response(self, 200, {"research_interest": update_research_interest(CONFIG.agent_root, interest_id, payload)})
                return
            if path.startswith("/failure-records/"):
                record_id = path.split("/")[2]
                json_response(self, 200, {"failure_record": update_failure_record(CONFIG.agent_root, record_id, payload)})
                return
            json_response(self, 404, {"error": "not found"})
        except Exception as exc:
            handle_error(self, exc)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path.startswith("/memory/"):
                memory_id = path.split("/")[2]
                json_response(self, 200, memory_api.delete_memory(CONFIG.agent_root, memory_id))
                return
            if path.startswith("/research-interests/"):
                interest_id = path.split("/")[2]
                json_response(self, 200, delete_research_interest(CONFIG.agent_root, interest_id))
                return
            if path.startswith("/failure-records/"):
                record_id = path.split("/")[2]
                json_response(self, 200, delete_failure_record(CONFIG.agent_root, record_id))
                return
            if path.startswith("/research-os/projects/"):
                project_id = urllib.parse.unquote(path.split("/")[3])
                query = urllib.parse.parse_qs(parsed.query)
                json_response(
                    self,
                    200,
                    research_os.purge_project(
                        CONFIG.agent_root,
                        project_id,
                        dry_run=query.get("dry_run", ["false"])[0].lower() in {"1", "true", "yes", "on"},
                        confirmation=query.get("confirmation", [""])[0],
                    ),
                )
                return
            json_response(self, 404, {"error": "not found"})
        except Exception as exc:
            handle_error(self, exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local AURA Research API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--agent-root", required=True)
    args = parser.parse_args()

    global CONFIG
    CONFIG = RuntimeConfig(Path(args.agent_root))
    CONFIG.agent_root.mkdir(parents=True, exist_ok=True)
    api_log(f"AURA Research API starting at http://{args.host}:{args.port}; agent_root={CONFIG.agent_root}")
    start_scheduler_once()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AURA Research API listening at http://{args.host}:{args.port}")
    print(f"Agent root: {CONFIG.agent_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        SCHEDULER_STOP.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
