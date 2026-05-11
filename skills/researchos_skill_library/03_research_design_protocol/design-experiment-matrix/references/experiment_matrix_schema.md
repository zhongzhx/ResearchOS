# Experiment Matrix Schema

## Core Fields

- `run_id`: stable run label.
- `objective`: research objective.
- `field`: biology, chemistry, materials, or general.
- `factors`: variables being changed.
- `levels`: values for each factor.
- `controls`: negative, positive, blank, baseline, or literature-standard controls.
- `metrics`: measurements and optimization direction.
- `replicates`: suggested repeat count or validation note.
- `safety_check`: compliance or hazard checkpoint.

## Design Rules

- Start with a minimal pilot when factors are numerous.
- Keep controls visible in the run table.
- Define success and failure criteria before execution.
- For wet-lab work, keep the design at planning level until a qualified human reviews the protocol.
- For computational work, include baseline and ablation where possible.
