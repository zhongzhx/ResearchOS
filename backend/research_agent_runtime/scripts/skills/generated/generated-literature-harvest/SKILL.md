# Generated Literature Harvest

# Purpose
Build User Research KB completed task_type=literature_harvest with status=completed.

# When to Use
Use when task_type is `literature_harvest` and the user has approved this generated skill.

# Inputs
- project_id
- task_input
- source_ids when evidence is required

# Outputs
- structured_outputs
- sources
- artifacts

# Procedure
1. Read only the task-specific inputs.
2. Execute the approved procedure.
3. Return structured outputs with provenance.

# Validation
- Require sources for evidence-backed claims.
- Mark low-confidence or unsupported claims clearly.

# Failure Modes
- Missing inputs.
- Missing evidence.
- Output validation failure.

# Human Review Requirements
- This generated skill is pending_review by default.
- Human review is required before activation.

# Provenance
- created_from_skillrun_id: a69b3abc0d5d9501ff5741a9
- risk_level: low
