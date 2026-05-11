---
name: weekly-research-digest
description: Generate and save a weekly research digest from configured research interests and recent notes for local-first experimental science labs. Use for synthetic chemistry, biology, materials science, pharmacology, toxicology, omics, electrochemistry, polymer science, AI for science, and related graduate research tracking.
---

# WeeklyResearchDigestSkill

## input_schema

`research_interests: string[]`, `recent_notes?: string[]`, `max_items?: number`, `language?: "en" | "zh"`, `project_name?: string`, `agent_root?: string`

## output_schema

`title`, `research_interests`, `items[{topic, why_it_matters, transferable_method, hypothesis, low_cost_validation, search_keywords}]`, `created_at`, `id`

## system_instruction

Use configured interests and recent local notes. Do not fabricate papers or citations. Prefer English search keywords. Save generated digests locally.

## run function

```powershell
py .\scripts\weekly_research_digest.py --agent-root "..\agent_data" --project-name "lab" --interest "synthetic chemistry" --interest "machine learning for science"
```

## example

Input: `synthetic chemistry`, `materials characterization`, `machine learning for science`.
Output includes AI-assisted condition optimization, transferable methods, small hypotheses, low-cost validation, and search keywords.
