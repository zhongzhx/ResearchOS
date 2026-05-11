name: evidence-promotion

Purpose:
Review ExecutionResult, SkillRun, artifacts, legacy KB outputs, and skill outputs, then decide what can be promoted into Research Brain Repo and at what confidence level.

When to Use:
- Execution Agent completes a task
- SkillRun has output_files or structured_outputs
- legacy KB outputs need Research Brain pages
- failed result must be written to failure memory

Inputs:
- ExecutionResult
- SkillRun
- TaskSpec
- selected_pipeline
- output_files
- structured_outputs
- sources
- validation_report
- artifacts
- project_id

Outputs:
- promotion_decision
- promoted_pages
- rejected_items
- confidence_assignments
- evidence_links
- context_index_update
- graph_update_candidates

Procedure:
1. Read selected_pipeline and promotion_targets.
2. Inspect ExecutionResult status.
3. If failed, only promote to failure memory.
4. Validate source_ids and provenance.
5. Separate evidence, hypothesis, decision, report, failure, and raw artifact.
6. Promote only validated items to Research Brain Repo.
7. Mark unsupported mechanism claims as hypothesis / low confidence.
8. Update Context Index and Research Graph candidates.
9. Return promotion summary.

Validation:
- No source_ids means no high-confidence claim.
- Browser learning evidence cannot become high-confidence peer-reviewed claim.
- Peer-review-simulation output is criticism, not factual evidence.
- Data analysis without statistics cannot claim significance.
- Failed tasks cannot promote success claims.
- Secrets must not be promoted.
- Raw logs should not become compiled truth.

Failure Modes:
- missing source_ids
- unsupported mechanism claim
- output file missing
- failed SkillRun
- ambiguous evidence type
- secret leakage detected
- insufficient statistics

Human Review Requirements:
- required for high-impact claim promotion
- required for animal/human/clinical/dangerous wet-lab conclusions
- required for changing high-confidence compiled truth
- required for promoting browser-derived evidence beyond low confidence

Provenance:
- Internal ResearchOS control skill. Do not store API keys, tokens, cookies, passwords, hidden prompts, or unrelated project memory in outputs.
