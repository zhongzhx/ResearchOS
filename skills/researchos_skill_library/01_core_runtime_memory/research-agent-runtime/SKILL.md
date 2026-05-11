---
name: research-agent-runtime
description: Run the complete research agent as a local command-line workflow or HTTP API. Use when Codex needs to orchestrate keyword literature search, campus-network download, per-article abstract analysis, knowledge-base updates, async job status, event logs, user feedback, and knowledge-base question answering for a user-specific research agent.
---

# Research Agent Runtime

## Overview

Use this skill as the top-level agent runtime. It connects the lower-level skills into one complete workflow:

1. Search by user keywords.
2. Process each article as it appears.
3. Analyze each article abstract into background, methods, results, and conclusion.
4. Update the user's research knowledge base.
5. Optionally use the user's authorized browser to learn the topic and store browser learning records.
6. Store job status, events, and centralized agent memory.
7. Accept user feedback.
8. Answer questions from the user's knowledge base with source references.

## Fast Path

Run one complete job:

```powershell
py .\scripts\run_research_job.py --project-name "my_project" --query "machine learning cancer diagnosis" --max-results 20 --agent-root ".\agent_data"
```

Enable browser learning as a first-class research mode:

```powershell
py .\scripts\run_research_job.py --project-name "my_project" --query "your topic" --max-results 20 --agent-root ".\agent_data" --browser-learning --browser-profile "Default" --browser-headed
```

Enable browser-use fallback when normal API/current-network download fails:

```powershell
py .\scripts\run_research_job.py --project-name "my_project" --query "your topic" --max-results 20 --agent-root ".\agent_data" --browser-fallback
```

Browser learning and browser fallback require the `browser-use` CLI to be installed on PATH. The repository may be present locally, but browser control remains unavailable until the CLI is installed.

Start the local API server:

```powershell
py .\scripts\research_agent_api.py --host 127.0.0.1 --port 8765 --agent-root ".\agent_data"
```

Every completed or failed job is recorded into centralized memory. By default this is:

```text
.\agent_data\agent_memory
```

Override it when needed:

```powershell
py .\scripts\run_research_job.py --project-name "my_project" --query "your topic" --agent-root ".\agent_data" --memory-root ".\agent_memory"
```

Ask the knowledge base:

```powershell
py .\scripts\answer_kb.py --kb-root ".\agent_data\kbs\my_project" --question "What methods are used?"
```

Record feedback:

```powershell
py .\scripts\record_feedback.py --agent-root ".\agent_data" --project-name "my_project" --doi "10.xxxx/example" --relevance relevant --notes "Useful methods section"
```

## API Endpoints

The server uses standard-library HTTP only.

- `GET /health`
- `POST /projects`
- `POST /search-jobs`
- `GET /jobs/<job_id>`
- `GET /jobs/<job_id>/events`
- `GET /articles?project_name=<name>&search=<text>`
- `GET /articles/<article_id>?project_name=<name>`
- `GET /browser-learning?project_name=<name>&search=<text>`
- `GET /research-interests?project_name=<name>`
- `POST /research-interests`
- `POST /weekly-digest`
- `GET /weekly-digest?project_name=<name>`
- `POST /protocol-extract`
- `POST /sop-generate`
- `GET /failure-records?project=<name>&search=<text>`
- `POST /failure-records`
- `POST /failure-records/match`
- `POST /peer-review`
- `POST /data-parse`
- `POST /result-narrative`
- `POST /rag/documents`
- `POST /rag/query`
- `GET /ui`
- `POST /kb/query`
- `POST /feedback`

Read `references/api.md` for request examples.

## Data Layout

Under `--agent-root`:

- `runtime_state.sqlite`: job, event, and feedback state.
- `jobs/<job_id>/`: per-job literature runs and logs.
- `kbs/<project_slug>/research_kb.sqlite`: project knowledge base.
- `kbs/<project_slug>/exports/`: CSV exports.
- `agent_memory/`: task records and compact context shards.
- `lab_agent_mvp.sqlite`: research interests, digest history, failure records, and local RAG document chunks.

## Rules

- Keep the lower-level skill outputs intact; this runtime should orchestrate, not replace them.
- Use async jobs for API calls; do not block HTTP requests until search/download finishes.
- Treat downloaded full text as user/project-local data.
- Browser-use fallback is optional. Use it when current-network/API download fails and the user wants browser-based discovery of PDF/full-text links.
- Browser learning is optional but first-class. Use it when the user wants the agent to search, open, read, and learn through the authorized local browser.
- Record meaningful tasks in `agent_memory` and compact context into shards instead of expanding one unbounded file.
- Every job must write status and event history.
- Every answer from the KB must include source article references when available.
