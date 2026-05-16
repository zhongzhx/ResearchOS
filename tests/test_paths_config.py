import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.config.paths import (
    ensure_runtime_dirs,
    get_agent_data_dir,
    get_generated_outputs_dir,
    get_memoryos_dir,
    get_repo_root,
    get_research_brain_dir,
    get_research_tasks_dir,
    get_runtime_dir,
)


class PathsConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_paths_"))
        self.previous = {
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "RESEARCH_BRAIN_ROOT": os.environ.get("RESEARCH_BRAIN_ROOT"),
            "RESEARCHOS_TASKS_ROOT": os.environ.get("RESEARCHOS_TASKS_ROOT"),
        }
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "brain")
        os.environ["RESEARCHOS_TASKS_ROOT"] = str(self.tmp / "tasks")

    def tearDown(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_paths_are_centralized_and_runtime_dirs_are_created(self) -> None:
        dirs = ensure_runtime_dirs()

        self.assertTrue((get_repo_root() / "backend").exists())
        self.assertEqual(get_agent_data_dir(), self.tmp / "agent_data")
        self.assertEqual(get_research_brain_dir(), self.tmp / "brain")
        self.assertEqual(get_research_tasks_dir(), self.tmp / "tasks")
        self.assertTrue(get_runtime_dir().exists())
        self.assertTrue(get_memoryos_dir().exists())
        self.assertTrue(get_generated_outputs_dir().exists())
        for path in dirs.values():
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
