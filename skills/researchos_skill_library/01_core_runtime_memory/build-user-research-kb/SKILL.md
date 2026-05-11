---
name: build-user-research-kb
description: Build and update a layered personal research knowledge base from literature search runs, article abstract analyses, candidate tables, access logs, and downloaded-paper metadata. Use when Codex needs to turn a user's repeated keyword searches into a durable local knowledge base with source records, article records, abstract understanding, keyword memory, evidence snippets, SQLite tables, CSV exports, and project-level summaries.
---

# Build User Research KB

## Overview

Use this skill after literature search/download and per-article abstract analysis have produced run folders. It builds a user-specific local research knowledge base that remembers what the user searched, what articles were found, what each abstract says, which terms recur, and where every record came from.

## Layers

1. Source record layer: run folders, candidate tables, access logs, article records, downloaded file paths.
2. Article record layer: DOI/title/journal/date/query/download status.
3. Abstract understanding layer: background, methods, results, conclusion per article.
4. Keyword memory layer: extracted keywords, keyphrases, include terms, and generated search queries.
5. Evidence snippet layer: sentence-level snippets from background/methods/results/conclusion.
6. User search memory layer: query history, project metadata, topic profile, and recurring terms.

## Fast Path

Build or update a KB from one search run:

```powershell
py .\scripts\build_research_kb.py --kb-root ".\my_kb" --project-name "my_project" --run-root "..\compliant-literature-access\access_runs\<run_folder>"
```

Build from multiple runs:

```powershell
py .\scripts\build_research_kb.py --kb-root ".\my_kb" --project-name "my_project" --run-root "<run1>" --run-root "<run2>"
```

Search the KB:

```powershell
py .\scripts\query_research_kb.py --kb-root ".\my_kb" --search "your keyword"
```

## Inputs

Preferred input is a run folder from `compliant-literature-access`. The builder looks for:

- `keyword_candidates.csv`
- `access_log.csv`
- `article_records/*.json`
- `article_abstracts/article_abstracts.csv`
- `article_abstracts/article_abstract_*/article_abstract_analysis.json`

It can also ingest an existing KB repeatedly; rows are upserted by DOI where possible.

## Outputs

Inside `--kb-root`:

- `research_kb.sqlite`: durable SQLite database.
- `exports/articles.csv`
- `exports/article_sections.csv`
- `exports/terms.csv`
- `exports/search_queries.csv`
- `exports/evidence_snippets.csv`
- `knowledge_base_summary.md`

## Rules

- Keep provenance for every row: run folder, source file, DOI, and timestamp where available.
- Do not duplicate articles when DOI matches; update them with better abstracts/sections when available.
- Keep metadata fallback rows, but mark their text mode clearly.
- Do not make field-specific assumptions. The KB must work for medicine, natural products, materials, social science, engineering, or any other research area.
- Treat summaries and extracted terms as working notes, not verified facts.
