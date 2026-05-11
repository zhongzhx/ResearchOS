from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse


@dataclass
class BrowserLearningPage:
    query: str
    source_site: str
    url: str
    title: str
    status: str
    page_kind: str
    extracted_text: str
    error: str = ""


class PageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.meta_description = ""
        self._tag_stack: list[str] = []
        self._current_href = ""
        self._link_text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value for name, value in attrs if value is not None}
        self._tag_stack.append(tag)
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            if name in {"description", "og:description", "citation_abstract"} and values.get("content"):
                self.meta_description = clean_text(values["content"])
        if tag == "a" and values.get("href"):
            self._current_href = urljoin(self.base_url, html.unescape(values["href"]))
            self._link_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "a" and self._current_href:
            text = clean_text(" ".join(self._link_text_parts))
            self.links.append((self._current_href, text))
            self._current_href = ""
            self._link_text_parts = []
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_text(data)
        if not text:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self.title_parts.append(text)
        if self._current_href:
            self._link_text_parts.append(text)
        if len(text) >= 20:
            self.text_parts.append(text)

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        pieces = []
        if self.meta_description:
            pieces.append(self.meta_description)
        pieces.extend(self.text_parts)
        return clean_text(" ".join(pieces))


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    if not text:
        return "browser_learning"
    if len(text) <= 48:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:39]}_{digest}"


def browser_command() -> list[str]:
    found = shutil.which("browser-use")
    if not found:
        raise FileNotFoundError(
            "browser-use CLI is not installed on PATH. Install it before browser learning, for example: "
            "cd browser-use; py -m pip install -e ."
        )
    return [found]


def browser_args(args: argparse.Namespace) -> list[str]:
    result = ["--session", args.session]
    if args.profile:
        result.extend(["--profile", args.profile])
    if args.cdp_url:
        result.extend(["--cdp-url", args.cdp_url])
    if args.headed:
        result.append("--headed")
    return result


