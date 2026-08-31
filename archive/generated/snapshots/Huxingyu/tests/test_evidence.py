import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from starter_kit.evaluator import validate_schema


ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "starter_kit" / "evidence" / "files"
EVENT_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
EVENT_END = datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)


class HardwareEvidenceTests(unittest.TestCase):
    def load(self, name):
        return json.loads((FILES / name).read_text(encoding="utf-8"))

    def assert_traceable_bell_result(self, payload):
        valid, reason = validate_schema(payload)
        self.assertTrue(valid, reason)
        self.assertTrue(payload["job_id"])
        self.assertEqual(sum(payload["counts"].values()), payload["shots"])
        self.assertEqual(
            {state for state, _ in sorted(payload["counts"].items(), key=lambda item: -item[1])[:2]},
            {"00", "11"},
        )
        timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        self.assertLessEqual(EVENT_START, timestamp)
        self.assertLess(timestamp, EVENT_END)
        self.assertFalse(payload["meta"]["is_mock"])

    def test_two_distinct_platforms_have_valid_traceable_bell_evidence(self):
        spinq = self.load("spinq-gemini-bell-result.json")
        originq = self.load("originq-wukong-bell-result.json")
        self.assert_traceable_bell_result(spinq)
        self.assert_traceable_bell_result(originq)
        self.assertNotEqual(spinq["backend"], originq["backend"])
        self.assertIn("raw_result_api", spinq)
        self.assertIn("raw_result_file_msgpack_base64", spinq)
        self.assertIn("raw_origin_data", originq)
        self.assertEqual(originq["raw_origin_data"]["obj"]["taskId"], originq["job_id"])

    def test_submitted_circuits_match_the_claimed_bell_experiment(self):
        for name in ("spinq-gemini-bell.qasm", "originq-wukong-bell.qasm"):
            qasm = (FILES / name).read_text(encoding="utf-8").lower()
            compact = re.sub(r"\s+", "", qasm)
            self.assertIn("qregq[2];", compact)
            self.assertIn("hq[0];", compact)
            self.assertIn("cxq[0],q[1];", compact)

        # SpinQ's cloud format measures all declared qubits implicitly; OriginIR/QASM
        # records the two measurement statements explicitly.
        originq_qasm = (FILES / "originq-wukong-bell.qasm").read_text(encoding="utf-8").lower()
        self.assertEqual(originq_qasm.count("measure"), 2)
        self.assertEqual(self.load("spinq-gemini-bell-result.json")["bit_num"], 2)


if __name__ == "__main__":
    unittest.main()
