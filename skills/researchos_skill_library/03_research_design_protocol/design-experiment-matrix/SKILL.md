---
name: design-experiment-matrix
description: Design controlled experiment matrices for biological, chemical, and materials projects from a research objective, KB evidence, variables, controls, metrics, and constraints. Use when Codex needs to plan experiment groups, factor levels, controls, evaluation metrics, minimal validation runs, and backup designs.
---

# Design Experiment Matrix

## Overview

Use this skill to convert a research objective into a controlled experiment plan. It is optimized for biology, chemistry, and materials projects where variables, controls, metrics, and feasibility constraints must be explicit.

## Fast Path

```powershell
py .\scripts\design_experiment_matrix.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --objective "optimize nanoparticle synthesis stability" --field materials --factor "temperature:60,80,100" --factor "pH:6,7,8" --metric "particle_size:min" --metric "stability:max" --output-root ".\experiment_designs"
```

## Design Standard

Every matrix should include:

- Objective and field.
- Factors and levels.
- Controls and baseline.
- Metrics and optimization direction.
- Run table.
- Minimal pilot subset.
- Randomization/replicate suggestion where applicable.
- Safety, ethics, and feasibility checkpoints.

Read `references/experiment_matrix_schema.md` for table structure.

## Rules

- Read project KB before proposing variables when a KB is available.
- Keep wet-lab instructions at design level unless the user has approved a safe protocol context.
- Add controls before optimization.
- Do not maximize novelty at the cost of losing a feasible thesis route.
