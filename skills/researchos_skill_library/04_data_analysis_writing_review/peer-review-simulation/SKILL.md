---
name: peer-review-simulation
description: Simulate peer-review criticism for manuscript sections, abstracts, results paragraphs, discussion paragraphs, or draft proposals. Use modes for mechanism, statistics, novelty, methods, hostile reviewer, or general review.
---

# PeerReviewSimulationSkill

## input_schema

`manuscript_text: string`, `target_journal?: string`, `research_field?: string`, `review_mode: "mechanism" | "statistics" | "novelty" | "methods" | "hostile_reviewer" | "general"`, `language?: "en" | "zh"`

## output_schema

`overall_assessment`, `major_concerns`, `minor_concerns`, `missing_controls`, `overclaimed_conclusions`, `statistical_issues`, `methodological_gaps`, `reproducibility_issues`, `suggested_experiments`, `suggested_rewriting`.

## system_instruction

Base criticism only on the user-provided text. Do not invent data, citations, or journal rules. Flag claims that are stronger than the provided evidence.

## run function

```powershell
py .\scripts\peer_review_simulation.py --review-mode hostile_reviewer --manuscript-text "Our treatment proves..."
```

## example

Hostile mode sharply flags missing controls, missing statistics, and overclaimed mechanism if those details are absent.
