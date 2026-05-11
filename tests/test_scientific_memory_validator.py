import unittest

from backend.researchos.brain.scientific_memory_validator import (
    detect_hidden_prompt_leak,
    detect_unsourced_mechanism_claim,
    validate_memory_write,
)


class ScientificMemoryValidatorTests(unittest.TestCase):
    def test_unsourced_mechanism_claim_is_marked(self) -> None:
        result = detect_unsourced_mechanism_claim("This compound inhibits NF-kB pathway activation.", [])

        self.assertFalse(result["valid"])
        self.assertEqual(result["risk_level"], "high")

    def test_hypothesis_is_not_high_confidence_conclusion(self) -> None:
        result = validate_memory_write({"type": "claim", "text": "Hypothesis: may regulate TLR4.", "source_ids": [], "confidence": "high"})

        self.assertFalse(result["valid"])
        self.assertTrue(any("hypothesis" in issue.lower() for issue in result["issues"]))

    def test_hidden_prompt_leak_is_detected(self) -> None:
        result = detect_hidden_prompt_leak("system prompt: hidden policies and internal tool instructions")

        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
