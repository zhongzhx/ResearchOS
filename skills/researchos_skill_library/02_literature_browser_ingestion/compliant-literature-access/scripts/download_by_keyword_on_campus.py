from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
import re
import html

import resolve_fulltext_access as access


def make_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "email": args.email,
        "run_name": args.run_name,
        "access_modes": {
            "open_access": args.also_open_access,
            "crossref_tdm": True,
            "campus_ip": True,
            "ezproxy": {"enabled": False},
        },
        "request": {
            "timeout_seconds": args.timeout_seconds,
            "delay_seconds": args.delay_seconds,
            "user_agent": (
                f"CampusKeywordLiteratureDownload/0.1 (mailto:{args.email})"
                if args.email
                else "CampusKeywordLiteratureDownload/0.1"
            ),
        },
        "download": {
            "save_html": True,
            "max_bytes": args.max_bytes,
            "stop_after_first_success": not args.keep_trying,
        },
        "publisher_headers": {},
    }


def first_date(parts: dict[str, Any]) -> str:
    values = parts.get("date-parts") or []
    if not values or not values[0]:
        return ""
    year = str(values[0][0])
    month = f"{values[0][1]:02d}" if len(values[0]) > 1 else "01"
    day = f"{values[0][2]:02d}" if len(values[0]) > 2 else "01"
    return f"{year}-{month}-{day}"


def excluded_article_title(title: str) -> bool:
    lowered = title.lower().strip()
    prefixes = (
        "correction:",
        "erratum",
        "retraction",
        "withdrawn",
        "publisher correction",
        "author correction",
        "comment on",
        "reply to",
    )
    return lowered.startswith(prefixes)


