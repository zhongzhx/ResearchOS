from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class UserWorkflowControllerTests(unittest.TestCase):
    def test_controller_exports_required_api_and_workflow_definitions(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        for export_name in [
            "WORKFLOW_DEFINITIONS",
            "createWorkflowDraft",
            "validateWorkflowParams",
            "buildWorkflowPlan",
            "updateWorkflowDraft",
            "executeWorkflow",
            "formatWorkflowResult",
        ]:
            with self.subTest(export_name=export_name):
                if export_name == "WORKFLOW_DEFINITIONS":
                    self.assertIn("export const WORKFLOW_DEFINITIONS", source)
                else:
                    self.assertRegex(source, rf"export\s+(async\s+)?function\s+{export_name}\b")

        for intent in [
            "literature_harvest_and_kb",
            "ingest_uploaded_papers",
            "data_analysis",
            "experiment_design",
            "protocol_to_sop",
            "writing_review",
            "failure_recovery",
            "weekly_report",
        ]:
            with self.subTest(intent=intent):
                self.assertIn(f"{intent}:", source)

    def test_literature_defaults_are_safe_and_limited(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        block = re.search(r"literature_harvest_and_kb:\s*\{(?P<body>.*?)\n  \},\n  ingest_uploaded_papers", source, re.S)
        self.assertIsNotNone(block)
        body = block.group("body")

        self.assertIn("max_papers: 20", body)
        self.assertIn("oa_only: true", body)
        self.assertIn("build_kb: true", body)
        self.assertIn('non_oa_policy: "manual_queue"', body)
        self.assertIn("合法开放获取", body)
        self.assertIn("用户手动下载", body)

    def test_missing_query_returns_followup_before_execution(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        validate = re.search(r"export function validateWorkflowParams\(.*?\n}\n\nexport function buildWorkflowPlan", source, re.S)
        self.assertIsNotNone(validate)

        self.assertIn("missing.push(key)", validate.group(0))
        self.assertIn('"query"', source)
        self.assertIn("请告诉我文献检索主题或关键词", validate.group(0))
        self.assertNotIn("createLiteratureSearchTask", validate.group(0))

    def test_execute_requires_confirmation_before_real_calls(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        execute = re.search(r"export async function executeWorkflow\(.*?\n}\n\nexport function formatWorkflowResult", source, re.S)
        self.assertIsNotNone(execute)
        body = execute.group(0)

        self.assertIn('draft?.status !== "confirmed"', body)
        guard = body.split('draft?.status !== "confirmed"', 1)[0]
        self.assertNotIn("createLiteratureSearchTask", guard)

    def test_confirmed_literature_calls_legacy_api_in_order(self) -> None:
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

    def test_failed_step_stops_with_chinese_error(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("没有完成", source)
        self.assertIn("已停止后续步骤", source)
        self.assertIn('status: "failed"', source)

    def test_data_analysis_not_ready_returns_plan_only(self) -> None:
        source = read(WEB_CLIENT / "user_workflows.js")
        block = re.search(r"data_analysis:\s*\{(?P<body>.*?)\n  \},\n  experiment_design", source, re.S)
        self.assertIsNotNone(block)

        self.assertIn('execution_strategy: "plan_only"', block.group("body"))
        self.assertIn("数据分析执行入口仍在接入中，我可以先帮你生成分析计划", source)
        self.assertNotIn("伪装", source)


if __name__ == "__main__":
    unittest.main()
