from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from starter_kit.hardware import braket_qpu, finalize_evidence, originq_real
from starter_kit.hardware.common import BELL_QASM2, EVIDENCE_ROOT, STARTER_ROOT
from starter_kit.hardware.validate_evidence import validate_metadata


class HardwareEvidenceFixture:
    def __init__(
        self,
        provider: str,
        *,
        job_id: str | None = None,
        secret: bool = False,
        probability: bool = False,
    ):
        self.temporary = tempfile.TemporaryDirectory(prefix="TEST-FIXTURE-", dir=EVIDENCE_ROOT)
        root = Path(self.temporary.name)
        self.qasm = root / "bell.qasm"
        self.raw = root / "raw.json"
        self.normalized = root / "normalized.json"
        self.metadata = root / "metadata.json"
        self.qasm.write_text(BELL_QASM2, encoding="utf-8")
        identifier = job_id or (
            "arn:aws:braket:us-west-1:123456789012:quantum-task/01234567-89ab-cdef-0123-456789abcdef"
            if provider == "braket"
            else "A1B2C3D4E5F60718293"
        )
        device = "Rigetti Ankaa-3 QPU" if provider == "braket" else "Origin Wukong 72-qubit QPU"
        result = {
            "backend": f"{provider}_real_qpu",
            "job_id": identifier,
            "shots": 100,
            "counts": {"00": 48, "11": 52},
            "bit_order": "little",
            "timestamp": "2026-08-20T08:00:10Z",
            "meta": {"provider": provider, "device": device, "is_hardware": True, "is_mock": False},
        }
        if probability:
            result["shots"] = None
            result.pop("counts")
            result["probabilities"] = {"00": 0.48, "11": 0.52}
        raw = {"provider_response": {"status": "COMPLETED"}}
        if secret:
            raw["api_key"] = "TEST-FIXTURE-SECRET"
        self.raw.write_text(json.dumps(raw), encoding="utf-8")
        self.normalized.write_text(json.dumps(result), encoding="utf-8")
        metadata = {
            "provider": provider,
            "device": device,
            "job_id": identifier,
            "shots": 100,
            "submitted_at": "2026-08-20T08:00:00Z",
            "completed_at": "2026-08-20T08:00:10Z",
            "qasm_path": self.qasm.relative_to(STARTER_ROOT).as_posix(),
            "raw_result_path": self.raw.relative_to(STARTER_ROOT).as_posix(),
            "normalized_result_path": self.normalized.relative_to(STARTER_ROOT).as_posix(),
            "test_fixture": True,
        }
        if probability:
            metadata["shots"] = None
            metadata["result_kind"] = "probabilities"
            metadata["shots_note"] = "TEST/FIXTURE ensemble probability export has no shots"
        self.metadata.write_text(json.dumps(metadata), encoding="utf-8")

    def cleanup(self) -> None:
        self.temporary.cleanup()


class EvidenceValidatorTests(unittest.TestCase):
    def test_fixture_structure_validates_only_with_explicit_test_allowance(self):
        fixture = HardwareEvidenceFixture("originq")
        try:
            result = validate_metadata(fixture.metadata, allow_test_fixture=True)
            self.assertEqual(result["provider"], "originq")
            with self.assertRaisesRegex(ValueError, "TEST/FIXTURE"):
                validate_metadata(fixture.metadata)
        finally:
            fixture.cleanup()

    def test_rejects_secret_fields_simulators_and_placeholder_ids(self):
        secret = HardwareEvidenceFixture("braket", secret=True)
        placeholder = HardwareEvidenceFixture("originq", job_id="originq-local-fixture")
        try:
            with self.assertRaisesRegex(ValueError, "secret-like"):
                validate_metadata(secret.metadata, allow_test_fixture=True)
            with self.assertRaisesRegex(ValueError, "placeholder"):
                validate_metadata(placeholder.metadata, allow_test_fixture=True)
        finally:
            secret.cleanup()
            placeholder.cleanup()

    def test_probability_only_hardware_is_preserved_without_fabricated_shots(self):
        fixture = HardwareEvidenceFixture("spinq", probability=True)
        try:
            result = validate_metadata(fixture.metadata, allow_test_fixture=True)
            self.assertIsNone(result["shots"])
            self.assertIn("no shots", result["shots_note"])
        finally:
            fixture.cleanup()

    def test_finalizer_requires_two_distinct_providers_and_preserves_other_sections(self):
        first = HardwareEvidenceFixture("originq")
        second = HardwareEvidenceFixture("braket")
        try:
            items = [
                validate_metadata(first.metadata, allow_test_fixture=True),
                validate_metadata(second.metadata, allow_test_fixture=True),
            ]
            source = "- [ ] L1 真机\n\n## L1 真机\nold\n\n## L2 交互体验\nkeep me\n"
            rendered = finalize_evidence.render(source, items)
            self.assertIn("- [x] L1 真机", rendered)
            self.assertIn("keep me", rendered)
            self.assertIn(items[0]["job_id"], rendered)
            self.assertIn(items[1]["job_id"], rendered)
            with self.assertRaisesRegex(ValueError, "distinct"):
                finalize_evidence.render(source, [items[0], items[0]])
        finally:
            first.cleanup()
            second.cleanup()


class HardwareRunnerSafetyTests(unittest.TestCase):
    def test_dry_runs_need_no_credentials_and_create_no_evidence(self):
        before = set(EVIDENCE_ROOT.glob("*-hardware-*.json"))
        commands = (
            [sys.executable, "-m", "starter_kit.hardware.originq_real", "--dry-run"],
            [sys.executable, "-m", "starter_kit.hardware.braket_qpu", "--dry-run"],
        )
        environment = os.environ.copy()
        for name in (
            "LOOMQ_ORIGINQ_TOKEN",
            "LOOMQ_BRAKET_DEVICE_ARN",
            "LOOMQ_BRAKET_S3_BUCKET",
            "LOOMQ_BRAKET_MAX_ESTIMATED_USD",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        ):
            environment.pop(name, None)
        environment["PYTHONUTF8"] = "1"
        for command in commands:
            with self.subTest(command=command):
                completed = subprocess.run(
                    command, cwd=STARTER_ROOT.parent, text=True, capture_output=True,
                    env=environment, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("will_submit=false", completed.stdout)
        self.assertEqual(set(EVIDENCE_ROOT.glob("*-hardware-*.json")), before)

    def test_real_submission_requires_local_credentials_and_explicit_confirmation(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "TOKEN"):
            originq_real.submit(shots=10, timeout=10, poll_interval=1, confirm=True)
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "confirm-paid"):
            braket_qpu.submit(shots=10, timeout=10, poll_interval=1, confirm=False, max_estimated_usd=1.0)

    def test_sources_never_define_explicit_cloud_access_keys(self):
        sources = (Path(originq_real.__file__), Path(braket_qpu.__file__))
        for source in sources:
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("AWS_ACCESS_KEY_ID", text)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", text)
            self.assertNotIn("localStorage", text)


if __name__ == "__main__":
    unittest.main()