def clean_abstract(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def openalex_abstract(inverted: dict[str, list[int]] | None) -> str:
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, indexes in inverted.items():
        for index in indexes:
            positions[index] = word
    if not positions:
        return ""
    return " ".join(positions[index] for index in sorted(positions))


def search_crossref(query: str, args: argparse.Namespace, session: access.HttpSession) -> list[dict[str, str]]:
    params = {
        "query.bibliographic": query,
        "rows": str(min(max(args.max_results * 5, 20), 100)),
        "select": "DOI,title,abstract,container-title,published-print,published-online,issued,URL,is-referenced-by-count",
        "sort": "relevance",
        "order": "desc",
    }
    filters = ["type:journal-article"]
    if args.from_year:
        filters.append(f"from-pub-date:{args.from_year}-01-01")
    if args.until_year:
        filters.append(f"until-pub-date:{args.until_year}-12-31")
    params["filter"] = ",".join(filters)
    url = "https://api.crossref.org/works?" + urlencode(params)
    headers = {"mailto": args.email} if args.email else {}
    try:
        resp = session.get(url, timeout=args.timeout_seconds, headers=headers)
    except access.HttpRequestError:
        return []
    if resp.status_code != 200:
        return []

    rows: list[dict[str, str]] = []
    for item in resp.json().get("message", {}).get("items", []):
        doi = access.normalize_doi(item.get("DOI") or "")
        if not doi:
            continue
        title = " ".join(item.get("title") or []).strip()
        if excluded_article_title(title):
            continue
        journal = " ".join(item.get("container-title") or []).strip()
        date = (
            first_date(item.get("published-online") or {})
            or first_date(item.get("published-print") or {})
            or first_date(item.get("issued") or {})
        )
        rows.append(
            {
                "query": query,
                "source": "crossref",
                "doi": doi,
                "title": title,
                "abstract": clean_abstract(item.get("abstract") or ""),
                "journal": journal,
                "publication_date": date,
                "landing_url": item.get("URL") or f"https://doi.org/{quote(doi, safe='/')}",
                "score": str(item.get("is-referenced-by-count", "")),
            }
        )
    return rows


def openalex_date_allowed(date: str, args: argparse.Namespace) -> bool:
    if not date:
        return True
    year = int(date[:4])
    if args.from_year and year < args.from_year:
        return False
    if args.until_year and year > args.until_year:
        return False
    return True


def search_openalex(query: str, args: argparse.Namespace, session: access.HttpSession) -> list[dict[str, str]]:
    params = {
        "search": query,
        "per-page": str(min(max(args.max_results * 5, 20), 200)),
        "filter": "type:article",
    }
    if args.email:
        params["mailto"] = args.email
    url = "https://api.openalex.org/works?" + urlencode(params)
    try:
        resp = session.get(url, timeout=args.timeout_seconds)
    except access.HttpRequestError:
        return []
    if resp.status_code != 200:
        return []

    rows: list[dict[str, str]] = []
    for item in resp.json().get("results", []):
        doi = access.normalize_doi(item.get("doi") or "")
        date = item.get("publication_date") or ""
        if not doi or not openalex_date_allowed(date, args):
            continue
        title = item.get("display_name") or ""
        if excluded_article_title(title):
            continue
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        rows.append(
            {
                "query": query,
                "source": "openalex",
                "doi": doi,
                "title": title,
                "abstract": clean_abstract(openalex_abstract(item.get("abstract_inverted_index"))),
                "journal": source.get("display_name") or "",
                "publication_date": date,
                "landing_url": item.get("doi") or item.get("id") or "",
                "score": str(item.get("cited_by_count", "")),
            }
        )
    return rows


def collect_search_results(queries: list[str], args: argparse.Namespace, config: dict[str, Any]) -> list[dict[str, str]]:
    session = access.make_session(config)
    rows: list[dict[str, str]] = []
    for query in queries:
        if args.source in {"crossref", "both"}:
            rows.extend(search_crossref(query, args, session))
            time.sleep(args.delay_seconds)
        if args.source in {"openalex", "both"}:
            rows.extend(search_openalex(query, args, session))
            time.sleep(args.delay_seconds)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = row["doi"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= args.max_results:
            break
    return deduped


def write_candidate_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["query", "source", "doi", "title", "abstract", "journal", "publication_date", "landing_url", "score"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def no_candidate_event(row: dict[str, str], attempt_index: int) -> dict[str, Any]:
    return {
        "timestamp_utc": access.now_utc(),
        "doi": row["doi"],
        "url": row.get("landing_url", ""),
        "source": row.get("source", ""),
        "method": "keyword_search_to_campus_download",
        "entitlement": "institution_or_public_web",
        "content_hint": "",
        "license_url": "",
        "session_name": "default",
        "attempt_index": attempt_index,
        "status": "no_candidate",
        "http_status": "",
        "content_format": "",
        "output_path": "",
        "bytes_written": 0,
        "error": "No full-text candidate discovered from DOI landing page or Crossref links",
        "keyword_query": row.get("query", ""),
        "title": row.get("title", ""),
        "abstract": row.get("abstract", ""),
        "journal": row.get("journal", ""),
        "publication_date": row.get("publication_date", ""),
    }


def extractor_script_path() -> Path | None:
    here = Path(__file__).resolve()
    workspace = here.parents[2]
    candidate = workspace / "extract-first-article-keywords" / "scripts" / "extract_first_article_keywords.py"
    return candidate if candidate.exists() else None


def write_article_record(run_dir: Path, attempt_index: int, row: dict[str, str], event: dict[str, Any]) -> Path:
    records_dir = run_dir / "article_records"
    records_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "attempt_index": attempt_index,
        "doi": row.get("doi", ""),
        "title": row.get("title", ""),
        "abstract": row.get("abstract", ""),
        "journal": row.get("journal", ""),
        "publication_date": row.get("publication_date", ""),
        "keyword_query": row.get("query", ""),
        "landing_url": row.get("landing_url", ""),
        "status": event.get("status", ""),
        "output_path": event.get("output_path", ""),
        "source": event.get("source", row.get("source", "")),
        "method": event.get("method", ""),
        "error": event.get("error", ""),
    }
    path = records_dir / f"article_{attempt_index:04d}_{access.safe_name(row.get('doi', 'record'), max_len=40)}.json"
    path.write_text(json_dumps(record), encoding="utf-8")
    return path


def json_dumps(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2)


def run_browser_fallback(run_dir: Path, article_index: int, row: dict[str, str], args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.browser_fallback:
        return None
    probe_script = Path(__file__).resolve().parent / "browser_use_literature_probe.py"
    output_root = run_dir / "browser_use_probe" / f"article_{article_index:04d}"
    command = [
        sys.executable,
        str(probe_script),
        "--doi",
        row.get("doi", ""),
        "--landing-url",
        row.get("landing_url", ""),
        "--output-root",
        str(output_root),
        "--session",
        args.browser_session,
    ]
    if args.browser_profile:
        command.extend(["--profile", args.browser_profile])
    if args.browser_headed:
        command.append("--headed")

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    payload: dict[str, Any]
    result_json = output_root / "browser_probe_result.json"
    if result_json.exists():
        payload = json.loads(result_json.read_text(encoding="utf-8"))
    else:
        payload = {
            "doi": row.get("doi", ""),
            "landing_url": row.get("landing_url", ""),
            "status": "browser_probe_failed",
            "method": "browser_use",
            "error": (result.stderr or result.stdout).strip(),
        }

    return {
        "timestamp_utc": access.now_utc(),
        "doi": row.get("doi", ""),
        "url": payload.get("pdf_url") or payload.get("landing_url") or row.get("landing_url", ""),
        "source": "browser_use",
        "method": "browser_use",
        "entitlement": "current_browser_or_network",
        "content_hint": payload.get("content_format", ""),
        "license_url": "",
        "session_name": args.browser_session,
        "attempt_index": -1,
        "status": payload.get("status", "browser_probe_failed"),
        "http_status": "",
        "content_format": payload.get("content_format", ""),
        "output_path": payload.get("output_path", ""),
        "bytes_written": payload.get("bytes_written", 0),
        "error": payload.get("error", ""),
        "keyword_query": row.get("query", ""),
        "title": row.get("title", ""),
        "abstract": row.get("abstract", ""),
        "journal": row.get("journal", ""),
        "publication_date": row.get("publication_date", ""),
    }


def run_article_abstract_extraction(
    run_dir: Path,
    record_path: Path,
    args: argparse.Namespace,
) -> None:
    if args.no_article_analysis or args.no_first_keywords:
        return
    script = extractor_script_path()
    if not script:
        print("Article abstract extractor skill not found; skipping article analysis.")
        return

    output_root = run_dir / "article_abstracts"
    summary_path = output_root / "article_abstracts.csv"
    command = [
        sys.executable,
        str(script),
        "--record-json",
        str(record_path),
        "--output-root",
        str(output_root),
        "--top-n",
        str(args.keyword_top_n),
        "--append-summary",
        str(summary_path),
    ]

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        print(f"Article abstract analysis completed for {record_path.name}.")
        if result.stdout.strip():
            print(result.stdout.strip())
    else:
        print(f"Article abstract analysis failed for {record_path.name}.")
        if result.stderr.strip():
            print(result.stderr.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search scholarly APIs by keyword, then download full text through current campus IP/VPN access."
    )
    parser.add_argument("--query", action="append", required=True, help="Keyword query. Can be passed more than once.")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum unique article records to try.")
    parser.add_argument("--source", choices=["crossref", "openalex", "both"], default="both")
    parser.add_argument("--from-year", type=int, help="Earliest publication year.")
    parser.add_argument("--until-year", type=int, help="Latest publication year.")
    parser.add_argument("--output-root", required=True, help="Parent folder for the run output.")
    parser.add_argument("--run-name", default="campus_keyword_download", help="Run folder prefix.")
    parser.add_argument("--email", default="", help="Optional contact email for polite API identification.")
    parser.add_argument("--also-open-access", action="store_true", help="Also try open-access resolvers such as Unpaywall.")
    parser.add_argument("--keep-trying", action="store_true", help="Try all candidate URLs for each article.")
    parser.add_argument("--no-article-analysis", action="store_true", help="Do not analyze each article abstract as it is processed.")
    parser.add_argument("--no-first-keywords", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--keyword-top-n", type=int, default=30, help="Top keyword/keyphrase count for per-article abstract analysis.")
    parser.add_argument("--browser-fallback", action="store_true", help="Use browser-use as a fallback when API/direct download fails.")
    parser.add_argument("--browser-session", default="research-literature", help="browser-use session name for fallback browsing.")
    parser.add_argument("--browser-profile", default="", help="Optional browser-use profile name, e.g. Default.")
    parser.add_argument("--browser-headed", action="store_true", help="Show browser window for browser-use fallback.")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--max-bytes", type=int, default=104857600)
    args = parser.parse_args()

    config = make_config(args)
    run_dir = access.build_run_dir(Path(args.output_root), args.run_name)
    candidate_rows = collect_search_results(args.query, args, config)
    write_candidate_csv(run_dir / "keyword_candidates.csv", candidate_rows)

    dois = [row["doi"] for row in candidate_rows]
    if not dois:
        access.write_logs(run_dir, [])
        access.write_summary(run_dir, [], [])
        print(f"Run folder: {run_dir}")
        print("No DOI-bearing article candidates found for the keyword query.")
        return 1

    sessions = {"default": access.make_session(config)}
    events: list[dict[str, Any]] = []
    attempt_index = 1
    article_index = 1
    for row in candidate_rows:
        candidates = access.collect_candidates_for_doi(row["doi"], config, sessions)
        if not candidates:
            event = no_candidate_event(row, attempt_index)
            browser_event = run_browser_fallback(run_dir, article_index, row, args)
            if browser_event:
                browser_event["attempt_index"] = attempt_index
                event = browser_event
            events.append(event)
            attempt_index += 1
            access.write_logs(run_dir, events)
            access.write_summary(run_dir, dois, events)
            record_path = write_article_record(run_dir, article_index, row, event)
            run_article_abstract_extraction(run_dir, record_path, args)
            article_index += 1
            continue

        doi_success = False
        article_event: dict[str, Any] | None = None
        for candidate in candidates:
            event = access.download_candidate(candidate, sessions, config, run_dir / "downloads", attempt_index)
            event["keyword_query"] = row.get("query", "")
            event["title"] = row.get("title", "")
            event["abstract"] = row.get("abstract", "")
            event["journal"] = row.get("journal", "")
            event["publication_date"] = row.get("publication_date", "")
            events.append(event)
            attempt_index += 1
            if event["status"] == "downloaded":
                doi_success = True
                article_event = event
                if config["download"]["stop_after_first_success"]:
                    break
            time.sleep(args.delay_seconds)

        if not doi_success:
            failed = no_candidate_event(row, attempt_index)
            failed["status"] = "no_successful_download"
            failed["error"] = "Candidates existed but none downloaded through current network"
            browser_event = run_browser_fallback(run_dir, article_index, row, args)
            if browser_event:
                browser_event["attempt_index"] = attempt_index
                failed = browser_event
                if failed["status"] == "downloaded":
                    doi_success = True
            events.append(failed)
            attempt_index += 1
            article_event = failed

        access.write_logs(run_dir, events)
        access.write_summary(run_dir, dois, events)
        if article_event:
            record_path = write_article_record(run_dir, article_index, row, article_event)
            run_article_abstract_extraction(run_dir, record_path, args)
            article_index += 1

    access.write_logs(run_dir, events)
    access.write_summary(run_dir, dois, events)
    print(f"Run folder: {run_dir}")
    print(f"Keyword queries: {len(args.query)}")
    print(f"Candidate articles: {len(candidate_rows)}")
    print(f"Downloaded files: {sum(1 for event in events if event.get('status') == 'downloaded')}")
    print(f"Candidate table: {run_dir / 'keyword_candidates.csv'}")
    print(f"Audit log: {run_dir / 'access_log.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
