from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import Cookie, CookieJar


@dataclass
class ProbeResult:
    doi: str
    landing_url: str
    status: str
    method: str
    pdf_url: str = ""
    output_path: str = ""
    content_format: str = ""
    bytes_written: int = 0
    error: str = ""


class FullTextLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "a" and values.get("href"):
            self._add(values["href"])
        if tag.lower() == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            content = values.get("content") or ""
            if "pdf" in name or name in {"citation_pdf_url", "citation_fulltext_html_url"}:
                self._add(content)

    def _add(self, value: str) -> None:
        url = urljoin(self.base_url, html.unescape(value.strip()))
        lower = url.lower()
        if (
            ".pdf" in lower
            or "/pdf" in lower
            or "pdf=" in lower
            or "type=pdf" in lower
            or "download" in lower
            or "article/file" in lower
            or "article/download" in lower
            or "fulltext" in lower
            or "full-text" in lower
        ):
            self.links.append(url)


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return text[:90] or "article"


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def browser_use_command() -> tuple[list[str], dict[str, str]]:
    found = shutil.which("browser-use")
    env = os.environ.copy()
    if found:
        return [found], env

    local_repo = workspace_root() / "browser-use"
    if local_repo.exists():
        raise FileNotFoundError(
            "browser-use repository is downloaded but the CLI is not installed. "
            "Install it before enabling browser fallback, for example: "
            "cd browser-use; py -m pip install -e ."
        )

    raise FileNotFoundError("browser-use CLI not found in PATH and local browser-use repository is missing.")


def run_cli(base: list[str], env: dict[str, str], args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(base + args, text=True, capture_output=True, timeout=timeout, env=env, check=False)


def browser_args(args: argparse.Namespace) -> list[str]:
    result = ["--session", args.session]
    if args.profile:
        result.extend(["--profile", args.profile])
    if args.headed:
        result.append("--headed")
    return result


def export_cookies(base: list[str], env: dict[str, str], args: argparse.Namespace, cookie_path: Path) -> None:
    run_cli(base, env, browser_args(args) + ["cookies", "export", str(cookie_path)], args.timeout_seconds)


def cookiejar_from_browser_export(cookie_path: Path) -> CookieJar:
    jar = CookieJar()
    if not cookie_path.exists():
        return jar
    try:
        data = json.loads(cookie_path.read_text(encoding="utf-8"))
    except Exception:
        return jar
    if isinstance(data, dict) and "cookies" in data:
        cookies = data["cookies"]
    elif isinstance(data, list):
        cookies = data
    else:
        cookies = []
    for item in cookies:
        domain = item.get("domain") or urlparse(item.get("url", "")).hostname or ""
        if not domain:
            continue
        cookie = Cookie(
            version=0,
            name=item.get("name", ""),
            value=item.get("value", ""),
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=True,
            domain_initial_dot=domain.startswith("."),
            path=item.get("path", "/"),
            path_specified=True,
            secure=bool(item.get("secure", False)),
            expires=item.get("expires") if isinstance(item.get("expires"), int) else None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        jar.set_cookie(cookie)
    return jar


def download_url(url: str, output_dir: Path, doi: str, cookie_path: Path, user_agent: str, max_bytes: int) -> ProbeResult:
    jar = cookiejar_from_browser_export(cookie_path)
    opener = build_opener(HTTPCookieProcessor(jar))
    req = Request(url, headers={"User-Agent": user_agent})
    with opener.open(req, timeout=45) as resp:
        body = resp.read(max_bytes + 1)
        content_type = resp.headers.get("Content-Type", "").lower()
        final_url = resp.geturl()
    if len(body) > max_bytes:
        return ProbeResult(doi=doi, landing_url="", status="max_bytes_exceeded", method="browser_use", pdf_url=url)

    if body.startswith(b"%PDF") or "application/pdf" in content_type or final_url.lower().endswith(".pdf"):
        ext = "pdf"
    elif "html" in content_type or body[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        ext = "html"
    elif "xml" in content_type or body[:100].lstrip().startswith(b"<?xml"):
        ext = "xml"
    else:
        ext = "bin"

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"browser_{safe_name(doi)}.{ext}"
    path.write_bytes(body)
    return ProbeResult(
        doi=doi,
        landing_url="",
        status="downloaded",
        method="browser_use",
        pdf_url=url,
        output_path=str(path),
        content_format=ext,
        bytes_written=len(body),
    )


def probe(args: argparse.Namespace) -> ProbeResult:
    doi = args.doi.strip()
    landing_url = args.landing_url or (f"https://doi.org/{quote(doi, safe='/')}" if doi else "")
    if not landing_url:
        return ProbeResult(doi=doi, landing_url="", status="no_url", method="browser_use", error="No DOI or landing URL supplied.")

    try:
        base, env = browser_use_command()
    except Exception as exc:
        return ProbeResult(doi=doi, landing_url=landing_url, status="browser_unavailable", method="browser_use", error=str(exc))

    open_result = run_cli(base, env, browser_args(args) + ["open", landing_url], args.timeout_seconds)
    if open_result.returncode != 0:
        return ProbeResult(
            doi=doi,
            landing_url=landing_url,
            status="browser_open_failed",
            method="browser_use",
            error=(open_result.stderr or open_result.stdout).strip(),
        )

    html_result = run_cli(base, env, browser_args(args) + ["get", "html"], args.timeout_seconds)
    if html_result.returncode != 0:
        return ProbeResult(
            doi=doi,
            landing_url=landing_url,
            status="browser_html_failed",
            method="browser_use",
            error=(html_result.stderr or html_result.stdout).strip(),
        )

    parser = FullTextLinkParser(landing_url)
    parser.feed(html_result.stdout)
    links = list(dict.fromkeys(parser.links))
    if not links:
        return ProbeResult(doi=doi, landing_url=landing_url, status="no_fulltext_link", method="browser_use")

    cookie_path = Path(args.output_root) / "browser_cookies.json"
    export_cookies(base, env, args, cookie_path)
    last_error = ""
    for link in links[: args.max_links_to_try]:
        try:
            result = download_url(link, Path(args.output_root) / "downloads", doi, cookie_path, args.user_agent, args.max_bytes)
            result.landing_url = landing_url
            if result.status == "downloaded":
                return result
        except Exception as exc:
            last_error = str(exc)
    return ProbeResult(
        doi=doi,
        landing_url=landing_url,
        status="browser_download_failed",
        method="browser_use",
        pdf_url=links[0],
        error=last_error,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Use browser-use to probe a literature landing page for full-text links.")
    parser.add_argument("--doi", default="")
    parser.add_argument("--landing-url", default="")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--session", default="research-literature")
    parser.add_argument("--profile", default="", help="Optional local browser profile name, e.g. Default.")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-bytes", type=int, default=104857600)
    parser.add_argument("--max-links-to-try", type=int, default=5)
    parser.add_argument("--user-agent", default="ResearchAgentBrowserUse/0.1")
    args = parser.parse_args()

    result = probe(args)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "browser_probe_result.json").write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")
    with (output_root / "browser_probe_result.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(result).keys()))
        writer.writeheader()
        writer.writerow(asdict(result))
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0 if result.status == "downloaded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
