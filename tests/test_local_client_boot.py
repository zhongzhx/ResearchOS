import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "researchos_local_client.pyw"


def load_client_module():
    spec = importlib.util.spec_from_file_location("researchos_local_client", CLIENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load client module from {CLIENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalClientBootTests(unittest.TestCase):
    def test_client_boots_without_tcl_layout_conflict(self) -> None:
        client_module = load_client_module()

        app = client_module.ResearchOSClientApp()
        try:
            self.assertIsNotNone(app.root)
        finally:
            app.root.destroy()

    def test_default_chat_does_not_try_scaffold_dual_agent_route(self) -> None:
        client_module = load_client_module()

        app = client_module.ResearchOSClientApp()
        try:
            app.developer_mode.set(False)
            self.assertFalse(app.should_try_dual_agent_route("生成报告"))
            self.assertFalse(app.should_try_dual_agent_route("帮我采集文献"))
        finally:
            app.root.destroy()

    def test_default_client_source_does_not_call_scaffold_coordinator_route(self) -> None:
        source = CLIENT_PATH.read_text(encoding="utf-8")

        self.assertNotIn('/api/agents/coordinator/run"', source)

    def test_workbench_theme_exposes_linear_surface_tokens(self) -> None:
        client_module = load_client_module()

        self.assertEqual(client_module.WorkbenchTheme.CANVAS, "#010102")
        self.assertEqual(client_module.WorkbenchTheme.ACCENT, "#5e6ad2")
        self.assertEqual(client_module.WorkbenchTheme.PANEL_RADIUS_NOTE, "soft-16-24px")

    def test_overview_source_keeps_home_as_conversation_only(self) -> None:
        source = CLIENT_PATH.read_text(encoding="utf-8")
        overview_source = source.split("    def _build_overview", 1)[1].split("    def render_overview_task_rows", 1)[0]

        self.assertIn("home_command_entry", overview_source)
        self.assertNotIn("overview_task_rows", overview_source)
        self.assertNotIn("overview_resource_rows", overview_source)

    def test_sidebar_source_does_not_bind_hover_expansion(self) -> None:
        source = CLIENT_PATH.read_text(encoding="utf-8")
        sidebar_source = source.split("    def _build_sidebar", 1)[1].split("    def render_sidebar_nav", 1)[0]

        self.assertNotIn('bind("<Enter>", self.expand_sidebar)', sidebar_source)
        self.assertNotIn('bind("<Leave>", self.collapse_sidebar)', sidebar_source)

    def test_primary_workspace_keys_are_low_density_user_workflows(self) -> None:
        client_module = load_client_module()

        self.assertEqual(
            [key for key, _label in client_module.PRIMARY_WORKSPACES],
            ["overview", "tasks_user", "library_user", "agent", "memory"],
        )

    def test_developer_workspace_keys_are_separate_from_primary_workflows(self) -> None:
        client_module = load_client_module()

        primary_keys = {key for key, _label in client_module.PRIMARY_WORKSPACES}
        developer_keys = {key for key, _label in client_module.DEVELOPER_WORKSPACES}

        self.assertFalse(primary_keys & developer_keys)
        self.assertIn("skills", developer_keys)
        self.assertIn("api", developer_keys)


if __name__ == "__main__":
    unittest.main()
