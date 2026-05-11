import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.brain.brain_page import create_brain_page
from backend.researchos.brain.evidence_manager import (
    create_evidence_item,
    find_claims_without_evidence,
    link_evidence_to_claim,
    mark_claim_as_hypothesis,
    promote_claim_confidence,
)


class EvidenceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_evidence_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evidence_can_link_to_claim(self) -> None:
        create_brain_page("claim", "claim-linked", {"title": "Claim", "project_id": "p1"}, "Hypothesis: X may affect Y.", [])
        evidence = create_evidence_item("doi:1", "paper", "X affects Y", "medium", {"doi": "10.1/a", "title": "Paper"})

        result = link_evidence_to_claim(evidence["evidence_id"], "claim-linked")

        self.assertEqual(result["claim_slug"], "claim-linked")
        self.assertEqual(result["evidence_id"], evidence["evidence_id"])

    def test_claim_without_evidence_is_found_and_can_be_hypothesis(self) -> None:
        create_brain_page("claim", "claim-no-evidence", {"title": "Claim", "project_id": "p1"}, "X activates pathway.", [])

        claims = find_claims_without_evidence("p1")
        updated = mark_claim_as_hypothesis("claim-no-evidence", "direct evidence missing")

        self.assertTrue(any(item["slug"] == "claim-no-evidence" for item in claims))
        self.assertIn("Hypothesis", updated["compiled_truth"])

    def test_promote_claim_requires_sources(self) -> None:
        create_brain_page("claim", "claim-promote", {"title": "Claim", "project_id": "p1"}, "Hypothesis: X.", [])

        with self.assertRaises(ValueError):
            promote_claim_confidence("claim-promote", "no evidence", [])


if __name__ == "__main__":
    unittest.main()
