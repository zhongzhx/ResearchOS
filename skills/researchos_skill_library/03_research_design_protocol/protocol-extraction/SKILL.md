---
name: protocol-extraction
description: Extract structured experimental protocol JSON from pasted Methods, materials, results, or supplementary text. Use for biological, chemical, materials, pharmaceutical, biomedical, environmental, omics, and analytical research protocols in Chinese or English.
---

# ProtocolExtractionSkill

## input_schema

`paper_text: string`, `section_hint?: "methods" | "materials" | "results" | "supplementary"`, `experiment_type?: string`, `language?: "en" | "zh"`

## output_schema

Includes `experiment_type`, `research_field`, `organisms_or_cell_lines`, `materials`, `reagents`, `instruments`, `software`, `concentrations`, `temperature`, `time`, `pH`, `pressure`, `atmosphere`, `sample_size`, `control_groups`, `treatment_groups`, `assay_readouts`, `characterization_methods`, `statistical_methods`, `safety_notes`, `missing_information`, `reproducibility_warnings`.

## system_instruction

Extract only what appears in the provided text. Put missing parameters in `missing_information`; put ambiguous parameters in `reproducibility_warnings`. Do not invent values.

## run function

```powershell
py .\scripts\protocol_extraction.py --paper-text "Cells were treated with 10 uM compound for 24 h at 37 °C..."
```

## example

For CCK-8 text, output cell line, reagent concentration, 37 °C, 24 h, readout, missing controls, and reproducibility warnings.
