from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class WorkflowArtifactTests(unittest.TestCase):
    def test_artifact_types_define_user_visible_research_outputs(self) -> None:
        source = read(WEB_CLIENT / "artifact_types.js")
        required = [
            "literature_table",
            "manual_download_queue",
            "paper_reading_markdown",
            "journal_club_ppt",
            "publication_figure",
            "polished_text",
            "citation_pack",
            "sop_document",
            "experiment_design_plan",
            "data_analysis_report",
            "reviewer_response_letter",
            "weekly_report_document",
        ]
        for artifact_type in required:
            with self.subTest(artifact_type=artifact_type):
                self.assertIn(artifact_type, source)

    def test_every_user_workflow_definition_has_output_artifacts(self) -> None:
        script = textwrap.dedent(
            f"""
            const {{ WORKFLOW_DEFINITIONS }} = await import({(WEB_CLIENT / "user_workflows.js").as_uri()!r});
            const missing = Object.entries(WORKFLOW_DEFINITIONS)
              .filter(([, definition]) => !Array.isArray(definition.output_artifacts) || definition.output_artifacts.length === 0)
              .map(([intent]) => intent);
            if (missing.length) throw new Error(`missing output_artifacts: ${{missing.join(",")}}`);
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_required_workflow_to_artifact_mapping(self) -> None:
        script = textwrap.dedent(
            f"""
            const {{ WORKFLOW_DEFINITIONS }} = await import({(WEB_CLIENT / "user_workflows.js").as_uri()!r});
            const expected = {{
              literature_search: ["literature_table"],
              literature_harvest_and_kb: ["literature_table", "manual_download_queue"],
              paper_reader: ["paper_reading_markdown"],
              paper_to_ppt: ["journal_club_ppt"],
              figure_generation: ["publication_figure"],
              english_polishing: ["polished_text"],
              citation_finder: ["citation_pack"],
              protocol_to_sop: ["sop_document"],
              experiment_design: ["experiment_design_plan"],
              table_analysis: ["data_analysis_report"],
              reviewer_response: ["reviewer_response_letter"],
              weekly_report: ["weekly_report_document"],
            }};
            for (const [intent, artifactTypes] of Object.entries(expected)) {{
              const actual = WORKFLOW_DEFINITIONS[intent]?.output_artifacts || [];
              for (const artifactType of artifactTypes) {{
                if (!actual.includes(artifactType)) {{
                  throw new Error(`${{intent}} missing ${{artifactType}} in ${{JSON.stringify(actual)}}`);
                }}
              }}
            }}
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_workflow_result_hides_raw_json_and_marks_plan_only_as_draft(self) -> None:
        source = read(WEB_CLIENT / "components" / "workflow_result.js")
        self.assertIn("renderWorkflowResult", source)
        for forbidden in ["Raw JSON", "raw JSON", "TaskSpec", "SkillRun", "Execution Memory"]:
            self.assertNotIn(forbidden, source)

        script = textwrap.dedent(
            f"""
            const {{ renderWorkflowResult }} = await import({(WEB_CLIENT / "components" / "workflow_result.js").as_uri()!r});
            const html = renderWorkflowResult({{
              title: "Plan",
              status: "plan_only",
              artifacts: [{{
                artifact_id: "a1",
                project_id: "project-a",
                artifact_type: "paper_reading_markdown",
                title: "Reading plan",
                content: "draft",
                created_at: "2026-05-20T00:00:00.000Z",
                status: "plan_only",
                downloadable: true,
              }}],
            }}, {{ projectId: "project-a" }});
            if (!html.includes("计划草稿")) throw new Error(html);
            if (html.includes("已生成文件")) throw new Error(html);
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_artifact_storage_is_project_scoped(self) -> None:
        script = textwrap.dedent(
            f"""
            const store = new Map();
            globalThis.localStorage = {{
              getItem: (key) => store.has(key) ? store.get(key) : null,
              setItem: (key, value) => store.set(key, value),
              removeItem: (key) => store.delete(key),
            }};
            const {{ saveArtifactToProject, listProjectArtifacts }} = await import({(WEB_CLIENT / "artifact_types.js").as_uri()!r});
            saveArtifactToProject("project-a", {{
              artifact_type: "paper_reading_markdown",
              title: "A paper",
              content: "A content",
              workflow_id: "paper_reader",
            }});
            saveArtifactToProject("project-b", {{
              artifact_type: "publication_figure",
              title: "B figure",
              content: "<svg></svg>",
              workflow_id: "figure_generation",
            }});
            const a = listProjectArtifacts("project-a");
            const b = listProjectArtifacts("project-b");
            if (a.length !== 1 || b.length !== 1) throw new Error(`${{a.length}}/${{b.length}}`);
            if (a[0].project_id !== "project-a" || b[0].project_id !== "project-b") throw new Error("wrong project id");
            if (a.some((item) => item.title === "B figure")) throw new Error("project bleed");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")


if __name__ == "__main__":
    unittest.main()
