import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"
PACKAGE_JSON = ROOT / "package.json"
ELECTRON_MAIN = ROOT / "electron" / "main.js"
CHECK_SCRIPT = ROOT / "scripts" / "check_web_client.py"
VIEW_FILES = [
    "chat.js",
    "task_lifecycle.js",
    "brain.js",
    "library.js",
    "skills.js",
    "runs.js",
    "settings.js",
]
COMPONENT_FILES = [
    "message.js",
    "cards.js",
    "details.js",
    "status_pill.js",
    "empty_state.js",
    "project_switcher.js",
    "json_viewer.js",
]
LEGACY_CLIENT_FILES = [
    ROOT / "researchos_local_client.pyw",
    ROOT / "researchos_web_client.py",
    ROOT / "tests" / "test_local_client_boot.py",
    ROOT / "tests" / "test_researchos_local_client_project_actions.py",
]


class ResearchOSWebClientTests(unittest.TestCase):
    def test_web_client_assets_exist(self) -> None:
        self.assertTrue((WEB_CLIENT / "index.html").exists())
        self.assertTrue((WEB_CLIENT / "styles.css").exists())
        self.assertTrue((WEB_CLIENT / "app.js").exists())
        self.assertTrue((WEB_CLIENT / "api.js").exists())
        self.assertTrue((WEB_CLIENT / "state.js").exists())
        for name in VIEW_FILES:
            self.assertTrue((WEB_CLIENT / "views" / name).exists(), name)
        for name in COMPONENT_FILES:
            self.assertTrue((WEB_CLIENT / "components" / name).exists(), name)
        self.assertTrue(CHECK_SCRIPT.exists())

    def test_shell_is_modular_conversation_first_html(self) -> None:
        html = (WEB_CLIENT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="viewRoot"', html)
        self.assertIn('type="module"', html)
        self.assertIn('data-view-target="chat"', html)
        self.assertNotIn("overview-grid", html)
        self.assertNotIn("dashboard-card", html)

    def test_css_uses_light_soft_html_surfaces(self) -> None:
        css = (WEB_CLIENT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("color-scheme: light", css)
        self.assertIn("--radius-lg: 28px", css)
        self.assertIn("--radius-md: 20px", css)
        self.assertIn("#f7f8fa", css)
        self.assertNotIn("border-radius: 0", css)

    def test_app_js_is_shell_not_api_dump(self) -> None:
        source = (WEB_CLIENT / "app.js").read_text(encoding="utf-8")

        self.assertIn("./api.js", source)
        self.assertIn("./state.js", source)
        self.assertNotIn("fetch(", source)

    def test_api_client_exposes_required_business_functions(self) -> None:
        source = (WEB_CLIENT / "api.js").read_text(encoding="utf-8")
        required = [
            "apiGet",
            "apiPost",
            "getHealth",
            "getProjects",
            "getTasks",
            "getReferences",
            "getMemoryContext",
            "sendLegacyChat",
            "runCoordinator",
            "runDualAgentDemo",
            "getSkillCatalog",
            "getSkillPipelines",
            "routeSkillQuery",
            "getResolverHealth",
            "getPendingSkills",
            "activatePendingSkill",
            "rejectPendingSkill",
            "getSkillRuns",
            "getExecutionMemory",
            "getClaims",
            "getDecisions",
            "getFailures",
            "getProtocols",
            "getReports",
            "getRelationships",
            "getFiles",
            "getEvidenceReview",
            "getClaimReview",
            "getRuntimeStatus",
            "getSchedulerStatus",
        ]
        for name in required:
            with self.subTest(name=name):
                self.assertIn(name, source)

    def test_api_client_exposes_legacy_runtime_capabilities(self) -> None:
        source = (WEB_CLIENT / "api.js").read_text(encoding="utf-8")
        required = [
            "apiPut",
            "apiDelete",
            "getDashboard",
            "createProject",
            "updateProject",
            "archiveProject",
            "unarchiveProject",
            "clearProject",
            "purgeProject",
            "createTask",
            "runTask",
            "cancelTask",
            "parseNaturalLanguageTask",
            "createTaskFromNaturalLanguage",
            "agentHeartbeat",
            "watchProject",
            "runScheduler",
            "acceptAgentFeedItem",
            "dismissAgentFeedItem",
            "getLegacySkills",
            "upsertLegacySkill",
            "runLegacySkill",
            "simulatePromptRouting",
            "promoteExecutionMemory",
            "createLiteratureSearchTask",
            "cancelLiteratureSearchTask",
            "expandLiteratureQuery",
            "mineLiteratureKeywords",
            "runLiteratureSearch",
            "createPaperRequest",
            "generatePaperRequests",
            "processPaperRequestWatchFolder",
            "upsertReference",
            "tagReference",
            "noteReference",
            "markReferenceImportant",
            "excludeReference",
            "linkReference",
            "buildKnowledgeBase",
            "queryResearchOsRag",
            "queryResearchContext",
            "searchResearchOsMemory",
            "mergeResearchOsMemory",
            "extractExperimentMemory",
            "submitUserCorrection",
            "registerFile",
            "runExtraction",
            "parseProtocolText",
            "storeProtocol",
            "generateExecutionPackage",
            "runCalculator",
            "createWorkflow",
            "runWorkflow",
            "approveWorkflowStep",
            "detectConflicts",
            "createReport",
            "extractReportClaims",
            "createClaim",
            "confirmClaim",
            "rejectClaim",
            "requestMoreClaimEvidence",
            "linkClaimEvidence",
            "unlinkClaimEvidence",
            "supersedeClaim",
            "queryRelationships",
            "validateResearchOsPayload",
            "createClaimReferenceLink",
            "writeConclusion",
            "writeDecision",
            "writeFailureLog",
            "writeFailure",
            "ingestExperimentLog",
            "generateRetrospective",
            "assistWriting",
            "upsertWeeklyDigestConfig",
            "generateWeeklyDigest",
            "upsertAgentMemory",
            "parseKitTemplate",
            "createMemory",
            "retrieveMemory",
            "buildMemoryContext",
            "consolidateMemory",
            "extractMemory",
            "archiveMemory",
            "createMemoryProject",
            "updateMemoryProject",
            "createResearchInterest",
            "updateResearchInterest",
            "deleteResearchInterest",
            "createFailureRecord",
            "updateFailureRecord",
            "deleteFailureRecord",
            "matchFailureRecords",
            "extractProtocol",
            "generateSop",
            "runPeerReview",
            "parseScientificData",
            "generateResultNarrative",
            "ingestRagDocument",
            "ingestRagPdfs",
            "queryLegacyRag",
            "createSearchJob",
            "queryKnowledgeBase",
            "sendFeedback",
            "getArticles",
            "getArticle",
            "getBrowserLearning",
        ]
        for name in required:
            with self.subTest(name=name):
                self.assertIn(name, source)

    def test_electron_package_declares_desktop_client_entry(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

        self.assertEqual(package["main"], "electron/main.js")
        self.assertEqual(package["scripts"]["client:electron"], "electron .")
        self.assertEqual(package["scripts"]["client:electron:smoke"], "electron . --smoke-test")
        self.assertEqual(package["scripts"]["client:check"], "py scripts/check_web_client.py")
        self.assertNotIn("client:web", package["scripts"])
        self.assertIn("electron", package["devDependencies"])

    def test_electron_main_loads_html_client_without_tk_shell(self) -> None:
        source = ELECTRON_MAIN.read_text(encoding="utf-8")

        self.assertIn("BrowserWindow", source)
        self.assertIn("web_client", source)
        self.assertIn("api/backend", source)
        self.assertIn("nodeIntegration: false", source)
        self.assertIn("--smoke-test", source)
        self.assertIn('themeSource = "light"', source)
        self.assertNotIn("tkinter", source.lower())

    def test_legacy_python_clients_are_removed(self) -> None:
        for path in LEGACY_CLIENT_FILES:
            with self.subTest(path=path.name):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
