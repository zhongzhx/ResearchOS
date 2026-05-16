import json
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_LIBRARY = ROOT / "skills" / "researchos_skill_library"
BACKEND_PROMPTS = ROOT / "backend" / "research_agent_runtime" / "prompts"
LEGACY_RUNTIME = SKILL_LIBRARY / "01_core_runtime_memory" / "research-agent-runtime"
GLOBAL_SYSTEM_PROMPT = "researchos_agent_system_prompt.md"


class DirectoryBoundaryTests(unittest.TestCase):
    def _skill_library_text_files(self) -> list[Path]:
        return [
            path
            for path in SKILL_LIBRARY.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml", ".toml"}
        ]

    def test_skill_library_does_not_contain_backend_server_entrypoints(self) -> None:
        forbidden_names = {"research_agent_api.py", "research_os_mvp.py"}

        found = [path for path in SKILL_LIBRARY.rglob("*") if path.is_file() and path.name in forbidden_names]

        self.assertEqual(found, [])

    def test_skill_library_does_not_contain_http_server_runtime_code(self) -> None:
        forbidden_markers = ["ThreadingHTTPServer", "BaseHTTPRequestHandler", "FastAPI("]
        violations: list[str] = []

        for path in self._skill_library_text_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden_markers:
                if marker in text:
                    violations.append(f"{path.relative_to(ROOT)} contains {marker}")

        self.assertEqual(violations, [])

    def test_skill_library_does_not_contain_active_global_system_prompt(self) -> None:
        violations: list[str] = []

        for path in SKILL_LIBRARY.rglob(GLOBAL_SYSTEM_PROMPT):
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            if "deprecated compatibility copy" not in text:
                violations.append(str(path.relative_to(ROOT)))

        self.assertEqual(violations, [])

    def test_skill_catalog_does_not_register_global_runtime(self) -> None:
        catalog = json.loads((SKILL_LIBRARY / "skill_catalog.json").read_text(encoding="utf-8-sig"))
        skill_ids = {str(item.get("skill_id") or "") for item in catalog.get("skills", [])}

        self.assertNotIn("research-agent-runtime", skill_ids)

    def test_skill_resolver_does_not_resolve_global_runtime_as_skill(self) -> None:
        from backend.researchos.skills.skill_catalog_loader import get_skill_by_id, list_active_skills, resolve_skill_path

        with self.assertRaises(KeyError):
            get_skill_by_id("research-agent-runtime")

        self.assertFalse(any(row.get("skill_id") == "research-agent-runtime" for row in list_active_skills()))
        self.assertNotIn("research-agent-runtime", resolve_skill_path("default chat"))

    def test_backend_prompt_directory_contains_global_system_prompt(self) -> None:
        self.assertTrue((BACKEND_PROMPTS / GLOBAL_SYSTEM_PROMPT).exists())
        self.assertTrue((BACKEND_PROMPTS / "zh").is_dir())

    def test_prompt_loader_defaults_to_backend_prompt_directory(self) -> None:
        from backend.research_agent_runtime.scripts import runtime_paths
        from backend.researchos.prompts.mvp_prompt_adapter import locate_mvp_prompt_sources

        self.assertEqual(runtime_paths.prompt_root(), BACKEND_PROMPTS)
        sources = locate_mvp_prompt_sources(ROOT)
        self.assertEqual(Path(sources["prompt_root"]), BACKEND_PROMPTS)
        self.assertNotIn("skills/researchos_skill_library", sources["prompt_root"].replace("\\", "/"))

    def test_prompt_loader_falls_back_to_deprecated_legacy_prompt_directory(self) -> None:
        from backend.research_agent_runtime.scripts import runtime_paths

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            legacy_prompt_dir = fake_root / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "prompts"
            legacy_prompt_dir.mkdir(parents=True)
            shutil.copy2(BACKEND_PROMPTS / GLOBAL_SYSTEM_PROMPT, legacy_prompt_dir / GLOBAL_SYSTEM_PROMPT)

            with patch.object(runtime_paths, "repo_root", return_value=fake_root), warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                resolved = runtime_paths.prompt_root()

        self.assertEqual(resolved, legacy_prompt_dir)
        self.assertTrue(any("deprecated" in str(item.message).casefold() for item in captured))


if __name__ == "__main__":
    unittest.main()
