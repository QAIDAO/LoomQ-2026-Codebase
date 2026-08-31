import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from loomq.hardware.errors import EvidenceError, ResultValidationError
from loomq.hardware.evidence import (
    EvidenceBundle,
    make_hardware_result,
    normalize_counts,
    record_evidence,
    redact_payload,
)


QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\n'
TIMESTAMP = "2026-08-21T12:34:56+08:00"


def _bundle():
    normalized = make_hardware_result(
        backend="originq:WK_C180_2",
        job_id="vendor-job-123",
        shots=10,
        counts={"0": 6, "1": 4},
        provider="originq",
        timestamp=TIMESTAMP,
        meta={"chip_id": "chip-1"},
    )
    return EvidenceBundle(
        provider="originq",
        input_qasm=QASM,
        submission={"backend": "WK_C180_2", "api_key": "must-not-survive"},
        raw_result={"counts": {"0": 6, "1": 4}, "token": "must-not-survive"},
        normalized_result=normalized,
        metadata={
            "execution_kind": "qpu",
            "qpu_verified": True,
            "job_id": "vendor-job-123",
            "timestamp": TIMESTAMP,
        },
    )


class CountNormalizationTests(unittest.TestCase):
    def test_accepts_exact_binary_counts(self):
        self.assertEqual(normalize_counts({"11": 3, "00": 7}, 10), {"00": 7, "11": 3})

    def test_rejects_count_sum_mismatch(self):
        with self.assertRaises(ResultValidationError):
            normalize_counts({"0": 4, "1": 5}, 10)

    def test_rejects_non_binary_and_mixed_width_keys(self):
        with self.assertRaises(ResultValidationError):
            normalize_counts({"0x0": 10}, 10)
        with self.assertRaises(ResultValidationError):
            normalize_counts({"0": 5, "11": 5}, 10)

    def test_rejects_boolean_count(self):
        with self.assertRaises(ResultValidationError):
            normalize_counts({"0": True, "1": 9}, 10)

    def test_result_requires_timezone_and_qpu_attestation(self):
        with self.assertRaises(ResultValidationError):
            make_hardware_result("x", "job", 1, {"0": 1}, "spinq", timestamp="2026-08-21T12:00:00")


class RedactionTests(unittest.TestCase):
    def test_redacts_sensitive_keys_and_values_recursively(self):
        clean = redact_payload(
            {"apiKey": "secret", "nested": [{"username": "alice"}, "prefix-secret-suffix"]},
            ("secret",),
        )
        self.assertEqual(clean["apiKey"], "[REDACTED]")
        self.assertEqual(clean["nested"][0]["username"], "[REDACTED]")
        self.assertEqual(clean["nested"][1], "prefix-[REDACTED]-suffix")


class EvidenceRecordingTests(unittest.TestCase):
    def test_commits_exact_bundle_and_hashes_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hardware"
            final = record_evidence(str(root), _bundle(), secret_values=("must-not-survive",))
            self.assertEqual(
                {path.name for path in final.iterdir()},
                {"input.qasm", "submission.json", "raw_result.json", "normalized_result.json", "metadata.json"},
            )
            self.assertFalse(any(path.name.startswith(".staging-") for path in root.iterdir()))
            all_text = "\n".join(path.read_text(encoding="utf-8") for path in final.iterdir())
            self.assertNotIn("must-not-survive", all_text)
            metadata = json.loads((final / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], "loomq.hardware.evidence/v1")
            for name, digest in metadata["artifact_sha256"].items():
                self.assertEqual(hashlib.sha256((final / name).read_bytes()).hexdigest(), digest)

    def test_does_not_create_evidence_for_unqualified_metadata(self):
        bundle = _bundle()
        invalid = EvidenceBundle(
            bundle.provider,
            bundle.input_qasm,
            bundle.submission,
            bundle.raw_result,
            bundle.normalized_result,
            {**bundle.metadata, "execution_kind": "simulator", "qpu_verified": False},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hardware"
            with self.assertRaises(EvidenceError):
                record_evidence(str(root), invalid)
            self.assertFalse(root.exists())

    def test_rejects_metadata_job_id_mismatch_before_writing(self):
        bundle = _bundle()
        invalid = EvidenceBundle(
            bundle.provider,
            bundle.input_qasm,
            bundle.submission,
            bundle.raw_result,
            bundle.normalized_result,
            {**bundle.metadata, "job_id": "different"},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hardware"
            with self.assertRaises(EvidenceError):
                record_evidence(str(root), invalid)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
