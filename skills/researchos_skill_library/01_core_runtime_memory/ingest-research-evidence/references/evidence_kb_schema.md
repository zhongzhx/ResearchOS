# Evidence KB Schema

All project skills should use the same project database:

`<kb-root>/research_kb.sqlite`

## Shared Tables

`research_evidence`
- Project-local evidence items from literature notes, browser learning, experiment records, result tables, route plans, advisor feedback, decisions, and failure notes.
- Keep `source_kind`, `source_path`, `content_text`, `content_json`, `tags_json`, and confidence/credibility separate.

`domain_entities`
- Extracted biological, chemical, and materials entities with source evidence and context.

`domain_relationships`
- Entity-to-entity or entity-to-method relationships extracted from evidence.

`experiment_designs`
- Experiment matrices, variables, controls, metrics, pilot subsets, and safety checkpoints.

`experiment_results`
- Result analyses, metric rankings, best conditions, uncertainty notes, and next action.

`bottleneck_diagnoses`
- Ranked causes, evidence signals, validation checks, and recovery actions.

`research_decisions`
- Human or agent-assisted decisions with rationale and linked evidence.

`weekly_reports`
- Advisor-ready weekly reports generated from project memory.

## Source Priority

1. Project KB evidence and experiment records.
2. Structured article metadata and abstract analysis.
3. Professional domain databases.
4. Browser learning records.
5. Agent inference.

Keep agent inference marked as inference.
