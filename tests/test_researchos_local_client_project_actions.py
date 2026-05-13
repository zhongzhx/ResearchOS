import importlib.machinery
import importlib.util
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "researchos_local_client.pyw"


def load_client_module():
    loader = importlib.machinery.SourceFileLoader("researchos_local_client_under_test", str(CLIENT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def load_module_from_path(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class FakeApi:
    def __init__(self, responses: list[tuple[int, dict]]) -> None:
        self.responses = list(responses)
        self.posts: list[tuple[str, dict, int]] = []

    def post(self, path: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
        self.posts.append((path, payload or {}, timeout))
        return self.responses.pop(0)


class LocalClientProjectActionTests(unittest.TestCase):
    def make_app(self, client, api: FakeApi):
        app = object.__new__(client.ResearchOSClientApp)
        app.api = api
        app.status_text = FakeStatus()
        app.client_cache = {"last_project_id": "project id/with space"}
        app.saved_cache = False
        app.default_project_id = lambda: "project id/with space"
        app._show_error = lambda message: (_ for _ in ()).throw(AssertionError(message))
        app._deletion_plan_text = lambda plan: f"plan for {plan.get('scope')}"
        app.load_workspace_summary_called = 0
        app.load_projects_called = 0
        app.show_view_called = ""
        app.load_workspace_summary = lambda: setattr(app, "load_workspace_summary_called", app.load_workspace_summary_called + 1)
        app.load_projects = lambda: setattr(app, "load_projects_called", app.load_projects_called + 1)
        app.show_view = lambda name: setattr(app, "show_view_called", name)
        app.save_client_cache = lambda: setattr(app, "saved_cache", True)
        app.run_async = lambda func, on_success=None, on_error=None: on_success(func()) if on_success else func()
        return app

    def test_api_script_resolves_to_existing_runtime_script(self) -> None:
        client = load_client_module()

        self.assertTrue(client.API_SCRIPT.exists(), client.API_SCRIPT)

    def test_api_module_resolves_workspace_root_from_canonical_skill_location(self) -> None:
        client = load_client_module()
        scripts_dir = client.API_SCRIPT.parent
        import sys

        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        api = load_module_from_path("research_agent_api_under_test", client.API_SCRIPT)

        self.assertEqual(api.workspace_root, ROOT)

    def test_run_async_reports_worker_exception_to_error_handler(self) -> None:
        client = load_client_module()
        app = object.__new__(client.ResearchOSClientApp)
        callbacks = []
        errors = []

        class FakeRoot:
            def after(self, _delay, callback):
                callbacks.append(callback)

        app.root = FakeRoot()

        def fail():
            raise RuntimeError("worker boom")

        app.run_async(fail, on_error=errors.append)
        deadline = time.time() + 2
        while not callbacks and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(callbacks)

        callbacks[0]()

        self.assertEqual(errors, ["worker boom"])

    def test_render_projects_clears_stale_deleted_project_cache_when_no_projects_remain(self) -> None:
        client = load_client_module()
        app = object.__new__(client.ResearchOSClientApp)
        app.client_cache = {"last_project_id": "deleted-project"}
        app.saved_cache = False
        app.status_text = FakeStatus()
        app.project_cache = []
        app.project_label_to_id = {}
        app.project_id_to_label = {}
        app._project_syncing = False
        app.is_client_hidden = lambda *_args: False
        app.save_client_cache = lambda: setattr(app, "saved_cache", True)
        for name in [
            "project_choice",
            "lit_project",
            "file_project",
            "data_project",
            "exp_project",
            "sample_project",
            "memory_project",
            "rag_project",
            "skill_project",
            "agent_project",
            "task_project",
        ]:
            setattr(app, name, FakeVar("deleted-project"))

        client.ResearchOSClientApp.render_projects(app, [])

        self.assertEqual(app.client_cache["last_project_id"], "")
        self.assertTrue(app.saved_cache)
        self.assertEqual(app.project_choice.get(), "")

    def test_clear_workspace_memory_posts_memory_scope_after_confirmation(self) -> None:
        client = load_client_module()
        phrase = "确认清空 Project Ops Demo"
        api = FakeApi(
            [
                (200, {"deletion_plan": {"scope": "memory", "confirmation_phrase": phrase}}),
                (200, {"ok": True, "executed": True}),
            ]
        )
        app = self.make_app(client, api)
        prompts = []

        with patch.object(client.messagebox, "askyesno", side_effect=lambda title, message: prompts.append(message) or True), patch.object(client.simpledialog, "askstring", return_value="确定"):
            app.clear_workspace_memory()

        self.assertEqual(
            api.posts,
            [
                ("/research-os/projects/project%20id%2Fwith%20space/clear", {"scope": "memory", "dry_run": True}, 60),
                ("/research-os/projects/project%20id%2Fwith%20space/clear", {"scope": "memory", "confirmation": phrase}, 120),
            ],
        )
        self.assertIn("输入：确定", prompts[0])
        self.assertNotIn(phrase, prompts[0])
        self.assertEqual(app.status_text.value, "项目记忆已清空")
        self.assertEqual(app.load_workspace_summary_called, 1)

    def test_delete_workspace_project_accepts_short_confirmation_and_posts_backend_phrase(self) -> None:
        client = load_client_module()
        phrase = "CONFIRM PURGE Backend Planned Project"
        api = FakeApi(
            [
                (
                    200,
                    {
                        "deletion_plan": {
                            "scope": "purge",
                            "confirmation_phrase": phrase,
                            "project": {"display_name": "Different Project"},
                        }
                    },
                ),
                (200, {"ok": True, "executed": True}),
            ]
        )
        app = self.make_app(client, api)
        prompts = []

        with patch.object(client.messagebox, "askyesno", side_effect=lambda title, message: prompts.append(message) or True), patch.object(client.simpledialog, "askstring", return_value="确定"):
            app.delete_workspace_project()

        self.assertEqual(api.posts[-1], ("/research-os/projects/project%20id%2Fwith%20space/purge", {"confirmation": phrase}, 120))
        self.assertIn("输入：确定", prompts[0])
        self.assertNotIn(phrase, prompts[0])
        self.assertEqual(app.status_text.value, "项目已彻底删除")
        self.assertEqual(app.client_cache["last_project_id"], "")
        self.assertTrue(app.saved_cache)
        self.assertEqual(app.load_projects_called, 1)
        self.assertEqual(app.show_view_called, "overview")


if __name__ == "__main__":
    unittest.main()
