from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import research_os_mvp as ros
import research_memory_canonical as canonical_memory
from runtime_paths import prompt_root


class ResearchOsMvpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.agent_root = Path(self.tmp.name)
        self.project = ros.create_project(
            self.agent_root,
            {
                "title": "Test Wet Lab Project",
                "research_area": "biomedical wet-lab",
                "keywords": ["qPCR", "ELISA"],
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def skill_id(self, name: str) -> str:
        return next(skill["skill_id"] for skill in ros.list_skills(self.agent_root, include_disabled=True) if skill["skill_name"] == name)

    def test_file_classification_detects_qpcr(self) -> None:
        category = ros.classify_file("messy_export.csv", "sample_id,gene,Ct value\nS001,IL6,23.1")
        self.assertEqual(category, "qPCR data")

    def test_entity_extraction_creates_provenance(self) -> None:
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "qPCR_results.csv",
                "content": "sample_id,group,condition,dose,timepoint,assay,gene,fold_change\nS001,Model,LPS,100 ng/mL,24h,qPCR,IL6,5.2\n",
            },
        )
        result = ros.run_extraction(self.agent_root, {"file_id": file_record["id"]})
        self.assertTrue(result["entities"])
        memory = ros.search_memory(self.agent_root, {"project_id": self.project["id"], "query": "S001"})
        self.assertTrue(memory["memory"])
        self.assertTrue(memory["memory"][0]["provenance"])

    def test_protocol_parser_returns_structured_steps(self) -> None:
        parsed = ros.parse_protocol_text(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "text": "Cells were treated with LPS for 24 h. RNA was extracted with TRIzol and measured by RT-qPCR.",
            },
        )
        protocol = parsed["protocol"]
        self.assertEqual(protocol["protocol_type"], "qPCR")
        self.assertGreaterEqual(len(protocol["steps"]), 1)
        self.assertIn("quality_control_points", protocol)

    def test_reagent_calculator_dilution(self) -> None:
        result = ros.dilution_calculation(100, 10, 1000)
        self.assertAlmostEqual(result["stock_volume"], 100)
        self.assertAlmostEqual(result["diluent_volume"], 900)

    def test_conflict_detection_same_sample_different_conditions(self) -> None:
        first = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "qpcr_24h.csv",
                "content": "sample_id,group,condition,dose,timepoint,assay,value\nS001,Model,LPS,100 ng/mL,24h,qPCR,5.0\n",
            },
        )
        second = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "elisa_24h.csv",
                "content": "sample_id,group,condition,dose,timepoint,assay,value\nS001,Treatment,LPS+NP-01,5 ug/mL,24h,ELISA,120\n",
            },
        )
        ros.run_extraction(self.agent_root, {"file_id": first["id"]})
        ros.run_extraction(self.agent_root, {"file_id": second["id"]})
        conflicts = ros.detect_conflicts(self.agent_root, self.project["id"])
        self.assertTrue(any("same sample ID" in item["conflict_type"] for item in conflicts))

    def test_workflow_runner_stops_at_human_checkpoint(self) -> None:
        workflow = ros.create_workflow(
            self.agent_root,
            {"project_id": self.project["id"], "template_key": "protocol_to_execution"},
        )
        result = ros.run_workflow(self.agent_root, workflow["id"])
        self.assertIsNotNone(result["waiting_step"])
        self.assertEqual(result["waiting_step"]["status"], "waiting_approval")

    def test_skill_registry_bootstraps_builtin_scientific_skills(self) -> None:
        skills = ros.list_skills(self.agent_root, include_disabled=True)
        names = {skill["skill_name"] for skill in skills}
        self.assertIn("PaperToProtocolSkill", names)
        self.assertIn("KitManualParserSkill", names)
        self.assertIn("ConflictDetectionSkill", names)
        self.assertTrue(all("project_id" not in skill for skill in skills))

    def test_agent_memory_keeps_system_and_project_scopes_separate(self) -> None:
        created = ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "title": "Project-only preference",
                "content": "Keep unpublished observations isolated to this project.",
                "trust_level": "user_confirmed",
            },
        )
        self.assertEqual(created["memory_scope"], "project")
        scoped = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)
        self.assertTrue(scoped["project_memory"])
        self.assertFalse(scoped["system_memory"])

    def test_kit_template_parser_learns_reusable_local_knowledge(self) -> None:
        kit = ros.parse_kit_template(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "ELISA_kit_manual.txt",
                "assay_type": "ELISA",
                "content": "Vendor: DemoBio. Use standards in duplicate on a 96-well plate. Add substrate and stop solution. Read wavelength 450 nm. Calculate concentration from standard curve.",
            },
        )
        self.assertEqual(kit["assay_type"], "ELISA")
        self.assertTrue(kit["parsed_qc_rules"])
        confirmed = ros.update_kit_template(self.agent_root, kit["id"], {"confirmed_by_user": True})
        self.assertTrue(confirmed["confirmed_by_user"])

    def test_data_context_marks_under_contextualized_files(self) -> None:
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "mystery_export.csv",
                "content": "value\n42\n",
            },
        )
        context = ros.list_data_contexts(self.agent_root, project_id=self.project["id"])
        file_context = next(item for item in context if item["file_id"] == file_record["id"])
        self.assertEqual(file_context["context_status"], "under_contextualized")
        self.assertIn("experiment_id", file_context["missing_metadata"])

    def test_workflow_board_contains_human_executable_task_fields(self) -> None:
        ros.create_workflow(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "template_key": "data_to_figure_conclusion",
                "responsible_person": "Alice",
                "instrument": "plate reader",
                "output_location": "local/results",
            },
        )
        board = ros.workflow_board(self.agent_root, self.project["id"])
        self.assertTrue(board["tasks"])
        first = board["tasks"][0]
        self.assertEqual(first["responsible_person"], "Alice")
        self.assertEqual(first["output_location"], "local/results")
        self.assertIn(first["status"], board["columns"])

    def test_claim_creation_and_evidence_linking(self) -> None:
        file_record = ros.register_file(
            self.agent_root,
            {"project_id": self.project["id"], "filename": "claim_source.txt", "content": "Conclusion: signal is weak."},
        )
        claim = ros.create_claim(
            self.agent_root,
            {"project_id": self.project["id"], "claim_text": "Signal is weak.", "claim_type": "conclusion"},
        )
        ros.add_claim_evidence(
            self.agent_root,
            claim["id"],
            {"evidence_type": "source_file", "evidence_id": file_record["id"], "source_file_id": file_record["id"], "source_snippet": "Conclusion: signal is weak."},
        )
        loaded = ros.get_claim_with_evidence(self.agent_root, claim["id"])
        self.assertEqual(loaded["evidence_count"], 1)
        self.assertEqual(loaded["status"], "weak")

    def test_report_generates_structured_claims(self) -> None:
        ros.register_file(
            self.agent_root,
            {"project_id": self.project["id"], "filename": "experiment_log.md", "content": "Next step: repeat qPCR before strong claims."},
        )
        report = ros.generate_report(self.agent_root, {"project_id": self.project["id"], "report_type": "weekly_report"})
        self.assertTrue(report["generated_claims"])
        claims = ros.list_claims(self.agent_root, project_id=self.project["id"])
        self.assertTrue(any(claim["created_from"] == "report" for claim in claims))
        self.assertTrue(all(claim["status"] != "confirmed" for claim in claims))

    def test_data_context_update_recomputes_status(self) -> None:
        protocol = ros.store_protocol(self.agent_root, {"project_id": self.project["id"], "title": "qPCR protocol", "protocol_type": "qPCR", "steps": []})
        file_record = ros.register_file(
            self.agent_root,
            {"project_id": self.project["id"], "filename": "mystery_qpcr.csv", "content": "sample_id,value\nS001,1\n"},
        )
        context = ros.read_file_record(self.agent_root, file_record["id"])["data_context"]
        self.assertEqual(context["context_status"], "under_contextualized")
        updated = ros.update_data_context(
            self.agent_root,
            context["id"],
            {
                "experiment_name": "Run 1",
                "sample_source": "S001",
                "assay_type": "qPCR",
                "instrument": "qPCR",
                "protocol_id": protocol["id"],
                "operator": "Alice",
                "experiment_date": "2026-04-30",
                "related_samples": ["S001"],
            },
        )
        self.assertEqual(updated["context_status"], "contextualized")
        self.assertEqual(updated["missing_metadata"], [])

    def test_csv_extraction_creates_direct_file_sample_links(self) -> None:
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "elisa.csv",
                "content": "well,sample_id,group,condition,timepoint,assay,OD450\nA1,S001,Control,Vehicle,24h,ELISA,0.1\nA2,S002,Treatment,LPS,24h,ELISA,0.4\n",
            },
        )
        ros.run_extraction(self.agent_root, {"file_id": file_record["id"]})
        samples = ros.file_samples(self.agent_root, file_record["id"])["samples"]
        labels = {sample["sample_label"] for sample in samples}
        self.assertIn("S001", labels)
        self.assertIn("S002", labels)
        self.assertTrue(any(sample["well"] == "A1" for sample in samples))

    def test_skill_run_persists_output_refs_and_report_claim_links(self) -> None:
        skill_id = self.skill_id("WeeklyReportSkill")
        result = ros.run_skill(self.agent_root, skill_id, project_id=self.project["id"], input_payload={"project_id": self.project["id"], "report_type": "weekly_report"})
        self.assertIn("skill_run_id", result)
        run = result["skill_run"]
        self.assertEqual(run["status"], "completed")
        output_types = {ref["type"] for ref in run["output_object_refs"]}
        self.assertIn("report", output_types)
        self.assertIn("claim", output_types)
        links = ros.relationship_query(self.agent_root, {"source_type": "skill_run", "source_id": run["id"], "target_type": "report"})
        self.assertTrue(links["relationships"])

    def test_paper_to_protocol_skill_run_generates_protocol_link(self) -> None:
        skill_id = self.skill_id("PaperToProtocolSkill")
        result = ros.run_skill(
            self.agent_root,
            skill_id,
            project_id=self.project["id"],
            input_payload={"project_id": self.project["id"], "text": "Cells were treated with LPS for 24 h and measured by qPCR."},
        )
        output_types = {ref["type"] for ref in result["skill_run"]["output_object_refs"]}
        self.assertIn("protocol", output_types)

    def test_existing_skill_run_route_function_remains_backward_compatible(self) -> None:
        skill_id = self.skill_id("ReagentCalculationSkill")
        result = ros.run_skill_example(
            self.agent_root,
            skill_id,
            {"project_id": self.project["id"], "mode": "dilution", "stock_concentration": 100, "target_concentration": 10, "final_volume": 1000},
        )
        self.assertIn("skill_run_id", result)
        self.assertIn("output", result)
        self.assertAlmostEqual(result["output"]["stock_volume"], 100)

    def test_imported_core_skills_are_registered_with_source_paths(self) -> None:
        skills = ros.list_skills(self.agent_root, include_disabled=True)
        core = [skill for skill in skills if skill["skill_id"].startswith("core_")]
        self.assertEqual(len(core), 21)
        self.assertTrue(all(skill["status"] in {"active", "draft", "duplicate", "deprecated"} for skill in core))
        self.assertTrue(all(skill.get("source_path", "").endswith("SKILL.md") for skill in core))
        scientific_paths = " ".join(str(skill.get("source_path") or "") for skill in skills)
        self.assertNotIn("ui\\skills\\shadcn", scientific_paths)
        self.assertNotIn("node_modules\\dotenv", scientific_paths)
        self.assertNotIn("browser-use\\skills\\browser-use", scientific_paths)
        self.assertEqual(len(ros.list_tool_capabilities(self.agent_root)), 4)

    def test_imported_skill_deduplication_report_documents_overlaps(self) -> None:
        report = ros.imported_skill_deduplication_report(self.agent_root)
        overlap_ids = {item["imported_skill_id"] for item in report["overlaps"]}
        self.assertIn("core_protocol_extraction", overlap_ids)
        self.assertIn("core_weekly_research_report", overlap_ids)

    def test_keyword_harvest_builds_literature_rag_pipeline(self) -> None:
        result = ros.run_skill(
            self.agent_root,
            "core_keyword_research_harvest",
            project_id=self.project["id"],
            input_payload={"project_id": self.project["id"], "keywords": ["autophagy LC-MS"], "provider": "mock"},
        )
        self.assertEqual(result["skill_run"]["status"], "completed")
        tasks = ros.list_literature_search_tasks(self.agent_root, self.project["id"])
        references = ros.list_references(self.agent_root, self.project["id"])
        chunks = ros.list_reference_chunks(self.agent_root, self.project["id"])
        entries = ros.list_knowledge_base_entries(self.agent_root, self.project["id"])
        self.assertTrue(tasks)
        self.assertTrue(references)
        self.assertTrue(chunks)
        self.assertTrue(entries)
        rag = ros.query_research_rag(self.agent_root, {"project_id": self.project["id"], "question": "autophagy methods"})
        self.assertTrue(rag["retrieved_chunks"])
        self.assertEqual(rag["retrieved_chunks"][0]["citation_id"], "[1]")

    def test_every_skill_run_creates_execution_memory_and_can_promote(self) -> None:
        result = ros.run_skill(
            self.agent_root,
            "core_manage_agent_memory",
            project_id=self.project["id"],
            input_payload={
                "project_id": self.project["id"],
                "title": "Reusable analysis preference",
                "content": "Always separate weak claims from confirmed claims.",
                "reusable_lesson": "Separate weak claims from confirmed claims in reports.",
            },
        )
        memories = ros.list_execution_memory(self.agent_root, project_id=self.project["id"], skill_id="core_manage_agent_memory")
        self.assertTrue(any(memory["skill_run_id"] == result["skill_run_id"] for memory in memories))
        promoted = ros.promote_execution_memory_to_skill_draft(self.agent_root, memories[0]["id"], {"skill_name": "Draft Claim Strength Reporter"})
        self.assertEqual(promoted["skill"]["status"], "draft")
        scoped = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)
        self.assertTrue(scoped["project_memory"])
        self.assertFalse(scoped["system_memory"])

    def test_protocol_extraction_and_weekly_report_core_adapters(self) -> None:
        protocol_result = ros.run_skill(
            self.agent_root,
            "core_protocol_extraction",
            project_id=self.project["id"],
            input_payload={"project_id": self.project["id"], "text": "Cells were treated with LPS for 24 h and measured by qPCR."},
        )
        protocol_refs = {ref["type"] for ref in protocol_result["skill_run"]["output_object_refs"]}
        self.assertIn("protocol", protocol_refs)
        report_result = ros.run_skill(
            self.agent_root,
            "core_weekly_research_report",
            project_id=self.project["id"],
            input_payload={"project_id": self.project["id"]},
        )
        report_refs = {ref["type"] for ref in report_result["skill_run"]["output_object_refs"]}
        self.assertIn("report", report_refs)

    def test_information_loop_keyword_mining_to_rag_and_memory(self) -> None:
        mined = ros.keyword_mine(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "research_direction": "I am working on fermented natural products and immunomodulation.",
                "create_search_task": True,
                "provider": "mock",
            },
        )
        self.assertIn("fermented natural products", " ".join(mined["keyword_mining"]["expanded_keywords"]))
        self.assertTrue(ros.list_literature_search_tasks(self.agent_root, self.project["id"]))
        self.assertTrue(ros.list_references(self.agent_root, self.project["id"]))
        self.assertTrue(ros.list_knowledge_base_entries(self.agent_root, self.project["id"]))
        rag = ros.query_research_rag(
            self.agent_root,
            {"project_id": self.project["id"], "question": "fermented immunomodulation macrophage", "mode": "literature_only", "save_to_memory": True},
        )
        self.assertTrue(rag["retrieved_chunks"])
        by_ref: dict[str, int] = {}
        for chunk in rag["retrieved_chunks"]:
            if chunk["citation_number"]:
                by_ref.setdefault(chunk["reference_id"], chunk["citation_number"])
                self.assertEqual(by_ref[chunk["reference_id"]], chunk["citation_number"])
        self.assertIsNotNone(rag["memory"])
        scoped = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)
        self.assertTrue(any(entry["memory_type"] == "rag_answer" for entry in scoped["project_memory"]))
        self.assertFalse(scoped["system_memory"])

    def test_natural_language_command_creates_structured_task_and_workflow(self) -> None:
        parsed = ros.parse_natural_language_task(
            self.agent_root,
            {"project_id": self.project["id"], "text": "帮我围绕发酵天然产物免疫调节，搜索近三年高分论文，每周推送，并把重要方法整理成protocol候选。"},
        )["parsed_task"]
        self.assertIn(parsed["task_type"], {"literature_mining", "weekly_digest", "protocol_extraction"})
        self.assertTrue(parsed["required_skills"])
        created = ros.create_task_from_natural_language(self.agent_root, {"project_id": self.project["id"], "text": parsed["objective"]})
        self.assertIn("workflow", created)
        self.assertIn("memory", created)

    def test_experiment_log_ingestion_retrospective_and_weak_claims(self) -> None:
        ingested = ros.ingest_experiment_log(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "text": "Date: 2026-04-30\nExperiment: pilot macrophage assay\nObservation: blank control drifted.\nAbnormal: blank control drifted\nNext step: repeat with fresh reagent.",
            },
        )
        self.assertTrue(ingested["experiment_log"]["id"])
        self.assertTrue(ingested["failure_log"])
        claims = ros.list_claims(self.agent_root, project_id=self.project["id"])
        self.assertTrue(claims)
        self.assertTrue(all(claim["status"] != "confirmed" for claim in claims))
        retrospective = ros.generate_retrospective(self.agent_root, {"project_id": self.project["id"]})
        self.assertIn("retrospective", retrospective)
        self.assertEqual(retrospective["memory"]["memory_scope"], "project")

    def test_writing_assistant_flags_unsupported_and_weekly_digest_is_cited(self) -> None:
        ros.search_literature(self.agent_root, {"project_id": self.project["id"], "keywords": ["fermented immunomodulation"], "provider": "mock"})
        ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Fermented extract strongly proves mechanism.", "claim_type": "conclusion", "status": "weak"})
        writing = ros.writing_assistant(self.agent_root, {"project_id": self.project["id"], "writing_task": "discussion_outline", "source_scope": "all_project_context", "save_to_memory": True})
        self.assertTrue(writing["unsupported_statements"])
        self.assertIn("draft", writing)
        digest = ros.generate_weekly_project_digest(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "research_interests": "fermented natural products immunomodulation",
                "keywords": ["fermented", "immunomodulation"],
                "provider": "mock",
                "max_papers": 3,
            },
        )
        self.assertIn("digest_report", digest)
        self.assertTrue(digest["rag"]["citation_map"])
        refs = ros.list_references(self.agent_root, self.project["id"])
        self.assertTrue(any("mock" in str(ref.get("source_provider", "")).lower() and ref.get("evidence_level") == "mock_not_evidence" for ref in refs))
        memories = ros.list_execution_memory(self.agent_root, project_id=self.project["id"])
        self.assertTrue(any(memory["skill_id"] == "core_weekly_research_digest" for memory in memories))


    def test_p1_natural_language_intent_boundaries_and_priorities(self) -> None:
        biological = ros.parse_natural_language_task(
            self.agent_root,
            {"project_id": self.project["id"], "text": "What biological models, mechanisms, assays, endpoints, and protocol candidates should we map for this project?"},
        )["parsed_task"]
        self.assertNotEqual(biological["task_type"], "experiment_log_ingestion")
        self.assertIn(biological["task_type"], {"literature_mining", "research_route_planning"})
        self.assertIn("confidence_score", biological)
        self.assertIn("alternative_task_types", biological)
        self.assertIn("explanation", biological)

        papers = ros.parse_natural_language_task(self.agent_root, {"project_id": self.project["id"], "text": "search papers and build KB"})["parsed_task"]
        self.assertEqual(papers["task_type"], "literature_mining")

        log = ros.parse_natural_language_task(self.agent_root, {"project_id": self.project["id"], "text": "paste today's experiment log"})["parsed_task"]
        self.assertEqual(log["task_type"], "experiment_log_ingestion")

        writing = ros.parse_natural_language_task(self.agent_root, {"project_id": self.project["id"], "text": "write an introduction outline"})["parsed_task"]
        self.assertEqual(writing["task_type"], "paper_writing")

        weekly = ros.parse_natural_language_task(self.agent_root, {"project_id": self.project["id"], "text": "generate weekly papers"})["parsed_task"]
        self.assertEqual(weekly["task_type"], "weekly_digest")

    def test_p1_experiment_log_parser_keeps_labeled_fields_separate(self) -> None:
        log_text = """Date: 2026-05-01
Experiment: FNP-MAC-001 pilot macrophage stimulation screen
Operator: validation_user
Objective: Test whether fermented natural product extract changes inflammatory response markers in macrophage-like cells.
Sample: fermented extract batch FNP-B01, vehicle control, LPS model control, FNP low/mid/high pretreatment groups.
Conditions: vehicle, LPS, FNP-low + LPS, FNP-mid + LPS, FNP-high + LPS; 24 h treatment.
Observations: Cells in high-dose FNP group looked stressed before endpoint collection. Medium color changed in two wells. Control wells looked normal.
Abnormal: high-dose stress signal and possible medium pH/color issue.
Failure reason: batch concentration and extract solubility may not have been controlled well enough.
Decision: Treat all endpoint interpretations as preliminary. Do not promote to conclusion.
Next step: Repeat with clarified stock preparation, lower high dose, viability check, and complete sample metadata.
"""
        ingested = ros.ingest_experiment_log(self.agent_root, {"project_id": self.project["id"], "text": log_text})
        entry = ingested["experiment_log"]
        self.assertEqual(entry["experiment_date"], "2026-05-01")
        self.assertEqual(entry["experiment_name"], "FNP-MAC-001 pilot macrophage stimulation screen")
        self.assertEqual(entry["operator"], "validation_user")
        self.assertEqual(entry["objective"], "Test whether fermented natural product extract changes inflammatory response markers in macrophage-like cells.")
        self.assertTrue(entry["sample_material"].startswith("fermented extract batch FNP-B01"))
        self.assertTrue(entry["conditions"].startswith("vehicle, LPS, FNP-low + LPS"))
        self.assertTrue(entry["observations"].startswith("Cells in high-dose"))
        self.assertTrue(entry["abnormal_events"].startswith("high-dose stress signal"))
        self.assertTrue(entry["failure_reason"].startswith("batch concentration and extract solubility"))
        self.assertTrue(entry["decision"].startswith("Treat all endpoint interpretations as preliminary"))
        self.assertTrue(entry["next_step"].startswith("Repeat with clarified stock preparation"))
        self.assertEqual(entry["missing_fields"], [])
        self.assertGreaterEqual(entry["field_confidence"]["experiment_name"], 0.9)

    def test_chinese_prompt_policy_files_cover_required_guardrails(self) -> None:
        prompt_dir = prompt_root() / "zh"
        base = prompt_dir / "base_identity_zh.md"
        evidence = (prompt_dir / "evidence_policy_zh.md").read_text(encoding="utf-8")
        citation = (prompt_dir / "citation_policy_zh.md").read_text(encoding="utf-8")
        memory = (prompt_dir / "memory_policy_zh.md").read_text(encoding="utf-8")
        claim = (prompt_dir / "claim_policy_zh.md").read_text(encoding="utf-8")
        task = (prompt_dir / "natural_language_task_policy_zh.md").read_text(encoding="utf-8")
        writing = (prompt_dir / "writing_assistant_policy_zh.md").read_text(encoding="utf-8")

        self.assertTrue(base.exists())
        self.assertIn("mock_not_evidence", evidence)
        self.assertIn("同一 reference 同一编号", citation)
        self.assertIn("不把 project memory 写入 system memory", memory)
        self.assertIn("confirmed claim 只能由人类", claim)
        self.assertIn("不要把 biological 里的 log", task)
        self.assertIn("正文草稿和证据列表分开", writing)

    def test_llm_adapter_loads_chinese_prompt_policy(self) -> None:
        adapter = ros.LLMAdapter(prompt_language="zh", prompt_policy="writing_assistant")
        result = adapter.generate_json("写一个 introduction outline。", "writing_test")
        self.assertTrue(result["_mock"])
        self.assertEqual(result["prompt_language"], "zh")
        self.assertEqual(result["prompt_policy"], "writing_assistant")
        self.assertTrue(any(path.endswith("writing_assistant_policy_zh.md") for path in result["prompt_files"]))
        self.assertIn("ResearchOS 中文基础身份提示词", result["system_prompt_preview"])

    def test_skill_run_records_chinese_prompt_policy(self) -> None:
        writing = ros.writing_assistant(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "writing_task": "introduction_outline",
                "prompt_language": "zh",
                "prompt_policy": "writing_assistant",
            },
        )
        run = ros.get_skill_run(self.agent_root, writing["skill_run_id"])
        self.assertEqual(run["prompt_language"], "zh")
        self.assertEqual(run["prompt_policy"], "writing_assistant")
        self.assertTrue(any(path.endswith("writing_assistant_policy_zh.md") for path in run["prompt_files"]))

    def test_p2_evidence_review_lists_core_evidence_types_and_cards(self) -> None:
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Manual FNP immunomodulation paper",
                "abstract": "Manual metadata about fermented natural products and macrophage assays.",
                "source_provider": "manual",
                "evidence_level": "manual_metadata",
            },
        )
        rag = ros.query_research_rag(self.agent_root, {"project_id": self.project["id"], "question": "fermented macrophage", "save_to_memory": True})
        log = ros.ingest_experiment_log(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "text": "Date: 2026-05-01\nExperiment: FNP review log\nObservations: cells looked stressed.\nAbnormal: stress phenotype in high-dose wells.\nFailure reason: dose may be too high.\nNext step: repeat.",
            },
        )
        claim = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "FNP extract may affect inflammatory readouts.", "claim_type": "hypothesis", "status": "weak"})
        evidence = ros.list_evidence_review_items(self.agent_root, self.project["id"])
        types = {item["evidence_type"] for item in evidence["evidence_items"]}
        self.assertIn("reference", types)
        self.assertIn("reference_chunk", types)
        self.assertIn("rag_query", types)
        self.assertIn("project_memory", types)
        self.assertIn("experiment_log", types)
        self.assertIn("failure_log", types)
        self.assertIn("claim", types)
        self.assertTrue(all("can_support_confirmed_claim" in item for item in evidence["evidence_items"]))
        labels = {item["friendly_evidence_label"] for item in evidence["evidence_items"]}
        self.assertIn("manual metadata", labels)
        self.assertIn("experiment log", labels)
        self.assertEqual(rag["memory"]["memory_scope"], "project")
        self.assertTrue(log["experiment_log"]["id"])
        self.assertTrue(claim["id"])

    def test_p2_mock_and_project_memory_gate_claim_confirmation(self) -> None:
        mock_ref = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Mock validation paper",
                "abstract": "Mock placeholder.",
                "source_provider": "mock",
                "evidence_level": "mock_not_evidence",
            },
        )
        claim = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Mock-backed claim should not confirm.", "claim_type": "conclusion", "status": "weak"})
        ros.add_claim_evidence(self.agent_root, claim["id"], {"evidence_type": "reference", "evidence_id": mock_ref["id"]})
        gate = ros.evaluate_evidence_for_claim_confirmation(self.agent_root, claim["id"])
        self.assertFalse(gate["can_confirm"])
        blocked = ros.confirm_claim(self.agent_root, claim["id"], {"confirmed_by": "pi"})
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["confirmation"]["blockers"])

        memory = ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "note",
                "title": "Raw project observation",
                "content": "Raw note only.",
                "trust_level": "raw_extracted",
            },
        )
        memory_claim = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Project memory alone should not confirm.", "claim_type": "conclusion", "status": "weak"})
        ros.link_evidence_item_to_claim(self.agent_root, f"project_memory:{memory['id']}", {"claim_id": memory_claim["id"]})
        self.assertFalse(ros.evaluate_evidence_for_claim_confirmation(self.agent_root, memory_claim["id"])["can_confirm"])

        confirmed_memory = ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "confirmed_data",
                "title": "Human confirmed project data",
                "content": "Human confirmed local result.",
                "trust_level": "human_confirmed",
            },
        )
        confirmed_claim = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Human confirmed memory can support confirmation.", "claim_type": "result", "status": "weak"})
        ros.link_evidence_item_to_claim(self.agent_root, f"project_memory:{confirmed_memory['id']}", {"claim_id": confirmed_claim["id"]})
        self.assertTrue(ros.evaluate_evidence_for_claim_confirmation(self.agent_root, confirmed_claim["id"])["can_confirm"])

    def test_p2_real_reference_can_confirm_and_needs_more_evidence_status(self) -> None:
        real_ref = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Fermented natural products and macrophage immunomodulation",
                "authors": ["Doe J"],
                "year": "2025",
                "journal": "Example Journal",
                "doi": "10.1234/example.fnp.2025",
                "abstract": "Real metadata style reference with DOI.",
                "source_provider": "crossref",
                "evidence_level": "peer_reviewed_metadata",
            },
        )
        claim = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Real reference can support a cautious claim.", "claim_type": "conclusion", "status": "weak"})
        ros.link_evidence_item_to_claim(self.agent_root, f"reference:{real_ref['id']}", {"claim_id": claim["id"]})
        gate = ros.evaluate_evidence_for_claim_confirmation(self.agent_root, claim["id"])
        self.assertTrue(gate["can_confirm"])
        confirmed = ros.confirm_claim(self.agent_root, claim["id"], {"confirmed_by": "pi"})
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(confirmed["claim"]["status"], "confirmed")

        weak = ros.create_claim(self.agent_root, {"project_id": self.project["id"], "claim_text": "Needs more evidence claim.", "claim_type": "hypothesis", "status": "weak"})
        marked = ros.mark_claim_needs_more_evidence(self.agent_root, weak["id"], {"reason": "Need real reference."})
        self.assertEqual(marked["claim"]["status"], "needs_more_evidence")

    def test_p2_manual_reference_edit_and_export_templates(self) -> None:
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Editable manual paper",
                "abstract": "Before edit.",
                "source_provider": "manual",
            },
        )
        updated = ros.update_reference(
            self.agent_root,
            reference["id"],
            {
                "title": "Edited manual paper",
                "authors": ["Validation User"],
                "year": "2026",
                "journal": "Manual Journal",
                "doi": "10.0000/manual",
                "url": "https://example.org/manual",
                "abstract": "After edit.",
                "full_text_path": "C:/local/paper.pdf",
                "paper_type": "methods",
                "reading_status": "reading",
                "impact_label": "important",
                "tags": ["FNP", "immunomodulation"],
                "method_relevance": "Useful extraction method.",
                "mechanism_relevance": "Possible macrophage pathway.",
                "protocol_candidates": ["macrophage stimulation"],
                "reason_for_inclusion": "Relevant to validation scenario.",
            },
        )
        self.assertEqual(updated["title"], "Edited manual paper")
        self.assertIn("FNP", updated["tags"])
        self.assertIn("macrophage stimulation", updated["protocol_candidates"])
        important = ros.mark_reference_important(self.agent_root, reference["id"], {"reason": "Read first."})
        self.assertEqual(important["impact_label"], "important")
        excluded = ros.exclude_reference(self.agent_root, reference["id"], {"reason": "Out of scope after review."})
        self.assertEqual(excluded["reading_status"], "excluded")

        for template, expected in {
            "agent_handoff": "## Project Summary",
            "pi_review": "## Weak Or Confirmed Claims",
            "manuscript_planning": "## Introduction Points",
            "weekly_update": "## New References",
            "evidence_audit": "## All Claims",
        }.items():
            exported = ros.export_project_context(self.agent_root, self.project["id"], template=template)
            self.assertEqual(exported["json"]["template"], template)
            self.assertIn(expected, exported["markdown"])

    def test_canonical_context_is_stable_for_same_memory_view_version(self) -> None:
        protocol = ros.store_protocol(
            self.agent_root,
            {"project_id": self.project["id"], "title": "Canonical qPCR protocol", "protocol_type": "qPCR", "steps": []},
        )
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "stable_context_qpcr.csv",
                "protocol_id": protocol["id"],
                "operator": "Alice",
                "experiment_name": "Stable context run",
                "experiment_date": "2026-05-01",
                "content": "sample_id,group,condition,dose,timepoint,assay,gene,fold_change\nS001,Control,Vehicle,0,24h,qPCR,IL6,1.0\nS002,Treatment,LPS,100 ng/mL,24h,qPCR,IL6,4.3\n",
            },
        )
        ros.run_extraction(self.agent_root, {"file_id": file_record["id"]})
        first = canonical_memory.query_research_context(self.agent_root, {"project_id": self.project["id"], "query": "S001 qPCR IL6", "limit": 10})
        second = canonical_memory.query_research_context(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "query": "S001 qPCR IL6",
                "limit": 10,
                "memory_view_version": first["memory_view_version"],
            },
        )
        self.assertEqual(first["memory_view_version"], second["memory_view_version"])
        self.assertEqual([item["id"] for item in first["results"]], [item["id"] for item in second["results"]])

    def test_extract_experiment_memory_from_natural_language_keeps_nulls_and_queues_review(self) -> None:
        extracted = canonical_memory.extract_experiment_memory(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "text": "Date: 2026-05-01\nExperiment: macrophage pilot\nOperator: Alice\nRAW264.7 cells were treated with LPS 100 ng/mL for 24 h.\nSample S001 and sample S002 were measured by qPCR.\nObservation: IL6 increased in the model group.\nDecision: do not write final conclusion yet.\nNext step: repeat with fresh reagent.",
            },
        )
        self.assertEqual(extracted["experiment"]["title"], "macrophage pilot")
        self.assertIn("S001", extracted["experiment"]["sample_ids_json"])
        self.assertIn("24 h", extracted["experiment"]["time_points_json"])
        self.assertIsNone(extracted["experiment"]["purpose"])
        self.assertTrue(extracted["needs_review"])
        queue = canonical_memory.list_memory_review_items(self.agent_root, project_id=self.project["id"])
        self.assertTrue(queue)

    def test_canonical_conclusion_supersedes_old_conclusion(self) -> None:
        first = canonical_memory.upsert_conclusion(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "conclusion_text": "NP-01 may reduce IL6 expression.",
                "supported_by_file_ids": ["file-1"],
                "status": "draft",
            },
        )
        second = canonical_memory.upsert_conclusion(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "conclusion_text": "NP-01 reduces IL6 expression only in the pilot assay.",
                "supported_by_file_ids": ["file-2"],
                "status": "weak",
                "supersedes": [first["id"]],
            },
        )
        conclusions = {item["id"]: item for item in canonical_memory.list_conclusions(self.agent_root, self.project["id"])}
        self.assertEqual(conclusions[first["id"]]["status"], "superseded")
        self.assertEqual(conclusions[second["id"]]["status"], "weak")

    def test_canonical_decision_supersedes_old_decision(self) -> None:
        first = canonical_memory.upsert_decision(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "decision_text": "Use ELISA as the primary validation assay.",
                "reason": "Initial plan.",
                "status": "active",
            },
        )
        second = canonical_memory.upsert_decision(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "decision_text": "Use qPCR first, then ELISA for orthogonal validation.",
                "reason": "Need faster pilot readout.",
                "status": "active",
                "supersedes": [first["id"]],
            },
        )
        decisions = {item["id"]: item for item in canonical_memory.list_decisions(self.agent_root, self.project["id"])}
        self.assertEqual(decisions[first["id"]]["status"], "superseded")
        self.assertEqual(decisions[second["id"]]["status"], "active")

    def test_agent_memory_entries_sync_into_canonical_context(self) -> None:
        ros.create_agent_memory_entry(
            self.agent_root,
            {
                "memory_scope": "project",
                "project_id": self.project["id"],
                "memory_type": "writing_output",
                "title": "Writing preference",
                "content": "Always separate preliminary data from final conclusions.",
                "trust_level": "user_confirmed",
            },
        )
        context = canonical_memory.build_research_memory_context(self.agent_root, {"project_id": self.project["id"], "query": "writing preference"})
        joined = "\n".join(item.get("content", "") for item in context["structured_context"]["preferences"])
        self.assertIn("preliminary data", joined)

    def test_broad_project_summary_context_keeps_experiments_samples_and_files(self) -> None:
        conn = ros.connect(self.agent_root)
        experiment = ros.ensure_experiment_record(
            conn,
            self.project["id"],
            "exp_qpcr_validation",
            "qPCR validation run",
            "qPCR",
            {
                "experiment_date": "2026-05-01",
                "operator": "tester",
                "sample_ids": ["S001"],
                "result_summary": "IL6 increased in treatment group.",
                "status": "completed",
            },
        )
        sample = ros.upsert_sample_record(
            conn,
            project_id=self.project["id"],
            sample_label="S001",
            metadata={"batch": "B1"},
        )
        conn.commit()
        experiment = ros.row_to_dict(conn.execute("SELECT * FROM experiments WHERE id=?", (experiment["id"],)).fetchone())
        sample = ros.row_to_dict(conn.execute("SELECT * FROM samples WHERE id=?", (sample["id"],)).fetchone())
        conn.close()
        canonical_memory.sync_experiment(self.agent_root, experiment)
        canonical_memory.sync_sample(self.agent_root, sample)
        file_record = ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "experiment_id": experiment["id"],
                "filename": "qpcr_s001.csv",
                "content": "sample_id,value\nS001,1.23\n",
            },
        )
        context = canonical_memory.build_research_memory_context(
            self.agent_root,
            {"project_id": self.project["id"], "query": "summarize current project state", "limit": 12},
        )
        experiment_ids = {item["id"] for item in context["structured_context"]["experiments"]}
        sample_ids = {item["id"] for item in context["structured_context"]["samples"]}
        file_ids = {item["id"] for item in context["structured_context"]["data_files"]}
        self.assertIn(experiment["id"], experiment_ids)
        self.assertIn(sample["id"], sample_ids)
        self.assertIn(file_record["id"], file_ids)

    def test_upsert_experiment_helper_creates_canonical_experiment(self) -> None:
        experiment = ros.upsert_experiment(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "API experiment",
                "experiment_type": "ELISA",
                "experiment_date": "2026-05-01",
                "operator": "tester",
                "result_summary": "Signal increased.",
                "status": "completed",
            },
        )
        experiments = {item["id"]: item for item in canonical_memory.list_experiments(self.agent_root, self.project["id"])}
        self.assertEqual(experiments[experiment["id"]]["title"], "API experiment")

    def test_upsert_sample_helper_creates_canonical_sample(self) -> None:
        sample = ros.upsert_sample(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "sample_code": "S888",
                "sample_type": "serum",
                "batch": "B8",
                "current_status": "stored",
            },
        )
        samples = {item["id"]: item for item in canonical_memory.list_samples(self.agent_root, self.project["id"])}
        self.assertEqual(samples[sample["id"]]["sample_code"], "S888")

    def test_research_asset_entries_register_artifacts_and_workspace_counts(self) -> None:
        project_id = self.project["id"]
        ros.upsert_experiment(
            self.agent_root,
            {"project_id": project_id, "title": "Artifact experiment", "experiment_type": "qPCR", "status": "completed"},
        )
        ros.upsert_sample(self.agent_root, {"project_id": project_id, "sample_code": "S-AF-001", "sample_type": "cell"})
        ros.register_file(self.agent_root, {"project_id": project_id, "filename": "artifact-paper.pdf", "content": "PDF text for artifact paper."})
        ros.register_file(self.agent_root, {"project_id": project_id, "filename": "artifact-data.csv", "content": "sample_id,group,value\nS-AF-001,Model,1.2"})
        ros.create_claim(self.agent_root, {"project_id": project_id, "claim_text": "Artifact result remains preliminary.", "claim_type": "result"})
        ros.upsert_conclusion(self.agent_root, {"project_id": project_id, "conclusion_text": "Artifact conclusion draft.", "status": "draft"})
        ros.create_failure_log(self.agent_root, {"project_id": project_id, "title": "Artifact failure", "observed_failure": "Control drift."})
        ros.upsert_decision(self.agent_root, {"project_id": project_id, "decision_text": "Use fresh controls.", "status": "active"})
        ros.store_protocol(
            self.agent_root,
            {
                "project_id": project_id,
                "title": "Artifact SOP",
                "protocol_type": "SOP",
                "steps": [{"step_number": 1, "action": "Prepare samples."}],
            },
        )
        ros.generate_report(self.agent_root, {"project_id": project_id, "report_type": "weekly_report", "generate_claims": False})
        reference = ros.import_reference(
            self.agent_root,
            {
                "project_id": project_id,
                "title": "Artifact reference",
                "abstract": "RAW264.7 LPS qPCR ELISA method evidence.",
                "full_text": "Methods used RAW264.7 cells, LPS stimulation, qPCR and ELISA endpoints.",
                "source_provider": "unit",
            },
        )
        ros.build_project_research_kb(self.agent_root, {"project_id": project_id, "reference_ids": [reference["id"]], "include_article_analysis": False})

        conn = ros.connect(self.agent_root)
        try:
            artifact_types = {
                row["type"]
                for row in conn.execute("SELECT type FROM artifacts WHERE project_id=?", (project_id,)).fetchall()
            }
        finally:
            conn.close()
        for artifact_type in {
            "experiment",
            "sample",
            "pdf",
            "data_file",
            "analysis_result",
            "conclusion",
            "failure",
            "decision",
            "protocol",
            "report",
            "reference",
            "chunk",
            "kb_entry",
        }:
            self.assertIn(artifact_type, artifact_types)

        state = ros.workspace_state(self.agent_root, project_id)
        by_type = state["artifact_summary"]["by_type"]
        self.assertGreaterEqual(by_type["experiment"], 1)
        self.assertGreaterEqual(by_type["sample"], 1)
        self.assertGreaterEqual(by_type["data_file"], 1)
        self.assertGreaterEqual(by_type["kb_entry"], 1)
        answer = ros.agent_chat(self.agent_root, {"project_id": project_id, "message": "这个项目现在有哪些资料"})
        self.assertEqual(answer["intent"], "project_status")
        self.assertIn("已注册资料", answer["answer"])

    def test_validator_flags_hallucinated_experiment_and_ignored_failure(self) -> None:
        ros.create_failure_log(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Pilot drift",
                "observed_failure": "Blank control drifted during ELISA readout.",
                "likely_reason": "Plate reader warm-up was incomplete.",
            },
        )
        verdict = canonical_memory.validate_research_answer(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "answer_text": "Experiment ZX-999 conclusively proves the mechanism and no failure affected interpretation.",
                "query": "Summarize current project progress",
            },
        )
        self.assertFalse(verdict["is_valid"])
        self.assertTrue(verdict["issues"])
        self.assertTrue(verdict["ignored_memory"])

    def test_report_claims_sync_to_canonical_conclusions(self) -> None:
        ros.register_file(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "filename": "weekly_memory_source.md",
                "content": "Observation: IL6 signal remained preliminary.\nNext step: repeat qPCR with fresh reagent.",
            },
        )
        report = ros.generate_report(self.agent_root, {"project_id": self.project["id"], "report_type": "weekly_report"})
        canonical = canonical_memory.list_conclusions(self.agent_root, self.project["id"])
        claim_ids = {claim["id"] for claim in report["generated_claims"]}
        self.assertTrue(any(item.get("source_claim_id") in claim_ids for item in canonical))

    def test_agent_task_queue_and_heartbeat_create_trackable_tasks(self) -> None:
        heartbeat = ros.agent_heartbeat(self.agent_root, {"project_id": self.project["id"], "trigger": "unit", "auto_run_low_risk": False})
        tasks = ros.list_agent_tasks(self.agent_root, project_id=self.project["id"])["tasks"]
        self.assertTrue(heartbeat["created_tasks"])
        self.assertTrue(any(task["task_type"] == "literature_harvest" for task in tasks))
        self.assertTrue(heartbeat["research_feed"])

    def test_memory_consolidation_task_writes_project_memory_and_feed(self) -> None:
        task = ros.create_agent_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_type": "memory_consolidation",
                "status": "pending",
                "priority": "low",
                "input": {"trigger": "unit"},
                "force_new": True,
            },
        )
        result = ros.run_agent_task(self.agent_root, task["task_id"], {"trigger": "unit"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["task"]["status"], "completed")
        memories = ros.list_agent_memory(self.agent_root, project_id=self.project["id"])["entries"]
        feed = ros.list_agent_inbox(self.agent_root, project_id=self.project["id"])["items"]
        self.assertTrue(any(item["memory_type"] == "project_operating_summary" for item in memories))
        self.assertTrue(any(item["type"] == "memory_summary" for item in feed))

    def test_asset_events_trigger_memory_consolidation_and_feed(self) -> None:
        project_id = self.project["id"]
        start_count = len(ros.list_memory_consolidations(self.agent_root, project_id))
        ros.upsert_experiment(
            self.agent_root,
            {"project_id": project_id, "title": "Event experiment", "experiment_type": "ELISA", "status": "completed"},
        )
        runs = ros.list_memory_consolidations(self.agent_root, project_id)
        self.assertGreater(len(runs), start_count)
        self.assertTrue(any(run["trigger"] == "artifact_created" and run["source_type"] == "experiment" for run in runs))

        ros.upsert_conclusion(self.agent_root, {"project_id": project_id, "conclusion_text": "Event conclusion remains draft.", "status": "draft"})
        ros.create_failure_log(self.agent_root, {"project_id": project_id, "title": "Event failure", "observed_failure": "High blank signal."})
        feed = ros.list_agent_inbox(self.agent_root, project_id=project_id)["items"]
        self.assertTrue(any(item["type"] in {"memory_summary", "next_action"} for item in feed))
        self.assertTrue(any(item["type"] == "failure_alert" for item in feed))

    def test_chunk_and_kb_entry_events_are_batched_for_consolidation(self) -> None:
        project_id = self.project["id"]
        for index in range(6):
            ros.register_artifact(
                self.agent_root,
                {
                    "project_id": project_id,
                    "type": "chunk" if index % 2 else "kb_entry",
                    "title": f"Batch artifact {index}",
                    "source_object_type": "reference_chunk",
                    "source_object_id": f"chunk-{index}",
                    "status": "indexed",
                },
            )
        tasks = [
            task
            for task in ros.list_agent_tasks(self.agent_root, project_id=project_id, task_type="memory_consolidation")["tasks"]
            if task["source_type"] == "artifact_batch"
        ]
        self.assertEqual(len(tasks), 2)
        self.assertEqual({task["source_id"] for task in tasks}, {"artifact_created:chunk", "artifact_created:kb_entry"})

    def test_task_and_skill_completion_events_trigger_consolidation(self) -> None:
        project_id = self.project["id"]
        task = ros.create_agent_task(
            self.agent_root,
            {
                "project_id": project_id,
                "task_type": "report_generation",
                "status": "pending",
                "priority": "medium",
                "input": {"scope": "unit"},
                "force_new": True,
            },
        )
        ros.update_agent_task(self.agent_root, task["task_id"], {"status": "completed"})
        service_run = ros.start_service_skill_run(self.agent_root, "unit_skill", "UnitSkill", project_id, {"project_id": project_id})
        ros.finish_service_skill_run(
            self.agent_root,
            service_run["id"],
            {"project_id": project_id, "result": "ok"},
            [{"type": "report", "id": "unit-report"}],
            ["unit run completed"],
        )

        runs = ros.list_memory_consolidations(self.agent_root, project_id)
        self.assertTrue(any(run["trigger"] == "task_completed" and run["source_type"] == "agent_task" for run in runs))
        self.assertTrue(any(run["trigger"] == "skill_run_completed" and run["source_type"] == "skill_run" for run in runs))
        answer = ros.agent_chat(self.agent_root, {"project_id": project_id, "message": "最近有什么进展"})
        self.assertEqual(answer["intent"], "proactive_status_query")
        self.assertTrue(answer.get("research_feed"))

    def test_user_correction_event_triggers_consolidation_without_confirming_claims(self) -> None:
        project_id = self.project["id"]
        result = ros.record_user_correction(
            self.agent_root,
            {"project_id": project_id, "correction_text": "The pilot ELISA conclusion should remain preliminary."},
        )
        self.assertEqual(result["correction_memory"]["memory_type"], "user_correction")
        runs = ros.list_memory_consolidations(self.agent_root, project_id)
        self.assertTrue(any(run["trigger"] == "user_correction_received" for run in runs))
        conclusions = canonical_memory.list_conclusions(self.agent_root, project_id, status="confirmed")
        self.assertFalse(conclusions)

    def test_agent_records_user_and_project_profile_without_research_advice(self) -> None:
        project_id = self.project["id"]
        message = "我叫钟正栩，我在研究先天免疫，我目前的课题是发酵肉桂渣的免疫调节活性"
        response = ros.agent_chat(self.agent_root, {"project_id": project_id, "message": message})
        self.assertIn(response["intent"], {"user_profile_update", "project_profile_update", "research_direction_update", "active_project_update"})
        self.assertIn("已记录", response["answer"])
        self.assertIn("钟正栩", response["answer"])
        self.assertIn("先天免疫", response["answer"])
        self.assertIn("发酵肉桂渣的免疫调节活性", response["answer"])
        self.assertNotIn("实验方案", response["answer"])
        self.assertNotIn("下一步", response["answer"])
        memory = ros.list_agent_memory(self.agent_root, scope="project", project_id=project_id, include_disabled=True)["entries"]
        memory_types = {item["memory_type"] for item in memory}
        self.assertIn("user_profile", memory_types)
        self.assertIn("project_profile", memory_types)

    def test_agent_answers_saved_user_name_and_current_topic(self) -> None:
        project_id = self.project["id"]
        conversation = ros.agent_chat(
            self.agent_root,
            {"project_id": project_id, "message": "我叫钟正栩，我在研究先天免疫，我目前的课题是发酵肉桂渣的免疫调节活性"},
        )
        name_answer = ros.agent_chat(self.agent_root, {"project_id": project_id, "conversation_id": conversation["conversation_id"], "message": "我叫什么"})
        topic_answer = ros.agent_chat(self.agent_root, {"project_id": project_id, "conversation_id": conversation["conversation_id"], "message": "我现在做什么课题"})
        self.assertEqual(name_answer["intent"], "user_profile_query")
        self.assertIn("你叫钟正栩", name_answer["answer"])
        self.assertEqual(topic_answer["intent"], "project_profile_query")
        self.assertIn("发酵肉桂渣的免疫调节活性", topic_answer["answer"])

    def test_agent_enters_research_advice_only_when_user_asks_to_introduce_topic(self) -> None:
        project_id = self.project["id"]
        conversation = ros.agent_chat(
            self.agent_root,
            {"project_id": project_id, "message": "我叫钟正栩，我在研究先天免疫，我目前的课题是发酵肉桂渣的免疫调节活性"},
        )
        response = ros.agent_chat(self.agent_root, {"project_id": project_id, "conversation_id": conversation["conversation_id"], "message": "介绍一下这个课题"})
        self.assertEqual(response["intent"], "research_advice")
        self.assertNotIn("我已记录", response["answer"])

    def test_agent_does_not_overwrite_literature_collection_name_as_project_title(self) -> None:
        raw_project = ros.create_project(self.agent_root, {"title": "RAW264.7", "research_area": "macrophage literature", "keywords": ["RAW264.7"]})
        message = "我叫钟正栩，我在研究先天免疫，我目前的课题是发酵肉桂渣的免疫调节活性"
        response = ros.agent_chat(self.agent_root, {"project_id": raw_project["id"], "message": message})
        self.assertIn("RAW264.7", response["answer"])
        self.assertIn("是否", response["answer"])
        project = ros.get_project_detail(self.agent_root, raw_project["id"])
        self.assertEqual(project["title"], "RAW264.7")

    def test_heartbeat_runs_batch_memory_consolidation_task(self) -> None:
        project_id = self.project["id"]
        ros.register_artifact(
            self.agent_root,
            {
                "project_id": project_id,
                "type": "chunk",
                "title": "Heartbeat batch chunk",
                "source_object_type": "reference_chunk",
                "source_object_id": "heartbeat-chunk-1",
                "status": "indexed",
            },
        )
        pending = [
            task
            for task in ros.list_agent_tasks(self.agent_root, project_id=project_id, task_type="memory_consolidation")["tasks"]
            if task["status"] == "pending"
        ]
        self.assertTrue(pending)
        heartbeat = ros.agent_heartbeat(self.agent_root, {"project_id": project_id, "trigger": "unit", "max_auto_run": 5})
        self.assertTrue(any(result.get("ok") for result in heartbeat["auto_run_results"]))
        completed = ros.get_agent_task(self.agent_root, pending[0]["task_id"])
        self.assertEqual(completed["status"], "completed")
        self.assertTrue(ros.list_memory_consolidations(self.agent_root, project_id))

    def test_heartbeat_auto_runs_low_risk_report_and_skill_learning_tasks(self) -> None:
        project_id = self.project["id"]
        report_task = ros.create_agent_task(
            self.agent_root,
            {"project_id": project_id, "task_type": "report_generation", "status": "pending", "priority": "low", "force_new": True},
        )
        skill_task = ros.create_agent_task(
            self.agent_root,
            {
                "project_id": project_id,
                "task_type": "skill_learning",
                "status": "pending",
                "priority": "low",
                "input": {"request": "Draft a reusable workflow"},
                "force_new": True,
            },
        )
        heartbeat = ros.agent_heartbeat(self.agent_root, {"project_id": project_id, "trigger": "unit", "max_auto_run": 5})
        run_task_ids = {result["task"]["task_id"] for result in heartbeat["auto_run_results"] if result.get("ok")}
        self.assertIn(report_task["task_id"], run_task_ids)
        self.assertIn(skill_task["task_id"], run_task_ids)
        self.assertEqual(ros.get_agent_task(self.agent_root, report_task["task_id"])["status"], "completed")
        self.assertEqual(ros.get_agent_task(self.agent_root, skill_task["task_id"])["status"], "completed")

    def test_heartbeat_does_not_auto_run_waiting_for_user_tasks(self) -> None:
        project_id = self.project["id"]
        task = ros.create_agent_task(
            self.agent_root,
            {"project_id": project_id, "task_type": "literature_harvest", "status": "waiting_for_user", "priority": "high", "force_new": True},
        )
        heartbeat = ros.agent_heartbeat(self.agent_root, {"project_id": project_id, "trigger": "unit", "max_auto_run": 5})
        self.assertFalse(any((result.get("task") or {}).get("task_id") == task["task_id"] for result in heartbeat["auto_run_results"]))
        self.assertEqual(ros.get_agent_task(self.agent_root, task["task_id"])["status"], "waiting_for_user")
        self.assertTrue(heartbeat["waiting_for_user"])

    def test_heartbeat_records_failed_low_risk_task_and_feed(self) -> None:
        project_id = self.project["id"]
        conn = ros.connect(self.agent_root)
        try:
            conn.execute("DELETE FROM skill_registry WHERE skill_id=?", ("core_weekly_research_report",))
            conn.commit()
        finally:
            conn.close()
        task = ros.create_agent_task(
            self.agent_root,
            {"project_id": project_id, "task_type": "report_generation", "status": "pending", "priority": "low", "force_new": True},
        )
        heartbeat = ros.agent_heartbeat(self.agent_root, {"project_id": project_id, "trigger": "unit", "max_auto_run": 5})
        failed = ros.get_agent_task(self.agent_root, task["task_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["error"])
        self.assertTrue(any(not result.get("ok") for result in heartbeat["auto_run_results"]))
        feed = ros.list_agent_inbox(self.agent_root, project_id=project_id)["items"]
        self.assertTrue(any(item["type"] in {"task_update", "failure_alert"} for item in feed))

    def test_scheduler_runs_pending_low_risk_tasks(self) -> None:
        project_id = self.project["id"]
        task = ros.create_agent_task(
            self.agent_root,
            {
                "project_id": project_id,
                "task_type": "memory_consolidation",
                "status": "pending",
                "priority": "low",
                "input": {"trigger": "scheduler_unit"},
                "force_new": True,
            },
        )
        ros.configure_project_watch(self.agent_root, project_id, {"auto_literature_scout": False, "watch_interval_minutes": 0})
        result = ros.run_scheduled_research_watch(self.agent_root, force=False, project_id=project_id)
        self.assertTrue(result["outcomes"])
        self.assertEqual(ros.get_agent_task(self.agent_root, task["task_id"])["status"], "completed")

    def test_skill_learning_task_creates_draft_not_active_skill(self) -> None:
        task = ros.create_agent_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_type": "skill_learning",
                "status": "pending",
                "priority": "medium",
                "input": {"request": "把刚才流程总结成 skill"},
                "force_new": True,
            },
        )
        result = ros.run_agent_task(self.agent_root, task["task_id"], {"message": "把刚才流程总结成 skill"})
        self.assertTrue(result["ok"])
        draft = result["result"]["skill_draft"]
        self.assertEqual(draft["status"], "draft")
        self.assertTrue(draft["steps"])


if __name__ == "__main__":
    unittest.main()
