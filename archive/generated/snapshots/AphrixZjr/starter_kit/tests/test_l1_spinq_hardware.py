import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import l1_spinq_hardware as hardware
import evaluator
import l1_reference
import loomq_l1
import run_spinq_hardware as hardware_cli


QASM = (
    "OPENQASM 2.0; include \"qelib1.inc\"; "
    "qreg q[2]; creg c[2]; h q[0]; cx q[0],q[1]; measure q -> c;"
)


class FakeCloudClient:
    def __init__(self, submission=None, outcomes=()):
        self.submission = submission or hardware.Submission(202, "task-123")
        self.outcomes = list(outcomes)
        self.compiled_source = None
        self.requests = []
        self.polled = []

    def compile_qasm(self, source):
        self.compiled_source = source
        return "compiled-ir"

    def submit_task(self, ir, request):
        self.requests.append((ir, request))
        return self.submission

    def poll_task(self, job_id):
        self.polled.append(job_id)
        return self.outcomes.pop(0)


def settings(key_file="private.pem"):
    return hardware.SpinQHardwareSettings(
        "private-user", key_file, "https://trusted.example", "device-code"
    )


class SpinQHardwareSettingsTests(unittest.TestCase):
    def test_missing_environment_reports_names_without_values(self):
        environment = {
            hardware.ENV_USERNAME: "secret-user",
            hardware.ENV_HOST: "https://secret-host.example",
        }
        with self.assertRaises(hardware.SpinQHardwareConfigurationError) as caught:
            hardware.SpinQHardwareSettings.from_environment(environment)
        message = str(caught.exception)
        self.assertIn(hardware.ENV_KEY_FILE, message)
        self.assertNotIn("secret-user", message)
        self.assertNotIn("secret-host", message)

    def test_username_and_private_key_use_spinqit_routing_defaults(self):
        with tempfile.NamedTemporaryFile() as key_file:
            configured = hardware.SpinQHardwareSettings.from_environment(
                {
                    hardware.ENV_USERNAME: "secret-user",
                    hardware.ENV_KEY_FILE: key_file.name,
                }
            )

        self.assertEqual(hardware.DEFAULT_HOST, configured.host)
        self.assertEqual(hardware.DEFAULT_PLATFORM, configured.platform)

    def test_environment_loads_without_exposing_secret_repr(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "private.pem"
            key_path.write_text("PRIVATE-CONTENT", encoding="utf-8")
            environment = {
                hardware.ENV_USERNAME: "secret-user",
                hardware.ENV_KEY_FILE: str(key_path),
                hardware.ENV_HOST: "https://cloud.example:6060/api",
                hardware.ENV_PLATFORM: "SQC-25",
            }
            configured = hardware.SpinQHardwareSettings.from_environment(environment)
        rendered = repr(configured)
        self.assertNotIn("secret-user", rendered)
        self.assertNotIn(str(key_path), rendered)
        self.assertNotIn("cloud.example", rendered)
        self.assertNotIn("SQC-25", rendered)

    def test_invalid_key_file_does_not_echo_path(self):
        secret_path = "D:/secret/account-private.pem"
        environment = {
            hardware.ENV_USERNAME: "user",
            hardware.ENV_KEY_FILE: secret_path,
            hardware.ENV_HOST: "https://cloud.example",
            hardware.ENV_PLATFORM: "device",
        }
        with self.assertRaises(hardware.SpinQHardwareConfigurationError) as caught:
            hardware.SpinQHardwareSettings.from_environment(environment)
        self.assertIn(hardware.ENV_KEY_FILE, str(caught.exception))
        self.assertNotIn(secret_path, str(caught.exception))

    def test_host_rejects_embedded_credentials(self):
        with tempfile.NamedTemporaryFile() as key_file:
            environment = {
                hardware.ENV_USERNAME: "user",
                hardware.ENV_KEY_FILE: key_file.name,
                hardware.ENV_HOST: "https://user:password@cloud.example",
                hardware.ENV_PLATFORM: "device",
            }
            with self.assertRaisesRegex(
                hardware.SpinQHardwareConfigurationError, hardware.ENV_HOST
            ):
                hardware.SpinQHardwareSettings.from_environment(environment)


class SpinQitCloudClientTests(unittest.TestCase):
    def test_default_host_is_omitted_from_sdk_factory_call(self):
        observed = {}

        def cloud_factory(*arguments):
            observed["arguments"] = arguments
            return object()

        configured = hardware.SpinQHardwareSettings(
            "private-user",
            "private.pem",
            hardware.DEFAULT_HOST,
            hardware.DEFAULT_PLATFORM,
        )
        hardware.SpinQitCloudClient(
            configured,
            sdk=(object, lambda name: object(), cloud_factory, Exception),
        )

        self.assertEqual(("private-user", "private.pem"), observed["arguments"])

    def test_verified_sdk_calls_are_configured_and_temp_qasm_is_removed(self):
        observed = {}

        class PendingError(Exception):
            pass

        class Config:
            def __init__(self):
                observed["config"] = self

            def configure_platform(self, value):
                observed["platform"] = value

            def configure_shots(self, value):
                observed["shots"] = value

            def configure_measured_qubits(self, value):
                observed["measured"] = value

            def configure_task(self, name, description):
                observed["task"] = (name, description)

        class Compiler:
            def compile(self, path, optimization):
                observed["path"] = path
                observed["source"] = Path(path).read_text(encoding="utf-8")
                observed["optimization"] = optimization
                return "ir"

        class Backend:
            def submit_task(self, ir, config):
                observed["submit"] = (ir, config)
                return 202, "accepted", "cloud-job"

            def get_task_result(self, job_id, hanging):
                observed["poll"] = (job_id, hanging)
                return type(
                    "Result",
                    (),
                    {
                        "counts": {"00": 2, "11": 2},
                        "probabilities": {"00": 0.5, "11": 0.5},
                        "_shots": 4,
                    },
                )()

        backend = Backend()

        def cloud_factory(username, key_file, host):
            observed["cloud"] = (username, key_file, host)
            return backend

        def compiler_factory(name):
            observed["compiler_name"] = name
            return Compiler()

        sdk = (Config, compiler_factory, cloud_factory, PendingError)
        client = hardware.SpinQitCloudClient(settings(), sdk=sdk)
        self.assertEqual("ir", client.compile_qasm("OPENQASM 2.0;"))
        self.assertFalse(Path(observed["path"]).exists())
        request = hardware.HardwareRequest(
            "device-code", 4, (0, 1), "task", "description"
        )
        self.assertEqual(
            hardware.Submission(202, "cloud-job"),
            client.submit_task("ir", request),
        )
        outcome = client.poll_task("cloud-job")

        self.assertEqual(("private-user", "private.pem", "https://trusted.example"), observed["cloud"])
        self.assertEqual("qasm", observed["compiler_name"])
        self.assertEqual(0, observed["optimization"])
        self.assertEqual("device-code", observed["platform"])
        self.assertEqual(4, observed["shots"])
        self.assertEqual([0, 1], observed["measured"])
        self.assertEqual(("task", "description"), observed["task"])
        self.assertEqual(("cloud-job", False), observed["poll"])
        self.assertEqual("succeeded", outcome.state)

    def test_sdk_pending_exception_maps_to_pending_state(self):
        class PendingError(Exception):
            pass

        class Backend:
            def get_task_result(self, job_id, hanging):
                raise PendingError("not ready")

        sdk = (
            object,
            lambda name: object(),
            lambda username, key_file, host: Backend(),
            PendingError,
        )
        client = hardware.SpinQitCloudClient(settings(), sdk=sdk)
        self.assertEqual("pending", client.poll_task("job").state)

    def test_sdk_failure_result_maps_to_failed_state_and_stdout_is_suppressed(self):
        class PendingError(Exception):
            pass

        class Backend:
            def get_task_result(self, job_id, hanging):
                print("PRIVATE-CONTENT")
                return None

        sdk = (
            object,
            lambda name: object(),
            lambda username, key_file, host: Backend(),
            PendingError,
        )
        client = hardware.SpinQitCloudClient(settings(), sdk=sdk)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            outcome = client.poll_task("job")
        self.assertEqual("failed", outcome.state)
        self.assertEqual("", output.getvalue())


class SpinQHardwareStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.circuit = loomq_l1.parse_qasm(QASM)

    def execute(self, client, **overrides):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds

        arguments = {
            "confirmation": hardware.SUBMISSION_CONFIRMATION,
            "client": client,
            "timeout_seconds": 10,
            "poll_interval_seconds": 1,
            "clock": lambda: now[0],
            "sleep": sleep,
        }
        arguments.update(overrides)
        return hardware.execute_spinq_hardware(
            self.circuit, 4, settings(), **arguments
        )

    def test_confirmation_is_checked_before_client_use(self):
        client = FakeCloudClient()
        with self.assertRaisesRegex(
            hardware.SpinQHardwareSubmissionError, "explicit confirmation"
        ):
            hardware.execute_spinq_hardware(
                self.circuit,
                4,
                settings(),
                confirmation="wrong",
                client=client,
            )
        self.assertIsNone(client.compiled_source)

    def test_pending_then_success_uses_shared_emitter_and_redacts_raw_result(self):
        raw = {
            "counts": {"00": 2, "11": 2},
            "shots": 4,
            "username": "private-user",
            "note": "file private.pem at https://trusted.example",
        }
        client = FakeCloudClient(
            outcomes=(
                hardware.PollOutcome.pending(),
                hardware.PollOutcome.succeeded({"00": 2, "11": 2}, raw),
            )
        )
        events = []
        result = self.execute(
            client, event_handler=lambda name, fields: events.append((name, fields))
        )

        self.assertNotIn("measure ", client.compiled_source.lower())
        self.assertEqual(
            hardware.emit_spinq_cloud(self.circuit), client.compiled_source
        )
        self.assertEqual("compiled-ir", client.requests[0][0])
        request = client.requests[0][1]
        self.assertEqual("device-code", request.platform)
        self.assertEqual((0, 1), request.measured_qubits)
        self.assertEqual({"00": 2, "11": 2}, result["counts"])
        serialized = json.dumps(result)
        self.assertNotIn("private-user", serialized)
        self.assertNotIn("private.pem", serialized)
        self.assertNotIn("trusted.example", serialized)
        self.assertEqual("<redacted>", result["raw_result"]["username"])
        self.assertEqual(["submitted", "pending"], [item[0] for item in events])
        self.assertEqual((True, "schema valid"), evaluator.validate_schema(result))
        self.assertEqual("SpinQ Cloud", result["meta"]["provider"])
        self.assertEqual("device-code", result["meta"]["device_code"])
        self.assertEqual("spinqit-0.2.4", result["meta"]["sdk_api"])
        self.assertEqual("counts", result["meta"]["result_kind"])
        self.assertEqual([0, 1], result["meta"]["measured_qubits"])
        self.assertEqual(
            [
                {"qubit": 0, "classical": 0},
                {"qubit": 1, "classical": 1},
            ],
            result["meta"]["measurement_map"],
        )
        self.assertEqual(result["submitted_at"], result["timestamp"])

    def test_probabilities_are_exactly_rounded_and_projected_to_classical_bits(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; include \"qelib1.inc\"; "
            "qreg q[3]; creg c[3]; x q[0]; x q[2]; "
            "measure q[0] -> c[0]; measure q[1] -> c[2]; "
            "measure q[2] -> c[1];"
        )
        client = FakeCloudClient(
            outcomes=(
                hardware.PollOutcome.succeeded(
                    {"101": 99, "000": 0},
                    {
                        "counts": {"101": 99, "000": 0},
                        "probabilities": {"101": 0.995, "000": 0.005},
                        "shots": 100,
                    },
                ),
            )
        )

        result = hardware.execute_spinq_hardware(
            circuit,
            100,
            settings(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            client=client,
        )

        self.assertEqual({"011": 99, "000": 1}, result["counts"])
        self.assertEqual(
            "probabilities-largest-remainder", result["counts_normalization"]
        )
        self.assertEqual(99, sum(result["raw_result"]["counts"].values()))

    def test_recovery_reads_existing_job_without_compiling_or_submitting(self):
        client = FakeCloudClient(
            outcomes=(
                hardware.PollOutcome.succeeded(
                    {"00": 2, "11": 2},
                    {"counts": {"00": 2, "11": 2}, "shots": 4},
                ),
            )
        )

        result = hardware.recover_spinq_hardware(
            self.circuit, 4, settings(), "existing-job", client=client
        )

        self.assertTrue(result["recovered_existing_job"])
        self.assertEqual("existing-job", result["job_id"])
        self.assertIsNone(client.compiled_source)
        self.assertEqual([], client.requests)
        self.assertEqual(["existing-job"], client.polled)
        self.assertEqual((True, "schema valid"), evaluator.validate_schema(result))

    def test_provider_shots_must_match_the_request_exactly(self):
        for provider_shots in (None, 3, 5, True):
            with self.subTest(provider_shots=provider_shots):
                raw = {"counts": {"00": 2, "11": 2}}
                if provider_shots is not None:
                    raw["shots"] = provider_shots
                client = FakeCloudClient(
                    outcomes=(
                        hardware.PollOutcome.succeeded(
                            {"00": 2, "11": 2}, raw
                        ),
                    )
                )
                with self.assertRaisesRegex(
                    hardware.SpinQHardwareTaskError, "_shots"
                ):
                    self.execute(client)

    def test_terminal_failure_is_reported_with_job_id(self):
        client = FakeCloudClient(outcomes=(hardware.PollOutcome.failed(),))
        with self.assertRaisesRegex(hardware.SpinQHardwareTaskError, "task-123 failed"):
            self.execute(client)

    def test_pending_task_times_out(self):
        client = FakeCloudClient(
            outcomes=(hardware.PollOutcome.pending(), hardware.PollOutcome.pending())
        )
        with self.assertRaisesRegex(hardware.SpinQHardwareTaskError, "timed out"):
            self.execute(client, timeout_seconds=1)

    def test_saved_but_not_runnable_submission_is_not_success(self):
        for status in (206, 226, 500):
            with self.subTest(status=status):
                client = FakeCloudClient(
                    submission=hardware.Submission(status, "traceable-job")
                )
                with self.assertRaisesRegex(
                    hardware.SpinQHardwareSubmissionError,
                    "status %d.*traceable-job" % status,
                ):
                    self.execute(client)
                self.assertEqual([], client.polled)

    def test_accepted_submission_requires_job_id(self):
        client = FakeCloudClient(submission=hardware.Submission(202, None))
        with self.assertRaisesRegex(
            hardware.SpinQHardwareSubmissionError, "without returning a job ID"
        ):
            self.execute(client)

    def test_invalid_counts_are_rejected(self):
        client = FakeCloudClient(
            outcomes=(
                hardware.PollOutcome.succeeded(
                    {"00": 3}, {"counts": {"00": 3}, "shots": 4}
                ),
            )
        )
        with self.assertRaisesRegex(hardware.SpinQHardwareTaskError, "invalid counts"):
            self.execute(client)

    def test_unknown_poll_state_is_rejected(self):
        client = FakeCloudClient(outcomes=(hardware.PollOutcome("mystery"),))
        with self.assertRaisesRegex(hardware.SpinQHardwareTaskError, "unknown state"):
            self.execute(client)


class SpinQArchivedEvidenceTests(unittest.TestCase):
    def test_all_archived_jobs_have_valid_bound_summaries(self):
        evidence_dir = Path(ROOT, "evidence", "files", "hardware", "spinq")
        metadata = json.loads(
            (evidence_dir / "spinq-task-metadata.json").read_text(encoding="utf-8")
        )
        created_at = {
            item["job_id"]: item["created_at"].replace("+0000", "Z")
            for item in metadata["tasks"]
        }
        summaries = sorted(evidence_dir.glob("spinq-*-summary.json"))
        self.assertEqual(4, len(summaries))
        required_meta = {
            "provider",
            "device_code",
            "sdk_api",
            "result_kind",
            "counts_normalization",
            "measured_qubits",
            "measurement_map",
            "source_qasm_sha256",
            "submitted_qasm_sha256",
            "raw_evidence_file",
        }

        for summary_path in summaries:
            with self.subTest(summary=summary_path.name):
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    (True, "schema valid"), evaluator.validate_schema(summary)
                )
                self.assertEqual(created_at[summary["job_id"]], summary["timestamp"])
                self.assertTrue(required_meta <= set(summary["meta"]))
                self.assertEqual(
                    "probabilities-largest-remainder",
                    summary["meta"]["counts_normalization"],
                )

                source_path = evidence_dir / summary["source_qasm_file"]
                submitted_path = evidence_dir / summary["submitted_qasm_file"]
                request_path = evidence_dir / summary["request_file"]
                raw_path = evidence_dir / summary["meta"]["raw_evidence_file"]
                legacy_raw_path = raw_path.with_name(
                    raw_path.name.replace("-raw.json", ".json")
                )
                legacy_submitted_path = submitted_path.with_name(
                    submitted_path.name.replace("-submitted.qasm", ".qasm")
                )
                request = json.loads(request_path.read_text(encoding="utf-8"))
                raw = json.loads(raw_path.read_text(encoding="utf-8"))

                self.assertEqual(raw_path.read_bytes(), legacy_raw_path.read_bytes())
                self.assertEqual(
                    submitted_path.read_bytes(), legacy_submitted_path.read_bytes()
                )

                source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
                submitted_hash = hashlib.sha256(
                    submitted_path.read_bytes()
                ).hexdigest()
                self.assertEqual(
                    source_hash, summary["meta"]["source_qasm_sha256"]
                )
                self.assertEqual(
                    submitted_hash, summary["meta"]["submitted_qasm_sha256"]
                )
                self.assertEqual(source_hash, request["source_qasm_sha256"])
                self.assertEqual(submitted_hash, request["submitted_qasm_sha256"])
                self.assertEqual(summary["shots"], request["shots"])
                self.assertEqual(
                    summary["shots"], raw["raw_result"]["shots"]
                )
                archived_circuit = loomq_l1.parse_qasm(
                    source_path.read_text(encoding="utf-8")
                )
                qubit_counts = hardware._largest_remainder_counts(
                    raw["raw_result"]["probabilities"],
                    summary["shots"],
                    archived_circuit.qubit_count,
                )
                self.assertEqual(
                    summary["counts"],
                    hardware._project_qubit_counts_to_classical(
                        qubit_counts, archived_circuit
                    ),
                )
                self.assertEqual(
                    summary["meta"]["measurement_map"],
                    request["measurement_map"],
                )
                self.assertIn("measure ", source_path.read_text(encoding="utf-8"))
                self.assertNotIn(
                    "measure ", submitted_path.read_text(encoding="utf-8")
                )


class SpinQHardwareCliTests(unittest.TestCase):
    def test_smoke_rejects_non_smoke_shot_count_before_cloud_use(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            hardware_cli.main(["smoke", "--shots", "257"])

    def test_git_and_docker_context_exclude_credential_files(self):
        gitignore = Path(ROOT, ".gitignore").read_text(encoding="utf-8")
        dockerignore = Path(ROOT, ".dockerignore").read_text(
            encoding="utf-8"
        )
        for pattern in (".env*", "*.env", "*.env.*", "*.pem", "*.key"):
            self.assertIn(pattern, dockerignore)
        for pattern in (
            "evidence/files/braket/*-prepared.json",
            "evidence/files/braket/*-submitted.json",
            "evidence/files/**/*-failed-*.json",
        ):
            self.assertIn(pattern, dockerignore)
        for pattern in ("*.env", "*.env.*", "*.pem", "*.key"):
            self.assertIn(pattern, gitignore)

    def test_default_dry_run_never_reads_credentials_or_calls_cloud(self):
        output = io.StringIO()
        with mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            side_effect=AssertionError("credentials read"),
        ), mock.patch.object(
            hardware_cli,
            "execute_spinq_hardware",
            side_effect=AssertionError("cloud called"),
        ), contextlib.redirect_stdout(output):
            status = hardware_cli.main([])
        manifests = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertEqual(
            ["bell", "bit_order", "ghz3"],
            [item["circuit"] for item in manifests],
        )
        self.assertTrue(all(not item["will_submit"] for item in manifests))

    def test_plan_reports_exact_procurement_workload_without_cloud_use(self):
        output = io.StringIO()
        with mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            side_effect=AssertionError("credentials read"),
        ), mock.patch.object(
            hardware_cli,
            "execute_spinq_hardware",
            side_effect=AssertionError("cloud called"),
        ), contextlib.redirect_stdout(output):
            status = hardware_cli.main(["plan"])
        self.assertEqual(0, status)
        self.assertIn("4 hardware tasks, 16584 shots", output.getvalue())
        self.assertIn("8 tasks, 33168 shots", output.getvalue())
        self.assertIn("optional direction probe", output.getvalue())

    def test_direction_probe_is_opt_in_single_task_and_bounded(self):
        circuit = hardware_cli._load_circuits(("bit_order_direction",))[0][1]
        self.assertEqual(
            (
                {"qubit": 0, "classical": 2},
                {"qubit": 1, "classical": 0},
                {"qubit": 2, "classical": 1},
            ),
            hardware._measurement_map(circuit),
        )
        self.assertEqual({"100": 1.0}, l1_reference.distribution(circuit))
        resume_args = hardware_cli._parser().parse_args(
            [
                "resume",
                "--job-id",
                "existing-direction-job",
                "--circuit",
                "bit_order_direction",
                "--shots",
                "100",
            ]
        )
        self.assertEqual("bit_order_direction", resume_args.circuit)
        configured = settings()
        cloud_result = {
            "schema_version": "loomq-spinq-hardware-v1",
            "backend": "spinq-cloud-hardware",
            "job_id": "direction-job",
            "shots": 100,
            "counts": {"100": 100},
            "bit_order": "little",
            "timestamp": "2026-08-15T00:00:00+00:00",
        }
        paths = tuple(Path("unused-%d" % index) for index in range(5))
        with mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            return_value=configured,
        ), mock.patch.object(
            hardware_cli,
            "_run_local_preflight",
            return_value={"expected_state_mass": 1.0},
        ), mock.patch.object(
            hardware_cli,
            "execute_spinq_hardware",
            return_value=cloud_result,
        ) as execute, mock.patch.object(
            hardware_cli, "_write_evidence_bundle", return_value=paths
        ) as write_bundle, contextlib.redirect_stdout(io.StringIO()):
            status = hardware_cli.main(
                [
                    "submit-one",
                    "--circuit",
                    "bit_order_direction",
                    "--shots",
                    "100",
                    "--confirm-submit",
                    hardware.SUBMISSION_CONFIRMATION,
                ]
            )
        self.assertEqual(0, status)
        execute.assert_called_once()
        self.assertEqual(100, execute.call_args.args[1])
        self.assertIn("bit_order_direction", execute.call_args.kwargs["task_name"])
        self.assertEqual("bit_order_direction", write_bundle.call_args.args[2])

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            hardware_cli.main(
                [
                    "submit-one",
                    "--circuit",
                    "bit_order_direction",
                    "--shots",
                    "257",
                    "--confirm-submit",
                    hardware.SUBMISSION_CONFIRMATION,
                ]
            )

    def test_smoke_without_literal_confirmation_stops_before_credentials(self):
        error = io.StringIO()
        with mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            side_effect=AssertionError("credentials read"),
        ), contextlib.redirect_stderr(error):
            status = hardware_cli.main(["smoke"])
        self.assertEqual(2, status)
        self.assertIn(hardware.SUBMISSION_CONFIRMATION, error.getvalue())

    def test_confirmed_smoke_writes_qasm_and_redacted_json(self):
        configured = settings()
        preflight = {
            "backend": "spinq-basic-simulator",
            "counts": {"00": 2, "11": 2},
            "expected_state_mass": 1.0,
        }

        def cloud_result(circuit, shots, configured_settings, **kwargs):
            counts = (
                {"00": 2, "11": 2}
                if circuit.classical_count == 2
                else {"011": 4}
            )
            source_qasm = kwargs["source_qasm"]
            submitted_qasm = hardware.emit_spinq_cloud(circuit)
            normalization = "counts"
            return {
                "schema_version": "loomq-spinq-hardware-v1",
                "sdk_api": "spinqit-0.2.4",
                "backend": "spinq-cloud-hardware",
                "device_code": "device-code",
                "job_id": "job-%d" % circuit.classical_count,
                "shots": shots,
                "counts": counts,
                "counts_normalization": normalization,
                "bit_order": "little",
                "timestamp": "2026-08-15T00:00:00+00:00",
                "meta": hardware._standard_meta(
                    circuit,
                    configured_settings,
                    normalization,
                    source_qasm,
                    submitted_qasm,
                ),
                "request": hardware._request_record(
                    circuit,
                    configured_settings,
                    shots,
                    source_qasm,
                    submitted_qasm,
                    provenance="client submission request",
                    task_name=kwargs["task_name"],
                    task_description=kwargs["task_description"],
                ),
                "raw_result": {"counts": counts, "shots": shots},
            }

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            return_value=configured,
        ), mock.patch.object(
            hardware_cli, "_run_local_preflight", return_value=preflight
        ), mock.patch.object(
            hardware_cli, "execute_spinq_hardware", side_effect=cloud_result
        ) as execute, contextlib.redirect_stdout(io.StringIO()):
            status = hardware_cli.main(
                [
                    "smoke",
                    "--shots",
                    "4",
                    "--confirm-submit",
                    hardware.SUBMISSION_CONFIRMATION,
                    "--output-dir",
                    directory,
                ]
            )
            files = sorted(Path(directory).iterdir())
            payloads = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in files
                if path.name.endswith("-summary.json")
            ]
            hashes_match = all(
                hashlib.sha256(
                    (Path(directory) / item["source_qasm_file"]).read_bytes()
                ).hexdigest()
                == item["meta"]["source_qasm_sha256"]
                and hashlib.sha256(
                    (Path(directory) / item["submitted_qasm_file"]).read_bytes()
                ).hexdigest()
                == item["meta"]["submitted_qasm_sha256"]
                for item in payloads
            )

        self.assertEqual(0, status)
        self.assertEqual(10, len(files))
        self.assertEqual({"bell", "bit_order"}, {item["circuit"] for item in payloads})
        self.assertTrue(
            all(
                item["schema_version"] == hardware_cli.SUMMARY_SCHEMA_VERSION
                for item in payloads
            )
        )
        self.assertTrue(all(item["hardware_validation_passed"] for item in payloads))
        self.assertTrue(all(evaluator.validate_schema(item)[0] for item in payloads))
        self.assertTrue(hashes_match)
        self.assertEqual(2, execute.call_count)
        for call in execute.call_args_list:
            self.assertEqual(
                hardware.SUBMISSION_CONFIRMATION,
                call.kwargs["confirmation"],
            )

    def test_resume_is_read_only_and_writes_existing_job_evidence(self):
        configured = settings()
        preflight = {
            "backend": "spinq-basic-simulator",
            "counts": {"011": 100},
            "expected_state_mass": 1.0,
        }

        def recovered_result(
            circuit, shots, configured_settings, job_id, **kwargs
        ):
            source_qasm = kwargs["source_qasm"]
            submitted_qasm = hardware.emit_spinq_cloud(circuit)
            normalization = "counts"
            return {
                "schema_version": "loomq-spinq-hardware-v1",
                "sdk_api": "spinqit-0.2.4",
                "backend": "spinq-cloud-hardware",
                "device_code": "device-code",
                "job_id": job_id,
                "shots": shots,
                "counts": {"011": 100},
                "counts_normalization": normalization,
                "bit_order": "little",
                "timestamp": "2026-08-15T00:00:00+00:00",
                "meta": hardware._standard_meta(
                    circuit,
                    configured_settings,
                    normalization,
                    source_qasm,
                    submitted_qasm,
                ),
                "request": hardware._request_record(
                    circuit,
                    configured_settings,
                    shots,
                    source_qasm,
                    submitted_qasm,
                    provenance="read-only recovery arguments",
                ),
                "recovered_existing_job": True,
                "raw_result": {"counts": {"101": 100}, "shots": shots},
            }

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            hardware_cli.SpinQHardwareSettings,
            "from_environment",
            return_value=configured,
        ), mock.patch.object(
            hardware_cli, "_run_local_preflight", return_value=preflight
        ), mock.patch.object(
            hardware_cli, "recover_spinq_hardware", side_effect=recovered_result
        ) as recover, contextlib.redirect_stdout(io.StringIO()):
            status = hardware_cli.main(
                [
                    "resume",
                    "--job-id",
                    "existing-job",
                    "--circuit",
                    "bit_order",
                    "--shots",
                    "100",
                    "--output-dir",
                    directory,
                ]
            )

            files = sorted(Path(directory).iterdir())
            payload = json.loads(
                next(
                    path for path in files if path.name.endswith("-summary.json")
                ).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(0, status)
        self.assertEqual(5, len(files))
        self.assertEqual(
            hardware_cli.SUMMARY_SCHEMA_VERSION, payload["schema_version"]
        )
        self.assertEqual("resume", payload["mode"])
        self.assertTrue(payload["hardware_validation_passed"])
        recover.assert_called_once()


if __name__ == "__main__":
    unittest.main()
