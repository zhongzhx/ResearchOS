import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.memory_event import (
    create_memory_event,
    event_from_dict,
    event_to_dict,
    redact_sensitive_event_payload,
    validate_memory_event,
)


class MemoryEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_event_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_event_creation_redacts_secret_payloads(self) -> None:
        event = create_memory_event(
            event_type="user_message",
            project_id="p1",
            conversation_id="c1",
            source_type="chat",
            payload={"message": "token=abc123 and sk-test12345"},
        )

        self.assertTrue(event.contains_sensitive_data)
        self.assertIn("[REDACTED]", str(event.payload))
        self.assertNotIn("abc123", str(event.payload))
        self.assertTrue(validate_memory_event(event)["valid"])

    def test_event_serialization_round_trips(self) -> None:
        event = create_memory_event(event_type="task_created", project_id="p1", task_id="t1", source_type="task", payload={"x": 1})
        restored = event_from_dict(event_to_dict(event))

        self.assertEqual(restored.event_id, event.event_id)
        self.assertEqual(restored.task_id, "t1")

    def test_event_requires_project_or_global_scope(self) -> None:
        event = create_memory_event(event_type="assistant_message", source_type="chat", payload={"message": "hello"})
        validation = validate_memory_event(event)

        self.assertFalse(validation["valid"])
        self.assertIn("project_id", " ".join(validation["errors"]))

    def test_redact_sensitive_event_payload_mutates_safely(self) -> None:
        event = create_memory_event(event_type="user_feedback", project_id="p1", source_type="user_confirmation", payload={"password": "abc"})
        redacted = redact_sensitive_event_payload(event)

        self.assertTrue(redacted.contains_sensitive_data)
        self.assertIn("[REDACTED]", str(redacted.payload))


if __name__ == "__main__":
    unittest.main()
