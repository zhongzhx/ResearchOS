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


if __name__ == "__main__":
    unittest.main()
