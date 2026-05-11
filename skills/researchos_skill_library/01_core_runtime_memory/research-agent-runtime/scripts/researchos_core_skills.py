from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


CORE_SKILL_FOLDERS = [
    "analyze-experiment-results",
    "browser-research-learning",
    "build-user-research-kb",
    "compliant-literature-access",
    "design-experiment-matrix",
    "diagnose-research-bottleneck",
    "extract-domain-entities",
    "extract-first-article-keywords",
    "failure-log",
    "ingest-research-evidence",
    "keyword-research-harvest",
    "manage-agent-memory",
    "parse-scientific-data",
    "peer-review-simulation",
    "plan-research-route",
    "protocol-extraction",
    "research-agent-runtime",
    "result-narrative",
    "sop-generation",
    "weekly-research-digest",
    "weekly-research-report",
    "nature-citation",
    "nature-data",
    "nature-figure",
    "nature-paper2ppt",
    "nature-polishing",
    "nature-response",
]

CANONICAL_SKILL_LOCATIONS = {
    "nature-citation": "skills/researchos_skill_library/02_literature_browser_ingestion/nature-citation",
    "nature-data": "skills/researchos_skill_library/04_data_analysis_writing_review/nature-data",
    "nature-figure": "skills/researchos_skill_library/04_data_analysis_writing_review/nature-figure",
    "nature-paper2ppt": "skills/researchos_skill_library/04_data_analysis_writing_review/nature-paper2ppt",
    "nature-polishing": "skills/researchos_skill_library/04_data_analysis_writing_review/nature-polishing",
    "nature-response": "skills/researchos_skill_library/04_data_analysis_writing_review/nature-response",
}

EXCLUDED_DEPENDENCY_SKILL_PATHS = [
    "ui/skills/shadcn/SKILL.md",
    "agent-ui/node_modules/dotenv/skills/dotenv/SKILL.md",
    "agent-ui/node_modules/dotenv/skills/dotenvx/SKILL.md",
]

BROWSER_TOOL_SKILL_PATHS = [
    "../02_literature_browser_ingestion/browser-use/SKILL.md",
    "../02_literature_browser_ingestion/cloud/SKILL.md",
    "../02_literature_browser_ingestion/open-source/SKILL.md",
    "../02_literature_browser_ingestion/remote-browser/SKILL.md",
]


COMMON_SCIENCE_DOMAINS = ["biology", "chemistry", "materials science", "biomedical research", "analytical science"]


