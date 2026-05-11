---
name: parse-scientific-data
description: Parse CSV and XLSX scientific data tables for local-first research workflows. Use when Codex needs to detect sample columns, group columns, numeric columns, missing values, duplicated samples, metadata columns, descriptive statistics, and possible omics fields for downstream result narrative generation.
---

# CSV and Excel Scientific Data Parser

## input_schema

`file_path?: string`, `csv_text?: string`, `file_name?: string`

## output_schema

`row_count`, `column_count`, `detected_groups`, `sample_count_per_group`, `missing_value_ratio`, `descriptive_statistics`, `sample_columns`, `group_columns`, `numeric_columns`, `possible_metadata_columns`, `omics_fields`.

## system_instruction

Return `unknown` when a field cannot be identified confidently. Validate file type and report errors clearly.

## run function

```powershell
py .\scripts\parse_scientific_data.py --csv-text "sample,group,value`ns1,control,1.2`ns2,treatment,2.4"
```

## example

CSV input returns group counts, numeric column stats, missing-value ratio, and omics field guesses when available.
