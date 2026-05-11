name: skill-router-orchestrator

Purpose:
Route a user research request to the correct ResearchOS pipeline, select active execution skills, define Brain Agent and Execution Agent responsibilities, and generate a safe TaskSpec.

When to Use:
- user request needs pipeline selection
- Brain Agent converts natural language to TaskSpec
- system must decide user authorization requirements

Inputs:
- user_query
- project_id
- project_context_index
- skill_catalog
- pipeline_registry
- resolver_entries
- user_authorization_flags

Outputs:
- selected_pipeline
- intent
- required_skills
- task_type
- expected_outputs
- validation_rules
- promotion_targets
- requires_user_authorization
- TaskSpec draft
- routing_explanation

Procedure:
1. Read user_query.
2. Match query to Pipeline Registry and RESOLVER.
3. Select the best pipeline.
4. Verify all required skills are active.
5. Reject pending_review / rejected / deprecated skills for auto execution.
6. Check whether the pipeline requires user authorization.
7. Build TaskSpec draft.
8. Set Brain Agent and Execution Agent responsibilities.
9. Pass TaskSpec through context isolation before dispatch.

Validation:
- selected_pipeline must exist in pipeline_registry.
- required_skills must exist in skill_catalog.
- Execution Agent can only receive active skills.
- Browser-related pipelines must require user authorization.
- context_package must be minimal and sanitized.
- Do not pass full Research Brain, full KB, full memory, full logs, or secrets to Execution Agent.

Failure Modes:
- no matching pipeline
- multiple ambiguous pipelines
- missing required skill
- required skill is pending_review
- browser task lacks user authorization
- context isolation fails

Human Review Requirements:
- required when task is high risk
- required when browser profile or local credentials are involved
- required when task modifies project code or raw data
- required when generated skill would be activated

Provenance:
- Internal ResearchOS control skill. Do not store API keys, tokens, cookies, passwords, hidden prompts, or unrelated project memory in outputs.
