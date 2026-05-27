from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def definition_block(source: str, intent: str) -> str:
    match = re.search(rf"{intent}:\s*\{{(?P<body>.*?)\n  \}},", source, re.S)
    return match.group("body") if match else ""


class UserWorkflowControllerTests(unittest.TestCase):
    def test_controller_exports_required_api_and_workflow_definitions(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        for export_name in [
            "WORKFLOW_DEFINITIONS",
            "WORKFLOW_GROUPS",
            "createWorkflowDraft",
            "validateWorkflowParams",
            "buildWorkflowPlan",
            "updateWorkflowDraft",
            "executeWorkflow",
            "formatWorkflowResult",
        ]:
            with self.subTest(export_name=export_name):
                if export_name in {"WORKFLOW_DEFINITIONS", "WORKFLOW_GROUPS"}:
                    self.assertIn(f"export const {export_name}", source)
                else:
                    self.assertRegex(source, rf"export\s+(async\s+)?function\s+{export_name}\b")

    def test_contains_required_user_workflow_intents(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        required = [
            "literature_search",
            "literature_harvest_and_kb",
            "ingest_uploaded_papers",
            "paper_reader",
            "citation_finder",
            "paper_to_ppt",
            "experiment_design",
            "protocol_to_sop",
            "failure_recovery",
            "experiment_log",
            "next_step_plan",
            "table_analysis",
            "qpcr_elisa_cck8_analysis",
            "metabolomics_interpretation",
            "figure_generation",
            "ml_modeling_assistant",
            "manuscript_section_writing",
            "english_polishing",
            "peer_review_simulation",
            "reviewer_response",
            "submission_checklist",
            "weekly_report",
        ]
        for intent in required:
            with self.subTest(intent=intent):
                self.assertIn(f"{intent}:", source)

        definition_count = len(re.findall(r"\n  [a-z0-9_]+:\s*\{", source))
        self.assertGreaterEqual(definition_count, 22)

    def test_each_definition_has_required_user_level_fields(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        for intent in re.findall(r"\n  ([a-z0-9_]+):\s*\{", source):
            body = definition_block(source, intent)
            with self.subTest(intent=intent):
                for field in [
                    "intent:",
                    "user_title:",
                    "user_description:",
                    "group:",
                    "required_params:",
                    "optional_params:",
                    "default_params:",
                    "confirmation_template:",
                    "user_visible_steps:",
                    "execution_strategy:",
                    "current_status:",
                    "output_types:",
                    "save_to_project:",
                    "developer_notes:",
                ]:
                    self.assertIn(field, body)

    def test_default_params_for_key_workflows(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        literature_search = definition_block(source, "literature_search")
        self.assertIn("max_results: 50", literature_search)
        self.assertIn("recent_years: 5", literature_search)
        self.assertIn("include_review: true", literature_search)

        harvest = definition_block(source, "literature_harvest_and_kb")
        self.assertIn("max_papers: 20", harvest)
        self.assertIn("oa_only: true", harvest)
        self.assertIn("build_kb: true", harvest)
        self.assertIn('non_oa_policy: "manual_queue"', harvest)

        paper_reader = definition_block(source, "paper_reader")
        self.assertIn('language: "zh"', paper_reader)
        self.assertIn('output_format: "markdown"', paper_reader)
        self.assertIn("include_figure_explanation: true", paper_reader)

        paper_to_ppt = definition_block(source, "paper_to_ppt")
        self.assertIn("slide_count: 15", paper_to_ppt)
        self.assertIn('language: "zh"', paper_to_ppt)
        self.assertIn("include_speaker_notes: true", paper_to_ppt)

        figure_generation = definition_block(source, "figure_generation")
        self.assertIn('output_format: "svg"', figure_generation)
        self.assertIn('style: "publication"', figure_generation)

        english_polishing = definition_block(source, "english_polishing")
        self.assertIn("check_overclaim: true", english_polishing)
        self.assertIn("preserve_meaning: true", english_polishing)

        reviewer_response = definition_block(source, "reviewer_response")
        self.assertIn("require_action_mapping: true", reviewer_response)
        self.assertIn("require_revision_location: true", reviewer_response)

    def test_statuses_cover_executable_plan_file_auth_and_not_ready(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        for status in ["executable", "plan_only", "needs_file", "needs_authorization", "not_ready"]:
            with self.subTest(status=status):
                self.assertIn(f'current_status: "{status}"', source)

    def test_missing_query_returns_followup_before_execution(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        validate = re.search(r"export function validateWorkflowParams\(.*?\n}\n\nfunction fillTemplate", source, re.S)
        self.assertIsNotNone(validate)

        self.assertIn("missing.push(key)", validate.group(0))
        self.assertIn('"query"', source)
        self.assertIn("QUESTION_BY_PARAM[key]", validate.group(0))
        self.assertIn('query: "请告诉我文献检索主题或关键词。"', source)
        self.assertNotIn("createLiteratureSearchTask", validate.group(0))

    def test_execute_requires_confirmation_before_real_calls(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        execute = re.search(r"export async function executeWorkflow\(.*?\n}\n\nexport function formatWorkflowResult", source, re.S)
        self.assertIsNotNone(execute)
        body = execute.group(0)

        self.assertIn('draft?.status !== "confirmed"', body)
        guard = body.split('draft?.status !== "confirmed"', 1)[0]
        self.assertNotIn("createLiteratureSearchTask", guard)

    def test_confirmed_literature_harvest_calls_legacy_api_in_order(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        body = re.search(r"async function executeLiteratureWorkflow\(.*?\n}\n\nasync function executePlanOnlyWorkflow", source, re.S)
        self.assertIsNotNone(body)
        text = body.group(0)

        ordered = [
            "api.createLiteratureSearchTask",
            "api.runLiteratureSearch",
            "api.generatePaperRequests",
            "api.buildKnowledgeBase",
        ]
        positions = [text.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("return failedWorkflowStep", text)
        self.assertIn("手动下载队列", text)

    def test_plan_only_and_not_ready_do_not_report_fake_success(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn('status: "plan_only"', source)
        self.assertIn("已生成计划", source)
        self.assertIn("该功能正在接入中", source)
        self.assertNotIn("伪装", source)

    def test_format_workflow_result_hides_technical_details_without_developer_mode(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        formatter = re.search(r"export function formatWorkflowResult\(.*?\n}\n\nexport function workflowHistoryRecord", source, re.S)
        self.assertIsNotNone(formatter)

        self.assertIn("developerMode && result?.technical", formatter.group(0))
        self.assertNotIn("developer_notes: result", formatter.group(0))


if __name__ == "__main__":
    unittest.main()
