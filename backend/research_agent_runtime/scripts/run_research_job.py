from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from lab_agent_features import ingest_downloaded_pdfs_to_rag
from runtime_common import (
    add_event,
    create_or_update_job,
    parse_run_folder,
    project_kb_root,
    run_command,
    script_path,
    slug,
    stable_id,
    workspace_root,
)


def record_memory(
    args: argparse.Namespace,
    agent_root: Path,
    job_id: str,
    project_name: str,
    query: str,
    status: str,
    job_root: Path,
    kb_root: Path,
    run_root: Path | None = None,
    browser_learning_run: Path | None = None,
    error: str = "",
) -> None:
    memory_root = Path(args.memory_root).resolve() if args.memory_root else agent_root / "agent_memory"
    try:
        memory_script = script_path("manage-agent-memory", "manage_agent_memory.py")
    except FileNotFoundError as exc:
        add_event(agent_root, job_id, "memory", f"Memory script unavailable: {exc}", level="warning")
        return
    summary = f"Research job {status}. Query: {query}."
    if error:
        summary += f" Error: {error}"
    command = [
        sys.executable,
        str(memory_script),
        "record",
        "--memory-root",
        str(memory_root),
        "--project-name",
        project_name,
        "--task-title",
        f"Research job {job_id}",
        "--task-kind",
        "research_agent_job",
        "--summary",
        summary,
        "--artifact-path",
        str(job_root),
        "--artifact-path",
        str(kb_root),
        "--auto-compact",
        "--max-shard-bytes",
        str(args.memory_max_shard_bytes),
        "--max-entry-bytes",
        str(args.memory_max_entry_bytes),
    ]
    if run_root:
        command.extend(["--artifact-path", str(run_root)])
    if browser_learning_run:
        command.extend(["--artifact-path", str(browser_learning_run)])
    code, _ = run_command(agent_root, job_id, "memory", command, workspace_root())
    if code != 0:
        add_event(agent_root, job_id, "memory", "Agent memory record failed.", level="warning")


