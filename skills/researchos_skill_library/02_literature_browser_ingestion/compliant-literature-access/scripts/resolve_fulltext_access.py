from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from http.cookiejar import CookieJar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from credential_store import CredentialStoreError, get_credentials


DEFAULT_CONFIG: dict[str, Any] = {
    "email": "",
    "run_name": "literature_access_run",
    "access_modes": {
        "open_access": True,
        "crossref_tdm": True,
        "campus_ip": True,
        "ezproxy": {
            "enabled": False,
            "base_url": "",
            "login_url": "",
            "service": "institution-access",
            "username_field": "user",
            "password_field": "pass",
            "extra_fields": {},
        },
    },
    "request": {
        "timeout_seconds": 45,
        "delay_seconds": 0.5,
        "user_agent": "CompliantLiteratureAccess/0.1",
    },
    "download": {
        "save_html": True,
        "max_bytes": 104857600,
        "stop_after_first_success": True,
    },
    "publisher_headers": {},
}


@dataclass
class Candidate:
    doi: str
    url: str
    source: str
    method: str
    entitlement: str
    content_hint: str = ""
    license_url: str = ""
    session_name: str = "default"


class HttpRequestError(RuntimeError):
    pass


class SimpleResponse:
    def __init__(self, status_code: int, headers: dict[str, str], url: str, body: bytes) -> None:
        self.status_code = status_code
        self.headers = headers
        self.url = url
        self.content = body

    @property
    def text(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r"charset=([^;]+)", content_type, flags=re.I)
        encoding = match.group(1).strip() if match else "utf-8"
        return self.content.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)

    def iter_content(self, chunk_size: int = 65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


class HttpSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(
        self,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        allow_redirects: bool = True,
        stream: bool = False,
        max_bytes: int | None = None,
    ) -> SimpleResponse:
        return self._request("GET", url, timeout, headers=headers, max_bytes=max_bytes)

    def post(
        self,
        url: str,
        data: dict[str, str],
        timeout: float,
        allow_redirects: bool = True,
    ) -> SimpleResponse:
        body = urlencode(data).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return self._request("POST", url, timeout, headers=headers, body=body)

    def _request(
        self,
        method: str,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        max_bytes: int | None = None,
    ) -> SimpleResponse:
        request_headers = dict(self.headers)
        request_headers.update(headers or {})
        req = Request(url, data=body, headers=request_headers, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                limit = max_bytes + 1 if max_bytes else None
                data = resp.read(limit)
                return SimpleResponse(resp.status, dict(resp.headers.items()), resp.geturl(), data)
        except HTTPError as exc:
            return SimpleResponse(exc.code, dict(exc.headers.items()), exc.geturl(), exc.read())
        except URLError as exc:
            raise HttpRequestError(str(exc)) from exc


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "a" and "href" in values:
            self._add_url(values["href"])
        if tag.lower() == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            content = values.get("content")
            if content and ("pdf" in name or name in {"citation_fulltext_html_url", "citation_pdf_url"}):
                self._add_url(content)

    def _add_url(self, value: str) -> None:
        url = urljoin(self.base_url, value.strip())
        if looks_like_fulltext_url(url):
            self.links.append(url)


def load_config(path: str | None) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path:
        return config
    with open(path, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    deep_update(config, user_config)
    return config


def deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def normalize_doi(value: str) -> str:
    doi = value.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    return doi.strip().strip(".")


def safe_name(value: str, max_len: int = 90) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    if len(text) <= max_len:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{text[: max_len - 11]}_{digest}"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def looks_like_fulltext_url(url: str) -> bool:
    lower = url.lower()
    return (
        ".pdf" in lower
        or "/pdf" in lower
        or "pdf/" in lower
        or "pdf=" in lower
        or "type=pdf" in lower
        or "type=printable" in lower
        or "download" in lower
        or "article/file" in lower
        or "article/download" in lower
        or "content/pdf" in lower
        or "fulltext" in lower
        or "full-text" in lower
        or lower.endswith(".xml")
    )


def make_session(config: dict[str, Any]) -> HttpSession:
    session = HttpSession()
    session.headers.update({"User-Agent": config["request"].get("user_agent", DEFAULT_CONFIG["request"]["user_agent"])})
    return session


def domain_headers(url: str, config: dict[str, Any]) -> dict[str, str]:
    host = urlparse(url).netloc.lower()
    headers: dict[str, str] = {}
    for domain, values in config.get("publisher_headers", {}).items():
        if host == domain.lower() or host.endswith("." + domain.lower()):
            for key, value in values.items():
                if isinstance(value, str) and value.startswith("env:"):
                    env_value = os.environ.get(value[4:])
                    if env_value:
                        headers[key] = env_value
                elif value:
                    headers[key] = str(value)
    return headers


def collect_unpaywall(doi: str, config: dict[str, Any], session: HttpSession) -> list[Candidate]:
    email = config.get("email", "")
    if not email:
        return []
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(email)}"
    try:
        resp = session.get(url, timeout=config["request"]["timeout_seconds"])
    except HttpRequestError:
        return []
    if resp.status_code != 200:
        return []

    data = resp.json()
    locations = []
    best = data.get("best_oa_location")
    if best:
        locations.append(best)
    locations.extend(data.get("oa_locations") or [])

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for loc in locations:
        for key in ("url_for_pdf", "url", "url_for_landing_page"):
            candidate_url = loc.get(key)
            if not candidate_url or candidate_url in seen:
                continue
            seen.add(candidate_url)
            candidates.append(
                Candidate(
                    doi=doi,
                    url=candidate_url,
                    source="unpaywall",
                    method="open_access",
                    entitlement="open_access",
                    content_hint=key,
                    license_url=loc.get("license") or "",
                )
            )
    return candidates


def collect_crossref(doi: str, config: dict[str, Any], session: HttpSession) -> list[Candidate]:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    headers = {}
    email = config.get("email")
    if email:
        headers["mailto"] = email
    try:
        resp = session.get(url, headers=headers, timeout=config["request"]["timeout_seconds"])
    except HttpRequestError:
        return []
    if resp.status_code != 200:
        return []

    message = resp.json().get("message", {})
    license_url = ""
    licenses = message.get("license") or []
    if licenses:
        license_url = licenses[0].get("URL", "")

    candidates: list[Candidate] = []
    for link in message.get("link") or []:
        link_url = link.get("URL")
        if not link_url:
            continue
        candidates.append(
            Candidate(
                doi=doi,
                url=link_url,
                source="crossref",
                method="tdm_link",
                entitlement="tdm_or_publisher_entitlement",
                content_hint=link.get("content-type") or link.get("intended-application") or "",
                license_url=license_url,
            )
        )
    return candidates


def discover_fulltext_links(
    doi: str,
    start_url: str,
    source: str,
    method: str,
    entitlement: str,
    config: dict[str, Any],
    session: HttpSession,
    session_name: str,
) -> list[Candidate]:
    try:
        resp = session.get(
            start_url,
            timeout=config["request"]["timeout_seconds"],
            headers=domain_headers(start_url, config),
            allow_redirects=True,
        )
    except HttpRequestError:
        return []
    content_type = resp.headers.get("Content-Type", "").lower()
    final_url = resp.url
    if "application/pdf" in content_type or final_url.lower().endswith(".pdf"):
        return [
            Candidate(
                doi=doi,
                url=final_url,
                source=source,
                method=method,
                entitlement=entitlement,
                content_hint=content_type,
                session_name=session_name,
            )
        ]

    if "html" not in content_type and "<html" not in resp.text[:1000].lower():
        return []

    parser = LinkParser(final_url)
    parser.feed(resp.text)
    candidates = []
    for link in dict.fromkeys(parser.links):
        candidates.append(
            Candidate(
                doi=doi,
                url=link,
                source=source,
                method=method,
                entitlement=entitlement,
                content_hint="discovered_from_html",
                session_name=session_name,
            )
        )
    return candidates


def proxify(url: str, ezproxy_config: dict[str, Any]) -> str:
    base = ezproxy_config.get("base_url", "")
    if "{url}" in base:
        return base.replace("{url}", quote(url, safe=""))
    return base + quote(url, safe="")


def prepare_ezproxy_session(config: dict[str, Any]) -> HttpSession | None:
    ez = config["access_modes"].get("ezproxy", {})
    if not ez.get("enabled"):
        return None
    session = make_session(config)
    login_url = ez.get("login_url")
    service = ez.get("service", "institution-access")
    if not login_url:
        return session

    creds = get_credentials(service)
    if creds is None:
        raise CredentialStoreError(
            f"No saved credentials for service '{service}'. "
            "Run save_credentials.py before enabling EZproxy login."
        )
    username, password = creds
    payload = dict(ez.get("extra_fields") or {})
    payload[ez.get("username_field", "user")] = username
    payload[ez.get("password_field", "pass")] = password
    resp = session.post(login_url, data=payload, timeout=config["request"]["timeout_seconds"], allow_redirects=True)
    if resp.status_code >= 400:
        raise RuntimeError(f"EZproxy login failed with HTTP {resp.status_code}")
    return session


def sniff_format(first_bytes: bytes, content_type: str, url: str) -> str:
    lower_type = content_type.lower()
    lower_url = url.lower()
    if first_bytes.startswith(b"%PDF") or "application/pdf" in lower_type or lower_url.endswith(".pdf"):
        return "pdf"
    sample = first_bytes[:2048].lstrip().lower()
    if "xml" in lower_type or sample.startswith(b"<?xml"):
        return "xml"
    if "html" in lower_type or sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return "html"
    if "text/plain" in lower_type:
        return "txt"
    return "unknown"


def download_candidate(
    candidate: Candidate,
    sessions: dict[str, HttpSession],
    config: dict[str, Any],
    download_dir: Path,
    index: int,
) -> dict[str, Any]:
    session = sessions[candidate.session_name]
    event: dict[str, Any] = {
        "timestamp_utc": now_utc(),
        **asdict(candidate),
        "attempt_index": index,
        "status": "attempted",
        "http_status": "",
        "content_format": "",
        "output_path": "",
        "bytes_written": 0,
        "error": "",
    }
    try:
        max_bytes = int(config["download"].get("max_bytes", 104857600))
        resp = session.get(
            candidate.url,
            timeout=config["request"]["timeout_seconds"],
            headers=domain_headers(candidate.url, config),
            stream=True,
            allow_redirects=True,
            max_bytes=max_bytes,
        )
        event["http_status"] = resp.status_code
        if resp.status_code >= 400:
            event["status"] = "http_error"
            event["error"] = f"HTTP {resp.status_code}"
            return event
        if len(resp.content) > max_bytes:
            event["status"] = "max_bytes_exceeded"
            event["error"] = f"Exceeded {max_bytes} bytes"
            return event

        iterator = resp.iter_content(chunk_size=65536)
        try:
            first = next(iterator)
        except StopIteration:
            first = b""

        content_format = sniff_format(first, resp.headers.get("Content-Type", ""), resp.url)
        event["content_format"] = content_format
        if content_format == "unknown":
            event["status"] = "unsupported_content"
            event["error"] = resp.headers.get("Content-Type", "")
            return event
        if content_format in {"html", "xml", "txt"} and not config["download"].get("save_html", True):
            event["status"] = "skipped_non_pdf"
            return event

        filename = f"{index:03d}_{safe_name(candidate.doi, max_len=50)}_{safe_name(candidate.source, max_len=24)}.{content_format}"
        path = download_dir / filename
        bytes_written = 0
        with path.open("wb") as f:
            if first:
                f.write(first)
                bytes_written += len(first)
            for chunk in iterator:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                f.write(chunk)

        event["status"] = "downloaded"
        event["output_path"] = str(path)
        event["bytes_written"] = bytes_written
        return event
    except HttpRequestError as exc:
        event["status"] = "request_error"
        event["error"] = str(exc)
        return event


def read_dois(args: argparse.Namespace) -> list[str]:
    dois: list[str] = []
    if args.doi:
        dois.extend(args.doi)
    if args.input_csv:
        with open(args.input_csv, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if args.doi_column not in (reader.fieldnames or []):
                raise ValueError(f"DOI column '{args.doi_column}' not found in CSV.")
            for row in reader:
                value = (row.get(args.doi_column) or "").strip()
                if value:
                    dois.append(value)
    normalized = []
    seen = set()
    for doi in dois:
        clean = normalize_doi(doi)
        if clean and clean.lower() not in seen:
            normalized.append(clean)
            seen.add(clean.lower())
    return normalized


def build_run_dir(output_root: Path, run_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"{safe_name(run_name)}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "downloads").mkdir()
    return run_dir


def write_logs(run_dir: Path, events: list[dict[str, Any]]) -> None:
    jsonl_path = run_dir / "access_log.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    csv_path = run_dir / "access_log.csv"
    if events:
        fieldnames = list(events[0].keys())
    else:
        fieldnames = [
            "timestamp_utc",
            "doi",
            "url",
            "source",
            "method",
            "entitlement",
            "status",
            "http_status",
            "content_format",
            "output_path",
            "bytes_written",
            "error",
        ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)


def write_summary(run_dir: Path, dois: list[str], events: list[dict[str, Any]]) -> None:
    downloaded = [event for event in events if event.get("status") == "downloaded"]
    pdfs = [event for event in downloaded if event.get("content_format") == "pdf"]
    html_like = [event for event in downloaded if event.get("content_format") in {"html", "xml", "txt"}]
    successful_dois = {event["doi"].lower() for event in downloaded}
    unresolved = [doi for doi in dois if doi.lower() not in successful_dois]

    lines = [
        "# Access Summary",
        "",
        f"- DOI records: {len(dois)}",
        f"- Downloaded files: {len(downloaded)}",
        f"- PDF files: {len(pdfs)}",
        f"- HTML/XML/text files: {len(html_like)}",
        f"- Unresolved DOI records: {len(unresolved)}",
        "",
        "## Unresolved DOI Records",
        "",
    ]
    lines.extend(f"- {doi}" for doi in unresolved)
    (run_dir / "access_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_candidates_for_doi(
    doi: str,
    config: dict[str, Any],
    sessions: dict[str, HttpSession],
) -> list[Candidate]:
    modes = config.get("access_modes", {})
    candidates: list[Candidate] = []

    if modes.get("open_access", True):
        candidates.extend(collect_unpaywall(doi, config, sessions["default"]))

    if modes.get("crossref_tdm", True):
        candidates.extend(collect_crossref(doi, config, sessions["default"]))

    doi_url = f"https://doi.org/{quote(doi, safe='/')}"
    if modes.get("campus_ip", True):
        candidates.extend(
            discover_fulltext_links(
                doi,
                doi_url,
                source="doi_landing",
                method="campus_ip_or_vpn",
                entitlement="institution_or_public_web",
                config=config,
                session=sessions["default"],
                session_name="default",
            )
        )

    ez = modes.get("ezproxy", {})
    if ez.get("enabled") and "ezproxy" in sessions and ez.get("base_url"):
        proxied_doi = proxify(doi_url, ez)
        discovered = discover_fulltext_links(
            doi,
            proxied_doi,
            source="ezproxy",
            method="institution_ezproxy",
            entitlement="institution_subscription",
            config=config,
            session=sessions["ezproxy"],
            session_name="ezproxy",
        )
        for item in discovered:
            if not item.url.startswith(ez.get("base_url", "")):
                item.url = proxify(item.url, ez)
            item.session_name = "ezproxy"
        candidates.extend(discovered)

    deduped: list[Candidate] = []
    seen = set()
    for candidate in candidates:
        key = candidate.url
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve compliant full-text access for scholarly DOI records.")
    parser.add_argument("--doi", action="append", help="DOI to resolve. Can be passed more than once.")
    parser.add_argument("--input-csv", help="CSV file containing DOI records.")
    parser.add_argument("--doi-column", default="DOI", help="DOI column name for --input-csv.")
    parser.add_argument("--config", help="Access configuration JSON.")
    parser.add_argument("--output-root", required=True, help="Parent folder for the run output.")
    parser.add_argument("--run-name", help="Override config run_name.")
    parser.add_argument("--keep-trying", action="store_true", help="Try all candidate URLs instead of stopping after success.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.run_name:
        config["run_name"] = args.run_name
    if args.keep_trying:
        config["download"]["stop_after_first_success"] = False

    dois = read_dois(args)
    if not dois:
        print("No DOI records supplied.", file=sys.stderr)
        return 1

    run_dir = build_run_dir(Path(args.output_root), config.get("run_name", "literature_access_run"))
    download_dir = run_dir / "downloads"
    sessions = {"default": make_session(config)}
    try:
        ezproxy_session = prepare_ezproxy_session(config)
        if ezproxy_session is not None:
            sessions["ezproxy"] = ezproxy_session
    except (CredentialStoreError, RuntimeError) as exc:
        print(f"EZproxy setup error: {exc}", file=sys.stderr)
        return 2

    events: list[dict[str, Any]] = []
    delay = float(config["request"].get("delay_seconds", 0.5))
    attempt_index = 1
    for doi in dois:
        candidates = collect_candidates_for_doi(doi, config, sessions)
        if not candidates:
            events.append(
                {
                    "timestamp_utc": now_utc(),
                    "doi": doi,
                    "url": "",
                    "source": "",
                    "method": "",
                    "entitlement": "",
                    "content_hint": "",
                    "license_url": "",
                    "session_name": "",
                    "attempt_index": attempt_index,
                    "status": "no_candidate",
                    "http_status": "",
                    "content_format": "",
                    "output_path": "",
                    "bytes_written": 0,
                    "error": "No compliant full-text candidate discovered",
                }
            )
            attempt_index += 1
            continue

        doi_success = False
        for candidate in candidates:
            event = download_candidate(candidate, sessions, config, download_dir, attempt_index)
            events.append(event)
            attempt_index += 1
            if event["status"] == "downloaded":
                doi_success = True
                if config["download"].get("stop_after_first_success", True):
                    break
            time.sleep(delay)
        if not doi_success:
            events.append(
                {
                    "timestamp_utc": now_utc(),
                    "doi": doi,
                    "url": "",
                    "source": "",
                    "method": "",
                    "entitlement": "",
                    "content_hint": "",
                    "license_url": "",
                    "session_name": "",
                    "attempt_index": attempt_index,
                    "status": "no_successful_download",
                    "http_status": "",
                    "content_format": "",
                    "output_path": "",
                    "bytes_written": 0,
                    "error": "Candidates existed but none downloaded",
                }
            )
            attempt_index += 1

    write_logs(run_dir, events)
    write_summary(run_dir, dois, events)
    print(f"Run folder: {run_dir}")
    print(f"DOI records: {len(dois)}")
    print(f"Downloaded files: {sum(1 for event in events if event.get('status') == 'downloaded')}")
    print(f"Audit log: {run_dir / 'access_log.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
