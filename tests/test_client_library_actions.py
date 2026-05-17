from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_JS = ROOT / "web_client" / "views" / "library.js"
API_JS = ROOT / "web_client" / "api.js"


class ClientLibraryActionsTests(unittest.TestCase):
    def test_library_uses_stable_literature_kb_and_rag_apis(self) -> None:
        source = LIBRARY_JS.read_text(encoding="utf-8")

        for name in [
            "createLiteratureSearchTask",
            "expandLiteratureQuery",
            "mineLiteratureKeywords",
            "runLiteratureSearch",
            "createPaperRequest",
            "generatePaperRequests",
            "processPaperRequestWatchFolder",
            "buildKnowledgeBase",
            "queryResearchOsRag",
        ]:
            self.assertIn(name, source)

        self.assertNotIn("runProductFeatureDemo", source)
        self.assertNotIn("demo_only 预览", source)

    def test_library_mutations_refresh_corresponding_lists_and_show_real_status(self) -> None:
        source = LIBRARY_JS.read_text(encoding="utf-8")

        for button_id in [
            "createLiteratureTask",
            "expandLiteratureQuery",
            "runLiteratureSearch",
            "generatePaperRequests",
            "processWatchFolder",
            "buildKnowledgeBase",
            "queryRag",
        ]:
            self.assertIn(button_id, source)

        self.assertIn("libraryActionStatus", source)
        self.assertIn("not_connected", source)
        self.assertIn("async function runLibraryAction", source)
        self.assertIn("await renderLibraryView({ root })", source)
        self.assertGreaterEqual(source.count("await runLibraryAction"), 8)

    def test_api_exposes_legacy_stable_literature_and_rag_actions(self) -> None:
        api = API_JS.read_text(encoding="utf-8")

        for endpoint in [
            "/research-os/literature/search-tasks",
            "/research-os/literature/expand-query",
            "/research-os/literature/keyword-mine",
            "/research-os/literature/search",
            "/research-os/literature/paper-requests/generate",
            "/research-os/literature/paper-requests/process-watch-folder",
            "/research-os/knowledge-base/build",
            "/research-os/rag/query",
        ]:
            self.assertIn(endpoint, api)


if __name__ == "__main__":
    unittest.main()
