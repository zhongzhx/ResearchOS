---
name: weekly-research-report
description: Generate advisor-ready weekly graduate research reports from the user's project knowledge base, literature progress, browser learning records, domain entities, experiment designs, experiment results, bottleneck diagnoses, decisions, blockers, and next-week plan. Use when Codex needs to produce a concise weekly report, group-meeting summary, or advisor update.
---

# Weekly Research Report

## Overview

Use this skill to turn project memory into a weekly research report. The report should help a graduate student explain what changed, what was learned, what failed, and what decision is needed next.

## Fast Path

```powershell
py .\scripts\weekly_research_report.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --output-root ".\weekly_reports"
```

Specify dates:

```powershell
py .\scripts\weekly_research_report.py --kb-root ".\agent_data\kbs\my_project" --project-name "my_project" --week-start "2026-04-22" --week-end "2026-04-29" --output-root ".\weekly_reports"
```

## Report Standard

Every weekly report should include:

- One-paragraph summary.
- Literature and knowledge-base progress.
- Experiment/design/result progress.
- Important entities, methods, or evidence added.
- Bottlenecks and risks.
- Decisions made.
- Questions for advisor.
- Next-week plan.

Read `references/weekly_report_schema.md` for the report structure.

## Rules

- Prefer KB evidence over memory.
- Mark empty sections clearly instead of inventing progress.
- Keep advisor summary concise.
- Write the generated report back into the KB.
