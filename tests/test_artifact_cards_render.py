from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_CARD = ROOT / "web_client" / "components" / "artifact_card.js"


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class ArtifactCardsRenderTests(unittest.TestCase):
    def test_normal_card_is_readable_and_raw_json_is_developer_only(self) -> None:
        script = textwrap.dedent(
            f"""
            const {{ renderArtifactCard }} = await import({ARTIFACT_CARD.as_uri()!r});
            const artifact = {{
              artifact_id: "artifact_abc",
              source_type: "generated_figure",
              display_name: "figure.png",
              absolute_path: "C:/agent/projects/demo/artifacts/figures/figure.png",
              status: "generated",
              ingest_status: "registered",
              size_bytes: 2048,
              run_id: "run_abc",
              sha256: "secret-debug-value",
              preview_type: "figure",
            }};
            const normal = renderArtifactCard(artifact, {{ developerMode: false }});
            const developer = renderArtifactCard(artifact, {{ developerMode: true }});
            if (!normal.includes("figure.png") || !normal.includes("run_abc") || !normal.includes("2.0 KB")) throw new Error("missing readable fields");
            if (normal.includes("secret-debug-value") || normal.includes("Artifact raw record")) throw new Error("raw details leaked");
            if (!developer.includes("secret-debug-value") || !developer.includes("Artifact raw record")) throw new Error("developer raw details missing");
            console.log("ok");
            """
        )

        self.assertEqual(run_node(script), "ok")


if __name__ == "__main__":
    unittest.main()
