import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skills" / "researchos_skill_library"


class SkillFolderLayoutTests(unittest.TestCase):
    def test_four_canonical_skill_categories_exist(self) -> None:
        expected = [
            "01_core_runtime_memory",
            "02_literature_browser_ingestion",
            "03_research_design_protocol",
            "04_data_analysis_writing_review",
        ]

        for name in expected:
            self.assertTrue((LIBRARY / name).is_dir(), name)

    def test_each_listed_canonical_skill_has_skill_md(self) -> None:
        expected_paths = [
            "01_core_runtime_memory/manage-agent-memory/SKILL.md",
            "01_core_runtime_memory/ingest-research-evidence/SKILL.md",
            "01_core_runtime_memory/build-user-research-kb/SKILL.md",
            "02_literature_browser_ingestion/keyword-research-harvest/SKILL.md",
            "02_literature_browser_ingestion/compliant-literature-access/SKILL.md",
            "02_literature_browser_ingestion/extract-first-article-keywords/SKILL.md",
            "02_literature_browser_ingestion/browser-research-learning/SKILL.md",
            "03_research_design_protocol/plan-research-route/SKILL.md",
            "03_research_design_protocol/extract-domain-entities/SKILL.md",
            "03_research_design_protocol/protocol-extraction/SKILL.md",
            "03_research_design_protocol/sop-generation/SKILL.md",
            "03_research_design_protocol/design-experiment-matrix/SKILL.md",
            "04_data_analysis_writing_review/parse-scientific-data/SKILL.md",
            "04_data_analysis_writing_review/analyze-experiment-results/SKILL.md",
            "04_data_analysis_writing_review/result-narrative/SKILL.md",
            "04_data_analysis_writing_review/peer-review-simulation/SKILL.md",
            "04_data_analysis_writing_review/diagnose-research-bottleneck/SKILL.md",
            "04_data_analysis_writing_review/failure-log/SKILL.md",
            "04_data_analysis_writing_review/weekly-research-report/SKILL.md",
            "04_data_analysis_writing_review/weekly-research-digest/SKILL.md",
        ]

        for relative in expected_paths:
            self.assertTrue((LIBRARY / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
