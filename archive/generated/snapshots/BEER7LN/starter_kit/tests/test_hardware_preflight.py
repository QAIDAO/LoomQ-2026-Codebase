"""Tests for the local-only real-hardware preparation helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.hardware import (  # noqa: E402
    assert_no_secret_values,
    extract_originq_counts,
    extract_spinq_counts,
    load_env_file,
    positive_int,
    prepare_spinq_cloud_qasm,
    redact_text,
    require_config,
    top_k_states,
)


class HardwarePreflightTests(unittest.TestCase):
    def test_load_env_file_supports_comments_quotes_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\nA=one\nexport B=\"two words\"\nC='three'\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_env_file(path),
                {"A": "one", "B": "two words", "C": "three"},
            )

    def test_require_config_reports_names_without_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "B, C"):
            require_config({"A": "configured", "B": ""}, ("A", "B", "C"))

    def test_positive_int_rejects_invalid_shots(self) -> None:
        self.assertEqual(positive_int("1024", "shots"), 1024)
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_int(value, "shots")

    def test_prepare_spinq_cloud_qasm_removes_measurements(self) -> None:
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""
        rendered = prepare_spinq_cloud_qasm(qasm)
        self.assertIn("h q[0];", rendered)
        self.assertIn("cx q[0], q[1];", rendered)
        self.assertNotIn("measure", rendered.lower())

    def test_secret_detection_and_redaction(self) -> None:
        config = {"TOKEN": "secret-value"}
        with self.assertRaisesRegex(ValueError, "sensitive configuration"):
            assert_no_secret_values("payload secret-value", config, ("TOKEN",))
        self.assertEqual(
            redact_text("failed for secret-value", config, ("TOKEN",)),
            "failed for <redacted>",
        )

    def test_extract_spinq_counts_and_bell_top_k(self) -> None:
        payload = {
            "run": {
                "count": {"00": 500, "01": 8, "10": 6, "11": 510},
            }
        }
        counts = extract_spinq_counts(payload, shots=1024, width=2)
        self.assertEqual(sum(counts.values()), 1024)
        self.assertEqual(set(top_k_states(counts, 2)), {"00", "11"})

    def test_extract_spinq_counts_can_derive_from_probabilities(self) -> None:
        payload = {"run": {"module": {"00": 0.49, "11": 0.51}}}
        counts = extract_spinq_counts(payload, shots=1024, width=2)
        self.assertEqual(sum(counts.values()), 1024)
        self.assertEqual(set(top_k_states(counts, 2)), {"00", "11"})

    def test_extract_originq_counts_from_probabilities(self) -> None:
        counts = extract_originq_counts(
            {"00": 0.48, "0x1": 0.02, "10": 0.01, "11": 0.49},
            shots=100,
            width=2,
        )
        self.assertEqual(counts, {"00": 48, "01": 2, "10": 1, "11": 49})
        self.assertEqual(sum(counts.values()), 100)

    def test_extract_originq_counts_rejects_invalid_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid bitstring"):
            extract_originq_counts({"012": 1.0}, shots=10, width=2)


if __name__ == "__main__":
    unittest.main()
