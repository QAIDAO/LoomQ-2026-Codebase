"""Security and atomicity checks for the UI evidence workspace."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from loomq.ui.workspace import (
    WorkspaceError,
    WorkspaceSession,
    redact_text,
    redact_value,
)


class WorkspaceSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.session = WorkspaceSession(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_uuid_children_atomic_writes_manifest_and_history(self) -> None:
        run = self.session.begin_request()
        self.assertRegex(run.run_id, r"^[0-9a-f]{32}$")
        self.assertEqual(run.path.parent, self.session.path)
        record = run.write_json("nested/request.json", {"qasm": "OPENQASM 2.0;"})
        self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue((run.path / "nested" / "request.json").is_file())
        self.assertFalse(list(run.path.rglob("*.tmp")))

        manifest = run.finalize("completed", {"task": "transpile"})
        self.assertTrue((run.path / "manifest.json").is_file())
        self.assertIn("manifest.json", {item["name"] for item in manifest["artifacts"]})
        history = self.session.history()
        self.assertEqual(history[0]["run_id"], run.run_id)
        self.assertEqual(history[0]["status"], "completed")

        payload, media_type = self.session.artifact(run.run_id, "nested/request.json")
        self.assertEqual(json.loads(payload)["qasm"], "OPENQASM 2.0;")
        self.assertIn("application/json", media_type)

    def test_path_traversal_and_unlisted_artifacts_are_rejected(self) -> None:
        run = self.session.begin_request()
        with self.assertRaisesRegex(WorkspaceError, "traversal"):
            run.write_text("../outside.txt", "no")
        with self.assertRaises(WorkspaceError):
            run.write_text(str(self.base / "outside.txt"), "no")
        run.write_text("safe.txt", "yes")
        run.finalize("completed", {"task": "test"})
        with self.assertRaisesRegex(WorkspaceError, "not listed"):
            self.session.artifact(run.run_id, "unknown.txt")
        self.assertFalse((self.base / "outside.txt").exists())

    def test_credentials_are_redacted_before_persistence(self) -> None:
        source_secret = "fixture-secret-abcdefghijklmnopqrstuvwxyz"
        self.assertNotIn(source_secret, redact_text("token=" + source_secret))
        redacted = redact_value(
            {
                "api_key": source_secret,
                "nested": {"Authorization": "Bearer abcdefghijklmnop"},
                "prompt": "token=very-secret-value",
            }
        )
        rendered = json.dumps(redacted)
        self.assertNotIn(source_secret, rendered)
        self.assertNotIn("abcdefghijklmnop", rendered)
        self.assertNotIn("very-secret-value", rendered)
        self.assertGreaterEqual(rendered.count("[REDACTED]"), 3)


if __name__ == "__main__":
    unittest.main()
