---
name: plan-research-route
description: Design a graduate-level research route from a topic direction, advisor prompt, or early research idea. Use when Codex needs to turn a broad topic into research questions, hypotheses, literature-search blocks, method routes, timeline milestones, risk controls, advisor-ready summaries, and next actions for a master's or doctoral research project.
---

# Plan Research Route

## Overview

Use this skill to turn a vague or early-stage research direction into an executable research route. The output should help a graduate student know what to read, what question to narrow, what method to try first, what backup route exists, and what to report to an advisor.

## Fast Path

Generate a route package:

```powershell
py .\scripts\plan_research_route.py --topic "machine learning cancer diagnosis" --field "biomedicine" --degree "master" --duration-months 6 --output-root ".\route_plans"
```

Add known constraints:

```powershell
py .\scripts\plan_research_route.py --topic "your topic" --field "computer science" --duration-months 9 --output-root ".\route_plans" --constraint "no private dataset yet" --available-method "public dataset replication"
```

## Workflow

1. Clarify the research object: topic, field, degree level, expected output, available data/equipment, time limit, and advisor constraints.
2. Split the topic into 3 research-question candidates: conservative, differentiated, and ambitious.
3. Build the literature route: seed keywords, search blocks, inclusion/exclusion rules, and a review matrix.
4. Build the method route: primary method, validation plan, baseline/comparison, backup method, and failure signals.
5. Build the schedule: near-term actions, monthly milestones, advisor checkpoints, and final deliverables.
6. Mark every uncertain item as a validation task, not a fact.

## Output Standard

Every research route must include:

- Research scope: what is inside and outside the project.
- Candidate research questions: at least 3, with tradeoffs.
- Literature search route: keyword groups, databases, screening rules, and reading order.
- Method route: data/materials, method steps, validation plan, analysis plan, backup plan.
- Timeline: weekly first month plus monthly milestones.
- Risk register: missing data, weak novelty, method infeasibility, time risk, compliance/ethics risk.
- Advisor-ready summary: one-page version for meeting discussion.
- Next actions: actions that can be done in the next 7 days.

Match the user's language. If the user asks in Chinese, produce the route in Chinese even when script-generated scaffolding is in English.

## Use With Other Skills

- Use `compliant-literature-access` after the route defines search blocks.
- Use `browser-research-learning` when the route needs active web exploration.
- Use `extract-first-article-keywords` for per-article background/method/result extraction as articles are found.
- Use `build-user-research-kb` to store the route, reading notes, terms, feedback, and evidence in the user's project memory.

## References

Read `references/research_route_schema.md` when a stricter output structure is needed.

## Rules

- Do not present a route as proven until the literature confirms it.
- Do not fabricate novelty, datasets, experimental results, references, or feasibility.
- Prefer a route that a graduate student can execute with visible next steps.
- Keep ambitious ideas paired with a fallback path.
- Separate article evidence, user constraints, and agent inference.
- Include compliance checkpoints for human subjects, animal experiments, clinical data, dangerous wet-lab work, restricted datasets, and institutional policies.
