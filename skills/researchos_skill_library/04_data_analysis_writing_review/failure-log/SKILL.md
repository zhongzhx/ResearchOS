---
name: failure-log
description: Manage a local failure log and negative-results encyclopedia for experimental research. Use to create, edit, delete, search, and match historical failed experiments against a new biological, chemical, or materials experimental plan.
---

# FailureLogSkill

## input_schema

`FailureRecord` fields: `id`, `title`, `project`, `research_field`, `experiment_type`, `date`, `operator`, `objective`, `protocol_summary`, `observed_failure`, `suspected_causes`, `confirmed_cause`, `solution_attempted`, `final_outcome`, `tags`, `related_files`, `created_at`, `updated_at`.

## output_schema

Create/edit/search returns failure records. Match returns `risk_level` and `matched_failures[{title, similarity_reason, suggestion}]`.

## system_instruction

Store negative results locally. For matching, explain why a historical failure is relevant and provide actionable suggestions. Do not overstate similarity.

## run function

```powershell
py .\scripts\failure_log.py create --agent-root "..\agent_data" --title "Poor reproducibility due to uncontrolled pH" --project "lab"
py .\scripts\failure_log.py match --agent-root "..\agent_data" --project "lab" --experimental-plan "nanoparticle synthesis with pH-sensitive condition"
```

## example

New pH-sensitive synthesis plan matches prior pH-related failure and suggests recording pH before/after reagent addition.
