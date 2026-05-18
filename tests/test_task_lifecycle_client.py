from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TASK_LIFECYCLE_JS = ROOT / "web_client" / "views" / "task_lifecycle.js"


class TaskLifecycleClientTests(unittest.TestCase):
    def test_task_list_filters_and_clicks_through_to_detail(self) -> None:
        source = TASK_LIFECYCLE_JS.read_text(encoding="utf-8")

        for marker in ["taskStatusFilter", "taskTypeFilter", "taskSearch", "getTask(button.dataset.itemId)"]:
            self.assertIn(marker, source)

    def test_full_research_task_and_legacy_mvp_metadata_sections_render(self) -> None:
        source = TASK_LIFECYCLE_JS.read_text(encoding="utf-8")

        for section in ["目标", "计划", "契约", "执行", "产物", "校验", "交接摘要", "记忆提交"]:
            self.assertIn(section, source)

        self.assertIn("历史元数据", source)
        self.assertIn("metadata", source)
        self.assertNotIn("runProductFeature", source)


if __name__ == "__main__":
    unittest.main()
