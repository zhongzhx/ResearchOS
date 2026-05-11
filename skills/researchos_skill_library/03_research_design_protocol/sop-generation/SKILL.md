---
name: sop-generation
description: Generate a conservative Standard Operating Procedure from an experiment goal, extracted protocol JSON, lab constraints, available equipment, and safety level. Use for local-first graduate lab SOP drafting and reproducibility checklists.
---

# SOPGenerationSkill

## input_schema

`experiment_goal: string`, `protocol_json?: object`, `lab_constraints?: string[]`, `available_equipment?: string[]`, `safety_level?: string`, `target_format?: "word" | "markdown" | "json"`, `language?: "en" | "zh"`

## output_schema

Includes `title`, `objective`, `principle`, `scope`, `materials_and_reagents`, `equipment`, `experimental_design`, `step_by_step_procedure`, `key_parameters`, `quality_control_points`, `common_failure_modes`, `troubleshooting`, `data_recording_template`, `safety_and_waste_disposal_notes`, `information_to_confirm_before_execution`.

## system_instruction

Be conservative and reproducibility-oriented. Do not invent missing parameters. For cell experiments, include contamination, cell state, passage number, solvent concentration, positive control, and negative control checks. For human/animal work, only provide design-level and ethics documentation guidance.

## run function

```powershell
py .\scripts\sop_generation.py --experiment-goal "Generate SOP for CCK-8 assay" --protocol-json ".\protocol.json"
```

## example

Input: goal plus extracted protocol JSON. Output: copyable Markdown SOP with missing information checklist.
