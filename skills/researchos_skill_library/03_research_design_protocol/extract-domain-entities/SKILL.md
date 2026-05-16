---
name: extract-domain-entities
description: Extract biological, chemical, and materials entities and relationships from project evidence. Use when Codex needs to identify genes, proteins, pathways, diseases, cell lines, compounds, solvents, catalysts, reactions, materials, synthesis conditions, characterization methods, or performance metrics from the user's knowledge base or input files.
---

# Extract Domain Entities

## Overview

Use this skill to turn evidence text into domain memory for biological, chemical, and materials projects. It should read the project KB first, extract entities with source context, and write them back to the KB.

## Fast Path

```powershell
py .\scripts\extract_domain_entities.py --kb-root "..\..\..\..\agent_data\kbs\my_project" --project-name "my_project" --field all --output-root ".\entity_runs"
```

Extract from a file:

```powershell
py .\scripts\extract_domain_entities.py --kb-root ".\agent_data\kbs\my_project" --project-name "my_project" --input-file ".\paper_note.md" --field bio --output-root ".\entity_runs"
```

## Entity Groups

- Biology: disease, gene/protein, pathway, cell line, model organism, assay.
- Chemistry: compound, formula, solvent, catalyst, reaction, condition, characterization.
- Materials: material, composition, synthesis condition, structure, characterization, performance metric.

Read `references/entity_taxonomy.md` for the taxonomy.

## Rules

- Keep source context with every entity.
- Mark extraction confidence; do not claim entity normalization is complete.
- Prefer KB evidence over model memory.
- Do not treat extracted entities as validated mechanisms without supporting article or experiment evidence.
