---
name: analyze-experiment-results
description: Analyze biological, chemical, and materials experiment result tables or logs, compare conditions, rank candidates, detect failure signals, choose next steps, and store the decision in the user's project knowledge base. Use when Codex needs to interpret result CSV files, metric tables, run logs, or summarized experimental outcomes.
---

# Analyze Experiment Results

## Overview

Use this skill after experiments or computational runs produce results. It ranks conditions, checks whether the result supports the current route, identifies failure patterns, and writes the analysis back to the project KB.

## Fast Path

```powershell
py .\scripts\analyze_experiment_results.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --result-file ".\results.csv" --metric "yield:max" --metric "impurity:min" --output-root ".\result_analysis"
```

## Analysis Standard

Every analysis should include:

- Result file and metrics used.
- Best condition and top-ranked alternatives.
- Whether the improvement is meaningful or only marginal.
- Missing values, outliers, contradictory metrics, and replicate issues.
- Recommended next action: continue, narrow, repeat, redesign, or stop.
- Evidence and decision record written into the KB.

Read `references/result_analysis_model.md` for scoring and decision rules.

## Rules

- Do not overinterpret weak or single-run results.
- Prefer repeated validation before claiming success.
- Report missing metrics and uncertainty explicitly.
- Do not fabricate significance testing if replicate data is unavailable.
