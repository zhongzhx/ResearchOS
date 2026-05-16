---
name: browser-research-learning
description: Use the user's authorized local browser for research learning. Use when the research agent should actively search web research pages, open scholarly result pages, read page titles/abstract-like text, collect source links, write browser learning notes, and store browser-derived learning records into the user's research knowledge base. This is a first-class browser learning mode, not only a download fallback.
---

# Browser Research Learning

## Overview

Use this skill when the agent should learn through the user's browser. It can search research sites, open pages, read visible/HTML content, collect candidate scholarly links, and write a browser learning record that can be merged into the user's knowledge base.

## Fast Path

```powershell
py .\scripts\browser_research_learning.py --query "machine learning cancer diagnosis" --output-root ".\browser_learning_runs"
```

Use a user browser profile:

```powershell
py .\scripts\browser_research_learning.py --query "your topic" --output-root ".\browser_learning_runs" --profile "Default" --headed
```

Connect to an already running browser through CDP:

```powershell
py .\scripts\browser_research_learning.py --query "your topic" --output-root ".\browser_learning_runs" --cdp-url "http://127.0.0.1:9222"
```

Write learning records into a KB:

```powershell
py .\scripts\browser_learning_to_kb.py --kb-root "..\research-agent-runtime\agent_data\kbs\my_project" --learning-run ".\browser_learning_runs\<run>"
```

Run it as part of the complete agent loop:

```powershell
py ..\..\..\..\backend\research_agent_runtime\scripts\run_research_job.py --project-name "my_project" --query "your topic" --agent-root "..\..\..\..\agent_data" --browser-learning --browser-profile "Default" --browser-headed
```

## What It Produces

Each learning run contains:

- `browser_learning_pages.csv`
- `browser_learning_pages.jsonl`
- `browser_learning_notes.md`
- `browser_learning_summary.json`

Read `references/browser_learning_model.md` when deciding how to treat browser-derived records.

## Rules

- Only use this with user authorization, because it controls a local browser.
- Do not bypass CAPTCHAs, MFA, SSO gates, paywalls, or anti-bot restrictions.
- Prefer user browser profiles only when the user intentionally wants existing login/session access.
- Use browser learning as an active research-learning mode: search, open, read, record, and store. Do not limit it to download fallback.
- Store page-level notes and links; do not claim browser-learned content is peer-reviewed evidence unless a scholarly source confirms it.
- Keep browser-derived records separate from article metadata and abstract-analysis records, but allow them to be connected in the KB.
