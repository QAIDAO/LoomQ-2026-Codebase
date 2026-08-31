"""Tests for the submission-disabled QPU evidence command-line interface."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from starter_kit.hardware import run_qpu
from starter_kit.loomq_l1.errors import CredentialError
from starter_kit.loomq_l1.emitters import emit
from starter_kit.loomq_l1.parser import parse_qasm


BELL_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''

EXPECTED_ORIGIN_IR = """QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
"""


class ExplodingCredentials(dict):
    """An environment mapping that proves dry-runs do not inspect credentials."""

    def get(self, key, default=None):
        if key in run_qpu.CREDENTIAL_VARIABLES:
            raise AssertionError("dry-run read a credential")
        return super().get(key, default)


class HardwareCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.qasm_path = self.root / "bell.qasm"
        self.qasm_path.write_text(BELL_QASM, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _main(self, argv, environ=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = run_qpu.main(argv, {} if environ is None else environ)
        return result, stdout.getvalue(), stderr.getvalue()

    def _write_provider_result(self, value, name="provider-result.json"):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def _valid_result(self, provider="originq"):
        return {
            "provider": provider,
            "job_id": "job-2026-08-18",
            "timestamp": "2026-08-18T02:30:00Z",
            "shots": 8,
            "counts": {"00": 4, "11": 4},
        }

    def test_dry_run_originq_emits_the_exact_standard_originir_without_credentials(self):
        secret = ("originq-" "token-that-must-not-leak")
        code, stdout, stderr = self._main(
            [
                "--provider",
                "originq",
                "--qasm",
                str(self.qasm_path),
                "--shots",
                "8192",
                "--dry-run",
            ],
            ExplodingCredentials(ORIGINQ_API_TOKEN=secret),
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout, EXPECTED_ORIGIN_IR)
        self.assertEqual(stderr, "")
        self.assertNotIn(secret, stdout + stderr)
        self.assertEqual(emit(parse_qasm(BELL_QASM), "originq"), EXPECTED_ORIGIN_IR)

    def test_dry_run_parses_and_emits_every_supported_provider_without_credentials(self):
        for provider in ("spinq", "originq", "braket"):
            with self.subTest(provider=provider):
                code, stdout, stderr = self._main(
                    ["--provider", provider, "--qasm", str(self.qasm_path), "--dry-run"],
                    ExplodingCredentials(SPINQ_API_TOKEN="spinq-secret"),
                )
                self.assertEqual(code, 0)
                self.assertEqual(stdout, emit(parse_qasm(BELL_QASM), provider))
                self.assertEqual(stderr, "")

    def test_live_run_aborts_for_missing_credentials_before_any_sdk_or_network_call(self):
        with patch.object(run_qpu, "_live_submission", side_effect=AssertionError("called")):
            with self.assertRaises(CredentialError) as raised:
                self._main(["--provider", "originq", "--qasm", str(self.qasm_path)], {})

        self.assertNotIn("ORIGINQ_API_TOKEN", str(raised.exception))

    def test_live_run_is_intentionally_unsupported_even_when_credentials_are_present(self):
        secret = ("originq-" "token-that-must-not-leak")
        with patch.object(run_qpu, "_live_submission", side_effect=AssertionError("called")):
            with self.assertRaises(CredentialError) as raised:
                self._main(
                    ["--provider", "originq", "--qasm", str(self.qasm_path)],
                    {"ORIGINQ_API_TOKEN": secret},
                )

        self.assertNotIn(secret, str(raised.exception))

    def test_import_result_writes_only_the_four_trace_artifacts_with_consistent_base_name(self):
        result_path = self._write_provider_result(self._valid_result())
        output_directory = self.root / "evidence"

        code, stdout, stderr = self._main(
            [
                "--provider",
                "originq",
                "--qasm",
                str(self.qasm_path),
                "--import-result",
                str(result_path),
                "--output-dir",
                str(output_directory),
            ]
        )

        base = "originq-job-2026-08-18"
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(
            {path.name for path in output_directory.iterdir()},
            {
                f"{base}-submission.qasm",
                f"{base}.native.ir",
                f"{base}.raw-result.json",
                f"{base}.normalized-result.json",
            },
        )
        self.assertEqual(
            (output_directory / f"{base}-submission.qasm").read_text(encoding="utf-8"),
            BELL_QASM,
        )
        self.assertEqual(
            (output_directory / f"{base}.native.ir").read_text(encoding="utf-8"),
            EXPECTED_ORIGIN_IR,
        )
        self.assertEqual(
            json.loads((output_directory / f"{base}.raw-result.json").read_text(encoding="utf-8")),
            self._valid_result(),
        )
        normalized = json.loads(
            (output_directory / f"{base}.normalized-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(normalized["job_id"], "job-2026-08-18")
        self.assertEqual(normalized["shots"], 8)
        self.assertEqual(normalized["counts"], {"00": 4, "11": 4})
        self.assertEqual(normalized["timestamp"], "2026-08-18T02:30:00+00:00")

    def test_import_result_rejects_malformed_provider_evidence(self):
        malformed = (
            {**self._valid_result(), "provider": "unsupported"},
            {**self._valid_result(), "job_id": ""},
            {**self._valid_result(), "job_id": "../../outside"},
            {**self._valid_result(), "timestamp": "2026-08-18T02:30:00"},
            {**self._valid_result(), "timestamp": "2026-08-18T02:30:00+08:00"},
            {**self._valid_result(), "shots": 0},
            {**self._valid_result(), "shots": True},
            {**self._valid_result(), "counts": {}},
            {**self._valid_result(), "counts": {"00": 4, "11": 3}},
            {**self._valid_result(), "counts": {"02": 8}},
            {**self._valid_result(), "counts": {"00": "8"}},
        )

        for index, value in enumerate(malformed):
            with self.subTest(value=value):
                result_path = self._write_provider_result(value, f"malformed-{index}.json")
                with self.assertRaises(ValueError):
                    self._main(
                        [
                            "--provider",
                            "originq",
                            "--qasm",
                            str(self.qasm_path),
                            "--import-result",
                            str(result_path),
                            "--output-dir",
                            str(self.root / f"bad-{index}"),
                        ]
                    )

    def test_import_rejects_malformed_timestamp_without_leaking_its_value(self):
        secret = ("originq-" "token-that-must-not-leak")
        result_path = self._write_provider_result(
            {**self._valid_result(), "timestamp": secret},
            "secret-timestamp.json",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(ValueError) as raised:
                run_qpu.main(
                    [
                        "--provider",
                        "originq",
                        "--qasm",
                        str(self.qasm_path),
                        "--import-result",
                        str(result_path),
                        "--output-dir",
                        str(self.root / "secret-timestamp-output"),
                    ],
                    {},
                )

        captured = stdout.getvalue() + stderr.getvalue() + str(raised.exception)
        formatted_exception = "".join(traceback.format_exception(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn(secret, captured + formatted_exception)

    def test_import_cleans_up_a_file_when_its_write_fails_after_creation(self):
        result_path = self._write_provider_result(self._valid_result())
        output_directory = self.root / "partial-write"

        class PartialWriter:
            def __init__(self, destination):
                self.destination = destination

            def __enter__(self):
                self.destination.__enter__()
                return self

            def write(self, content):
                self.destination.write(content[:1])
                raise OSError("simulated write failure")

            def __exit__(self, *arguments):
                return self.destination.__exit__(*arguments)

        original_open = Path.open

        def open_with_partial_write(path, *arguments, **keywords):
            destination = original_open(path, *arguments, **keywords)
            if path.name.endswith(".native.ir"):
                return PartialWriter(destination)
            return destination

        with patch.object(Path, "open", new=open_with_partial_write):
            with self.assertRaises(OSError):
                self._main(
                    [
                        "--provider",
                        "originq",
                        "--qasm",
                        str(self.qasm_path),
                        "--import-result",
                        str(result_path),
                        "--output-dir",
                        str(output_directory),
                    ]
                )

        self.assertEqual(list(output_directory.iterdir()), [])

    def test_import_preserves_a_race_created_artifact_after_exclusive_create_collision(self):
        result_path = self._write_provider_result(self._valid_result())
        output_directory = self.root / "exclusive-create-collision"
        original_write = run_qpu._write_new
        race_content = "evidence owned by another process"

        def create_then_collide(path, content):
            if path.name.endswith(".native.ir"):
                path.write_text(race_content, encoding="utf-8")
                raise FileExistsError("simulated exclusive create collision")
            original_write(path, content)

        with patch.object(run_qpu, "_write_new", side_effect=create_then_collide):
            with self.assertRaises(FileExistsError):
                self._main(
                    [
                        "--provider",
                        "originq",
                        "--qasm",
                        str(self.qasm_path),
                        "--import-result",
                        str(result_path),
                        "--output-dir",
                        str(output_directory),
                    ]
                )

        collision_path = output_directory / "originq-job-2026-08-18.native.ir"
        self.assertEqual(list(output_directory.iterdir()), [collision_path])
        self.assertEqual(collision_path.read_text(encoding="utf-8"), race_content)

    def test_import_result_requires_the_selected_supported_provider_and_never_overwrites(self):
        result_path = self._write_provider_result(self._valid_result("spinq"))
        with self.assertRaises(ValueError):
            self._main(
                [
                    "--provider",
                    "originq",
                    "--qasm",
                    str(self.qasm_path),
                    "--import-result",
                    str(result_path),
                    "--output-dir",
                    str(self.root / "mismatch"),
                ]
            )

        output_directory = self.root / "collision"
        matching_path = self._write_provider_result(self._valid_result())
        arguments = [
            "--provider",
            "originq",
            "--qasm",
            str(self.qasm_path),
            "--import-result",
            str(matching_path),
            "--output-dir",
            str(output_directory),
        ]
        self.assertEqual(self._main(arguments)[0], 0)
        with self.assertRaises(FileExistsError):
            self._main(arguments)

    def test_import_artifacts_stdout_stderr_and_contents_redact_all_environment_values(self):
        secrets = {
            "SPINQ_API_TOKEN": "spinq-secret-that-must-not-leak",
            "ORIGINQ_API_TOKEN": "originq-secret-that-must-not-leak",
            "AWS_ACCESS_KEY_ID": "aws-access-that-must-not-leak",
            "AWS_SECRET_ACCESS_KEY": "aws-secret-that-must-not-leak",
            "AWS_BRAKET_DEVICE_ARN": "arn:aws:braket:secret-device",
        }
        result_path = self._write_provider_result(self._valid_result())
        output_directory = self.root / "redacted"
        code, stdout, stderr = self._main(
            [
                "--provider",
                "originq",
                "--qasm",
                str(self.qasm_path),
                "--import-result",
                str(result_path),
                "--output-dir",
                str(output_directory),
            ],
            secrets,
        )

        self.assertEqual(code, 0)
        captured = stdout + stderr + "".join(
            path.read_text(encoding="utf-8") for path in output_directory.iterdir()
        )
        for secret in secrets.values():
            with self.subTest(secret=secret):
                self.assertNotIn(secret, captured)


if __name__ == "__main__":
    unittest.main()
