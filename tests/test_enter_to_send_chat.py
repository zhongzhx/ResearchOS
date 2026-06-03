from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "web_client" / "views" / "chat.js"


class EnterToSendChatTests(unittest.TestCase):
    def test_enter_submits_and_shift_enter_remains_available_for_newline(self) -> None:
        source = CHAT.read_text(encoding="utf-8")

        self.assertIn('event.key === "Enter" && !event.shiftKey', source)
        self.assertIn("event.preventDefault()", source)
        self.assertIn("submitPrompt(root, input.value.trim())", source)


if __name__ == "__main__":
    unittest.main()
