from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "web_client" / "views" / "simplified_library.js"


class LibraryArtifactUiTests(unittest.TestCase):
    def test_library_uses_registry_artifact_cards_and_category_filters(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")

        self.assertIn("getProjectArtifacts", source)
        self.assertIn("renderArtifactCard", source)
        self.assertIn("artifactCategory", source)
        self.assertIn("bindArtifactCategoryButtons(root)", source)
        for category in ["all", "uploads", "papers", "documents", "figures_tables", "ppt", "kb", "manual"]:
            with self.subTest(category=category):
                self.assertIn(f'["{category}"', source)


if __name__ == "__main__":
    unittest.main()