def run_cli(base: list[str], args: argparse.Namespace, command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(base + browser_args(args) + command, text=True, capture_output=True, timeout=args.timeout_seconds, check=False)


def search_url(site: str, query: str) -> str:
    q = quote_plus(query)
    if site == "pubmed":
        return f"https://pubmed.ncbi.nlm.nih.gov/?term={q}"
    if site == "semantic_scholar":
        return f"https://www.semanticscholar.org/search?q={q}&sort=relevance"
    if site == "google_scholar":
        return f"https://scholar.google.com/scholar?q={q}"
    return f"https://www.google.com/search?q={q}"


def scholarly_link(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    blocked = {"accounts.google.com", "support.google.com", "policies.google.com"}
    if host in blocked:
        return False
    markers = [
        "pubmed.ncbi.nlm.nih.gov",
        "doi.org",
        "semanticscholar.org",
        "sciencedirect.com",
        "springer.com",
        "nature.com",
        "wiley.com",
        "tandfonline.com",
        "mdpi.com",
        "frontiersin.org",
        "plos.org",
        "arxiv.org",
        "biorxiv.org",
        "medrxiv.org",
        "openalex.org",
        "crossref.org",
        "ncbi.nlm.nih.gov",
    ]
    return any(marker in host for marker in markers)


def parse_html(base_url: str, html_text: str) -> PageParser:
    parser = PageParser(base_url)
    parser.feed(html_text)
    return parser


def open_and_read(base: list[str], args: argparse.Namespace, url: str) -> tuple[str, str, str]:
    opened = run_cli(base, args, ["open", url])
    if opened.returncode != 0:
        raise RuntimeError((opened.stderr or opened.stdout).strip())
    time.sleep(args.page_delay_seconds)
    html_result = run_cli(base, args, ["get", "html"])
    if html_result.returncode != 0:
        raise RuntimeError((html_result.stderr or html_result.stdout).strip())
    parser = parse_html(url, html_result.stdout)
    return parser.title, parser.text, html_result.stdout


def collect_links_from_search(base: list[str], args: argparse.Namespace, site: str, query: str) -> tuple[BrowserLearningPage, list[str]]:
    url = search_url(site, query)
    title, text, html_text = open_and_read(base, args, url)
    parser = parse_html(url, html_text)
    links = []
    for link, _ in parser.links:
        if scholarly_link(link) and link not in links:
            links.append(link)
    search_page = BrowserLearningPage(
        query=query,
        source_site=site,
        url=url,
        title=title,
        status="read",
        page_kind="search_page",
        extracted_text=text[: args.max_text_chars],
    )
    return search_page, links[: args.max_pages]


def learn(args: argparse.Namespace) -> tuple[Path, list[BrowserLearningPage], dict[str, Any]]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = Path(args.output_root)
    run_dir = output_root / f"browser_learning_{stamp}_{safe_slug(args.query)}"
    run_dir.mkdir(parents=True, exist_ok=False)

    pages: list[BrowserLearningPage] = []
    summary: dict[str, Any] = {
        "query": args.query,
        "status": "started",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "browser_profile": args.profile,
        "browser_cdp_url": args.cdp_url,
        "browser_session": args.session,
        "sources": args.site,
        "run_dir": str(run_dir),
    }

    try:
        base = browser_command()
    except Exception as exc:
        summary["status"] = "browser_unavailable"
        summary["error"] = str(exc)
        write_outputs(run_dir, pages, summary)
        return run_dir, pages, summary

    for site in args.site:
        try:
            search_page, links = collect_links_from_search(base, args, site, args.query)
            pages.append(search_page)
        except Exception as exc:
            pages.append(
                BrowserLearningPage(
                    query=args.query,
                    source_site=site,
                    url=search_url(site, args.query),
                    title="",
                    status="search_failed",
                    page_kind="search_page",
                    extracted_text="",
                    error=str(exc),
                )
            )
            continue

        for link in links:
            try:
                title, text, _ = open_and_read(base, args, link)
                pages.append(
                    BrowserLearningPage(
                        query=args.query,
                        source_site=site,
                        url=link,
                        title=title,
                        status="read",
                        page_kind="learned_page",
                        extracted_text=text[: args.max_text_chars],
                    )
                )
            except Exception as exc:
                pages.append(
                    BrowserLearningPage(
                        query=args.query,
                        source_site=site,
                        url=link,
                        title="",
                        status="read_failed",
                        page_kind="learned_page",
                        extracted_text="",
                        error=str(exc),
                    )
                )

    summary["status"] = "completed"
    summary["page_count"] = len(pages)
    summary["read_count"] = sum(1 for page in pages if page.status == "read")
    write_outputs(run_dir, pages, summary)
    return run_dir, pages, summary


def write_outputs(run_dir: Path, pages: list[BrowserLearningPage], summary: dict[str, Any]) -> None:
    (run_dir / "browser_learning_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "browser_learning_pages.jsonl").open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(asdict(page), ensure_ascii=False) + "\n")
    with (run_dir / "browser_learning_pages.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(BrowserLearningPage.__dataclass_fields__.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for page in pages:
            writer.writerow(asdict(page))

    lines = ["# Browser Research Learning Notes", "", f"- Query: {summary.get('query', '')}", f"- Status: {summary.get('status', '')}", ""]
    if summary.get("error"):
        lines.extend(["## Error", "", str(summary["error"]), ""])
    for i, page in enumerate(pages, 1):
        lines.extend(
            [
                f"## {i}. {page.title or page.url}",
                "",
                f"- URL: {page.url}",
                f"- Source site: {page.source_site}",
                f"- Status: {page.status}",
                f"- Page kind: {page.page_kind}",
                "",
                page.extracted_text[:1500] or page.error or "No text extracted.",
                "",
            ]
        )
    (run_dir / "browser_learning_notes.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Use browser-use to learn a research topic through the user's browser.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--site", action="append", choices=["pubmed", "semantic_scholar", "google_scholar", "google"], default=None)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-text-chars", type=int, default=4000)
    parser.add_argument("--session", default="research-learning")
    parser.add_argument("--profile", default="")
    parser.add_argument("--cdp-url", default="")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--page-delay-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if not args.site:
        args.site = ["pubmed", "semantic_scholar"]

    run_dir, pages, summary = learn(args)
    print(f"Run folder: {run_dir}")
    print(json.dumps({"run_dir": str(run_dir), "summary": summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