CORE_SKILL_METADATA: dict[str, dict[str, Any]] = {
    "analyze-experiment-results": {
        "domain": "data_analysis",
        "applicable_domains": COMMON_SCIENCE_DOMAINS,
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "result_file|csv_text|file_id": "string optional", "metrics": "array optional"},
        "output_schema": {"analysis": "object", "claims": "array", "next_actions": "array", "evidence_refs": "array"},
        "required_file_types": ["csv", "xlsx", "txt", "md", "instrument export"],
        "required_tools": ["DataContext", "Claim/Provenance", "local SQLite", "rule parser"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Every result claim should point to source files, rows, DataContext, or SkillRun provenance.",
        "memory_policy": "Write project-level execution memory and evidence-linked claims; do not promote project data to system memory.",
        "migration_notes": "Merged with DataContext, report generation, and Claim/Provenance handlers.",
    },
    "browser-research-learning": {
        "domain": "literature",
        "applicable_domains": ["scholarly literature", "browser-based research", "methods scouting"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "keywords": "array|string", "authorized_browser_notes": "string optional"},
        "output_schema": {"literature_search_task": "object", "browser_learning_plan": "object", "references": "array"},
        "required_file_types": ["html", "txt", "md", "csv"],
        "required_tools": ["manual/browser provider", "Reference memory", "RAG knowledge base"],
        "required_models": ["mock/manual provider"],
        "citation_policy": "Use citation-numbered outputs from stored references and chunks; store URLs and access notes.",
        "memory_policy": "Store browser-derived learning as literature/reference memory and project KB entries.",
        "migration_notes": "Registered as a scientific literature workflow; nested browser-use skills remain tool capabilities.",
    },
    "build-user-research-kb": {
        "domain": "literature",
        "applicable_domains": ["project knowledge base", "RAG", "literature review"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "reference_ids": "array optional", "keywords": "array optional"},
        "output_schema": {"knowledge_base_entries": "array", "reference_chunks": "array", "rag_ready": "boolean"},
        "required_file_types": ["csv", "json", "txt", "md", "pdf text"],
        "required_tools": ["references", "reference_chunks", "knowledge_base_entries", "RAG query"],
        "required_models": ["local lexical retriever"],
        "citation_policy": "Keep reference ids and stable citation numbers in each RAG answer.",
        "memory_policy": "Store durable project KB entries without mixing projects.",
        "migration_notes": "Connected to ResearchOS literature/RAG tables.",
    },
    "compliant-literature-access": {
        "domain": "literature_access",
        "applicable_domains": ["scholarly literature", "open access", "institutional access"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string optional", "doi|url|title|keywords": "string|array", "access_mode": "string optional"},
        "output_schema": {"access_plan": "object", "references": "array", "audit_notes": "array"},
        "required_file_types": ["doi list", "csv", "pdf metadata", "html metadata"],
        "required_tools": ["DOI metadata", "access policy", "reference tracking"],
        "required_models": ["none"],
        "citation_policy": "Store metadata, DOI, URL, access status, and source path; do not cite unavailable full text as read.",
        "memory_policy": "Store access decisions as provenance and reference memory.",
        "migration_notes": "Connected to legal literature access policy and metadata-only imports.",
    },
    "design-experiment-matrix": {
        "domain": "experiment_design",
        "applicable_domains": COMMON_SCIENCE_DOMAINS,
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "objective": "string", "variables": "array optional", "controls": "array optional"},
        "output_schema": {"experiment_matrix": "array", "sample_table": "array", "qc_rules": "array"},
        "required_file_types": ["md", "txt", "csv"],
        "required_tools": ["protocol structure", "sample table generator", "workflow board"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Tie design decisions to source protocols, KB evidence, or user constraints.",
        "memory_policy": "Create execution memory; optionally store project planning notes.",
        "migration_notes": "Complements built-in plate layout, reagent, sample table, and workflow board logic.",
    },
    "diagnose-research-bottleneck": {
        "domain": "project_diagnosis",
        "applicable_domains": COMMON_SCIENCE_DOMAINS,
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "question": "string optional"},
        "output_schema": {"diagnosis_report": "object", "unsupported_claims": "array", "next_steps": "array"},
        "required_file_types": ["md", "txt", "csv"],
        "required_tools": ["failure-log", "claims", "project gap analysis", "reports"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Each diagnosis must name the claim, file, failure log, or report that supports it.",
        "memory_policy": "Store reusable lessons only when stripped of private project data.",
        "migration_notes": "Mapped to ProjectGapAnalysisSkill, failure logs, claims, and weekly reports.",
    },
    "extract-domain-entities": {
        "domain": "entity_extraction",
        "applicable_domains": COMMON_SCIENCE_DOMAINS,
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "text|file_id": "string"},
        "output_schema": {"entities": "array", "relationships": "array", "provenance": "array"},
        "required_file_types": ["txt", "md", "csv", "pdf text"],
        "required_tools": ["research memory", "domain ontology", "provenance records"],
        "required_models": ["rule parser", "mock LLM adapter optional"],
        "citation_policy": "Entity extraction must preserve source snippets and file ids.",
        "memory_policy": "Write project memory entities with trust_level raw_extracted until confirmed.",
        "migration_notes": "Connected to ResearchOS memory_entities and provenance_records.",
    },
    "extract-first-article-keywords": {
        "domain": "literature",
        "applicable_domains": ["literature search", "keyword expansion", "RAG ingestion"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string optional", "article_text|abstract|reference_id": "string"},
        "output_schema": {"seed_keywords": "array", "expanded_queries": "array", "article_summary": "object"},
        "required_file_types": ["txt", "md", "html", "pdf text"],
        "required_tools": ["keyword-research-harvest", "reference_chunks", "RAG ingestion"],
        "required_models": ["rule parser"],
        "citation_policy": "Keyword expansions should refer to the originating article/reference.",
        "memory_policy": "Store keyword seeds in literature/reference memory when project_id is present.",
        "migration_notes": "Connected to keyword harvest and literature search seed generation.",
    },
    "failure-log": {
        "domain": "execution_memory",
        "applicable_domains": COMMON_SCIENCE_DOMAINS,
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "title": "string", "observed_failure": "string optional"},
        "output_schema": {"failure_log": "object", "matched_failures": "array"},
        "required_file_types": ["md", "txt", "csv"],
        "required_tools": ["failure_logs", "project memory", "weekly report"],
        "required_models": ["none"],
        "citation_policy": "Failure records should link to experiment files, protocols, or SkillRuns when available.",
        "memory_policy": "Keep failure logs project-scoped and searchable for future diagnostics.",
        "migration_notes": "Connected to new ResearchOS failure_logs and execution memory.",
    },
    "ingest-research-evidence": {
        "domain": "evidence_ingestion",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["literature review"],
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "evidence_text|reference|file_id": "object|string"},
        "output_schema": {"references": "array", "claims": "array", "knowledge_base_entries": "array"},
        "required_file_types": ["txt", "md", "csv", "json", "pdf text"],
        "required_tools": ["references", "claims", "claim_evidence", "source provenance"],
        "required_models": ["rule parser"],
        "citation_policy": "Evidence ingestion must preserve source paths, snippets, and reference ids.",
        "memory_policy": "Write project-local evidence; do not silently create confirmed claims.",
        "migration_notes": "Connected to references, papers, reports, claims, and provenance.",
    },
    "keyword-research-harvest": {
        "domain": "literature",
        "applicable_domains": ["keyword search", "literature harvesting", "RAG"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "keywords": "array|string", "provider": "manual|mock|browser optional"},
        "output_schema": {"literature_search_task": "object", "references": "array", "knowledge_base_entries": "array"},
        "required_file_types": ["csv", "json", "pdf metadata", "html", "txt"],
        "required_tools": ["literature_search_tasks", "references", "manual/mock provider", "RAG"],
        "required_models": ["none"],
        "citation_policy": "References imported from harvests must keep DOI/URL/source metadata.",
        "memory_policy": "Store task and reference memory at project scope.",
        "migration_notes": "Connected to local literature search task, reference import, and RAG construction.",
    },
    "manage-agent-memory": {
        "domain": "memory",
        "applicable_domains": ["agent memory", "project memory", "execution memory", "skill memory"],
        "skill_type": "workflow",
        "input_schema": {"memory_scope": "system|project|skill|literature|execution", "project_id": "string optional", "title": "string", "content": "string"},
        "output_schema": {"memory": "object", "isolation": "object"},
        "required_file_types": ["md", "json"],
        "required_tools": ["agent_memory_entries", "execution_memory", "old agent_memory compatibility"],
        "required_models": ["none"],
        "citation_policy": "Memory entries should preserve source_type, source_id, and provenance where available.",
        "memory_policy": "System, project, execution, skill, and literature memory are separate scopes.",
        "migration_notes": "Preserves existing agent_memory behavior and adds explicit execution memory records.",
    },
    "parse-scientific-data": {
        "domain": "data_parsing",
        "applicable_domains": ["qPCR", "ELISA", "LC-MS", "Western blot", "animal records", "scientific tables"],
        "skill_type": "code",
        "input_schema": {"project_id": "string", "csv_text|file_path|file_id": "string"},
        "output_schema": {"parsed_table": "object", "data_context": "object", "evidence": "array"},
        "required_file_types": ["csv", "tsv", "xlsx", "txt"],
        "required_tools": ["file ingestion", "DataContext", "sample links"],
        "required_models": ["none"],
        "citation_policy": "Parsed values should retain file id, row, column, and sample links where possible.",
        "memory_policy": "Create execution memory and data context; do not delete raw files.",
        "migration_notes": "Merged with current file extraction and DataContext completion flow.",
    },
    "peer-review-simulation": {
        "domain": "peer_review",
        "applicable_domains": ["manuscripts", "grant proposals", "result interpretation"],
        "skill_type": "prompt",
        "input_schema": {"project_id": "string optional", "manuscript_text|claim_text": "string", "review_mode": "string optional"},
        "output_schema": {"review": "object", "unsupported_claims": "array", "risk_flags": "array"},
        "required_file_types": ["md", "txt", "docx text"],
        "required_tools": ["claims", "unsupported conclusion detection", "report generation"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Criticism should identify which local claim or passage it targets.",
        "memory_policy": "Store execution memory; do not auto-confirm reviewer claims.",
        "migration_notes": "Connected to claims and manuscript risk analysis.",
    },
    "plan-research-route": {
        "domain": "planning",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["graduate research planning"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "topic|objective": "string", "constraints": "array optional"},
        "output_schema": {"route": "object", "workflow": "object", "next_experiments": "array"},
        "required_file_types": ["md", "txt"],
        "required_tools": ["workflow templates", "weekly direction tracking", "decision loop"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Route recommendations should cite KB evidence or explicitly mark assumptions.",
        "memory_policy": "Store project planning memory and execution memory.",
        "migration_notes": "Connected to project planning, workflow templates, and next-step recommendations.",
    },
    "protocol-extraction": {
        "domain": "protocols",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["protocol extraction"],
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "paper_text|methods_text|text": "string"},
        "output_schema": {"protocol": "object", "steps": "array", "warnings": "array"},
        "required_file_types": ["txt", "md", "pdf text", "html"],
        "required_tools": ["PaperToProtocolSkill", "protocols", "KitTemplate"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Protocol fields should preserve source text snippets or source file ids.",
        "memory_policy": "Create protocol records with skill_run_id and provenance.",
        "migration_notes": "Uses existing PaperToProtocolSkill handler rather than duplicating protocol storage.",
    },
    "research-agent-runtime": {
        "domain": "runtime",
        "applicable_domains": ["runtime orchestration", "SkillRun", "workflow runner", "execution logs"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string optional", "task_title": "string optional", "input_payload": "object optional"},
        "output_schema": {"runtime_status": "object", "execution_memory": "object"},
        "required_file_types": ["json", "md"],
        "required_tools": ["SkillRun", "workflow runner", "execution_memory"],
        "required_models": ["none"],
        "citation_policy": "Runtime records preserve object refs and provenance, not scientific claims by themselves.",
        "memory_policy": "Every run creates execution memory and may promote reusable lessons to draft skills.",
        "migration_notes": "Connected to unified SkillRun and execution memory persistence.",
    },
    "result-narrative": {
        "domain": "writing",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["manuscript writing", "figure legends"],
        "skill_type": "prompt",
        "input_schema": {"project_id": "string optional", "data_summary": "string", "parsed_table": "object optional"},
        "output_schema": {"result_paragraph": "string", "figure_legend": "string", "claims": "array"},
        "required_file_types": ["csv", "xlsx", "md", "txt"],
        "required_tools": ["result summary", "claims", "evidence links"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Narratives must not claim significance without replicate/statistical evidence.",
        "memory_policy": "Store draft claims as weak until evidence is added or human-confirmed.",
        "migration_notes": "Connected to result summaries, figure legends, and evidence-linked claims.",
    },
    "sop-generation": {
        "domain": "protocols",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["SOP", "ELN"],
        "skill_type": "hybrid",
        "input_schema": {"project_id": "string", "protocol_id|protocol_json|experiment_goal": "string|object"},
        "output_schema": {"sop": "object", "execution_package": "object", "qc_checklist": "array"},
        "required_file_types": ["md", "txt", "json"],
        "required_tools": ["protocol execution package", "ELN template", "reagent table", "sample table"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "SOPs should identify source protocol and warn when parameters are inferred.",
        "memory_policy": "Store execution package refs and execution memory.",
        "migration_notes": "Merged with current protocol execution package generation.",
    },
    "weekly-research-digest": {
        "domain": "literature",
        "applicable_domains": ["literature monitoring", "weekly digest", "RAG updates"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "keywords": "array optional", "recent_notes": "array optional"},
        "output_schema": {"digest": "object", "references": "array", "memory_updates": "array"},
        "required_file_types": ["md", "txt", "csv"],
        "required_tools": ["literature monitoring", "keyword harvest", "RAG", "project memory"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Digest items should include citation ids for retrieved references.",
        "memory_policy": "Store weekly digest summary in project memory and keep references in literature memory.",
        "migration_notes": "Connected to literature harvest, RAG updates, and weekly summary flow.",
    },
    "weekly-research-report": {
        "domain": "reporting",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["weekly reporting", "advisor updates"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string", "report_type": "weekly_report optional"},
        "output_schema": {"report": "object", "claims": "array", "next_steps": "array"},
        "required_file_types": ["md", "txt", "csv"],
        "required_tools": ["weekly report", "workflow board", "claims", "conflicts", "DataContext"],
        "required_models": ["mock LLM adapter optional"],
        "citation_policy": "Weekly reports should list limitations and preserve evidence links for generated claims.",
        "memory_policy": "Create report, claims, and execution memory; project memory remains isolated.",
        "migration_notes": "Uses existing WeeklyReportSkill/report generator with imported instructions retained.",
    },
    "nature-citation": {
        "domain": "citation_support",
        "applicable_domains": ["manuscript writing", "literature support", "Nature/CNS citation"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string optional", "manuscript_text|claim_text": "string", "export_format": "ENW|RIS|RDF optional"},
        "output_schema": {"citation_candidates": "array", "reference_export": "object", "evidence_notes": "array"},
        "required_file_types": ["md", "txt", "docx text", "manuscript text"],
        "required_tools": ["Crossref/PubMed metadata", "reference export", "citation screening"],
        "required_models": ["LLM optional for claim segmentation"],
        "citation_policy": "Do not fabricate DOI, pages, journal metadata, or claim support.",
        "memory_policy": "Promote only verified references and evidence notes; keep unsupported candidates as low-confidence notes.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
    "nature-data": {
        "domain": "data_availability",
        "applicable_domains": ["Nature submissions", "FAIR metadata", "data repository planning"],
        "skill_type": "prompt",
        "input_schema": {"project_id": "string optional", "dataset_inventory|manuscript_notes": "string|object", "target_journal": "string optional"},
        "output_schema": {"data_availability_statement": "string", "repository_actions": "array", "fair_audit": "array"},
        "required_file_types": ["md", "txt", "csv", "xlsx", "dataset inventory"],
        "required_tools": ["dataset inventory", "repository policy references"],
        "required_models": ["LLM optional"],
        "citation_policy": "Do not invent accession numbers, DOIs, repository records, licences, or embargo dates.",
        "memory_policy": "Store dataset decisions as project-scoped report/decision memory only after review.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
    "nature-figure": {
        "domain": "scientific_figure",
        "applicable_domains": COMMON_SCIENCE_DOMAINS + ["publication figures", "scientific visualization"],
        "skill_type": "code",
        "input_schema": {"project_id": "string optional", "figure_goal": "string", "data_file": "string optional", "backend_choice": "Python|R required before rendering"},
        "output_schema": {"figure_spec": "object", "figure_code": "string", "output_files": "array", "qa_report": "object"},
        "required_file_types": ["csv", "xlsx", "tsv", "json", "image", "plotting notes"],
        "required_tools": ["matplotlib or R plotting backend", "file writer", "QA renderer"],
        "required_models": ["LLM optional for figure contract"],
        "citation_policy": "Figure claims must be grounded in supplied data or explicit project evidence.",
        "memory_policy": "Register figure outputs as artifacts; do not promote figure interpretation without data provenance.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
    "nature-paper2ppt": {
        "domain": "presentation",
        "applicable_domains": ["journal club", "paper presentation", "group meeting", "PPTX generation"],
        "skill_type": "workflow",
        "input_schema": {"project_id": "string optional", "paper_pdf|paper_text|reading_notes": "string", "language": "zh optional"},
        "output_schema": {"pptx": "file", "speaker_notes": "array", "qa_report": "object"},
        "required_file_types": ["pdf", "md", "txt", "paper notes"],
        "required_tools": ["PyMuPDF optional", "python-pptx optional", "file writer"],
        "required_models": ["LLM optional"],
        "citation_policy": "Do not fabricate paper findings, figures, datasets, mechanisms, or methods.",
        "memory_policy": "Register decks as report artifacts; do not write paper conclusions as project experimental claims.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
    "nature-polishing": {
        "domain": "academic_writing",
        "applicable_domains": ["manuscript polishing", "abstract writing", "Nature-style academic prose"],
        "skill_type": "prompt",
        "input_schema": {"project_id": "string optional", "manuscript_text": "string", "section_type": "string optional"},
        "output_schema": {"polished_text": "string", "revision_notes": "array", "risk_flags": "array"},
        "required_file_types": ["md", "txt", "docx text"],
        "required_tools": ["writing style rules", "overclaim checker"],
        "required_models": ["LLM"],
        "citation_policy": "Polishing must not add unverified citations, mechanisms, novelty, or results.",
        "memory_policy": "Store as draft report output, not confirmed scientific memory.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
    "nature-response": {
        "domain": "reviewer_response",
        "applicable_domains": ["manuscript revision", "rebuttal letter", "reviewer comments"],
        "skill_type": "prompt",
        "input_schema": {"project_id": "string optional", "reviewer_comments|decision_letter": "string", "revision_notes": "string optional"},
        "output_schema": {"response_letter": "string", "comment_triage": "array", "author_inputs_needed": "array"},
        "required_file_types": ["md", "txt", "docx text"],
        "required_tools": ["comment triage", "traceability checklist"],
        "required_models": ["LLM"],
        "citation_policy": "Do not invent manuscript changes, line numbers, experiments, citations, or editor instructions.",
        "memory_policy": "Store unresolved items and decisions as draft review memory only.",
        "migration_notes": "Imported from nature-skills and routed through ResearchOS SkillRun.",
    },
}


DUPLICATE_CANDIDATES = {
    "protocol-extraction": "PaperToProtocolSkill",
    "sop-generation": "Protocol execution package generation",
    "weekly-research-report": "WeeklyReportSkill",
    "design-experiment-matrix": "PlateLayoutSkill/ReagentCalculationSkill workflow pieces",
    "parse-scientific-data": "CSVTemplateParserSkill and current file extraction",
    "manage-agent-memory": "agent_memory_entries",
    "keyword-research-harvest": "existing search job and RAG routes",
}


def stable_id(*parts: Any, length: int = 24) -> str:
    joined = "|".join(re.sub(r"\s+", " ", str(part or "")).strip().lower() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_library_roots() -> list[Path]:
    root = workspace_root()
    candidates = [
        root,
        root.parent,
        root.parent.parent,
        root.parent.parent.parent,
    ]
    roots: list[Path] = []
    for candidate in candidates:
        if (candidate / "01_core_runtime_memory").exists():
            roots.append(candidate)
        library = candidate / "skills" / "researchos_skill_library"
        if library.exists():
            roots.append(library)
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in roots:
        key = str(candidate.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def resolve_skill_folder(folder: str) -> Path:
    root = workspace_root()
    candidates = [root / folder]
    if folder in CANONICAL_SKILL_LOCATIONS:
        candidates.append(root / CANONICAL_SKILL_LOCATIONS[folder])
        for library_root in skill_library_roots():
            candidates.append(library_root / CANONICAL_SKILL_LOCATIONS[folder])
    for library_root in skill_library_roots():
        candidates.append(library_root / folder)
        candidates.extend(sorted(library_root.glob(f"*/{folder}")))
    for candidate in candidates:
        if (candidate / "SKILL.md").exists():
            return candidate
    return root / folder


def skill_catalog_path() -> Path:
    for library_root in skill_library_roots():
        path = library_root / "skill_catalog.json"
        if path.exists():
            return path
    return workspace_root().parent / "skill_catalog.json"


def load_skill_catalog_rows() -> list[dict[str, Any]]:
    path = skill_catalog_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return [row for row in data.get("skills", []) if isinstance(row, dict)]


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    values: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^(##+)\s+(.+)$", text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


def read_skill_file(folder: str) -> dict[str, Any]:
    base = resolve_skill_folder(folder)
    source = base / "SKILL.md"
    text = source.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else folder
    sections = parse_sections(text)
    metadata = CORE_SKILL_METADATA[folder]
    overview = sections.get("Overview", "")
    overview_first_line = overview.splitlines()[0].strip() if overview.splitlines() else ""
    purpose = frontmatter.get("description") or overview_first_line or metadata["migration_notes"]
    return {
        "folder": folder,
        "title": title,
        "purpose": purpose,
        "frontmatter": frontmatter,
        "sections": sections,
        "instruction_body": text,
        "source_path": str(source.resolve()),
        **metadata,
    }


def imported_core_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for folder in CORE_SKILL_FOLDERS:
        parsed = read_skill_file(folder)
        skills.append(
            {
                "skill_id": folder if folder.startswith("nature-") else f"core_{folder.replace('-', '_')}",
                "skill_name": parsed["title"],
                "version": "1.0-imported",
                "description": parsed["purpose"],
                "domain": parsed["domain"],
                "applicable_domains": parsed["applicable_domains"],
                "skill_type": parsed["skill_type"],
                "source_path": parsed["source_path"],
                "input_schema": parsed["input_schema"],
                "output_schema": parsed["output_schema"],
                "required_file_types": parsed["required_file_types"],
                "required_tools": parsed["required_tools"],
                "required_models": parsed["required_models"],
                "handler": f"core_skill:{folder}",
                "handler_ref": f"core_skill:{folder}",
                "prompt_template": "",
                "instruction_body": parsed["instruction_body"],
                "example_inputs": extract_examples(parsed),
                "example_outputs": [],
                "safety_or_reliability_notes": extract_rules(parsed),
                "citation_policy": parsed["citation_policy"],
                "memory_policy": parsed["memory_policy"],
                "status": "active",
                "duplicate_of_skill_id": "",
                "migration_notes": parsed["migration_notes"],
                "folder": folder,
                "parsed_sections": parsed["sections"],
            }
        )
    covered = set(CORE_SKILL_FOLDERS)
    for row in load_skill_catalog_rows():
        skill_id = str(row.get("skill_id") or "").strip()
        canonical_path = str(row.get("canonical_path") or "").strip()
        if not skill_id or skill_id in covered or "{" in canonical_path:
            continue
        base = resolve_skill_folder(skill_id)
        source = base / "SKILL.md"
        if not source.exists():
            continue
        text = source.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        title = str(row.get("display_name") or (title_match.group(1).strip() if title_match else skill_id))
        description = frontmatter.get("description") or str(row.get("notes") or title)
        category = str(row.get("category") or "catalog")
        skills.append(
            {
                "skill_id": skill_id,
                "skill_name": title,
                "version": "1.0-catalog",
                "description": description,
                "domain": category,
                "applicable_domains": [category],
                "skill_type": "catalog",
                "source_path": str(source.resolve()),
                "input_schema": {"input": row.get("input_types") or []},
                "output_schema": {"output": row.get("output_types") or []},
                "required_file_types": [],
                "required_tools": row.get("allowed_tools") or [],
                "required_models": ["none"],
                "handler": f"core_skill:{skill_id}",
                "handler_ref": f"core_skill:{skill_id}",
                "prompt_template": "",
                "instruction_body": text,
                "example_inputs": [],
                "example_outputs": [],
                "safety_or_reliability_notes": [str(row.get("notes") or "")],
                "citation_policy": "Preserve source paths, citations, and provenance records required by the skill instructions.",
                "memory_policy": "Follow the skill instructions and keep project memory scoped to the active project.",
                "status": str(row.get("status") or "active"),
                "duplicate_of_skill_id": "",
                "migration_notes": "Imported from skill_catalog.json so backend runtime can discover every classified skill.",
                "folder": skill_id,
                "parsed_sections": parse_sections(text),
            }
        )
    return skills


def extract_rules(parsed: dict[str, Any]) -> list[str]:
    sections = parsed.get("sections") or {}
    rules_text = sections.get("Rules") or sections.get("Guardrails") or sections.get("Constraints") or ""
    rules = []
    for line in rules_text.splitlines():
        item = line.strip().lstrip("- ").strip()
        if item:
            rules.append(item)
    return rules or [parsed["memory_policy"], parsed["citation_policy"]]


def extract_examples(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    sections = parsed.get("sections") or {}
    examples = []
    for key in ["Fast Path", "example", "Quick Start"]:
        if sections.get(key):
            examples.append({"section": key, "content": sections[key]})
    return examples


def tool_capability_skills() -> list[dict[str, Any]]:
    root = workspace_root()
    capabilities = []
    for rel_path in BROWSER_TOOL_SKILL_PATHS:
        source = root / rel_path
        title = source.parent.name
        description = "Browser-use infrastructure capability."
        if source.exists():
            text = source.read_text(encoding="utf-8", errors="replace")
            title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            frontmatter = parse_frontmatter(text)
            description = frontmatter.get("description") or description
        capabilities.append(
            {
                "capability_id": f"tool_{source.parent.name.replace('-', '_')}",
                "capability_name": title,
                "capability_type": "external_tool",
                "source_path": str(source.resolve()),
                "description": description,
                "status": "draft",
            }
        )
    return capabilities


def integration_counts() -> dict[str, int]:
    catalog_rows = [row for row in load_skill_catalog_rows() if "{" not in str(row.get("canonical_path") or "")]
    return {
        "total_skill_md_found": len(catalog_rows) or len(CORE_SKILL_FOLDERS),
        "core_project_skills": len(CORE_SKILL_FOLDERS),
        "excluded_ui_dependency_skills": len(EXCLUDED_DEPENDENCY_SKILL_PATHS),
        "browser_tool_infrastructure_skills": len(BROWSER_TOOL_SKILL_PATHS),
    }
