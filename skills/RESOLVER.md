# Skill Resolver

This file is the human-readable mirror of `skills/researchos_skill_library/pipeline_registry.json`.
Execution should prefer the JSON registry and the canonical skill paths in `skill_catalog.json`.

## System Control Skills

### skill_router_orchestrator
Used by Brain Agent before every task to select pipeline and build TaskSpec.

### context_compiler_maintenance
Used by Brain Agent before dispatching to Execution Agent and after Research Brain updates.

### skill_output_validator
Used after every Execution Agent skill run and before evidence promotion.

### evidence_promotion
Used after validation to decide what enters Research Brain Repo.

For every pipeline:

Pre-dispatch:
- skill-router-orchestrator
- context-compiler-maintenance

Post-execution:
- skill-output-validator
- evidence-promotion

## literature_harvest
Intent: literature_harvest
Trigger phrases:
- 文献采集
- 搜索文献
- 下载论文
- keyword harvest
- literature harvest
Planner: brain_agent
Executor: execution_agent
Execution skills:
- compliant-literature-access
- extract-first-article-keywords
- build-user-research-kb
Brain responsibilities:
- define search scope
- check compliance requirements
- validate article evidence
- update Research Brain and Context Index
- decide skill crystallization
Execution responsibilities:
- run compliant literature access
- extract article keywords
- build local KB
Required inputs:
- keywords
- project_id
Expected outputs:
- paper_table
- downloaded_pdfs
- ingestion_status
Validation rules:
- check compliance requirements
- article evidence must retain source_ids
- do not bypass paywalls
Promotion targets:
- papers
- claims
- project memory
- context index
Auto-call policy: medium risk; small compliant access can auto-run, large harvest requires task-level user approval.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/02_literature_browser_ingestion/compliant-literature-access/SKILL.md
Fallback:
skills/researchos_skill_library/02_literature_browser_ingestion/keyword-research-harvest/SKILL.md

## browser_research_learning
Intent: browser_research_learning
Trigger phrases:
- 浏览器学习
- browser learning
- learn this website
Planner: brain_agent
Executor: execution_agent
Execution skills:
- browser-research-learning
Brain responsibilities:
- request authorization
- downgrade confidence
- decide whether notes enter memory
Execution responsibilities:
- only visit authorized pages
- record browser learning evidence
Required inputs:
- url
- user_authorization
Expected outputs:
- browser_learning_evidence
Validation rules:
- requires user authorization
- no CAPTCHA, MFA, SSO, paywall, or anti-bot bypass
- browser records are browser_learning evidence, not peer-reviewed evidence
Promotion targets:
- browser_learning evidence
- project memory
- low-confidence notes
Auto-call policy: never auto-call without explicit user authorization.
Requires user authorization: true
Skill path:
skills/researchos_skill_library/02_literature_browser_ingestion/browser-research-learning/SKILL.md
Fallback:

## research_route_planning
Intent: research_route_planning
Trigger phrases:
- 规划研究路线
- research route
- 项目路线
Planner: brain_agent
Executor: execution_agent
Execution skills:
- plan-research-route
- ingest-research-evidence
Brain responsibilities:
- define project route
- write decisions after review
Execution responsibilities:
- run route planning and evidence ingest skills
Required inputs:
- project_context
Expected outputs:
- research_plan
- evidence_items
Validation rules:
- separate project data from literature evidence
- uncertain suggestions stay draft
Promotion targets:
- project memory
- decisions
- workflows
Auto-call policy: allowed when context is local and low risk.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/03_research_design_protocol/plan-research-route/SKILL.md
Fallback:
skills/researchos_skill_library/01_core_runtime_memory/ingest-research-evidence/SKILL.md

## protocol_to_sop
Intent: protocol_to_sop
Trigger phrases:
- Methods 转 SOP
- method to SOP
- protocol to sop
- 生成 SOP
Planner: brain_agent
Executor: execution_agent
Execution skills:
- protocol-extraction
- sop-generation
Brain responsibilities:
- validate protocol provenance
- decide if SOP is usable
Execution responsibilities:
- extract protocol
- generate SOP
Required inputs:
- method_text
Expected outputs:
- protocol
- sop
Validation rules:
- preserve source protocol
- mark inferred steps
- human confirmation before wet-lab use
Promotion targets:
- protocols
- experiments
- decisions
Auto-call policy: allowed for draft SOP only.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/03_research_design_protocol/protocol-extraction/SKILL.md
Fallback:
skills/researchos_skill_library/03_research_design_protocol/sop-generation/SKILL.md

