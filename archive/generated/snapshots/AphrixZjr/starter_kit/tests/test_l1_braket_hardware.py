import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import l1_braket_hardware as hardware
import loomq_l1
import run_braket_hardware as cli


DEVICE_ARN = "arn:aws:braket:us-east-1::device/qpu/test/vendor"
TASK_ARN = (
    "arn:aws:braket:us-east-1:123456789012:"
    "quantum-task/11111111-2222-3333-4444-555555555555"
)
FAKE_AWS_ACCESS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


def config(**changes):
    values = {
        "profile": "loomq-braket",
        "region": "us-east-1",
        "device_arn": DEVICE_ARN,
        "s3_bucket": "loomq-private-results",
        "s3_prefix": "loomq/l1",
        "poll_interval_seconds": 0.01,
        "job_timeout_seconds": 30.0,
    }
    values.update(changes)
    return hardware.BraketHardwareConfig(**values)


def prepared_receipt(
    directory, name="bit_order", shots=100, cfg=None, token="retry-token-123"
):
    active_config = config() if cfg is None else cfg
    qasm2 = cli.CIRCUITS[name].read_text(encoding="utf-8")
    circuit = loomq_l1.parse_qasm(qasm2)
    qasm3 = cli.emit_braket_executable(circuit)
    request_sha256 = cli._request_sha256(
        active_config, shots, qasm3, token
    )
    path = cli._write_prepared_receipt(
        Path(directory),
        name,
        shots,
        qasm3,
        token,
        request_sha256,
    )
    return path, token, qasm3, request_sha256


def device(status="ONLINE", operations=None):
    capabilities = {
        "paradigm": {"qubitCount": 20},
        "action": {
            "braket.ir.openqasm.program": {
                "supportedOperations": operations or ["h", "x", "cnot", "rz", "t"],
                "supportedResultTypes": [
                    {"name": "Sample", "minShots": 1, "maxShots": 100000}
                ],
            }
        },
    }
    return {
        "deviceArn": DEVICE_ARN,
        "deviceName": "TestQPU",
        "providerName": "Trusted Provider",
        "deviceType": "QPU",
        "deviceStatus": status,
        "deviceCapabilities": json.dumps(capabilities),
    }


def result_payload(measurements, measured_qubits, shots):
    return json.dumps(
        {
            "braketSchemaHeader": {
                "name": "braket.task_result.gate_model_task_result",
                "version": "1",
            },
            "taskMetadata": {
                "id": TASK_ARN,
                "shots": shots,
                "deviceId": DEVICE_ARN,
            },
            "measuredQubits": measured_qubits,
            "measurements": measurements,
            "numSuccessfulShots": shots,
            "numFailedShots": 0,
        }
    ).encode("utf-8")


class FakeClient:
    def __init__(self, states=None, payload=None, device_response=None, shots=1):
        self.states = list(states or ["COMPLETED"])
        self.payload = payload
        self.device_response = device_response or device()
        self.shots = shots
        self.calls = []
        self.closed = False
        self.output_directory = "loomq/l1/tasks/opaque/task"

    def get_device(self):
        self.calls.append("get_device")
        return self.device_response

    def check_s3(self):
        self.calls.append("check_s3")
        return {"bucket_location": "us-east-1", "prefix_key_count": 0}

    def submit(self, qasm3, shots, client_token, output_prefix):
        self.calls.append(("submit", shots, output_prefix))
        self.output_directory = output_prefix + "/task"
        return TASK_ARN

    def poll(self, task_arn):
        self.calls.append("poll")
        state = self.states.pop(0)
        if isinstance(state, Exception):
            raise state
        return {
            "quantumTaskArn": task_arn,
            "deviceArn": DEVICE_ARN,
            "shots": self.shots,
            "status": state,
            "outputS3Bucket": "loomq-private-results",
            "outputS3Directory": self.output_directory,
        }

    def download_result(self, task, expected_prefix):
        self.calls.append("download")
        return self.payload

    def close(self):
        self.closed = True


