from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ChatWorkflowIntentTests(unittest.TestCase):
    def test_literature_request_is_recognized_as_user_intent(self) -> None:
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("literature_harvest_and_kb", intents)
        self.assertIn("下载文献", intents)
        self.assertIn("构建知识库", intents)

    def test_missing_literature_topic_asks_followup_without_execution(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("请告诉我文献检索主题或关键词", intents)
        missing_block = re.search(r"function handleWorkflowIntent\(.*?return true;\n}\n", chat, re.S)
        self.assertIsNotNone(missing_block)
        self.assertIn("validateWorkflowParams", missing_block.group(0))
        self.assertNotIn("executeWorkflow(", missing_block.group(0))

    def test_literature_topic_builds_confirmation_with_default_max_papers(self) -> None:
        intents = read(WEB_CLIENT / "user_workflows.js")
        message = read(WEB_CLIENT / "components" / "message.js")

        self.assertIn("max_papers: 20", intents)
        self.assertIn("仅开放获取文献", message)
        self.assertIn("构建知识库", message)
        self.assertIn("开始", message)
        self.assertIn("修改设置", message)
        self.assertIn("取消", message)

    def test_confirmation_reply_executes_only_after_pending_confirmation(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")

        self.assertIn("isWorkflowConfirmation(prompt)", chat)
        self.assertIn('status: "confirmed"', chat)
        self.assertIn("await executePendingWorkflow", chat)
        submit_block = re.search(r"async function submitPrompt\(.*?\n}\n\nexport async function renderChatView", chat, re.S)
        self.assertIsNotNone(submit_block)
        self.assertIn("handlePendingWorkflowReply(root, prompt)", submit_block.group(0))

    def test_parameter_update_rerenders_confirmation_without_execution(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("updateWorkflowDraft", intents)
        self.assertIn("extractCount", intents)
        self.assertIn("max_papers", intents)
        update_block = re.search(r"const updated = updateWorkflowDraft\(.*?return true;\n  }\n", chat, re.S)
        self.assertIsNotNone(update_block)
        self.assertNotIn("executeWorkflow(", update_block.group(0))

    def test_cancel_reply_clears_pending_workflow(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("isWorkflowCancellation(prompt)", chat)
        self.assertIn("pendingWorkflow = null", chat)
        self.assertIn("已取消这次任务。", chat)

    def test_general_question_does_not_trigger_workflow(self) -> None:
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("什么是阿尔茨海默症", intents)
        self.assertIn("return null", intents)

    def test_experiment_design_intent_has_required_research_goal(self) -> None:
        intents = read(WEB_CLIENT / "user_workflows.js")

        self.assertIn("raw264.7", intents)
        self.assertIn("experiment_design", intents)
        self.assertIn("research_goal", intents)
        self.assertIn("请补充实验目标", intents)

    def test_experiment_design_request_goes_directly_to_chat_answer(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        backend = read(ROOT / "backend" / "research_agent_runtime" / "scripts" / "research_os_mvp.py")

        self.assertIn('if (detected.intent === "experiment_design") return false;', chat)
        self.assertIn("experiment_plan_output_schema", backend)
        for section in ["实验名称", "实验目的", "实验试剂", "实验模型", "实验步骤"]:
            with self.subTest(section=section):
                self.assertIn(section, backend)

    def test_normal_mode_hides_internal_terms(self) -> None:
        combined = "\n".join(
            read(path)
            for path in [
                WEB_CLIENT / "views" / "chat.js",
                WEB_CLIENT / "components" / "message.js",
            ]
        )
        render_blocks = "\n".join(
            match.group(0)
            for match in re.finditer(r"export function (workflowConfirmationMessage|workflowResultMessage|plainMessage|chatAnswerMessage).*?\n}\n", combined, re.S)
        )
        for token in ["skill_id", "pipeline_id", "TaskSpec", "SkillRun", "raw JSON", "backend route"]:
            with self.subTest(token=token):
                self.assertNotIn(token, render_blocks)

    def test_not_connected_result_uses_truthful_chinese_copy(self) -> None:
        api = read(WEB_CLIENT / "api.js")
        message = read(WEB_CLIENT / "components" / "message.js")

        self.assertIn("真实执行入口尚未接入", api + message)
        self.assertNotIn("伪装执行成功", api + message)

    def test_developer_mode_can_show_technical_details(self) -> None:
        message = read(WEB_CLIENT / "components" / "message.js")

        self.assertIn("developerMode", message)
        self.assertIn("技术详情", message)

    def test_default_chat_still_uses_send_legacy_chat(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")

        self.assertIn("sendLegacyChat(prompt", chat)
        self.assertIn("await sendStableChat(prompt)", chat)


if __name__ == "__main__":
    unittest.main()
