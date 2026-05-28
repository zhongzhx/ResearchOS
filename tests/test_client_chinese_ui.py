from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClientChineseUiTests(unittest.TestCase):
    def test_shell_and_chat_copy_are_chinese(self) -> None:
        index = (ROOT / "web_client" / "index.html").read_text(encoding="utf-8")
        chat = (ROOT / "web_client" / "views" / "chat.js").read_text(encoding="utf-8")

        self.assertIn('<html lang="zh-CN">', index)
        for label in ["聊天", "项目", "设置"]:
            self.assertIn(label, index + chat)
        for label in ["任务流程", "研究大脑", "文献库", "技能", "运行记录"]:
            self.assertNotIn(label, index + chat)
        for label in ["Stable Chat", "Dual-Agent Experimental", ">Send<", ">Demo<", "No project selected"]:
            self.assertNotIn(label, chat)

    def test_feature_tabs_use_chinese_labels(self) -> None:
        files = [
            ROOT / "web_client" / "views" / "brain.js",
            ROOT / "web_client" / "views" / "library.js",
            ROOT / "web_client" / "views" / "runs.js",
            ROOT / "web_client" / "views" / "skills.js",
            ROOT / "web_client" / "views" / "settings.js",
            ROOT / "web_client" / "views" / "task_lifecycle.js",
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in files)

        for label in ["主张", "决策", "失败记录", "实验方案", "报告", "关系", "待复核", "引用", "任务", "运行记录", "功能流程", "路由测试", "运行状态"]:
            self.assertIn(label, source)
        for label in ["Loading", "No tasks yet", "Route query", "Runtime Status", "Task Lifecycle"]:
            self.assertNotIn(label, source)


if __name__ == "__main__":
    unittest.main()
