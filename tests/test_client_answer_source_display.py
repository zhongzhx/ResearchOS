from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClientAnswerSourceDisplayTests(unittest.TestCase):
    def test_chat_answer_hides_provenance_until_debug_is_enabled(self) -> None:
        source = (ROOT / "web_client" / "components" / "message.js").read_text(encoding="utf-8")
        chat_answer = source.split("export function dualAgentMessage", 1)[0]

        self.assertIn("shouldShowChatDiagnostics", chat_answer)
        self.assertIn("show_diagnostics", chat_answer)
        self.assertIn("answer_source", chat_answer)
        self.assertIn("llm_called", chat_answer)
        self.assertIn("llm_output_used", chat_answer)
        self.assertIn("answer_overwritten_after_llm", chat_answer)
        self.assertIn("回答来源", chat_answer)
        self.assertIn("任务状态", chat_answer)
        self.assertNotIn('const details = [answerSourceDetails(data), taskStatusDetails(data)].join("");', chat_answer)
        self.assertNotIn('jsonDetails("Raw JSON"', chat_answer)

    def test_research_task_handoff_is_not_used_as_plain_chat_answer(self) -> None:
        source = (ROOT / "web_client" / "components" / "message.js").read_text(encoding="utf-8")

        self.assertIn("Research Task Handoff", source)
        self.assertIn("该响应来自任务执行链路，已隐藏内部交接内容。请在实验模式或任务页查看详情。", source)


if __name__ == "__main__":
    unittest.main()
