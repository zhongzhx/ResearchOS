from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web_client"

REQUIRED = [
    WEB / "index.html",
    WEB / "styles.css",
    WEB / "app.js",
    WEB / "api.js",
    WEB / "state.js",
    WEB / "views" / "chat.js",
    WEB / "views" / "task_lifecycle.js",
    WEB / "views" / "brain.js",
    WEB / "views" / "library.js",
    WEB / "views" / "skills.js",
    WEB / "views" / "runs.js",
    WEB / "views" / "settings.js",
    WEB / "components" / "message.js",
    WEB / "components" / "cards.js",
    WEB / "components" / "details.js",
    WEB / "components" / "status_pill.js",
    WEB / "components" / "empty_state.js",
    WEB / "components" / "artifact_card.js",
    WEB / "components" / "workflow_card.js",
    WEB / "components" / "project_status_card.js",
    WEB / "components" / "developer_details.js",
    WEB / "components" / "project_switcher.js",
    WEB / "components" / "json_viewer.js",
]

SECRET_LITERALS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]


def fail(message: str) -> None:
    print(f"web client check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    missing = [path for path in REQUIRED if not path.exists()]
    if missing:
      fail("missing files: " + ", ".join(str(path.relative_to(ROOT)) for path in missing))

    html = (WEB / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r'(?:src|href)="([^"]+)"', html):
        value = match.group(1)
        if not value.startswith("/"):
            continue
        target = WEB / value.lstrip("/")
        if not target.exists():
            fail(f"index.html references missing asset: {value}")

    for path in WEB.rglob("*"):
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "console.log" in text:
            fail(f"console.log is not allowed in static client files: {path.relative_to(ROOT)}")
        for pattern in SECRET_LITERALS:
            if pattern.search(text):
                fail(f"possible secret literal in {path.relative_to(ROOT)}")

    print("web client check passed")


if __name__ == "__main__":
    main()
