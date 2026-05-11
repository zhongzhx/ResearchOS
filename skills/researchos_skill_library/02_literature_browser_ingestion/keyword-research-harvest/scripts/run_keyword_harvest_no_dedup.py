from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cancel_requested(run_root: Path) -> bool:
    return (run_root / ".researchos_cancel").exists()


def raise_if_cancelled(run_root: Path) -> None:
    if cancel_requested(run_root):
        raise SystemExit("keyword harvest cancelled by user")


def log(message: str) -> None:
    print(f"[keyword-harvest] {message}", flush=True)


def stable_candidate_record_id(row: pd.Series, fallback_index: int, utils: Any) -> str:
    parts = [
        utils.clean_text(row.get("doi")),
        utils.clean_text(row.get("pmid")),
        utils.clean_text(row.get("pmcid")),
        utils.normalize_title(row.get("title")) if hasattr(utils, "normalize_title") else utils.clean_text(row.get("title")).lower(),
        utils.clean_text(row.get("source_record_id")),
    ]
    key = "|".join(part for part in parts if part) or f"row:{fallback_index}"
    digest = hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"KWPAPER-{digest}"


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def short_download_filename(record_id: Any, stem: str, extension: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(record_id or "record")).strip("._-") or "record"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(stem or "")).strip("._-")
    safe_stem = safe_stem[:42].strip("._-")
    return f"{safe_id}_{safe_stem}{extension}" if safe_stem else f"{safe_id}{extension}"


def detect_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def article_type_guess(title: str, publication_type: str) -> str:
    text = f"{title} {publication_type}".lower()
    if any(token in text for token in ["review", "systematic review", "meta-analysis"]):
        return "review"
    if any(token in text for token in ["editorial", "commentary", "news", "conference abstract", "patent"]):
        return "exclude_non_article"
    if any(token in text for token in ["journal article", "research article", "article"]):
        return "research_article"
    return "research_article_like"


def route_label(url: str) -> str:
    lowered = (url or "").lower()
    if "europepmc" in lowered:
        return "europe_pmc"
    if "pmc.ncbi.nlm.nih.gov" in lowered:
        return "pmc"
    if "doi.org" in lowered:
        return "doi_resolve"
    return "publisher_direct"


def looks_like_direct_fulltext_url(url: str) -> bool:
    lowered = (url or "").lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    return any(
        token in lowered
        for token in [
            ".pdf",
            "/pdf",
            "pdf=",
            "download",
            "fulltextxml",
            "fulltext/xml",
            ".xml",
        ]
    )