## experiment_design
Intent: experiment_design
Trigger phrases:
- 实验设计
- 实验分组
- experiment design
Planner: brain_agent
Executor: execution_agent
Execution skills:
- design-experiment-matrix
Brain responsibilities:
- ensure design matches project context
Execution responsibilities:
- build experiment matrix
Required inputs:
- objective
- constraints
Expected outputs:
- experiment_matrix
Validation rules:
- include controls
- report missing replicates
- mark assumptions
Promotion targets:
- experiments
- protocols
- decisions
Auto-call policy: allowed for draft plans.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/03_research_design_protocol/design-experiment-matrix/SKILL.md
Fallback:
skills/researchos_skill_library/03_research_design_protocol/plan-research-route/SKILL.md

## data_analysis_to_narrative
Intent: data_analysis_to_narrative
Trigger phrases:
- 分析 CSV 并写结果段
- 分析数据写结果
- data analysis narrative
Planner: brain_agent
Executor: execution_agent
Execution skills:
- parse-scientific-data
- analyze-experiment-results
- result-narrative
Brain responsibilities:
- validate claims and confidence
- promote supported outputs
Execution responsibilities:
- parse data
- analyze results
- write narrative
Required inputs:
- data_file
Expected outputs:
- structured_data
- analysis_result
- narrative
Validation rules:
- do not claim significance without statistical evidence
- no raw replicate values means low-confidence conclusion
- missing values and uncertainty must be reported
Promotion targets:
- datasets
- claims
- decisions
- reports
Auto-call policy: allowed for local files; never modify raw data.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/parse-scientific-data/SKILL.md
Fallback:
skills/researchos_skill_library/04_data_analysis_writing_review/analyze-experiment-results/SKILL.md

## failure_recovery
Intent: failure_recovery
Trigger phrases:
- 实验失败复盘
- failure recovery
- 失败记录
Planner: brain_agent
Executor: execution_agent
Execution skills:
- failure-log
- diagnose-research-bottleneck
Brain responsibilities:
- write failure memory
- decide whether reusable fix exists
Execution responsibilities:
- structure failure log
- diagnose bottleneck
Required inputs:
- failure_description
Expected outputs:
- failure_memory
- diagnosis
Validation rules:
- do not blame without evidence
- separate hypothesis from confirmed failure reason
Promotion targets:
- failures
- decisions
- pending skills if reusable fix exists
Auto-call policy: allowed.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/failure-log/SKILL.md
Fallback:
skills/researchos_skill_library/04_data_analysis_writing_review/diagnose-research-bottleneck/SKILL.md

## writing_review
Intent: writing_review
Trigger phrases:
- 模拟审稿人批评
- peer review
- review my draft
Planner: brain_agent
Executor: execution_agent
Execution skills:
- result-narrative
- peer-review-simulation
Brain responsibilities:
- separate critique from evidence
- store unresolved issues
Execution responsibilities:
- write narrative
- produce review critique
Required inputs:
- draft_or_result_summary
Expected outputs:
- narrative
- critique
Validation rules:
- peer review output is criticism, not factual evidence
- do not invent citations or journal rules
Promotion targets:
- reports
- decisions
- unresolved issues
Auto-call policy: allowed, but output is not factual evidence.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/result-narrative/SKILL.md
Fallback:
skills/researchos_skill_library/04_data_analysis_writing_review/peer-review-simulation/SKILL.md

## weekly_reporting
Intent: weekly_reporting
Trigger phrases:
- 周报
- weekly report
- weekly digest
Planner: brain_agent
Executor: execution_agent
Execution skills:
- weekly-research-report
- weekly-research-digest
Brain responsibilities:
- confirm memory updates
- track next actions
Execution responsibilities:
- generate report and digest
Required inputs:
- project_id
Expected outputs:
- report
- digest
Validation rules:
- report only known project state
- mark missing context
Promotion targets:
- reports
- project memory
- next actions
Auto-call policy: allowed for draft reports.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/weekly-research-report/SKILL.md
Fallback:
skills/researchos_skill_library/04_data_analysis_writing_review/weekly-research-digest/SKILL.md

## entity_extraction
Intent: entity_extraction
Trigger phrases:
- 提取实体
- extract entities
- 靶点模型方法
Planner: brain_agent
Executor: execution_agent
Execution skills:
- extract-domain-entities
- ingest-research-evidence
Brain responsibilities:
- promote to graph and low-risk memory
Execution responsibilities:
- extract entities and evidence
Required inputs:
- text
Expected outputs:
- entities
- evidence_items
Validation rules:
- keep source_ids
- do not promote unsourced mechanisms as facts
Promotion targets:
- graph
- claims
- project memory
Auto-call policy: allowed.
Requires user authorization: false
Skill path:
skills/researchos_skill_library/03_research_design_protocol/extract-domain-entities/SKILL.md
Fallback:
skills/researchos_skill_library/01_core_runtime_memory/ingest-research-evidence/SKILL.md


