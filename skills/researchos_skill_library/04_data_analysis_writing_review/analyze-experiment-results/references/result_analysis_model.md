# Result Analysis Model

## Scoring

Use user-provided metric directions when available:

- `metric:max`: higher is better.
- `metric:min`: lower is better.

Normalize numeric metrics before combining when there is more than one metric. If replicate columns or repeated conditions are present, report uncertainty rather than claiming a stable winner.

## Decision Categories

- Continue: clear improvement and no blocking risk.
- Narrow: one factor dominates and the next run should refine it.
- Repeat: promising result but weak replicate support.
- Redesign: results conflict with the hypothesis or controls fail.
- Stop: route is not producing useful signal and a backup route is stronger.

## Failure Signals

- Missing metrics.
- Controls missing or worse than expected.
- Large variance between replicates.
- Improvement is marginal.
- One metric improves while another critical metric collapses.
