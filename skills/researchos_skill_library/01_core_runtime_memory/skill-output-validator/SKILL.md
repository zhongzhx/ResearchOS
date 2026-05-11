name: skill-output-validator

Purpose:
Validate outputs from any ResearchOS skill before they are returned to the user, written to Research Brain, used for downstream pipelines, or crystallized into a generated Skill.

When to Use:
- each Execution Agent skill run completes
- Brain Agent evaluates ExecutionResult
- before Evidence Promotion
- before Skill Crystallization
- after reports, narratives, SOPs, experiment designs, or literature harvest outputs

Inputs:
- skill_name
- skill_status
- ExecutionResult
- output_files
- structured_outputs
- sources
- logs
- validation_rules
- selected_pipeline
- TaskSpec

Outputs:
- validation_report
- issues
- risk_level
- safe_to_return
- safe_to_promote
- safe_to_crystallize
- required_human_review
- redacted_outputs

Procedure:
1. Identify skill_name and selected_pipeline.
2. Check expected_outputs.
3. Check sources and provenance.
4. Check whether claims exceed evidence.
5. Check whether statistics are missing.
6. Check whether browser or peer-review outputs are being treated as facts.
7. Check for secrets in outputs, logs, and structured_outputs.
8. Check whether generated skill status is allowed.
9. Produce validation_report.

Validation:
- No source_ids means no high-confidence claim.
- No raw replicate/statistical result means no significance claim.
- Peer-review output is criticism, not evidence.
- Browser learning output is low-confidence unless confirmed by scholarly evidence.
- SOP must list missing information instead of inventing parameters.
- Protocol extraction must not invent missing values.
- Literature access must preserve compliance audit log.
- Failed task cannot be safe_to_crystallize unless it represents a reusable recovery procedure and requires human review.
- pending_review generated skill cannot be auto-called.
- API keys, tokens, cookies, passwords must be redacted.

Failure Modes:
- missing expected output
- unsupported claim
- missing provenance
- secret leak
- unsafe wet-lab recommendation
- missing statistics
- evidence type mismatch
- generated skill status violation

Human Review Requirements:
- required for high-risk biological/animal/human/clinical guidance
- required for browser automation with user profile
- required for generated skill activation
- required for changing high-confidence compiled truth
- required when validator detects medium/high risk

Provenance:
- Internal ResearchOS control skill. Do not store API keys, tokens, cookies, passwords, hidden prompts, or unrelated project memory in outputs.