def run_job(args: argparse.Namespace) -> int:
    agent_root = Path(args.agent_root).resolve()
    project_name = args.project_name
    query = args.query
    job_id = args.job_id or f"job_{time.strftime('%Y%m%d_%H%M%S')}_{stable_id(project_name, query)}"
    job_root = agent_root / "jobs" / job_id
    literature_root = job_root / "lit"
    browser_learning_root = job_root / "browser"
    kb_root = project_kb_root(agent_root, project_name)
    job_root.mkdir(parents=True, exist_ok=True)
    literature_root.mkdir(parents=True, exist_ok=True)
    browser_learning_run: Path | None = None

    create_or_update_job(
        agent_root,
        job_id,
        project_name,
        query,
        "queued",
        job_root,
        kb_root,
        args.max_results,
        args.source,
    )
    add_event(agent_root, job_id, "queued", "Job created")

    try:
        create_or_update_job(agent_root, job_id, project_name, query, "searching", job_root, kb_root, args.max_results, args.source)
        search_script = script_path("compliant-literature-access", "download_by_keyword_on_campus.py")
        command = [
            sys.executable,
            str(search_script),
            "--query",
            query,
            "--max-results",
            str(args.max_results),
            "--source",
            args.source,
            "--output-root",
            str(literature_root),
            "--run-name",
            stable_id(job_id, "literature"),
            "--keyword-top-n",
            str(args.keyword_top_n),
        ]
        if args.email:
            command.extend(["--email", args.email])
        if args.also_open_access:
            command.append("--also-open-access")
        if args.no_article_analysis:
            command.append("--no-article-analysis")
        if args.browser_fallback:
            command.append("--browser-fallback")
        if args.browser_profile:
            command.extend(["--browser-profile", args.browser_profile])
        if args.browser_headed:
            command.append("--browser-headed")
        if args.browser_session:
            command.extend(["--browser-session", args.browser_session])
        if args.from_year:
            command.extend(["--from-year", str(args.from_year)])
        if args.until_year:
            command.extend(["--until-year", str(args.until_year)])

        search_code, search_output = run_command(agent_root, job_id, "searching", command, workspace_root())
        run_root = parse_run_folder(search_output)
        if run_root and not run_root.is_absolute():
            run_root = (workspace_root() / run_root).resolve()
        if not run_root or not run_root.exists():
            raise RuntimeError("Search run folder was not created.")
        create_or_update_job(agent_root, job_id, project_name, query, "building_kb", job_root, kb_root, args.max_results, args.source, run_root)
        if search_code != 0:
            add_event(agent_root, job_id, "searching", "Search command returned a non-zero code; attempting KB build from partial outputs.", level="warning")

        kb_script = script_path("build-user-research-kb", "build_research_kb.py")
        kb_command = [
            sys.executable,
            str(kb_script),
            "--kb-root",
            str(kb_root),
            "--project-name",
            project_name,
            "--run-root",
            str(run_root),
        ]
        kb_code, _ = run_command(agent_root, job_id, "building_kb", kb_command, workspace_root())
        if kb_code != 0:
            raise RuntimeError("Knowledge-base build failed.")

        if not args.skip_pdf_rag_ingest:
            try:
                pdf_rag_result = ingest_downloaded_pdfs_to_rag(
                    agent_root,
                    {
                        "project_name": project_name,
                        "pdf_dir": str(run_root / "downloads"),
                        "source_type": "paper",
                        "recursive": True,
                        "max_files": args.pdf_rag_max_files,
                    },
                )
                add_event(
                    agent_root,
                    job_id,
                    "pdf_rag_ingest",
                    "Downloaded PDFs were chunked into the local RAG store.",
                    data=pdf_rag_result,
                )
            except Exception as exc:
                add_event(agent_root, job_id, "pdf_rag_ingest", f"PDF RAG ingest failed: {exc}", level="warning")

        if args.browser_learning:
            create_or_update_job(
                agent_root,
                job_id,
                project_name,
                query,
                "browser_learning",
                job_root,
                kb_root,
                args.max_results,
                args.source,
                run_root,
            )
            browser_learning_root.mkdir(parents=True, exist_ok=True)
            learning_script = script_path("browser-research-learning", "browser_research_learning.py")
            learning_command = [
                sys.executable,
                str(learning_script),
                "--query",
                query,
                "--output-root",
                str(browser_learning_root),
                "--max-pages",
                str(args.browser_learning_max_pages),
                "--session",
                args.browser_learning_session,
            ]
            for site in args.browser_learning_site or []:
                learning_command.extend(["--site", site])
            if args.browser_profile:
                learning_command.extend(["--profile", args.browser_profile])
            if args.browser_headed:
                learning_command.append("--headed")
            if args.browser_cdp_url:
                learning_command.extend(["--cdp-url", args.browser_cdp_url])

            learning_code, learning_output = run_command(agent_root, job_id, "browser_learning", learning_command, workspace_root())
            browser_learning_run = parse_run_folder(learning_output)
            if browser_learning_run and not browser_learning_run.is_absolute():
                browser_learning_run = (workspace_root() / browser_learning_run).resolve()
            if learning_code != 0:
                add_event(agent_root, job_id, "browser_learning", "Browser learning command returned a non-zero code.", level="warning")

            if browser_learning_run and browser_learning_run.exists():
                ingest_script = script_path("browser-research-learning", "browser_learning_to_kb.py")
                ingest_command = [
                    sys.executable,
                    str(ingest_script),
                    "--kb-root",
                    str(kb_root),
                    "--learning-run",
                    str(browser_learning_run),
                ]
                ingest_code, _ = run_command(agent_root, job_id, "browser_learning_ingest", ingest_command, workspace_root())
                if ingest_code != 0:
                    add_event(agent_root, job_id, "browser_learning_ingest", "Browser learning records were not written into the KB.", level="warning")
            else:
                add_event(agent_root, job_id, "browser_learning", "Browser learning run folder was not created.", level="warning")

        create_or_update_job(agent_root, job_id, project_name, query, "completed", job_root, kb_root, args.max_results, args.source, run_root)
        add_event(
            agent_root,
            job_id,
            "completed",
            "Job completed",
            data={
                "kb_root": str(kb_root),
                "run_root": str(run_root),
                "browser_learning_run": str(browser_learning_run) if browser_learning_run else "",
            },
        )
        record_memory(args, agent_root, job_id, project_name, query, "completed", job_root, kb_root, run_root, browser_learning_run)
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "job_root": str(job_root),
                    "run_root": str(run_root),
                    "kb_root": str(kb_root),
                    "browser_learning_run": str(browser_learning_run) if browser_learning_run else "",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        create_or_update_job(agent_root, job_id, project_name, query, "failed", job_root, kb_root, args.max_results, args.source, error=str(exc))
        add_event(agent_root, job_id, "failed", str(exc), level="error")
        record_memory(args, agent_root, job_id, project_name, query, "failed", job_root, kb_root, error=str(exc))
        print(json.dumps({"job_id": job_id, "status": "failed", "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a complete research agent job.")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--agent-root", required=True)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--source", choices=["crossref", "openalex", "both"], default="both")
    parser.add_argument("--email", default="")
    parser.add_argument("--also-open-access", action="store_true")
    parser.add_argument("--no-article-analysis", action="store_true")
    parser.add_argument("--browser-fallback", action="store_true")
    parser.add_argument("--browser-learning", action="store_true")
    parser.add_argument("--browser-learning-max-pages", type=int, default=5)
    parser.add_argument("--browser-learning-site", action="append", choices=["pubmed", "semantic_scholar", "google_scholar", "google"], default=None)
    parser.add_argument("--browser-learning-session", default="research-learning")
    parser.add_argument("--browser-profile", default="")
    parser.add_argument("--browser-headed", action="store_true")
    parser.add_argument("--browser-session", default="research-literature")
    parser.add_argument("--browser-cdp-url", default="")
    parser.add_argument("--keyword-top-n", type=int, default=30)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--until-year", type=int)
    parser.add_argument("--job-id")
    parser.add_argument("--memory-root", default="")
    parser.add_argument("--memory-max-shard-bytes", type=int, default=120000)
    parser.add_argument("--memory-max-entry-bytes", type=int, default=24000)
    parser.add_argument("--skip-pdf-rag-ingest", action="store_true")
    parser.add_argument("--pdf-rag-max-files", type=int, default=200)
    args = parser.parse_args()
    return run_job(args)


if __name__ == "__main__":
    raise SystemExit(main())