def candidate_urls(row: pd.Series, utils: Any) -> list[str]:
    urls: list[str] = []
    for key in ["pdf_url", "fulltext_url"]:
        value = utils.clean_text(row.get(key))
        if looks_like_direct_fulltext_url(value):
            urls.append(value)
    raw_json = utils.clean_text(row.get("candidate_urls_json"))
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        value = utils.clean_text(item)
                    elif isinstance(item, dict):
                        value = utils.clean_text(item.get("url"))
                    else:
                        value = ""
                    if looks_like_direct_fulltext_url(value):
                        urls.append(value)
        except json.JSONDecodeError:
            pass
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def build_candidate_rows(raw_df: pd.DataFrame, config: dict[str, Any], utils: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    include_terms = config.get("include_terms", [])
    secondary_terms = config.get("secondary_terms", [])
    exclude_terms = config.get("exclude_terms", [])
    exclude_reviews = bool(config.get("exclude_reviews_by_default", False))

    for idx, row in raw_df.reset_index(drop=True).iterrows():
        title = utils.clean_text(row.get("title"))
        abstract = utils.clean_text(row.get("abstract"))
        publication_type = utils.clean_text(row.get("publication_type"))
        query_name = utils.clean_text(row.get("query_name"))
        search_query = utils.clean_text(row.get("search_query"))
        evidence_text = " ".join(part for part in [title, abstract, publication_type] if part)
        query_text = " ".join(part for part in [query_name, search_query] if part)
        type_guess = article_type_guess(title, publication_type)
        include_hits = detect_terms(evidence_text, include_terms)
        secondary_hits = detect_terms(evidence_text, secondary_terms)
        exclude_hits = detect_terms(evidence_text, exclude_terms)
        query_hits = detect_terms(query_text, include_terms + secondary_terms)

        score = 0
        if include_hits:
            score += 2 + min(len(include_hits), 3)
        elif query_hits:
            score += 1
        if secondary_hits:
            score += min(len(secondary_hits), 2)
        if bool(row.get("open_access_flag")):
            score += 1
        if type_guess == "review":
            score -= 1
        if type_guess == "exclude_non_article":
            score -= 3
        if exclude_hits and not include_hits:
            score -= 2

        exclusion_reason = ""
        if not title:
            exclusion_reason = "missing_title"
        elif type_guess == "exclude_non_article":
            exclusion_reason = "non_article_type"
        elif exclude_reviews and type_guess == "review":
            exclusion_reason = "review_deprioritized"
        elif exclude_hits and not include_hits:
            exclusion_reason = "excluded_by_title_abstract_terms"
        elif not include_hits and not secondary_hits and not query_hits:
            exclusion_reason = "query_only_without_keyword_signal"
        elif score < 1:
            exclusion_reason = "low_relevance"

        priority = "high" if score >= 4 else ("medium" if score >= 2 else "low")
        rows.append(
            {
                "record_id": stable_candidate_record_id(row, idx + 1, utils),
                "title": title,
                "authors": utils.clean_text(row.get("authors")),
                "year": row.get("year"),
                "journal": utils.clean_text(row.get("journal")),
                "doi": utils.clean_text(row.get("doi")),
                "source_database": utils.clean_text(row.get("source_database")),
                "abstract_if_available": abstract,
                "article_type_guess": type_guess,
                "keyword_include_hits": "; ".join(include_hits),
                "keyword_secondary_hits": "; ".join(secondary_hits),
                "keyword_exclude_hits": "; ".join(exclude_hits),
                "keyword_relevance_score": score,
                "research_article_flag": "yes" if type_guess in {"research_article", "research_article_like"} else "no",
                "likely_topic_tags": "; ".join(sorted(set(include_hits + secondary_hits))),
                "open_access_status_if_detectable": "open_access" if bool(row.get("open_access_flag")) else "not_detected",
                "pdf_url_candidate": utils.clean_text(row.get("pdf_url")) or utils.clean_text(row.get("fulltext_url")) or utils.clean_text(row.get("landing_page_url")),
                "landing_page_url": utils.clean_text(row.get("landing_page_url")),
                "download_status": "excluded" if exclusion_reason else "pending",
                "exclusion_reason_if_any": exclusion_reason,
                "query_name": query_name,
                "search_query": search_query,
                "source_record_id": utils.clean_text(row.get("source_record_id")),
                "candidate_urls_json": row.get("candidate_urls_json", "[]"),
                "pdf_url": utils.clean_text(row.get("pdf_url")),
                "fulltext_url": utils.clean_text(row.get("fulltext_url")),
                "publication_type": publication_type,
            }
        )
    return pd.DataFrame(rows)


def run_downloads(candidate_df: pd.DataFrame, run_root: Path, utils: Any, downloader: Any, config: dict[str, Any]) -> pd.DataFrame:
    work_dir = run_root / "_work"
    pdf_dir = work_dir / "downloaded_pdfs"
    non_pdf_dir = work_dir / "non_pdf"
    log_dir = work_dir / "download_logs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    non_pdf_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "keyword_research_download_log.csv"

    timeout_seconds = int(config.get("download", {}).get("timeout_seconds", 30))
    max_attempts = int(config.get("download", {}).get("max_attempts_per_record", 3))
    delay_seconds = float(config.get("delay_seconds", {}).get("download", 0.2))

    existing_log = safe_read_csv(log_path)
    processed = set(existing_log.get("record_id", pd.Series(dtype=str)).astype(str))
    target_df = candidate_df.loc[
        candidate_df["exclusion_reason_if_any"].fillna("").eq("")
        & ~candidate_df["record_id"].astype(str).isin(processed)
    ].copy()
    log(f"download queue: {len(target_df)} new candidate(s), {len(processed)} already processed")

    rows: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(target_df.iterrows(), start=1):
        raise_if_cancelled(run_root)
        status = "metadata_only"
        reason = "no_candidate_url"
        final_path = ""
        final_url = ""
        access_route = "failed"
        content_format = ""
        attempts = 0
        fallback_path = ""
        fallback_url = ""
        fallback_route = ""
        fallback_format = ""

        for url in candidate_urls(row, utils)[:max_attempts]:
            attempts += 1
            try:
                response = downloader.attempt_download(url, timeout_seconds)
                payload = response["payload"]
                content_type = response["content_type"]
                final_url = response["final_url"] or url
                kind = downloader.classify_payload(payload, content_type)
                if kind == "html":
                    html_text = payload[:25000].decode("utf-8", errors="ignore")
                    if downloader.looks_paywalled(html_text):
                        status = "inaccessible"
                        reason = "paywall_detected"
                        access_route = route_label(final_url)
                        continue
                extension = ".pdf" if kind == "pdf" else utils.content_extension(content_type, final_url)
                if kind == "html":
                    extension = ".html"
                elif kind == "xml":
                    extension = ".xml"
                output_dir = pdf_dir if kind == "pdf" else non_pdf_dir
                output = output_dir / short_download_filename(row.get("record_id"), utils.stable_file_stem(row), extension)
                output.write_bytes(payload)
                if kind != "pdf":
                    fallback_path = fallback_path or str(output)
                    fallback_url = fallback_url or final_url
                    fallback_route = fallback_route or route_label(final_url)
                    fallback_format = fallback_format or kind
                    status = "fulltext_only"
                    reason = "non_pdf_fulltext_saved"
                    final_path = fallback_path
                    access_route = fallback_route
                    content_format = fallback_format
                    continue
                status = "success"
                reason = ""
                final_path = str(output)
                access_route = route_label(final_url)
                content_format = kind
                break
            except urllib.error.HTTPError as exc:
                code = int(getattr(exc, "code", 0))
                status = "inaccessible" if code in {401, 402, 403} else ("broken_link" if code in {404, 410} else "metadata_only")
                if code == 429:
                    status = "rate_limited"
                reason = f"http_{code}"
                final_url = url
                access_route = route_label(url)
                if code == 429:
                    break
                continue
            except Exception as exc:  # noqa: BLE001
                status = "metadata_only"
                reason = type(exc).__name__
                final_url = url
                access_route = route_label(url)
                continue
            finally:
                time.sleep(delay_seconds)

        if not final_path and fallback_path:
            status = "fulltext_only"
            reason = "non_pdf_fulltext_saved"
            final_path = fallback_path
            final_url = fallback_url
            access_route = fallback_route
            content_format = fallback_format

        rows.append(
            {
                "record_id": row["record_id"],
                "doi": row.get("doi"),
                "title": row.get("title"),
                "final_pdf_path": final_path,
                "final_pdf_url": final_url,
                "download_status": status,
                "failure_reason": reason,
                "access_route_used": access_route,
                "content_format": content_format,
                "attempt_count": attempts,
            }
        )
        if status == "success":
            log(f"downloaded {idx}/{len(target_df)}: {content_format or 'file'} {row.get('title')}")
        elif idx == 1 or idx % 10 == 0:
            log(f"download checked {idx}/{len(target_df)}: {status} {reason}")
        chunk = pd.DataFrame(rows)
        if log_path.exists():
            combined = pd.concat([safe_read_csv(log_path), chunk], ignore_index=True)
        else:
            combined = chunk
        combined = combined.drop_duplicates(subset=["record_id"], keep="last")
        combined.to_csv(log_path, index=False, encoding="utf-8-sig")
        rows = []

    if log_path.exists():
        combined = pd.concat([safe_read_csv(log_path), pd.DataFrame(rows)], ignore_index=True)
    else:
        combined = pd.DataFrame(rows)
    if not combined.empty:
        combined = combined.drop_duplicates(subset=["record_id"], keep="last")
    combined.to_csv(log_path, index=False, encoding="utf-8-sig")
    return combined


def build_write_and_download(
    run_root: Path,
    config: dict[str, Any],
    utils: Any,
    downloader: Any,
    *,
    load_sources: Any,
    normalize_columns: Any,
    deduplicate_sources: Any | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_df, _ = load_sources()
    raw_df = normalize_columns(raw_df)
    if deduplicate_sources is not None and not raw_df.empty:
        raw_df, _ = deduplicate_sources(raw_df)
    candidate_df = build_candidate_rows(raw_df, config, utils)
    if candidate_df.empty:
        for column in [
            "record_id",
            "exclusion_reason_if_any",
            "keyword_relevance_score",
            "year",
            "download_status",
        ]:
            if column not in candidate_df.columns:
                candidate_df[column] = pd.Series(dtype="object")
    else:
        candidate_df = candidate_df.sort_values(["keyword_relevance_score", "year"], ascending=[False, False], na_position="last").reset_index(drop=True)
    utils.write_csv(candidate_df, run_root / "keyword_research_candidate_table.csv")

    high_df = candidate_df.loc[candidate_df["exclusion_reason_if_any"].eq("") & candidate_df["keyword_relevance_score"].ge(4)].copy()
    medium_df = candidate_df.loc[candidate_df["exclusion_reason_if_any"].eq("") & candidate_df["keyword_relevance_score"].between(2, 3)].copy()
    utils.write_csv(high_df, run_root / "keyword_research_high_priority.csv")
    utils.write_csv(medium_df, run_root / "keyword_research_medium_priority.csv")

    log(f"candidate table updated: {len(candidate_df)} rows; high={len(high_df)}, medium={len(medium_df)}")
    log_df = run_downloads(candidate_df, run_root, utils, downloader, config)
    raise_if_cancelled(run_root)

    if {"record_id", "download_status"}.issubset(set(log_df.columns)):
        status = log_df[["record_id", "download_status"]].drop_duplicates("record_id", keep="last")
    else:
        status = pd.DataFrame(columns=["record_id", "download_status"])
    candidate_df = candidate_df.drop(columns=["download_status"], errors="ignore").merge(status, on="record_id", how="left")
    candidate_df["download_status"] = candidate_df["download_status"].fillna(candidate_df["exclusion_reason_if_any"].map(lambda x: "excluded" if x else "pending"))
    utils.write_csv(candidate_df, run_root / "keyword_research_candidate_table.csv")
    return candidate_df, high_df, medium_df, log_df


def write_summary(run_root: Path, candidate_df: pd.DataFrame, high_df: pd.DataFrame, medium_df: pd.DataFrame, log_df: pd.DataFrame) -> None:
    success = int(log_df["download_status"].eq("success").sum()) if not log_df.empty else 0
    pdf_count = int(log_df.loc[log_df["download_status"].eq("success"), "content_format"].fillna("").eq("pdf").sum()) if not log_df.empty else 0
    non_pdf = success - pdf_count
    pending = int(candidate_df["download_status"].eq("pending").sum())
    lines = [
        "# Keyword Research Harvest Summary",
        "",
        f"- Candidate rows: `{len(candidate_df)}`",
        f"- High-priority rows: `{len(high_df)}`",
        f"- Medium-priority rows: `{len(medium_df)}`",
        f"- Successful downloads/full texts: `{success}`",
        f"- True PDFs: `{pdf_count}`",
        f"- HTML/XML full texts: `{non_pdf}`",
        f"- Remaining pending: `{pending}`",
        f"- Download log: `{run_root / '_work' / 'download_logs' / 'keyword_research_download_log.csv'}`",
    ]
    (run_root / "keyword_research_harvest_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, help="Parent folder where the new run folder should be created")
    parser.add_argument("--config", required=True, help="JSON config path")
    parser.add_argument("--run-name", required=True, help="New run folder name under literature_harvest")
    parser.add_argument("--skip-search", action="store_true")
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    run_root = output_root / args.run_name
    run_root.mkdir(parents=True, exist_ok=True)
    work_root = run_root / "_work"
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ["ASPERGILLUS_HARVEST_ROOT"] = str(work_root)

    skill_root = Path(__file__).resolve().parents[1]
    scripts_dir = skill_root / "literature_harvest" / "scripts"
    sys.path.insert(0, str(scripts_dir))

    from download_fulltexts import attempt_download, classify_payload, looks_paywalled  # noqa: WPS433
    from harvest_utils import ensure_directories, load_config, write_csv  # noqa: WPS433
    from merge_and_deduplicate import deduplicate, load_sources, normalize_columns  # noqa: WPS433
    from search_crossref import search_crossref  # noqa: WPS433
    from search_europepmc import search_europepmc  # noqa: WPS433
    from search_openalex import search_openalex  # noqa: WPS433
    from search_pubmed import search_pubmed_and_pmc  # noqa: WPS433
    import harvest_utils as utils  # noqa: WPS433

    config = load_json(Path(args.config))
    ensure_directories()

    downloader = type(
        "DownloaderNamespace",
        (),
        {
            "attempt_download": staticmethod(attempt_download),
            "classify_payload": staticmethod(classify_payload),
            "looks_paywalled": staticmethod(looks_paywalled),
        },
    )

    candidate_df = pd.DataFrame()
    high_df = pd.DataFrame()
    medium_df = pd.DataFrame()
    log_df = pd.DataFrame()

    if not args.skip_search:
        search_stages = [
            ("OpenAlex", search_openalex),
            ("Crossref", search_crossref),
            ("EuropePMC", search_europepmc),
            ("PubMed/PMC", search_pubmed_and_pmc),
        ]
        for source_name, search_func in search_stages:
            raise_if_cancelled(run_root)
            log(f"search started: {source_name}")
            try:
                source_df = search_func(args.config)
                log(f"search finished: {source_name}, rows={len(source_df)}")
            except Exception as exc:  # noqa: BLE001
                append_jsonl(
                    run_root / "search_stage_errors.jsonl",
                    {
                        "source": source_name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(limit=4),
                    },
                )
                log(f"search failed: {source_name}, {type(exc).__name__}: {exc}")
                continue
            candidate_df, high_df, medium_df, log_df = build_write_and_download(
                run_root,
                config,
                utils,
                downloader,
                load_sources=load_sources,
                normalize_columns=normalize_columns,
                deduplicate_sources=deduplicate,
            )
    else:
        log("skip-search enabled; using existing raw API result tables")

    candidate_df, high_df, medium_df, log_df = build_write_and_download(
        run_root,
        config,
        utils,
        downloader,
        load_sources=load_sources,
        normalize_columns=normalize_columns,
        deduplicate_sources=deduplicate,
    )
    write_summary(run_root, candidate_df, high_df, medium_df, log_df)
    log("keyword harvest first pass completed")


if __name__ == "__main__":
    main()
