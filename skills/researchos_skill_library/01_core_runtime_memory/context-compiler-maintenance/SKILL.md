name: context-compiler-maintenance

Purpose:
Maintain project context indexes, select high-value context for Brain Agent, and generate minimal sanitized context packages for Execution Agent.

When to Use:
- Brain Agent starts planning
- Research Brain Repo updates
- SkillRun completes
- Context Index needs refresh
- Execution Agent needs task-specific context_package

Inputs:
- project_id
- user_query
- intent
- Research Brain Repo index
- project_context_index
- recent SkillRuns
- active claims
- hypotheses
- failures
- datasets
- protocols
- skill_catalog
- pipeline_registry

Outputs:
- brain_context_envelope
- execution_context_package
- selected_sources
- memory_used
- skills_available
- context_hash
- redaction_report

Procedure:
1. Load project_context_index.
2. Select only context relevant to user_query and intent.
3. Build Brain Agent context envelope.
4. Build minimal Execution Agent context_package.
5. Remove forbidden context types.
6. Remove secrets and hidden prompts.
7. Generate context_hash.
8. Record context selection summary.

Validation:
- Execution Agent must not receive full Agent Memory.
- Execution Agent must not receive full Research Brain Repo.
- Execution Agent must not receive full project history.
- Execution Agent must not receive user profile unless required.
- context_package must stay below max_context_tokens.
- forbidden_context_types must be redacted.
- all included sources must be traceable.

Failure Modes:
- context index missing
- too much context selected
- forbidden context detected
- source trace missing
- context hash failure
- secret leakage detected

Human Review Requirements:
- required when private files or browser profile context are included
- required when exporting project context outside local environment
- required when high-risk wet-lab context is used for execution planning

Provenance:
- Internal ResearchOS control skill. Do not store API keys, tokens, cookies, passwords, hidden prompts, or unrelated project memory in outputs.
