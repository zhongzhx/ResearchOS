# Research Agent Runtime API

Start server:

```powershell
py ..\..\..\..\backend\research_agent_runtime\scripts\research_agent_api.py --host 127.0.0.1 --port 8765 --agent-root ".\agent_data"
```

## Create Project

`POST /projects`

```json
{"project_name": "my_project"}
```

## Start Search Job

`POST /search-jobs`

```json
{
  "project_name": "my_project",
  "query": "machine learning cancer diagnosis",
  "max_results": 20,
  "source": "both",
  "also_open_access": false,
  "email": "",
  "browser_fallback": false,
  "browser_learning": true,
  "browser_learning_max_pages": 5,
  "browser_learning_site": ["pubmed", "semantic_scholar"],
  "browser_learning_session": "research-learning",
  "browser_profile": "",
  "browser_headed": false,
  "browser_cdp_url": "",
  "memory_root": "",
  "memory_max_shard_bytes": 120000,
  "memory_max_entry_bytes": 24000
}
```

`browser_fallback` requires the `browser-use` CLI to be installed on PATH. If it is not installed, the job continues and records a browser fallback event as unavailable.

`browser_learning` is a first-class browser research mode. It opens research pages with the user's authorized browser session, writes `browser_learning_*` output files under the job folder, and ingests page-level learning records into the project KB. If `browser-use` is not installed, the job continues and records the browser learning run as unavailable.

If `memory_root` is empty, the job records task memory under `<agent_root>/agent_memory`. The memory manager writes task records and compact context shards, creating new shard files when one context file reaches the configured size.

## Job Status

`GET /jobs/<job_id>`

`GET /jobs/<job_id>/events`

## Articles

`GET /articles?project_name=<name>&search=<text>`

`GET /articles/<article_id>?project_name=<name>`

## Browser Learning Pages

`GET /browser-learning?project_name=<name>&search=<text>`

## Lab Agent MVP Endpoints

Agent memory:

`POST /memory/groups`

`POST /memory/projects`

`PUT /memory/projects/<project_id>`

`POST /memory/experiments`

`PUT /memory/experiments/<experiment_id>`

`POST /memory/samples`

`PUT /memory/samples/<sample_id>`

`POST /memory/protocols`

`PUT /memory/protocols/<protocol_id>`

`POST /memory/data-files`

`POST /memory/data-files/link-project`

`POST /memory/data-files/link-experiment`

`POST /memory/create`

`PUT /memory/<memory_id>`

`POST /memory/archive`

`DELETE /memory/<memory_id>`

`POST /memory/retrieve`

```json
{
  "user_id": "local_user",
  "project_id": "project_id",
  "query": "What failed qPCR experiments should we avoid repeating?",
  "memory_types": ["failure_memory"],
  "max_results": 20
}
```

`POST /memory/context`

```json
{
  "user_id": "local_user",
  "project_id": "project_id",
  "query": "What should the assistant remember before writing the manuscript?",
  "max_tokens": 1500
}
```

`POST /memory/consolidate`

`POST /memory/extract`

`GET /memory/projects/<project_id>/memory`

`GET /memory/projects/<project_id>/view`

`GET /memory/experiments/<experiment_id>/memory`

`GET /memory/review-queue`

Research interests:

`GET /research-interests?project_name=<name>`

`POST /research-interests`

```json
{"project_name": "my_project", "keyword": "synthetic chemistry", "description": "reaction condition optimization"}
```

Weekly digest:

`POST /weekly-digest`

```json
{
  "project_name": "my_project",
  "research_interests": ["synthetic chemistry", "machine learning for science"],
  "recent_notes": ["Need better pH tracking"],
  "max_items": 5,
  "language": "en"
}
```

Protocol/SOP:

`POST /protocol-extract`

`POST /sop-generate`

Failure encyclopedia:

`GET /failure-records?project=<name>&search=<text>`

`POST /failure-records`

`POST /failure-records/match`

Review, data, and RAG:

`POST /peer-review`

`POST /data-parse`

`POST /result-narrative`

`POST /rag/documents`

`POST /rag/ingest-pdfs`

```json
{
  "project_name": "my_project",
  "pdf_dir": "C:\\Users\\me\\Downloads\\papers",
  "source_type": "paper",
  "recursive": true,
  "max_files": 200,
  "force": false
}
```

This scans the folder for PDF files, extracts text page by page, chunks it into the local RAG store, and preserves page numbers in chunk metadata.

`POST /rag/query`

Local UI:

`GET /ui`

## Query KB

`POST /kb/query`

```json
{
  "project_name": "my_project",
  "question": "What methods are used?"
}
```

## Feedback

`POST /feedback`

```json
{
  "project_name": "my_project",
  "doi": "10.xxxx/example",
  "relevance": "relevant",
  "notes": "Important methods section",
  "tags": ["keep", "methods"]
}
```
