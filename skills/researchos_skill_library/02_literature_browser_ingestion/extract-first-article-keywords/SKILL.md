---
name: extract-first-article-keywords
description: Summarize each newly found or downloaded scholarly article as it appears, extract abstract background, methods, results, conclusion, and generate search-expansion terms. Use when a literature agent is streaming papers from keyword search, campus-network download, DOI run, CSV candidate table, PDF, HTML, XML, or text file and should analyze every article immediately rather than waiting for the full batch.
---

# Extract Article Abstracts As Found

## Overview

Use this skill every time a new article is found or downloaded. Its job is to read that article's abstract first, summarize the paper into background, methods, results, and conclusion, then produce a compact keyword expansion package for search refinement.

## Fast Path

From a run folder created by `compliant-literature-access`:

```powershell
py .\scripts\extract_first_article_keywords.py --run-root "..\compliant-literature-access\access_runs\<run_folder>" --output-root ".\keyword_outputs"
```

From one streamed article record:

```powershell
py .\scripts\extract_first_article_keywords.py --record-json ".\article_records\article_0001.json" --output-root ".\article_abstracts" --append-summary ".\article_abstracts\article_abstracts.csv"
```

From a single article file:

```powershell
py .\scripts\extract_first_article_keywords.py --article-file ".\paper.pdf" --output-root ".\keyword_outputs"
```

From a candidate table before a file is downloaded:

```powershell
py .\scripts\extract_first_article_keywords.py --candidate-csv ".\keyword_candidates.csv" --output-root ".\keyword_outputs"
```

## Workflow

1. Identify one article:
   - Prefer `--record-json` when the search/download agent is streaming articles one by one.
   - Use `--article-file` for a direct PDF/HTML/XML/text file.
   - `--run-root` and `--candidate-csv` remain available for compatibility and analyze the first usable row only.
2. Extract abstract:
   - Prefer the `abstract` column from `keyword_candidates.csv` or `access_log.csv`.
   - If no abstract metadata exists, try to find the abstract inside downloaded HTML/XML/text/PDF.
   - If abstract extraction fails, fall back to title/journal/metadata and clearly mark that fallback.
3. Generate:
   - `abstract_summary`: background, methods, results, and conclusion.
   - `primary_keywords`: generic search terms useful for the next query.
   - `keyphrases`: 2-5 word phrases useful for exact or quoted search.
   - `search_queries`: ready-to-run query suggestions.
   - `include_terms`: terms likely related to the user's topic.
   - `exclude_terms`: generic or weak terms to avoid over-broad search.
4. Write outputs:
   - `article_abstract_report.md`
   - `article_abstract_analysis.csv`
   - `article_abstract_analysis.json`
   - `next_search_terms.txt`

## Use With The First Skill

When the download/search agent finds or finishes one article, run this skill immediately for that article. The `compliant-literature-access` keyword script does this automatically when both skill folders are adjacent in the same workspace. It writes one per-article folder and appends a row to `article_abstracts/article_abstracts.csv`.

Use abstract metadata when available. If only full text exists, extract the abstract from the full text. If only metadata exists, still run the extractor, but report that the output came from metadata fallback rather than a real abstract.

## Constraints

- Do not claim an abstract was read if extraction failed. The report must state the source used: abstract metadata, abstract extracted from full text, full-text fallback, or metadata fallback.
- Keep per-article outputs separate, and append the one-row summary to the aggregate `article_abstracts.csv`.
- Keep this skill domain-neutral. Do not hard-code natural-products, medical, materials, or other field-specific keyword boosts unless the user asks for that vertical.
- Treat extracted keywords as suggestions, not verified domain entities.
