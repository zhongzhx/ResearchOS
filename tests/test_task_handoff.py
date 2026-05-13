import unittest

from backend.researchos.tasks.research_task import ResearchTask
from backend.researchos.tasks.task_handoff import compose_handoff


class TaskHandoffTests(unittest.TestCase):
    def test_handoff_contains_required_sections(self) -> None:
        task = ResearchTask(task_id="task_handoff", project_id="project_1", user_query="summarize")
        task.status = "committed"
        task.execution = {"status": "success", "structured_outputs": {"summary": "Summarized evidence."}, "errors": [], "unresolved_items": []}
        task.artifacts = [{"artifact_id": "a1", "path": "/tmp/report.md", "type": "md"}]
        task.validation = {"safe_to_return": True, "safe_to_promote": True}
        task.memory_commit = {"promoted_pages": [{"page_type": "project"}], "required_human_review": False}

        handoff = compose_handoff(task)

        self.assertIn("完成了什么", handoff)
        self.assertIn("生成了哪些文件", handoff)
        self.assertIn("关键结论和置信度", handoff)
        self.assertIn("未解决项", handoff)
        self.assertIn("可复用流程候选", handoff)


if __name__ == "__main__":
    unittest.main()
