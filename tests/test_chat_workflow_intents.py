from pathlib import Path
import json
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str) -> str:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def detect(message: str) -> dict | None:
    output = run_node(
        f"""
        const {{ detectWorkflowIntent }} = await import({(WEB_CLIENT / "workflow_intents.js").as_uri()!r});
        process.stdout.write(JSON.stringify(detectWorkflowIntent({json.dumps(message, ensure_ascii=False)})));
        """
    )
    return json.loads(output)


class ChatWorkflowIntentTests(unittest.TestCase):
    def test_required_chat_messages_detect_expected_intents_and_params(self) -> None:
        cases = [
            ("帮我下载文献构建知识库，主题是神经炎症天然产物，20篇", "literature_harvest_and_kb", {"query": "神经炎症天然产物", "max_papers": 20, "build_kb": True}),
            ("帮我找近五年 RAW264.7 抗炎文献", "literature_search", {"query": "RAW264.7 抗炎", "recent_years": 5}),
            ("把这篇论文做成15页组会PPT", "paper_to_ppt", {"slide_count": 15}),
            ("润色这段英文并检查过度声称", "english_polishing", {"check_overclaim": True}),
            ("帮我做 qPCR 数据分析", "qpcr_elisa_cck8_analysis", {"assay_type": "qPCR"}),
            ("帮我设计 RAW264.7 实验方案", "experiment_design", {"model": "RAW264.7"}),
        ]
        for message, intent, expected_params in cases:
            with self.subTest(message=message):
                result = detect(message)
                self.assertIsNotNone(result)
                self.assertEqual(result["intent"], intent)
                for key, value in expected_params.items():
                    self.assertEqual(result["params"].get(key), value)

    def test_each_required_intent_has_at_least_five_chinese_triggers(self) -> None:
        output = run_node(
            f"""
            const {{ USER_WORKFLOW_INTENTS }} = await import({(WEB_CLIENT / "workflow_intents.js").as_uri()!r});
            process.stdout.write(JSON.stringify(USER_WORKFLOW_INTENTS.map((item) => [item.intent, item.triggers.length])));
            """
        )
        counts = dict(json.loads(output))
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
                self.assertGreaterEqual(counts.get(intent, 0), 5)

    def test_missing_required_params_asks_followup_without_execution(self) -> None:
        output = run_node(
            f"""
            const {{ detectWorkflowIntent }} = await import({(WEB_CLIENT / "workflow_intents.js").as_uri()!r});
            const {{ createWorkflowDraft, validateWorkflowParams, executeWorkflow }} = await import({(WEB_CLIENT / "user_workflows.js").as_uri()!r});
            const detected = detectWorkflowIntent("帮我做 qPCR 数据分析");
            const draft = createWorkflowDraft(detected.intent, detected.params, {{ projectId: "p1" }});
            const validation = validateWorkflowParams(draft.intent, draft.params);
            let called = false;
            const result = await executeWorkflow(draft, {{ createLiteratureSearchTask: () => {{ called = true; }} }});
            process.stdout.write(JSON.stringify({{ detected, validation, result, called }}));
            """
        )
        data = json.loads(output)
        self.assertEqual(data["detected"]["intent"], "qpcr_elisa_cck8_analysis")
        self.assertIn("file_id", data["validation"]["missing"])
        self.assertFalse(data["called"])
        self.assertIn(data["result"]["status"], {"pending_confirmation", "needs_input"})

    def test_confirmation_update_and_cancel_are_handled_by_controller(self) -> None:
        output = run_node(
            f"""
            const {{ detectWorkflowIntent }} = await import({(WEB_CLIENT / "workflow_intents.js").as_uri()!r});
            const {{ createWorkflowDraft, updateWorkflowDraft, isWorkflowCancellation }} = await import({(WEB_CLIENT / "user_workflows.js").as_uri()!r});
            const detected = detectWorkflowIntent("帮我下载文献构建知识库，主题是神经炎症天然产物，20篇");
            const draft = createWorkflowDraft(detected.intent, detected.params, {{ projectId: "p1" }});
            const updated = updateWorkflowDraft(draft, "改成50篇，只要近三年");
            const cancelled = updateWorkflowDraft(updated, "取消");
            process.stdout.write(JSON.stringify({{ updated, cancelled, isCancel: isWorkflowCancellation("不用了") }}));
            """
        )
        data = json.loads(output)
        self.assertEqual(data["updated"]["params"]["max_papers"], 50)
        self.assertEqual(data["updated"]["params"]["recent_years"], 3)
        self.assertEqual(data["cancelled"]["status"], "cancelled")
        self.assertTrue(data["isCancel"])

    def test_general_questions_do_not_trigger_workflow(self) -> None:
        messages = [
            "什么是阿尔兹海默症？",
            "训练免疫是什么？",
            "NF-kB 是什么？",
            "你可以为我做什么？",
            "这篇话怎么理解？",
            "我应该怎么规划学习？",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertIsNone(detect(message))

    def test_chat_uses_workflow_intents_and_hides_internal_terms(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        message = read(WEB_CLIENT / "components" / "message.js")
        workflow_intents = read(WEB_CLIENT / "workflow_intents.js")

        self.assertIn('from "../workflow_intents.js"', chat)
        self.assertIn("executeWorkflow(workflow, api", chat)
        self.assertIn("saveWorkflowHistory", chat)
        self.assertIn("USER_WORKFLOW_INTENTS", workflow_intents)
        visible_blocks = chat + message
        for token in ["skill_id", "TaskSpec", "SkillRun", "Raw JSON"]:
            with self.subTest(token=token):
                self.assertNotIn(token, visible_blocks)


if __name__ == "__main__":
    unittest.main()
