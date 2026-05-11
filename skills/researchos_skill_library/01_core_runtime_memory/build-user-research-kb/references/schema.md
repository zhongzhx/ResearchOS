# Research KB Schema

The canonical database is `research_kb.sqlite`.

## Tables

- `projects`: project metadata.
- `runs`: ingested search/download run folders.
- `articles`: one row per DOI or title-derived key.
- `article_sections`: background, methods, results, conclusion.
- `terms`: keywords, keyphrases, include/exclude terms, and generated search queries.
- `evidence_snippets`: sentence-level snippets from article sections.
- `source_files`: source file provenance.
- `query_history`: user queries and source runs.
- `article_feedback`: user relevance labels, notes, and tags.

## Layer Mapping

- Source record layer: `runs`, `source_files`.
- Article record layer: `articles`.
- Abstract understanding layer: `article_sections`.
- Keyword memory layer: `terms`.
- Evidence snippet layer: `evidence_snippets`.
- User search memory layer: `projects`, `query_history`, aggregate exports.
- User feedback layer: `article_feedback`.