class BraketHardwareTests(unittest.TestCase):
    def test_credential_template_and_iam_policy_are_least_privilege_placeholders(self):
        starter = Path(ROOT)
        assignments = {
            line.split("=", 1)[0]
            for line in (starter / "hardware.env.example").read_text(
                encoding="utf-8"
            ).splitlines()
            if line and not line.startswith("#") and "=" in line
        }
        self.assertTrue(set(hardware.ENVIRONMENT_FIELDS) <= assignments)
        self.assertNotIn("AWS_ACCESS_KEY_ID", assignments)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", assignments)

        policy_path = starter / "docs" / "aws_braket_iam_policy.template.json"
        policy_text = policy_path.read_text(encoding="utf-8")
        policy = json.loads(policy_text)
        statements = {item["Sid"]: item for item in policy["Statement"]}
        self.assertEqual(
            "REPLACE_WITH_FULL_QPU_DEVICE_ARN",
            statements["ReadSelectedBraketDevice"]["Resource"],
        )
        create_resources = statements["CreateTasksOnlyOnSelectedDevice"][
            "Resource"
        ]
        self.assertIn("REPLACE_WITH_FULL_QPU_DEVICE_ARN", create_resources)
        self.assertTrue(
            any(resource.endswith(":quantum-task/*") for resource in create_resources)
        )
        self.assertTrue(
            statements["ReadOwnBraketTasks"]["Resource"].endswith(
                ":quantum-task/*"
            )
        )
        self.assertNotIn('"Resource": "*"', policy_text)
        self.assertNotIn("braket:deviceArn", policy_text)

    def test_config_requires_named_profile_and_matching_qpu_region(self):
        env = {
            hardware.PROFILE_ENV: "loomq-braket",
            hardware.REGION_ENV: "us-east-1",
            hardware.DEVICE_ARN_ENV: DEVICE_ARN,
            hardware.S3_BUCKET_ENV: "loomq-private-results",
        }
        parsed = hardware.BraketHardwareConfig.from_env(env)
        self.assertEqual("loomq-braket", parsed.profile)
        self.assertNotIn(parsed.profile, repr(parsed))
        self.assertNotIn(parsed.s3_bucket, repr(parsed))
        with self.assertRaisesRegex(ValueError, hardware.PROFILE_ENV):
            hardware.BraketHardwareConfig.from_env({**env, hardware.PROFILE_ENV: ""})
        with self.assertRaisesRegex(ValueError, "region"):
            hardware.BraketHardwareConfig.from_env(
                {**env, hardware.REGION_ENV: "us-west-2"}
            )
        with self.assertRaisesRegex(ValueError, "QPU ARN"):
            hardware.BraketHardwareConfig.from_env(
                {
                    **env,
                    hardware.DEVICE_ARN_ENV: (
                        "arn:aws:braket:us-east-1::device/quantum-simulator/amazon/sv1"
                    ),
                }
            )

    def test_config_rejects_placeholders_bad_storage_and_unbounded_values(self):
        base = {
            hardware.PROFILE_ENV: "loomq-braket",
            hardware.REGION_ENV: "us-east-1",
            hardware.DEVICE_ARN_ENV: DEVICE_ARN,
            hardware.S3_BUCKET_ENV: "loomq-private-results",
        }
        invalid = (
            (hardware.PROFILE_ENV, "your-profile"),
            (hardware.S3_BUCKET_ENV, "Bad_Bucket"),
            (hardware.S3_PREFIX_ENV, "../private"),
            (hardware.S3_PREFIX_ENV, "your-prefix"),
            (hardware.POLL_INTERVAL_ENV, "0"),
            (hardware.POLL_INTERVAL_ENV, "301"),
            (hardware.JOB_TIMEOUT_ENV, "nan"),
            (hardware.JOB_TIMEOUT_ENV, "604801"),
        )
        for field, value in invalid:
            with self.subTest(field=field), self.assertRaises(ValueError):
                hardware.BraketHardwareConfig.from_env({**base, field: value})

    def test_client_initialization_hides_profile_and_credentials_path(self):
        secret = r"C:\Users\private\.aws\credentials loomq-braket"

        class BadBoto3:
            @staticmethod
            def Session(**_kwargs):
                raise RuntimeError(secret)

        with mock.patch.object(
            hardware, "_load_boto3", return_value=(BadBoto3, object)
        ):
            with self.assertRaises(hardware.BraketHardwareError) as caught:
                hardware.Boto3BraketHardwareClient(config())
        self.assertEqual(
            "AWS named profile or client initialization failed",
            str(caught.exception),
        )
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("loomq-braket", str(caught.exception))
        self.assertNotIn("credentials", str(caught.exception))

    def test_client_rejects_configured_service_endpoint(self):
        with mock.patch.dict(
            os.environ, {"AWS_ENDPOINT_URL_BRAKET": "http://untrusted.invalid"}
        ):
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "custom AWS service endpoints"
            ):
                hardware.Boto3BraketHardwareClient(config())

    def test_boto3_wrapper_pins_endpoint_policy_and_request_fields(self):
        observed = {}

        class FakeConfig:
            def __init__(self, **kwargs):
                observed["config"] = kwargs

        class BraketService:
            def create_quantum_task(self, **kwargs):
                observed["create"] = kwargs
                return {"quantumTaskArn": TASK_ARN}

            def close(self):
                observed["braket_closed"] = True

        class ResultBody:
            def read(self, amount):
                observed["read_limit"] = amount
                return b"{}"

            def close(self):
                observed["body_closed"] = True

        class S3Service:
            def get_bucket_location(self, **kwargs):
                observed["location"] = kwargs
                return {"LocationConstraint": None}

            def list_objects_v2(self, **kwargs):
                observed["list"] = kwargs
                return {"KeyCount": 0}

            def get_object(self, **kwargs):
                observed["get"] = kwargs
                return {"ContentLength": 2, "Body": ResultBody()}

            def close(self):
                observed["s3_closed"] = True

        braket_service = BraketService()
        s3_service = S3Service()

        class FakeSession:
            def __init__(self, **kwargs):
                observed["session"] = kwargs

            def client(self, name, **kwargs):
                observed.setdefault("clients", []).append((name, kwargs))
                return braket_service if name == "braket" else s3_service

        class FakeBoto3:
            Session = FakeSession

        with mock.patch.object(
            hardware, "_load_boto3", return_value=(FakeBoto3, FakeConfig)
        ):
            client = hardware.Boto3BraketHardwareClient(config())
        self.assertTrue(observed["config"]["ignore_configured_endpoint_urls"])
        self.assertEqual(
            {"mode": "standard", "max_attempts": 4},
            observed["config"]["retries"],
        )
        self.assertEqual(
            {"bucket_location": None, "prefix_key_count": 0},
            client.check_s3(),
        )
        self.assertEqual(
            TASK_ARN,
            client.submit("OPENQASM 3.0;", 7, "client-token", "loomq/l1/task"),
        )
        self.assertEqual("client-token", observed["create"]["clientToken"])
        self.assertEqual(7, observed["create"]["shots"])
        self.assertEqual("loomq-private-results", observed["create"]["outputS3Bucket"])
        self.assertEqual("loomq/l1/task", observed["create"]["outputS3KeyPrefix"])
        payload = client.download_result(
            {
                "outputS3Bucket": "loomq-private-results",
                "outputS3Directory": "loomq/l1/task",
            },
            "loomq/l1/task",
        )
        self.assertEqual(b"{}", payload)
        self.assertEqual(
            "loomq/l1/task/results.json", observed["get"]["Key"]
        )
        self.assertEqual(hardware.MAX_RESULT_BYTES + 1, observed["read_limit"])
        self.assertTrue(observed["body_closed"])
        client.close()

    def test_cli_client_initialization_failure_has_no_traceback_or_path(self):
        secret = r"C:\Users\private\.aws\credentials loomq-braket"

        class BadBoto3:
            @staticmethod
            def Session(**_kwargs):
                raise RuntimeError(secret)

        stderr = io.StringIO()
        with mock.patch.object(
            cli.BraketHardwareConfig, "from_env", return_value=config()
        ), mock.patch.object(
            hardware, "_load_boto3", return_value=(BadBoto3, object)
        ), redirect_stderr(stderr):
            self.assertEqual(1, cli.main(["check"]))
        output = stderr.getvalue()
        self.assertIn("initialization failed", output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("loomq-braket", output)
        self.assertNotIn("credentials", output)

    def test_confirmation_is_checked_before_client_use(self):
        fake = FakeClient()
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        with self.assertRaisesRegex(hardware.BraketHardwareError, "confirmation"):
            hardware.run_braket_hardware(
                circuit, 1, config(), confirmation="wrong", client=fake
            )
        self.assertEqual([], fake.calls)
        self.assertFalse(fake.closed)

    def test_state_machine_maps_nontrivial_bit_order_and_closes(self):
        circuit = loomq_l1.parse_qasm(
            Path(cli.CIRCUITS["bit_order"]).read_text(encoding="utf-8")
        )
        fake = FakeClient(
            states=["QUEUED", "RUNNING", "COMPLETED"],
            payload=result_payload([[1, 0, 1]] * 4, [0, 1, 2], 4),
            shots=4,
        )
        submitted = []
        run = hardware.run_braket_hardware(
            circuit,
            4,
            config(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            client=fake,
            client_token="persisted-client-token",
            sleep=lambda _seconds: None,
            on_submitted=submitted.append,
        )
        self.assertEqual({"011": 4}, run.summary["counts"])
        self.assertEqual("measurements", run.summary["counts_source"])
        self.assertEqual(["11111111-2222-3333-4444-555555555555"], submitted)
        self.assertEqual("COMPLETED", run.raw_record["terminal_state"])
        encoded_raw = json.dumps(run.raw_record)
        self.assertNotIn("123456789012", encoded_raw)
        self.assertNotIn("persisted-client-token", encoded_raw)
        self.assertTrue(
            any(
                "persisted-client-token" in call[2]
                for call in fake.calls
                if isinstance(call, tuple)
            )
        )
        self.assertTrue(fake.closed)

    def test_polling_retries_are_bounded_and_never_resubmit(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        transient = hardware.BraketHardwareError("temporary read failure")
        succeeded = FakeClient(
            states=[transient, transient, transient, "COMPLETED"],
            payload=result_payload([[0]], [0], 1),
        )
        run = hardware.run_braket_hardware(
            circuit,
            1,
            config(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            client=succeeded,
            sleep=lambda _seconds: None,
        )
        self.assertEqual({"0": 1}, run.summary["counts"])
        self.assertEqual(1, len([call for call in succeeded.calls if isinstance(call, tuple)]))
        self.assertEqual(4, succeeded.calls.count("poll"))

        exhausted = FakeClient(states=[transient] * 4)
        with self.assertRaisesRegex(
            hardware.BraketHardwareError, "bounded retries"
        ) as caught:
            hardware.run_braket_hardware(
                circuit,
                1,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=exhausted,
                sleep=lambda _seconds: None,
            )
        self.assertEqual(1, len([call for call in exhausted.calls if isinstance(call, tuple)]))
        self.assertEqual(4, exhausted.calls.count("poll"))
        self.assertEqual(
            "11111111-2222-3333-4444-555555555555",
            caught.exception.raw_record["job_id"],
        )

    def test_resume_by_task_arn_skips_paid_submission(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        fake = FakeClient(
            states=["COMPLETED"],
            payload=result_payload([[0]], [0], 1),
        )
        identified = []
        run = hardware.run_braket_hardware(
            circuit,
            1,
            config(),
            client=fake,
            client_token="persisted-client-token",
            resume_task_arn=TASK_ARN,
            sleep=lambda _seconds: None,
            on_submitted=identified.append,
        )
        self.assertNotIn("submit", [call for call in fake.calls if isinstance(call, str)])
        self.assertFalse(any(isinstance(call, tuple) for call in fake.calls))
        self.assertEqual("resume", run.raw_record["execution_mode"])
        self.assertEqual(
            ["11111111-2222-3333-4444-555555555555"], identified
        )

    def test_downloaded_result_is_retained_safely_when_validation_fails(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        bad = json.loads(result_payload([[0]], [0], 1).decode("utf-8"))
        bad["taskMetadata"]["deviceId"] = "wrong-device"
        bad["debug"] = (
            "arn:aws:braket:us-east-1:123456789012:quantum-task/private "
            + FAKE_AWS_ACCESS_KEY
        )
        fake = FakeClient(
            states=["COMPLETED"],
            payload=json.dumps(bad).encode("utf-8"),
        )
        with self.assertRaisesRegex(
            hardware.BraketHardwareError, "device does not match"
        ) as caught:
            hardware.run_braket_hardware(
                circuit,
                1,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=fake,
            )
        raw = caught.exception.raw_record
        self.assertIn("downloaded_result", raw)
        self.assertTrue(raw["downloaded_result"]["json"])
        encoded = json.dumps(raw)
        self.assertNotIn("123456789012", encoded)
        self.assertNotIn(FAKE_AWS_ACCESS_KEY, encoded)

    def test_result_must_match_task_shots_and_device(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        base = json.loads(result_payload([[0]], [0], 1).decode("utf-8"))
        mutations = (
            ("id", TASK_ARN.replace("11111111", "99999999"), "identifier"),
            ("shots", 2, "shots"),
            ("deviceId", "wrong-device", "device"),
        )
        for key, value, message in mutations:
            payload = json.loads(json.dumps(base))
            payload["taskMetadata"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                hardware.BraketHardwareError, message
            ):
                hardware.parse_braket_result(
                    payload,
                    circuit,
                    1,
                    expected_task_arn=TASK_ARN,
                    expected_device_arn=DEVICE_ARN,
                )

    def test_probability_result_uses_largest_remainder(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[2]; creg c[2]; "
            "measure q[0] -> c[0]; measure q[1] -> c[1];"
        )
        payload = {
            "braketSchemaHeader": {
                "name": "braket.task_result.gate_model_task_result",
                "version": "1",
            },
            "taskMetadata": {"shots": 3},
            "measuredQubits": [0, 1],
            "measurementProbabilities": {"00": 0.5, "10": 0.5},
        }
        counts, raw = hardware.parse_braket_result(payload, circuit, 3)
        self.assertEqual({"00": 2, "01": 1}, counts)
        self.assertEqual(3, sum(counts.values()))
        self.assertEqual("derived_from_probabilities", raw["loomq_counts_source"])
        self.assertEqual(
            {"00": 0.5, "10": 0.5}, raw["measurementProbabilities"]
        )

    def test_failure_and_timeout_preserve_safe_task_id(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        failed = FakeClient(states=["FAILED"])
        with self.assertRaises(hardware.BraketHardwareJobFailed) as caught:
            hardware.run_braket_hardware(
                circuit,
                1,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=failed,
            )
        encoded = json.dumps(caught.exception.raw_record)
        self.assertIn("11111111-2222-3333-4444-555555555555", encoded)
        self.assertNotIn("123456789012", encoded)
        self.assertTrue(failed.closed)

        timed = FakeClient(states=["RUNNING"])
        clock = iter((0.0, 2.0))
        with self.assertRaisesRegex(hardware.BraketHardwareTimeout, "not cancelled"):
            hardware.run_braket_hardware(
                circuit,
                1,
                config(job_timeout_seconds=1.0),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=timed,
                monotonic=lambda: next(clock),
            )
        self.assertTrue(timed.closed)

    def test_submit_transport_failure_is_marked_ambiguous(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        fake = FakeClient()
        fake.submit = mock.Mock(
            side_effect=hardware.BraketHardwareError(
                "AWS Braket CreateQuantumTask failed"
            )
        )
        with self.assertRaises(hardware.BraketHardwareError) as caught:
            hardware.run_braket_hardware(
                circuit,
                1,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=fake,
                client_token="persisted-client-token",
            )
        self.assertEqual(
            "SUBMISSION_UNCERTAIN",
            caught.exception.raw_record["terminal_state"],
        )
        self.assertTrue(caught.exception.raw_record["submission_attempted"])

    def test_unknown_state_fails_closed(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"
        )
        fake = FakeClient(states=["MYSTERY"])
        with self.assertRaisesRegex(hardware.BraketHardwareJobFailed, "unknown state"):
            hardware.run_braket_hardware(
                circuit,
                1,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=fake,
            )

    def test_check_is_read_only(self):
        fake = FakeClient()
        report = hardware.check_braket_hardware(config(), fake)
        self.assertEqual(["get_device", "check_s3"], fake.calls)
        self.assertTrue(report["read_only_configuration_valid"])
        self.assertTrue(report["qpu_online"])
        self.assertFalse(report["paid_submission_permission_verified"])
        self.assertTrue(fake.closed)

    def test_check_rejects_bucket_in_another_region(self):
        fake = FakeClient()
        fake.check_s3 = mock.Mock(
            return_value={
                "bucket_location": "us-west-2",
                "prefix_key_count": 0,
            }
        )
        with self.assertRaisesRegex(
            hardware.BraketHardwareError, "bucket region"
        ):
            hardware.check_braket_hardware(config(), fake)
        self.assertTrue(fake.closed)

    def test_redaction_removes_aws_credentials_and_request_metadata(self):
        value = hardware.sanitize_for_json(
            {
                "profile": "private-profile",
                "ResponseMetadata": {"RequestId": "request"},
                "arn": TASK_ARN,
                "message": "key " + FAKE_AWS_ACCESS_KEY,
            }
        )
        encoded = json.dumps(value)
        for secret in (
            "private-profile",
            "request",
            "123456789012",
            FAKE_AWS_ACCESS_KEY,
        ):
            self.assertNotIn(secret, encoded)

    def test_cli_plan_is_offline_and_describes_four_tasks(self):
        output = io.StringIO()
        with mock.patch.object(
            cli.BraketHardwareConfig,
            "from_env",
            side_effect=AssertionError("credentials must not be read"),
        ), redirect_stdout(output):
            self.assertEqual(0, cli.main(["plan"]))
        self.assertIn("4 QPU tasks, 16584 shots", output.getvalue())

    def test_smoke_order_and_limit(self):
        parser = cli._parser()
        shots, names = cli._validate_args(
            parser,
            parser.parse_args(
                ["smoke", "--confirm-submit", hardware.SUBMISSION_CONFIRMATION]
            ),
        )
        self.assertEqual(100, shots)
        self.assertEqual(["bell", "bit_order"], names)
        with self.assertRaises(SystemExit):
            cli._validate_args(
                parser,
                parser.parse_args(
                    [
                        "smoke",
                        "--confirm-submit",
                        hardware.SUBMISSION_CONFIRMATION,
                        "--shots",
                        "257",
                    ]
                ),
            )

    def test_single_task_modes_require_explicit_bounded_arguments(self):
        parser = cli._parser()
        for mode in ("submit-one", "retry-prepared"):
            argv = [
                mode,
                "--circuit",
                "bit_order",
                "--shots",
                "100",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ]
            if mode == "retry-prepared":
                argv += [
                    "--prepared-receipt",
                    "braket-bit_order-0123456789abcdef0123-prepared.json",
                ]
            shots, names = cli._validate_args(parser, parser.parse_args(argv))
            self.assertEqual(100, shots)
            self.assertEqual(["bit_order"], names)

        invalid = (
            ["submit-one", "--circuit", "bit_order", "--shots", "100"],
            [
                "submit-one",
                "--circuit",
                "bit_order",
                "--shots",
                "257",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
            [
                "submit-one",
                "--circuit",
                "bell",
                "--shots",
                "8193",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
            [
                "retry-prepared",
                "--circuit",
                "bit_order",
                "--shots",
                "100",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
            [
                "retry-prepared",
                "--circuit",
                "bit_order",
                "--shots",
                "100",
                "--client-token",
                "not-accepted",
                "--prepared-receipt",
                "braket-bit_order-0123456789abcdef0123-prepared.json",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
        )
        for argv in invalid:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli._validate_args(parser, parser.parse_args(argv))

    def test_single_task_cli_dispatches_one_item_without_exposed_token(self):
        base = [
            "--circuit",
            "bit_order",
            "--shots",
            "100",
            "--confirm-submit",
            hardware.SUBMISSION_CONFIRMATION,
        ]
        with mock.patch.object(
            cli.BraketHardwareConfig, "from_env", return_value=config()
        ), mock.patch.object(cli, "_execute", return_value=0) as execute:
            self.assertEqual(0, cli.main(["submit-one"] + base))
        self.assertEqual(["bit_order"], execute.call_args.args[0])
        self.assertEqual(100, execute.call_args.args[1])
        self.assertIsNone(execute.call_args.kwargs["retry_prepared_name"])

        receipt_name = "braket-bit_order-0123456789abcdef0123-prepared.json"
        with mock.patch.object(
            cli.BraketHardwareConfig, "from_env", return_value=config()
        ), mock.patch.object(cli, "_execute", return_value=0) as execute:
            self.assertEqual(
                0,
                cli.main(
                    ["retry-prepared"]
                    + base
                    + ["--prepared-receipt", receipt_name]
                ),
            )
        self.assertEqual(["bit_order"], execute.call_args.args[0])
        self.assertEqual(receipt_name, execute.call_args.kwargs["retry_prepared_name"])
        self.assertIsNone(execute.call_args.kwargs["resume_client_token"])

    def test_all_local_preflights_finish_before_submission(self):
        events = []
        archived = []

        def preflight(name, _circuit, shots):
            events.append("local:" + name)
            return {"shots": shots}

        def remote(circuit, shots, _config, **_kwargs):
            name = "bit_order" if circuit.qubit_count == 3 else "bell"
            events.append("remote:" + name)
            counts = (
                {"011": shots}
                if name == "bit_order"
                else {"00": shots // 2, "11": shots - shots // 2}
            )
            return hardware.BraketHardwareRun(
                "OPENQASM 3.0;\n",
                {"job_id": name},
                {"job_id": name, "shots": shots, "counts": counts},
            )

        def bundle(_output_dir, name, _qasm2, run):
            archived.append((name, run.summary["local_preflight"]))
            return {"summary": "summary"}

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            cli, "_run_local_preflight", side_effect=preflight
        ), mock.patch.object(
            cli, "run_braket_hardware", side_effect=remote
        ), mock.patch.object(cli, "_write_bundle", side_effect=bundle):
            root = Path(directory)
            self.assertEqual(
                0,
                cli._execute(
                    ["bell", "bit_order"],
                    100,
                    root / "public",
                    config(),
                    receipt_dir=root / "private",
                ),
            )
        self.assertEqual(
            ["local:bell", "local:bit_order", "remote:bell", "remote:bit_order"],
            events,
        )
        self.assertEqual(
            [("bell", {"shots": 100}), ("bit_order", {"shots": 100})],
            archived,
        )

    def test_evidence_bundle_is_exclusive(self):
        run = hardware.BraketHardwareRun(
            "OPENQASM 3.0;\n",
            {"job_id": "task"},
            {"job_id": "task", "shots": 1, "counts": {"011": 1}},
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            paths = cli._write_bundle(target, "bit_order", "OPENQASM 2.0;\n", run)
            original = paths["qasm"].read_text(encoding="utf-8")
            with self.assertRaises(FileExistsError):
                cli._write_bundle(target, "bit_order", "changed", run)
            self.assertEqual(original, paths["qasm"].read_text(encoding="utf-8"))

    def test_exclusive_text_and_json_partial_writes_are_removed(self):
        class FailingTextHandle:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def write(self, _text):
                raise OSError("injected text write failure")

        class FakePath:
            def __init__(self):
                self.unlinked = False

            def open(self, *_args, **_kwargs):
                return FailingTextHandle()

            def unlink(self, *, missing_ok=False):
                self.unlinked = missing_ok

        fake_path = FakePath()
        with self.assertRaisesRegex(OSError, "injected text"):
            cli._write_text_exclusive(fake_path, "OPENQASM 2.0;\n")
        self.assertTrue(fake_path.unlinked)

        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory, "partial.json")

            def fail_after_partial(payload, handle, **kwargs):
                handle.write("{partial")
                raise OSError("injected JSON write failure")

            with mock.patch.object(json, "dump", side_effect=fail_after_partial):
                with self.assertRaisesRegex(OSError, "injected JSON"):
                    hardware.write_json(
                        json_path, {"safe": True}, exclusive=True
                    )
            self.assertFalse(json_path.exists())

            json_path.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                hardware.write_json(
                    json_path, {"safe": True}, exclusive=True
                )
            self.assertEqual("original", json_path.read_text(encoding="utf-8"))

    def test_evidence_job_id_preserves_legitimate_twelve_digit_segment(self):
        task_id = "11111111-2222-3333-4444-123456789012"
        run = hardware.BraketHardwareRun(
            "OPENQASM 3.0;\n",
            {"job_id": task_id},
            {"job_id": task_id, "shots": 1, "counts": {"011": 1}},
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = cli._write_bundle(
                Path(directory), "bit_order", "OPENQASM 2.0;\n", run
            )
            raw = json.loads(paths["raw"].read_text(encoding="utf-8"))
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
        self.assertEqual(task_id, raw["job_id"])
        self.assertEqual(task_id, summary["job_id"])

    def test_private_receipts_are_isolated_from_custom_public_output(self):
        task_id = "11111111-2222-3333-4444-555555555555"

        def preflight(name, _circuit, shots):
            return {"backend": "local", "name": name, "shots": shots}

        def remote(_circuit, _shots, _config, **kwargs):
            kwargs["on_submitted"](task_id)
            raise hardware.BraketHardwareError(
                "AWS Braket S3 result download failed",
                {
                    "job_id": task_id,
                    "terminal_state": "CLIENT_ERROR",
                    "downloaded_result": {
                        "json": {
                            "task": TASK_ARN,
                            "key": FAKE_AWS_ACCESS_KEY,
                        }
                    },
                },
            )

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            cli, "_run_local_preflight", side_effect=preflight
        ), mock.patch.object(
            cli, "run_braket_hardware", side_effect=remote
        ), redirect_stdout(stdout):
            root = Path(directory)
            target = root / "custom-public-evidence"
            private = root / "fixed-private-state"
            with self.assertRaises(hardware.BraketHardwareError):
                cli._execute(
                    ["bit_order"],
                    1,
                    target,
                    config(),
                    receipt_dir=private,
                )
            prepared = list(private.glob("*-prepared.json"))
            submitted = list(private.glob("*-submitted.json"))
            failures = list(target.glob("*-failure.json"))
            self.assertEqual(1, len(prepared))
            self.assertEqual(1, len(submitted))
            self.assertEqual(1, len(failures))
            self.assertEqual([], list(target.glob("*-prepared.json")))
            self.assertEqual([], list(target.glob("*-submitted.json")))
            prepared_data = json.loads(prepared[0].read_text(encoding="utf-8"))
            submitted_data = json.loads(submitted[0].read_text(encoding="utf-8"))
            failure_data = json.loads(failures[0].read_text(encoding="utf-8"))
            self.assertEqual(
                prepared_data["clientToken"], submitted_data["clientToken"]
            )
            self.assertEqual(task_id, submitted_data["job_id"])
            self.assertEqual(task_id, failure_data["job_id"])
            self.assertEqual(task_id, failure_data["raw_record"]["job_id"])
            public_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            )
            self.assertNotIn(prepared_data["clientToken"], public_text)
            self.assertNotIn("clientToken", public_text)
            with self.assertRaises(FileExistsError):
                cli._write_failure_evidence(
                    target,
                    "bit_order",
                    "OPENQASM 2.0;\n",
                    "OPENQASM 3.0;\n",
                    hardware.BraketHardwareError(
                        "second", {"job_id": task_id}
                    ),
                    {"backend": "local"},
                )
        output = stdout.getvalue()
        self.assertNotIn(TASK_ARN, output)
        self.assertNotIn("123456789012", output)
        self.assertNotIn("loomq-braket", output)
        self.assertNotIn("loomq-private-results", output)
        encoded_failure = json.dumps(failure_data)
        self.assertNotIn("123456789012", encoded_failure)
        self.assertNotIn(FAKE_AWS_ACCESS_KEY, encoded_failure)

    def test_retry_prepared_reuses_token_and_submits_exactly_once(self):
        task_id = "11111111-2222-3333-4444-555555555555"
        observed = []

        def remote(circuit, shots, _config, **kwargs):
            observed.append(
                {
                    "token": kwargs["client_token"],
                    "confirmation": kwargs["confirmation"],
                    "resume": kwargs["resume_task_arn"],
                }
            )
            kwargs["on_submitted"](task_id)
            return hardware.BraketHardwareRun(
                cli.emit_braket_executable(circuit),
                {"job_id": task_id},
                {"job_id": task_id, "shots": shots, "counts": {"011": shots}},
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private"
            path, token, qasm3, request_sha256 = prepared_receipt(private)
            with mock.patch.object(
                cli,
                "_run_local_preflight",
                return_value={"backend": "local"},
            ), mock.patch.object(
                cli, "run_braket_hardware", side_effect=remote
            ), mock.patch.object(cli, "_write_bundle", return_value={}):
                self.assertEqual(
                    0,
                    cli._execute(
                        ["bit_order"],
                        100,
                        root / "public",
                        config(),
                        retry_prepared_name=path.name,
                        receipt_dir=private,
                    ),
                )
            self.assertEqual(1, len(observed))
            self.assertEqual(token, observed[0]["token"])
            self.assertEqual(hardware.SUBMISSION_CONFIRMATION, observed[0]["confirmation"])
            self.assertIsNone(observed[0]["resume"])
            self.assertEqual(1, len(list(private.glob("*-prepared.json"))))
            submitted = list(private.glob("*-submitted.json"))
            self.assertEqual(1, len(submitted))
            submitted_payload = json.loads(submitted[0].read_text(encoding="utf-8"))
            self.assertEqual(request_sha256, submitted_payload["request_sha256"])
            self.assertEqual(token, submitted_payload["clientToken"])

            with self.assertRaises(FileExistsError):
                cli._write_submitted_receipt(
                    private,
                    "bit_order",
                    100,
                    qasm3,
                    token,
                    task_id,
                    request_sha256,
                )

    def test_retry_prepared_accepts_identical_existing_submitted_receipt_only(self):
        task_id = "11111111-2222-3333-4444-555555555555"

        def remote(circuit, shots, _config, **kwargs):
            kwargs["on_submitted"](task_id)
            return hardware.BraketHardwareRun(
                cli.emit_braket_executable(circuit),
                {"job_id": task_id},
                {"job_id": task_id, "shots": shots, "counts": {"011": shots}},
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private"
            prepared, _token, _qasm3, _request_sha256 = prepared_receipt(private)
            patches = (
                mock.patch.object(
                    cli,
                    "_run_local_preflight",
                    return_value={"backend": "local"},
                ),
                mock.patch.object(cli, "run_braket_hardware", side_effect=remote),
                mock.patch.object(cli, "_write_bundle", return_value={}),
            )
            with patches[0], patches[1], patches[2]:
                for _ in range(2):
                    self.assertEqual(
                        0,
                        cli._execute(
                            ["bit_order"],
                            100,
                            root / "public",
                            config(),
                            retry_prepared_name=prepared.name,
                            receipt_dir=private,
                        ),
                    )
            submitted = next(private.glob("*-submitted.json"))
            payload = json.loads(submitted.read_text(encoding="utf-8"))
            payload["request_sha256"] = "0" * 64
            submitted.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(
                cli,
                "_run_local_preflight",
                return_value={"backend": "local"},
            ), mock.patch.object(
                cli, "run_braket_hardware", side_effect=remote
            ), mock.patch.object(cli, "_write_bundle", return_value={}):
                with self.assertRaisesRegex(
                    hardware.BraketHardwareError, "SUBMITTED receipt"
                ):
                    cli._execute(
                        ["bit_order"],
                        100,
                        root / "public",
                        config(),
                        retry_prepared_name=prepared.name,
                        receipt_dir=private,
                    )

    def test_retry_submitted_fingerprint_cannot_move_to_a_different_task(self):
        task_a = "aaaaaaaa-2222-3333-4444-555555555555"
        task_b = "bbbbbbbb-2222-3333-4444-555555555555"
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            _prepared, token, qasm3, request_sha256 = prepared_receipt(private)
            first = cli._write_submitted_receipt(
                private,
                "bit_order",
                100,
                qasm3,
                token,
                task_a,
                request_sha256,
            )
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "different task"
            ):
                cli._write_submitted_receipt(
                    private,
                    "bit_order",
                    100,
                    qasm3,
                    token,
                    task_b,
                    request_sha256,
                    allow_existing=True,
                )
            submitted = list(private.glob("*-submitted.json"))
            self.assertEqual([first], submitted)
            self.assertFalse(
                (private / ("braket-bit_order-%s-submitted.json" % task_b)).exists()
            )

    def test_retry_client_token_cannot_move_between_circuits(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            token = "same-client-token"
            bell_qasm3 = cli.emit_braket_executable(
                loomq_l1.parse_qasm(
                    cli.CIRCUITS["bell"].read_text(encoding="utf-8")
                )
            )
            bit_order_qasm3 = cli.emit_braket_executable(
                loomq_l1.parse_qasm(
                    cli.CIRCUITS["bit_order"].read_text(encoding="utf-8")
                )
            )
            first = cli._write_submitted_receipt(
                private,
                "bell",
                100,
                bell_qasm3,
                token,
                "task-a",
                cli._request_sha256(config(), 100, bell_qasm3, token),
            )
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "different task"
            ):
                cli._write_submitted_receipt(
                    private,
                    "bit_order",
                    100,
                    bit_order_qasm3,
                    token,
                    "task-b",
                    cli._request_sha256(
                        config(), 100, bit_order_qasm3, token
                    ),
                    allow_existing=True,
                )
            self.assertEqual([first], list(private.glob("*-submitted.json")))

    def test_private_receipt_duplicate_keys_and_schema_v1_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            path, _token, qasm3, _request_sha256 = prepared_receipt(private)
            text = path.read_text(encoding="utf-8")
            marker = '"clientToken": "retry-token-123"'
            self.assertIn(marker, text)
            path.write_text(
                text.replace(marker, marker + ",\n  " + marker),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "invalid"
            ):
                cli._load_prepared_receipt(
                    private,
                    path.name,
                    "bit_order",
                    100,
                    qasm3,
                    config(),
                )

        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            path, _token, qasm3, _request_sha256 = prepared_receipt(private)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["schema_version"] = 1
            payload.pop("request_sha256")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "schema"
            ):
                cli._load_prepared_receipt(
                    private,
                    path.name,
                    "bit_order",
                    100,
                    qasm3,
                    config(),
                )

    def test_private_root_and_parent_reparse_fail_before_submission(self):
        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("paid submission must not be reached")

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            outside = base / "outside"
            outside.mkdir()
            for receipt_dir, reparse_path in (
                (base / "private-root", base / "private-root"),
                (base / "linked-parent" / "braket", base / "linked-parent"),
            ):
                with self.subTest(receipt_dir=receipt_dir), mock.patch.object(
                    cli,
                    "_path_is_reparse",
                    side_effect=lambda path, blocked=reparse_path: Path(path) == blocked,
                ), mock.patch.object(
                    cli, "run_braket_hardware", side_effect=fail_if_called
                ) as remote:
                    with self.assertRaisesRegex(
                        hardware.BraketHardwareError, "reparse"
                    ):
                        cli._execute(
                            ["bit_order"],
                            100,
                            base / "public",
                            config(),
                            receipt_dir=receipt_dir,
                        )
                    remote.assert_not_called()
            self.assertEqual([], list(outside.iterdir()))

        fake_metadata = mock.Mock(
            st_mode=stat.S_IFDIR,
            st_file_attributes=getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
            ),
        )
        with mock.patch.object(cli.os, "lstat", return_value=fake_metadata):
            self.assertTrue(cli._path_is_reparse(Path("junction")))

    def test_prepared_receipt_rejects_hash_identity_escape_symlink_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private"
            path, token, qasm3, _request_sha256 = prepared_receipt(private)
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "does not match"
            ):
                cli._load_prepared_receipt(
                    private,
                    path.name,
                    "bit_order",
                    100,
                    qasm3 + "\n",
                    config(),
                )
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "does not match"
            ):
                cli._load_prepared_receipt(
                    private,
                    path.name,
                    "bit_order",
                    100,
                    qasm3,
                    config(profile="another-profile"),
                )
            with self.assertRaisesRegex(
                hardware.BraketHardwareError, "filename"
            ):
                cli._load_prepared_receipt(
                    private,
                    "../" + path.name,
                    "bit_order",
                    100,
                    qasm3,
                    config(),
                )

            large_name = "braket-bit_order-%s-prepared.json" % ("a" * 20)
            (private / large_name).write_bytes(b"x" * (cli.MAX_PRIVATE_RECEIPT_BYTES + 1))
            with self.assertRaisesRegex(hardware.BraketHardwareError, "size"):
                cli._load_prepared_receipt(
                    private,
                    large_name,
                    "bit_order",
                    100,
                    qasm3,
                    config(),
                )

            link_name = "braket-bit_order-%s-prepared.json" % ("b" * 20)
            outside = root / "outside.json"
            outside.write_bytes(path.read_bytes())
            link = private / link_name
            try:
                link.symlink_to(outside)
            except OSError:
                pass
            else:
                with self.assertRaisesRegex(
                    hardware.BraketHardwareError, "reparse point"
                ):
                    cli._load_prepared_receipt(
                        private,
                        link_name,
                        "bit_order",
                        100,
                        qasm3,
                        config(),
                    )

            canonical = cli._canonical_create_request(config(), 100, qasm3, token)
            self.assertEqual(config().profile, canonical["_localAwsProfile"])
            self.assertEqual(config().region, canonical["_localAwsRegion"])
            self.assertEqual("{}", canonical["deviceParameters"])
            self.assertEqual(
                "loomq/l1/tasks/%s" % token,
                canonical["outputS3KeyPrefix"],
            )

    def test_ambiguous_submission_failure_still_writes_failure_evidence(self):
        def preflight(name, _circuit, shots):
            return {"backend": "local", "name": name, "shots": shots}

        def remote(_circuit, _shots, _config, **_kwargs):
            raise hardware.BraketHardwareError(
                "AWS Braket CreateQuantumTask failed",
                {
                    "submission_attempted": True,
                    "terminal_state": "SUBMISSION_UNCERTAIN",
                },
            )

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            cli, "_run_local_preflight", side_effect=preflight
        ), mock.patch.object(
            cli, "run_braket_hardware", side_effect=remote
        ):
            root = Path(directory)
            target = root / "public"
            with self.assertRaises(hardware.BraketHardwareError):
                cli._execute(
                    ["bell"],
                    1,
                    target,
                    config(),
                    receipt_dir=root / "private",
                )
            failures = list(target.glob("*-failure.json"))
            self.assertEqual(1, len(failures))
            failure = json.loads(failures[0].read_text(encoding="utf-8"))
        self.assertIsNone(failure["job_id"])
        self.assertEqual(
            "SUBMISSION_UNCERTAIN",
            failure["raw_record"]["terminal_state"],
        )

    def test_resume_cli_validation_requires_recovery_fields(self):
        parser = cli._parser()
        args = parser.parse_args(
            [
                "resume",
                "--task-arn",
                TASK_ARN,
                "--client-token",
                "persisted-client-token",
                "--circuit",
                "bell",
                "--shots",
                "8192",
            ]
        )
        shots, names = cli._validate_args(parser, args)
        self.assertEqual(8192, shots)
        self.assertEqual(["bell"], names)
        help_text = parser.format_help()
        self.assertIn("smoke defaults to 100", help_text)
        self.assertIn("formal is fixed at 8192", help_text)
        self.assertIn("resume requires the original", help_text)

    def test_default_private_receipt_directory_is_ignored_and_not_configurable(self):
        self.assertEqual(
            Path(cli.HERE) / ".hardware-private" / "braket",
            cli.PRIVATE_RECEIPT_DIR,
        )
        root_ignore = (Path(ROOT) / ".gitignore").read_text(encoding="utf-8")
        docker_ignore = (Path(ROOT) / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn(".hardware-private/", root_ignore)
        self.assertIn(".hardware-private/", docker_ignore)
        self.assertNotIn("--receipt-dir", cli._parser().format_help())


if __name__ == "__main__":
    unittest.main()
