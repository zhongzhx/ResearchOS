from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
API_JS = ROOT / "web_client" / "api.js"
CHAT_JS = ROOT / "web_client" / "views" / "chat.js"
LIBRARY_JS = ROOT / "web_client" / "views" / "library.js"
SERVER = ROOT / "backend" / "research_agent_runtime" / "scripts" / "research_agent_api.py"
DUAL_AGENT_ROUTES = ROOT / "backend" / "researchos" / "api" / "dual_agent_routes.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def exported_api_calls() -> dict[str, tuple[str, str]]:
    api_js = read(API_JS)
    pattern = re.compile(
        r"export const (?P<name>\w+)\s*=\s*(?:\([^)]*\)|\w+)?\s*=>\s*"
        r"(?P<method>apiGet|apiPost|apiPut|apiDelete)\((?:withProject\()?(?P<quote>[`\"])(?P<path>[^`\"]+)(?P=quote)",
        re.MULTILINE,
    )
    method_map = {"apiGet": "GET", "apiPost": "POST", "apiPut": "PUT", "apiDelete": "DELETE"}
    exports = {match.group("name"): (method_map[match.group("method")], match.group("path")) for match in pattern.finditer(api_js)}
    block_pattern = re.compile(
        r"export const (?P<name>\w+)\s*=\s*\([^)]*\)\s*=>\s*\{(?P<body>.*?)\n\};",
        re.MULTILINE | re.DOTALL,
    )
    call_pattern = re.compile(r"(?P<method>apiGet|apiPost|apiPut|apiDelete)\((?:withProject\()?(?P<quote>[`\"])(?P<path>[^`\"]+)(?P=quote)")
    for match in block_pattern.finditer(api_js):
        call = call_pattern.search(match.group("body"))
        if call:
            exports[match.group("name")] = (method_map[call.group("method")], call.group("path"))
    return exports


def backend_text() -> str:
    return read(SERVER) + "\n" + read(DUAL_AGENT_ROUTES)


class ApiAlignmentTests(unittest.TestCase):
    def test_actual_ui_api_calls_have_backend_handlers_or_explicit_status(self) -> None:
        exports = exported_api_calls()
        backend = backend_text()
        actual_ui_calls = {
            "sendLegacyChat",
            "runCoordinator",
            "runProductDemoFlow",
            "runProductFeatureDemo",
            "getProductFeatures",
            "getSkillCatalog",
            "getSkillPipelines",
            "routeSkillQuery",
            "getResolverHealth",
            "getLlmSettings",
            "saveLlmSettings",
            "testLlmSettings",
            "getMemoryHealth",
            "getCognitiveState",
            "getMemoryItems",
            "getMemoryEpisodes",
            "getMemoryEvents",
            "getReferences",
            "getReferenceChunks",
            "getKnowledgeBaseEntries",
            "getRagQueries",
            "getLiteratureSearchTasks",
            "getPaperRequests",
            "getUnmatchedPdfs",
        }

        missing = []
        for function_name in actual_ui_calls:
            method, path = exports[function_name]
            if "${" in path:
                base_path = path.split("${", 1)[0].rstrip("/")
                handled = base_path in backend
            else:
                handled = f'path == "{path}"' in backend or f'"{path}"' in backend
            if not handled:
                missing.append((function_name, method, path))

        self.assertEqual(missing, [])

    def test_product_demo_frontend_uses_get_demo_routes_not_post_run_routes(self) -> None:
        api_js = read(API_JS)
        chat_js = read(CHAT_JS)
        library_js = read(LIBRARY_JS)

        self.assertIn('runProductDemoFlow = (projectId) => apiGet(withProject("/api/demo/product-flow"', api_js)
        self.assertNotIn("runProductFeatureDemo", library_js)
        self.assertIn("createLiteratureSearchTask", library_js)
        self.assertIn("runLiteratureSearch", library_js)
        self.assertNotIn("/api/demo/product-flow/run", api_js + chat_js)
        self.assertNotIn("runProductFeature(", library_js)
        self.assertNotIn("/api/product/features/${encodeURIComponent(featureId)}/run", api_js)

    def test_not_connected_product_run_api_is_not_a_backend_call(self) -> None:
        api_js = read(API_JS)

        self.assertIn("notConnected(", api_js)
        self.assertIn("runProductFeature = (featureId", api_js)
        self.assertIn('status: "not_connected"', api_js)
        self.assertNotIn("apiPost(`/api/product/features/${encodeURIComponent(featureId)}/run`", api_js)

    def test_default_chat_uses_legacy_chat_and_coordinator_is_experimental_only(self) -> None:
        chat_js = read(CHAT_JS)

        self.assertIn("async function sendStableChat", chat_js)
        self.assertIn("sendLegacyChat(prompt", chat_js)
        self.assertIn("if (appState.dualAgentEnabled)", chat_js)
        self.assertIn("await sendCoordinatorChat(prompt)", chat_js)
        stable_block = re.search(r"async function sendStableChat\(prompt\) \{(?P<body>.*?)\n\}", chat_js, re.DOTALL)
        self.assertIsNotNone(stable_block)
        self.assertNotIn("runCoordinator", stable_block.group("body"))

    def test_api_alignment_document_uses_allowed_status_values(self) -> None:
        document = read(ROOT / "API_ALIGNMENT.md")
        allowed = {"implemented", "missing", "method_mismatch", "demo_only", "not_connected", "legacy_stable", "experimental"}
        statuses = set(re.findall(r"\|\s*(implemented|missing|method_mismatch|demo_only|not_connected|legacy_stable|experimental)\s*\|", document))

        self.assertTrue(statuses)
        self.assertLessEqual(statuses, allowed)
        self.assertIn("POST /research-os/agent/chat", document)
        self.assertIn("GET /api/demo/product-flow", document)
        self.assertIn("POST /api/product/features/{id}/run", document)


if __name__ == "__main__":
    unittest.main()
