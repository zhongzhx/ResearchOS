from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WorkspaceChatWorkflowIntegrationTests(unittest.TestCase):
    def test_workspace_and_chat_use_same_controller_for_drafts(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        chat = read(WEB_CLIENT / "views" / "chat.js")

        self.assertIn('from "../user_workflows.js"', workspace)
        self.assertIn('from "../user_workflows.js"', chat)
        self.assertIn("createWorkflowDraft(", workspace)
        self.assertIn("createWorkflowDraft(", chat)
        self.assertIn("buildWorkflowPlan(", workspace)
        self.assertIn("buildWorkflowPlan(", chat)

    def test_workspace_and_chat_execute_only_through_execute_workflow(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        chat = read(WEB_CLIENT / "views" / "chat.js")

        for source in [workspace, chat]:
            with self.subTest(source=source[:20]):
                self.assertIn("executeWorkflow(", source)
                self.assertNotIn("executeConfirmedWorkflow", source)
                self.assertNotIn("runProductFeature", source)

        workflow_paths = [workspace, chat]
        for token in ["createLiteratureSearchTask", "runLiteratureSearch", "generatePaperRequests", "buildKnowledgeBase", "runLegacySkill"]:
            with self.subTest(token=token):
                self.assertTrue(all(token not in source for source in workflow_paths))

    def test_history_is_project_scoped_and_shared(self) -> None:
        controller = read(WEB_CLIENT / "user_workflows.js")
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        chat = read(WEB_CLIENT / "views" / "chat.js")

        self.assertIn("researchos.workflowHistory.v1.", controller)
        self.assertIn("saveWorkflowHistory", controller)
        self.assertIn("listWorkflowHistory", controller)
        self.assertIn("linked_conversation_id", controller)
        self.assertIn("listWorkflowHistory(projectId)", workspace)
        self.assertIn("saveWorkflowHistory", chat)

    def test_chat_workflow_result_is_visible_to_workspace_history(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        chat_execute = re.search(r"async function executePendingWorkflow\(.*?\n}\n\nasync function handlePendingWorkflowReply", chat, re.S)
        self.assertIsNotNone(chat_execute)
        self.assertIn("saveWorkflowHistory", chat_execute.group(0))
        self.assertIn("result_summary", chat_execute.group(0))

        self.assertIn("最近工作流", workspace)
        self.assertIn("result_summary", workspace)

    def test_workspace_workflow_result_can_be_reflected_in_chat(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        confirm = re.search(r'id === "confirm".*?window\.dispatchEvent', workspace, re.S)
        self.assertIsNotNone(confirm)
        self.assertIn("saveChatMessage", confirm.group(0))
        self.assertIn("formatWorkflowResult", confirm.group(0))

    def test_status_component_hides_technical_details_in_normal_mode(self) -> None:
        status = read(WEB_CLIENT / "components" / "workflow_status.js")
        render = re.search(r"export function workflowStatusPanel\(.*?\n}\n", status, re.S)
        self.assertIsNotNone(render)
        body = render.group(0)

        for token in ["SkillRun", "TaskSpec", "pipeline_id", "raw JSON", "backend route"]:
            with self.subTest(token=token):
                self.assertNotIn(token, body)
        self.assertIn("developerMode", status)
        self.assertIn("技术详情", status)
        self.assertIn("<details", status)


if __name__ == "__main__":
    unittest.main()
