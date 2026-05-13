# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent
LEGACY_API_SCRIPT = WORKSPACE_ROOT / "research-agent-runtime" / "scripts" / "research_agent_api.py"
CANONICAL_API_SCRIPT = WORKSPACE_ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts" / "research_agent_api.py"
API_SCRIPT = LEGACY_API_SCRIPT if LEGACY_API_SCRIPT.exists() else CANONICAL_API_SCRIPT
WEB_ROOT = WORKSPACE_ROOT / "web_client"
AGENT_ROOT = Path(os.environ.get("RESEARCHOS_AGENT_ROOT", str(WORKSPACE_ROOT / "agent_data")))
API_HOST = os.environ.get("RESEARCHOS_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("RESEARCHOS_PORT", "8765"))
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
WEB_HOST = os.environ.get("RESEARCHOS_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("RESEARCHOS_WEB_PORT", "58259"))
LOG_ROOT = AGENT_ROOT / "logs"
API_LOG_PATH = LOG_ROOT / "researchos_api.log"


def python_for_api() -> str:
    return os.environ.get("RESEARCHOS_API_PYTHON") or sys.executable


def backend_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def start_backend() -> subprocess.Popen | None:
    if backend_ready():
        return None
    AGENT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["RESEARCHOS_AGENT_ROOT"] = str(AGENT_ROOT)
    env["RESEARCHOS_HOST"] = API_HOST
    env["RESEARCHOS_PORT"] = str(API_PORT)
    env.setdefault("RESEARCHOS_DUAL_AGENT_API_ENABLED", "true")
    env_file = WORKSPACE_ROOT / ".env"
    if env_file.exists():
        env["RESEARCHOS_ENV_FILE"] = str(env_file)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    log_handle = API_LOG_PATH.open("a", encoding="utf-8", buffering=1)
    log_handle.write(f"\n--- starting web-backed API at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    process = subprocess.Popen(
        [python_for_api(), str(API_SCRIPT), "--agent-root", str(AGENT_ROOT), "--host", API_HOST, "--port", str(API_PORT)],
        cwd=str(API_SCRIPT.parent),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    log_handle.close()
    deadline = time.time() + 30
    while time.time() < deadline:
        if backend_ready():
            return process
        if process.poll() is not None:
            raise RuntimeError(f"ResearchOS API exited early. See {API_LOG_PATH}")
        time.sleep(0.5)
    raise RuntimeError(f"ResearchOS API startup timed out. See {API_LOG_PATH}")


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


class WebClientHandler(BaseHTTPRequestHandler):
    server_version = "ResearchOSWebClient/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path.startswith("/api/backend/") or self.path == "/api/backend":
            self.proxy_backend()
            return
        self.serve_static()

    def do_POST(self) -> None:
        if self.path.startswith("/api/backend/") or self.path == "/api/backend":
            self.proxy_backend()
            return
        self.send_json(404, {"error": "Not found"})

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, status: int, payload: object) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = urllib.parse.unquote(parsed.path).lstrip("/")
        if not route:
            route = "index.html"
        target = (WEB_ROOT / route).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.exists() or not target.is_file():
            target = WEB_ROOT / "index.html"
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(target.suffix.lower(), "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy_backend(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        suffix = parsed.path.removeprefix("/api/backend")
        suffix = suffix or "/"
        target_url = f"{API_BASE_URL}{suffix}"
        if parsed.query:
            target_url += f"?{parsed.query}"
        body = None
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length:
            body = self.rfile.read(length)
        headers = {"Accept": "application/json"}
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(target_url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                response_body = response.read()
                status = response.status
                response_type = response.headers.get("Content-Type", "application/json; charset=utf-8")
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = exc.code
            response_type = exc.headers.get("Content-Type", "application/json; charset=utf-8")
        except Exception as exc:
            self.send_json(502, {"error": str(exc), "backend": API_BASE_URL})
            return
        self.send_response(status)
        self.send_header("Content-Type", response_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ResearchOS HTML client.")
    parser.add_argument("--host", default=WEB_HOST)
    parser.add_argument("--port", type=int, default=WEB_PORT)
    parser.add_argument("--open", action="store_true", help="Open the web client in the default browser.")
    args = parser.parse_args()
    backend_process = start_backend()
    server = ThreadingHTTPServer((args.host, args.port), WebClientHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"ResearchOS web client: {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
