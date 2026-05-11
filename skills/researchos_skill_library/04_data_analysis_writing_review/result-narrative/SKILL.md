---
name: result-narrative
description: Generate result paragraphs, figure legends, and statistical advice from experimental data summaries or parsed tables. Use for thesis writing, journal manuscript drafting, and presentation result slides across common biological, chemical, materials, analytical, microscopy, chromatography, spectroscopy, and omics outputs.
---

# ResultNarrativeSkill

## input_schema

`data_summary: string`, `parsed_table?: object`, `experiment_type?: string`, `research_field?: string`, `groups?: string[]`, `statistical_method?: string`, `target_style?: "thesis" | "journal" | "presentation"`, `language?: "en" | "zh"`

## output_schema

`result_paragraph`, `figure_legend`, `statistical_advice`, `conclusion_strength`, `unsupported_claims_to_avoid`, `required_additional_information`.

## system_instruction

Do not claim significance without raw replicate values or statistical results. Keep conclusions separated by evidence strength.

## run function

```powershell
py .\scripts\result_narrative.py --data-summary "Treatment increased fluorescence but no p value is available."
```

## example

If only summary data are provided, output descriptive result text and list required replicate/statistical information.
