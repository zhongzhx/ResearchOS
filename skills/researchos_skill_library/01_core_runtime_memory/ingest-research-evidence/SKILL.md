---
name: ingest-research-evidence
description: Ingest project evidence into the user's research knowledge base. Use when Codex needs to store literature notes, browser learning outputs, experiment records, result tables, advisor feedback, research-route plans, failure notes, or user decisions as project-local evidence before downstream biological, chemical, or materials research analysis.
---

# Ingest Research Evidence

## Overview

Use this skill as the entry point for anything that should become project memory. The project knowledge base is the first reference source for later planning, diagnosis, experiment design, result analysis, and weekly reporting.

## Fast Path

```powershell
py .\scripts\ingest_research_evidence.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --source-file ".\note.md" --source-kind "literature_note"
```

Ingest direct text:

```powershell
py .\scripts\ingest_research_evidence.py --kb-root ".\agent_data\kbs\my_project" --project-name "my_project" --source-text "Advisor suggested narrowing to PI3K/AKT pathway." --source-kind "advisor_feedback" --title "Advisor meeting"
```

## Workflow

1. Identify the project KB before answering.
2. Store the incoming material as `research_evidence`.
3. Keep the source kind explicit: `literature_note`, `experiment_record`, `result_table`, `browser_learning`, `advisor_feedback`, `route_plan`, `failure_note`, or `decision_note`.
4. Preserve source path and tags when available.
5. Trigger downstream skills only after evidence is stored or clearly unavailable.

## Knowledge Base Rule

Every downstream skill should read the project KB first. Every downstream skill should write its useful output back as evidence, decision, design, result, diagnosis, or report.

Read `references/evidence_kb_schema.md` for the shared table names.

## Rules

- Do not merge user evidence with external facts without marking the source.
- Do not overwrite prior evidence; append or update by stable evidence id.
- Treat user notes, browser pages, and model inferences as lower-confidence than structured article evidence unless validated.
- Do not store passwords, tokens, private patient identifiers, or unapproved sensitive data.
