---
name: diagnose-research-bottleneck
description: Diagnose stalled biological, chemical, or materials research projects using the user's knowledge base, experiment records, failed attempts, result tables, literature evidence, and constraints. Use when Codex needs to find bottleneck causes, rank likely issues, propose validation checks, and recommend next actions.
---

# Diagnose Research Bottleneck

## Overview

Use this skill when progress is stuck. It should inspect the project KB first, compare the current plan, evidence, experiment records, and results, then produce a ranked bottleneck diagnosis and practical recovery plan.

## Fast Path

```powershell
py .\scripts\diagnose_research_bottleneck.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --problem "cell viability improvement has plateaued" --output-root ".\diagnosis_runs"
```

Add experiment files:

```powershell
py .\scripts\diagnose_research_bottleneck.py --kb-root ".\agent_data\kbs\my_project" --project-name "my_project" --problem "yield remains low" --experiment-file ".\results.csv" --output-root ".\diagnosis_runs"
```

## Diagnosis Standard

Every diagnosis should include:

- Current bottleneck statement.
- Evidence used from KB and user files.
- Ranked likely causes.
- What signal supports each cause.
- What quick validation should be run.
- Low-risk fix, medium-risk fix, and ambitious fix.
- Decision checkpoint for continuing, narrowing, or stopping.

Read `references/bottleneck_diagnostic_model.md` for the diagnostic model.

## Rules

- Do not invent experiment results.
- Do not recommend unsafe wet-lab execution without human review and institutional approval.
- Separate evidence, hypothesis, and action.
- Prefer small validation checks before large redesigns.