## nature_figure_generation
Intent: nature_figure_generation
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-figure
Brain responsibilities:
- define figure claim and evidence logic
- verify supplied data provenance
- keep figure interpretation draft unless evidence is present
Execution responsibilities:
- run Nature figure workflow
- create figure spec, code, output files, and QA notes when backend is selected
Required inputs:
- figure_goal
- data_file
- backend_choice
Expected outputs:
- figure_spec
- figure_code
- qa_report
Validation rules:
- ask Python or R before rendering
- do not fabricate data
- keep editable vector output when possible
Promotion targets:
- figures
- reports
- datasets
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- Nature figure
- publication figure
- scientific figure
- manuscript figure
- 科研作图
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/nature-figure/SKILL.md

## nature_citation_support
Intent: nature_citation_support
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-citation
Brain responsibilities:
- define citation scope
- validate whether candidates actually support each claim segment
Execution responsibilities:
- run Nature/CNS citation workflow
- return citation candidates, evidence notes, and export metadata
Required inputs:
- manuscript_text or claim_text
Expected outputs:
- citation_candidates
- reference_export
- evidence_notes
Validation rules:
- do not fabricate DOI, pages, volume, journal metadata, or claim support
Promotion targets:
- references
- reports
- citation evidence
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- Nature citation
- CNS citation
- supporting references
- text citation
- 补引用
- 支撑文献
Skill path:
skills/researchos_skill_library/02_literature_browser_ingestion/nature-citation/SKILL.md

## nature_academic_polishing
Intent: nature_academic_polishing
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-polishing
Brain responsibilities:
- identify section purpose and overclaim risk
- prevent invented claims or citations
Execution responsibilities:
- polish manuscript text and return revision notes
Required inputs:
- manuscript_text
- section_type
Expected outputs:
- polished_text
- revision_notes
- risk_flags
Validation rules:
- preserve scientific meaning
- do not invent data or citations
- flag overclaims
Promotion targets:
- reports
- manuscript drafts
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- Nature style
- academic polishing
- polish manuscript
- 论文润色
- 学术英语
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/nature-polishing/SKILL.md

## nature_data_availability
Intent: nature_data_availability
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-data
Brain responsibilities:
- check dataset coverage and confidence
- store only reviewed dataset decisions
Execution responsibilities:
- draft Data Availability statement and FAIR checklist
Required inputs:
- dataset_inventory
- journal_context
Expected outputs:
- data_availability_statement
- repository_actions
- fair_audit
Validation rules:
- do not invent accession numbers
- map every dataset to an access route
- flag missing repository metadata
Promotion targets:
- datasets
- reports
- decisions
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- Data Availability
- FAIR metadata
- repository plan
- 数据可用性
- 数据共享
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/nature-data/SKILL.md

## nature_reviewer_response
Intent: nature_reviewer_response
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-response
Brain responsibilities:
- verify response traceability
- separate manuscript commitments from missing author input
Execution responsibilities:
- triage reviewer comments and draft response letter
Required inputs:
- reviewer_comments
- revision_notes
Expected outputs:
- response_letter
- comment_triage
- author_inputs_needed
Validation rules:
- do not invent manuscript changes, experiments, citations, or line numbers
- every reviewer comment must be addressed or flagged
Promotion targets:
- reports
- decisions
- unresolved issues
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- response to reviewers
- rebuttal letter
- major revision
- 审稿意见回复
- 返修回复
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/nature-response/SKILL.md

## nature_paper_to_ppt
Intent: nature_paper_to_ppt
Planner: brain_agent
Executor: execution_agent
Execution skills:
- nature-paper2ppt
Brain responsibilities:
- define presentation goal and factual boundaries
- prevent fabricated paper results
Execution responsibilities:
- build PPTX package and QA summary from paper material
Required inputs:
- paper_pdf or paper_text
Expected outputs:
- pptx
- speaker_notes
- qa_report
Validation rules:
- do not fabricate paper results or figure details
- slides must follow the paper argument
Promotion targets:
- reports
- presentations
Auto-call policy:
- active skill can be routed by Brain Agent
Requires user authorization:
- false
Trigger phrases:
- paper PPT
- paper to slides
- journal club
- 文献汇报
- 组会PPT
Skill path:
skills/researchos_skill_library/04_data_analysis_writing_review/nature-paper2ppt/SKILL.md
