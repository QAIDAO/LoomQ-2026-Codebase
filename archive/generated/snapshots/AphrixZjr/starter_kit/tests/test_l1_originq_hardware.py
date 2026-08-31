import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT
sys.path.insert(0, str(STARTER))

import l1_originq_hardware as hardware
import run_originq_hardware as hardware_cli
from loomq_l1 import emit_originq, parse_qasm


BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeClient:
    def __init__(self, responses, job_id="ORIGIN-JOB-1"):
        self.responses = list(responses)
        self.job_id = job_id
        self.submissions = []
        self.attachments = []
        self.polls = []
        self.closed = False

    def submit(self, origin_ir, shots, task_name):
        self.submissions.append((origin_ir, shots, task_name))
        return self.job_id

    def attach(self, job_id):
        self.attachments.append(job_id)
        return job_id

    def poll(self, job_id):
        self.polls.append(job_id)
        if not self.responses:
            raise AssertionError("fake response queue exhausted")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        self.closed = True


def config(**updates):
    values = {
        "token": "private-test-token",
        "chip_id": "WK_C180",
        "poll_interval_seconds": 2.0,
        "job_timeout_seconds": 20.0,
    }
    values.update(updates)
    return hardware.OriginQHardwareConfig(**values)


class OriginQHardwareConfigTests(unittest.TestCase):
    def test_reads_documented_environment_fields_without_exposing_token(self):
        env = {
            hardware.TOKEN_ENV: "secret-value",
            hardware.CHIP_ID_ENV: "WK_C180",
            hardware.QCLOUD_URL_ENV: "https://qcloud.example.test/api/",
            hardware.POLL_INTERVAL_ENV: "1.5",
            hardware.JOB_TIMEOUT_ENV: "60",
            hardware.IS_AMEND_ENV: "false",
            hardware.IS_MAPPING_ENV: "true",
            hardware.IS_OPTIMIZATION_ENV: "0",
        }
        loaded = hardware.OriginQHardwareConfig.from_env(env)
        self.assertEqual(loaded.token, "secret-value")
        self.assertEqual(loaded.chip_id, "WK_C180")
        self.assertEqual(loaded.qcloud_url, "https://qcloud.example.test/api")
        self.assertFalse(loaded.is_amend)
        self.assertTrue(loaded.is_mapping)
        self.assertFalse(loaded.is_optimization)
        self.assertNotIn("secret-value", repr(loaded))

    def test_rejects_missing_credentials_and_unsafe_url(self):
        with self.assertRaisesRegex(ValueError, hardware.CHIP_ID_ENV):
            hardware.OriginQHardwareConfig.from_env({hardware.TOKEN_ENV: "x"})
        with self.assertRaisesRegex(ValueError, hardware.TOKEN_ENV):
            hardware.OriginQHardwareConfig.from_env(
                {hardware.TOKEN_ENV: "", hardware.CHIP_ID_ENV: "72"}
            )
        with self.assertRaisesRegex(ValueError, "HTTPS URL"):
            config(qcloud_url="http://qcloud.example.test")

    def test_uses_forced_https_default_and_rejects_invalid_backend_name(self):
        loaded = hardware.OriginQHardwareConfig.from_env(
            {
                hardware.TOKEN_ENV: "secret-value",
                hardware.CHIP_ID_ENV: "WK_C180",
            }
        )
        self.assertEqual(hardware.DEFAULT_QCLOUD_URL, loaded.qcloud_url)
        with self.assertRaisesRegex(ValueError, "backend name"):
            config(chip_id="../WK_C180")


class OriginQHardwareStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.circuit = parse_qasm(BELL)
        self.now = lambda: datetime(2026, 8, 3, 1, 2, 3, tzinfo=timezone.utc)

    def test_waits_computes_and_normalizes_finished_probabilities(self):
        client = FakeClient(
            [
                [1, None],
                [2, None],
                [3, json.dumps({"00": 0.5, "11": 0.5})],
            ]
        )
        clock = FakeClock()
        submitted = []
        result = hardware.run_originq_hardware(
            self.circuit,
            101,
            config(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            task_name="LoomQ-test-bell",
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            now=self.now,
            on_submitted=submitted.append,
        )
        self.assertEqual(result.summary["counts"], {"00": 51, "11": 50})
        self.assertEqual(result.summary["job_id"], "ORIGIN-JOB-1")
        self.assertEqual(result.raw_record["terminal_state"], "FINISHED")
        self.assertEqual(
            client.submissions,
            [(emit_originq(self.circuit), 101, "LoomQ-test-bell")],
        )
        self.assertEqual(client.polls, ["ORIGIN-JOB-1"] * 3)
        self.assertEqual(submitted, ["ORIGIN-JOB-1"])
        self.assertTrue(client.closed)

    def test_terminal_failure_is_redacted_and_closes_client(self):
        secret = "private-test-token"
        client = FakeClient([[4, None, "token=%s account_id=123" % secret]])
        with self.assertRaises(hardware.OriginQHardwareJobFailed) as caught:
            hardware.run_originq_hardware(
                self.circuit,
                10,
                config(token=secret),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=client,
                now=self.now,
            )
        message = str(caught.exception)
        serialized = json.dumps(caught.exception.raw_record)
        self.assertNotIn(secret, message + serialized)
        self.assertNotIn("account_id=123", message + serialized)
        self.assertIn("[REDACTED]", message)
        self.assertTrue(client.closed)

    def test_four_field_failure_uses_documented_error_info(self):
        client = FakeClient([[4, None, 5001, "device calibration failed"]])
        with self.assertRaises(hardware.OriginQHardwareJobFailed) as caught:
            hardware.run_originq_hardware(
                self.circuit,
                10,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=client,
                now=self.now,
            )
        self.assertIn("device calibration failed", str(caught.exception))
        self.assertNotIn(": 5001", str(caught.exception))

    def test_times_out_with_last_state_and_closes_client(self):
        client = FakeClient([[1, None], [2, None], [5, None]])
        clock = FakeClock()
        with self.assertRaises(hardware.OriginQHardwareTimeout) as caught:
            hardware.run_originq_hardware(
                self.circuit,
                10,
                config(job_timeout_seconds=4.0, poll_interval_seconds=2.0),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=client,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
                now=self.now,
            )
        self.assertEqual(caught.exception.raw_record["terminal_state"], "TIMEOUT")
        self.assertEqual(caught.exception.raw_record["last_remote_state"], "QUEUING")
        self.assertTrue(client.closed)

    def test_retries_transient_status_queries_without_resubmitting(self):
        transient = hardware.OriginQHardwareStatusQueryError("temporary")
        client = FakeClient(
            [transient, transient, {"status": "FINISHED", "result": {"00": 1.0}}]
        )
        clock = FakeClock()
        result = hardware.run_originq_hardware(
            self.circuit,
            10,
            config(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            now=self.now,
        )
        self.assertEqual(result.summary["counts"], {"00": 10})
        self.assertEqual(result.raw_record["status_query_retries"], 2)
        self.assertEqual(len(client.submissions), 1)
        self.assertEqual(len(client.polls), 3)

    def test_resume_attaches_to_existing_job_without_submitting(self):
        client = FakeClient(
            [{"status": "FINISHED", "result": {"00": 0.5, "11": 0.5}}],
            job_id="EXISTING-JOB-9",
        )
        result = hardware.resume_originq_hardware(
            self.circuit,
            10,
            config(),
            job_id="EXISTING-JOB-9",
            client=client,
            now=self.now,
        )
        self.assertEqual([], client.submissions)
        self.assertEqual(["EXISTING-JOB-9"], client.attachments)
        self.assertEqual(["EXISTING-JOB-9"], client.polls)
        self.assertTrue(result.raw_record["resume_only"])
        self.assertNotIn("submitted_at", result.raw_record)
        self.assertTrue(result.summary["meta"]["resumed"])

    def test_retries_result_queries_without_resubmitting(self):
        transient = hardware.OriginQHardwareResultQueryError("temporary")
        client = FakeClient(
            [transient, transient, {"status": "FINISHED", "result": {"00": 1.0}}]
        )
        clock = FakeClock()
        result = hardware.run_originq_hardware(
            self.circuit,
            10,
            config(),
            confirmation=hardware.SUBMISSION_CONFIRMATION,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            now=self.now,
        )
        self.assertEqual({"00": 10}, result.summary["counts"])
        self.assertEqual(2, result.raw_record["result_query_retries"])
        self.assertEqual(1, len(client.submissions))

    def test_status_query_retries_are_bounded_and_never_resubmit(self):
        client = FakeClient(
            [
                hardware.OriginQHardwareStatusQueryError("temporary")
                for _ in range(hardware.STATUS_QUERY_RETRY_LIMIT + 1)
            ]
        )
        clock = FakeClock()
        with self.assertRaises(hardware.OriginQHardwareStatusQueryError) as caught:
            hardware.run_originq_hardware(
                self.circuit,
                10,
                config(),
                confirmation=hardware.SUBMISSION_CONFIRMATION,
                client=client,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
                now=self.now,
            )
        self.assertEqual(len(client.submissions), 1)
        self.assertEqual(
            len(client.polls), hardware.STATUS_QUERY_RETRY_LIMIT + 1
        )
        self.assertEqual(
            caught.exception.raw_record["status_query_retries"],
            hardware.STATUS_QUERY_RETRY_LIMIT,
        )

    def test_rejects_unknown_state_and_malformed_result(self):
        for response in ([99, None], [3, {"not-counts": "bad"}]):
            with self.subTest(response=response):
                client = FakeClient([response])
                with self.assertRaises(hardware.OriginQHardwareError) as caught:
                    hardware.run_originq_hardware(
                        self.circuit,
                        10,
                        config(),
                        confirmation=hardware.SUBMISSION_CONFIRMATION,
                        client=client,
                        now=self.now,
                    )
                self.assertEqual(
                    caught.exception.raw_record["job_id"], "ORIGIN-JOB-1"
                )
                self.assertTrue(client.closed)


class PyQPandaQCloudClientTests(unittest.TestCase):
    class Status:
        def __init__(self, name, value):
            self.name = name
            self.value = value

    class Result:
        def __init__(self):
            self.calls = []

        def get_probs(self):
            self.calls.append(("get_probs",))
            return {"00": 0.5, "11": 0.5}

        def origin_data(self):
            self.calls.append(("origin_data",))
            return json.dumps({"task": {"state": "3"}, "token": "secret"})

    class Job:
        def __init__(self, statuses, result):
            self.statuses = list(statuses)
            self.cloud_result = result
            self.calls = []

        def job_id(self):
            self.calls.append(("job_id",))
            return "SDK-JOB"

        def status(self):
            self.calls.append(("status",))
            return self.statuses.pop(0)

        def result(self):
            self.calls.append(("result",))
            return self.cloud_result

    class Options:
        def __init__(self):
            self.calls = []

        def set_amend(self, value):
            self.calls.append(("amend", value))

        def set_mapping(self, value):
            self.calls.append(("mapping", value))

        def set_optimization(self, value):
            self.calls.append(("optimization", value))

    class Backend:
        def __init__(self, job):
            self.job = job
            self.calls = []

        def run(self, *args):
            self.calls.append(("run", args))
            return self.job

    class Service:
        def __init__(self, backend):
            self.backend_value = backend
            self.calls = []

        def backend(self, name):
            self.calls.append(("backend", name))
            return self.backend_value

    class SDK:
        def __init__(self, service, options):
            self.service = service
            self.options = options
            self.service_arguments = []
            self.attached_job_ids = []
            self.converted = []

        def QCloudService(self, *args):
            self.service_arguments.append(args)
            return self.service

        def QCloudOptions(self):
            return self.options

        def QCloudJob(self, job_id):
            self.attached_job_ids.append(job_id)
            return self.service.backend_value.job

        def convert_originir_string_to_qprog(self, origin_ir):
            self.converted.append(origin_ir)
            return "PROGRAM"

    def test_uses_pinned_pyqpanda3_qcloud_contract(self):
        waiting = self.Status("WAITING", 1)
        finished = self.Status("FINISHED", 3)
        cloud_result = self.Result()
        job = self.Job([waiting, finished], cloud_result)
        options = self.Options()
        backend = self.Backend(job)
        service = self.Service(backend)
        sdk = self.SDK(service, options)
        cfg = config(qcloud_url="https://qcloud.example.test")
        client = hardware.PyQPandaQCloudClient(cfg, sdk=sdk)
        job_id = client.submit("QINIT 1\nCREG 1\n", 32, "LoomQ-test")
        attached_job_id = client.attach(job_id)
        pending = client.poll(job_id)
        response = client.poll(job_id)
        client.close()
        self.assertEqual(job_id, "SDK-JOB")
        self.assertEqual(attached_job_id, "SDK-JOB")
        self.assertEqual(sdk.attached_job_ids, ["SDK-JOB"])
        self.assertIs(pending["status"], waiting)
        self.assertNotIn("result", pending)
        self.assertEqual(response["result"], {"00": 0.5, "11": 0.5})
        self.assertEqual(
            sdk.service_arguments,
            [(cfg.token, "https://qcloud.example.test")],
        )
        self.assertEqual(service.calls, [("backend", "WK_C180")])
        self.assertEqual(
            options.calls,
            [("amend", True), ("mapping", True), ("optimization", True)],
        )
        self.assertEqual(sdk.converted, ["QINIT 1\nCREG 1\n"])
        self.assertEqual(backend.calls, [("run", ("PROGRAM", 32, options))])
        self.assertEqual(job.calls.count(("status",)), 2)
        self.assertEqual(job.calls.count(("result",)), 1)
        self.assertIsInstance(response["origin_data"], dict)
        self.assertEqual(response["origin_data"]["task"]["state"], "3")
        self.assertEqual(client.jobs, {})

        fresh_job = self.Job([finished], self.Result())
        fresh_backend = self.Backend(fresh_job)
        fresh_service = self.Service(fresh_backend)
        fresh_sdk = self.SDK(fresh_service, self.Options())
        fresh_client = hardware.PyQPandaQCloudClient(cfg, sdk=fresh_sdk)
        self.assertEqual("SDK-JOB", fresh_client.attach("SDK-JOB"))
        self.assertEqual([], fresh_service.calls)
        self.assertEqual([], fresh_backend.calls)
        self.assertEqual(["SDK-JOB"], fresh_sdk.attached_job_ids)
        fresh_client.close()

    def test_pyqpanda3_cpuqvm_preflight_uses_originir_converter(self):
        class LocalResult:
            def get_counts(self):
                return {"00": 5, "11": 5}

        class LocalMachine:
            def __init__(self):
                self.calls = []

            def run(self, program, shots):
                self.calls.append((program, shots))

            def result(self):
                return LocalResult()

        class LocalSDK:
            def __init__(self):
                self.machine = LocalMachine()
                self.converted = []

            def convert_originir_string_to_qprog(self, origin_ir):
                self.converted.append(origin_ir)
                return "PROGRAM"

            def CPUQVM(self):
                return self.machine

        sdk = LocalSDK()
        circuit = parse_qasm(BELL)
        counts, backend, _job_id, meta = hardware.run_pyqpanda3_cpuqvm(
            circuit, 10, sdk=sdk
        )
        self.assertEqual(counts, {"00": 5, "11": 5})
        self.assertEqual(backend, "originq-pyqpanda3-cpuqvm")
        self.assertEqual(meta["engine"], "pyqpanda3 0.4.0 CPUQVM")
        self.assertEqual(sdk.converted, [emit_originq(circuit)])
        self.assertEqual(sdk.machine.calls, [("PROGRAM", 10)])

    def test_qcloud_result_retrieval_failure_is_retryable(self):
        finished = self.Status("FINISHED", 3)

        class FailingJob(self.Job):
            def result(self):
                self.calls.append(("result",))
                raise OSError("temporary result transport failure")

        job = FailingJob([finished], self.Result())
        options = self.Options()
        backend = self.Backend(job)
        sdk = self.SDK(self.Service(backend), options)
        client = hardware.PyQPandaQCloudClient(config(), sdk=sdk)
        job_id = client.submit("QINIT 1\nCREG 1\n", 32, "LoomQ-test")
        with self.assertRaises(hardware.OriginQHardwareResultQueryError):
            client.poll(job_id)
        self.assertEqual(1, len(backend.calls))


class OriginQHardwareSafetyTests(unittest.TestCase):
    def test_core_submission_requires_exact_confirmation(self):
        circuit = parse_qasm(BELL)
        client = FakeClient([[3, {"00": 1.0}]])
        with self.assertRaisesRegex(hardware.OriginQHardwareError, "confirmation"):
            hardware.run_originq_hardware(
                circuit,
                10,
                config(),
                confirmation="wrong",
                client=client,
            )
        self.assertEqual([], client.submissions)

    def test_local_preflight_completes_before_cloud_submission(self):
        events = []
        run = hardware.OriginQHardwareRun(
            origin_ir="QINIT 2\nCREG 2\n",
            raw_record={"job_id": "job-one", "terminal_state": "FINISHED"},
            summary={
                "backend": "originq-qcloud-WK_C180",
                "job_id": "job-one",
                "shots": 10,
                "counts": {"00": 5, "11": 5},
                "bit_order": "little",
                "timestamp": "2026-08-03T01:02:03+00:00",
            },
        )
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            hardware_cli.OriginQHardwareConfig,
            "from_env",
            return_value=config(),
        ), mock.patch.object(
            hardware_cli,
            "_run_local_preflight",
            side_effect=lambda *args: events.append("local") or {"counts": {}},
        ), mock.patch.object(
            hardware_cli,
            "run_originq_hardware",
            side_effect=lambda *args, **kwargs: events.append("cloud") or run,
        ) as cloud:
            status = hardware_cli._execute(
                ["bell"], 10, Path(temp), "LoomQ-test"
            )
        self.assertEqual(0, status)
        self.assertEqual(["local", "cloud"], events)
        self.assertEqual(
            hardware.SUBMISSION_CONFIRMATION,
            cloud.call_args.kwargs["confirmation"],
        )

    def test_failed_local_preflight_prevents_cloud_submission(self):
        with mock.patch.object(
            hardware_cli.OriginQHardwareConfig,
            "from_env",
            return_value=config(),
        ), mock.patch.object(
            hardware_cli,
            "_run_local_preflight",
            side_effect=RuntimeError("local failed"),
        ), mock.patch.object(hardware_cli, "run_originq_hardware") as cloud:
            with self.assertRaisesRegex(RuntimeError, "local failed"):
                hardware_cli._execute(
                    ["bell"], 10, Path("unused"), "LoomQ-test"
                )
        cloud.assert_not_called()

    def test_recursive_json_sanitization(self):
        token = "secret-token"
        raw = {
            "token": token,
            "nested": {"authorization": "Bearer abc", "message": "token=" + token},
            "job_id": "safe-job",
        }
        safe = hardware.sanitize_for_json(raw, (token,))
        text = json.dumps(safe)
        self.assertNotIn(token, text)
        self.assertNotIn("Bearer abc", text)
        self.assertEqual(safe["job_id"], "safe-job")

    def test_cli_plan_is_offline_and_submission_needs_exact_confirmation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(hardware_cli.main(["plan"]), 0)
        self.assertIn("no job submitted", output.getvalue())
        with mock.patch.object(hardware_cli, "_execute") as execute:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    hardware_cli.main(["smoke"])
                with self.assertRaises(SystemExit):
                    hardware_cli.main(
                        ["formal", "--confirm-submit", "WRONG"]
                    )
                with self.assertRaises(SystemExit):
                    hardware_cli.main(
                        [
                            "smoke",
                            "--confirm-submit",
                            hardware.SUBMISSION_CONFIRMATION,
                            "--shots",
                            "0",
                        ]
                    )
            execute.assert_not_called()

        with mock.patch.object(hardware_cli, "_execute", return_value=0) as execute:
            self.assertEqual(
                hardware_cli.main(
                    [
                        "resume",
                        "--job-id",
                        "EXISTING-JOB-9",
                        "--circuit",
                        "bell",
                        "--shots",
                        "100",
                    ]
                ),
                0,
            )
        self.assertEqual(["bell"], execute.call_args.args[0])
        self.assertEqual(
            "EXISTING-JOB-9", execute.call_args.kwargs["resume_job_id"]
        )

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                hardware_cli.main(
                    [
                        "resume",
                        "--job-id",
                        "EXISTING-JOB-9",
                        "--circuit",
                        "bell",
                        "--shots",
                        "100",
                        "--confirm-submit",
                        hardware.SUBMISSION_CONFIRMATION,
                    ]
                )

    def test_submit_one_requires_explicit_bounded_single_task(self):
        with mock.patch.object(hardware_cli, "_execute", return_value=0) as execute:
            status = hardware_cli.main(
                [
                    "submit-one",
                    "--circuit",
                    "bit_order",
                    "--shots",
                    "100",
                    "--confirm-submit",
                    hardware.SUBMISSION_CONFIRMATION,
                ]
            )
        self.assertEqual(0, status)
        self.assertEqual(["bit_order"], execute.call_args.args[0])
        self.assertEqual(100, execute.call_args.args[1])
        self.assertIsNone(execute.call_args.kwargs["resume_job_id"])

        invalid = (
            ["submit-one", "--circuit", "bit_order", "--shots", "100"],
            [
                "submit-one",
                "--shots",
                "100",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
            [
                "submit-one",
                "--circuit",
                "bit_order",
                "--confirm-submit",
                hardware.SUBMISSION_CONFIRMATION,
            ],
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
        )
        with mock.patch.object(hardware_cli, "_execute") as execute:
            for argv in invalid:
                with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        hardware_cli.main(argv)
            execute.assert_not_called()

    def test_hardware_validation_requires_both_peaks_and_minimum_support(self):
        collapsed = hardware_cli._dominance_summary(
            "bell", {"00": 100}, 100
        )
        self.assertFalse(collapsed["dominant_states_match"])
        self.assertFalse(collapsed["hardware_validation_passed"])

        noisy_ghz = {
            "000": 20,
            "111": 20,
            "001": 10,
            "010": 10,
            "011": 10,
            "100": 10,
            "101": 10,
            "110": 10,
        }
        low_support = hardware_cli._dominance_summary("ghz3", noisy_ghz, 100)
        self.assertTrue(low_support["dominant_states_match"])
        self.assertFalse(low_support["hardware_validation_passed"])

        healthy = hardware_cli._dominance_summary(
            "bell", {"00": 48, "11": 47, "01": 3, "10": 2}, 100
        )
        self.assertTrue(healthy["hardware_validation_passed"])

        bit_order = hardware_cli._dominance_summary(
            "bit_order", {"011": 95, "110": 5}, 100
        )
        reversed_order = hardware_cli._dominance_summary(
            "bit_order", {"110": 100}, 100
        )
        self.assertTrue(bit_order["hardware_validation_passed"])
        self.assertFalse(reversed_order["hardware_validation_passed"])

    def test_smoke_includes_bell_and_asymmetric_bit_order_probe(self):
        with mock.patch.object(hardware_cli, "_execute", return_value=0) as execute:
            status = hardware_cli.main(
                [
                    "smoke",
                    "--confirm-submit",
                    hardware.SUBMISSION_CONFIRMATION,
                ]
            )
        self.assertEqual(0, status)
        self.assertEqual(["bell", "bit_order"], execute.call_args.args[0])

    def test_interrupt_after_submission_prints_resume_only_instruction(self):
        def interrupt(*_args, **kwargs):
            kwargs["on_submitted"]("KNOWN-JOB-7")
            raise KeyboardInterrupt

        stderr = io.StringIO()
        with mock.patch.object(
            hardware_cli.OriginQHardwareConfig,
            "from_env",
            return_value=config(),
        ), mock.patch.object(
            hardware_cli,
            "_run_local_preflight",
            return_value={"counts": {}},
        ), mock.patch.object(
            hardware_cli,
            "run_originq_hardware",
            side_effect=interrupt,
        ), contextlib.redirect_stderr(stderr):
            with self.assertRaises(KeyboardInterrupt):
                hardware_cli._execute(
                    ["bell"], 100, Path("unused"), "LoomQ-test"
                )
        message = stderr.getvalue()
        self.assertIn("KNOWN-JOB-7", message)
        self.assertIn("resume --job-id", message)
        self.assertIn("Do not rerun", message)

    def test_evidence_bundle_contains_sanitized_raw_and_standard_summary(self):
        run = hardware.OriginQHardwareRun(
            origin_ir="QINIT 2\nCREG 2\n",
            raw_record={
                "job_id": "job/1",
                "terminal_state": "FINISHED",
                "account_id": "private-account",
                "sdk_response": {"token": "private-token"},
            },
            summary={
                "backend": "originq-qcloud-WK_C180",
                "job_id": "job/1",
                "shots": 10,
                "counts": {"00": 6, "11": 4},
                "bit_order": "little",
                "timestamp": "2026-08-03T01:02:03+00:00",
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            paths = hardware_cli._write_bundle(Path(temp), "bell", BELL, run)
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
            raw = json.loads(paths["raw"].read_text(encoding="utf-8"))
            self.assertEqual(summary["expected_support_probability"], 1.0)
            self.assertEqual(raw["account_id"], "[REDACTED]")
            self.assertEqual(raw["sdk_response"]["token"], "[REDACTED]")
            self.assertTrue(paths["raw"].is_file())
            self.assertTrue(paths["qasm"].is_file())
            self.assertTrue(paths["origin_ir"].is_file())

    def test_evidence_bundle_never_overwrites_an_existing_job(self):
        run = hardware.OriginQHardwareRun(
            origin_ir="QINIT 2\nCREG 2\n",
            raw_record={"job_id": "same-job", "terminal_state": "FINISHED"},
            summary={
                "backend": "originq-qcloud-WK_C180",
                "job_id": "same-job",
                "shots": 10,
                "counts": {"00": 5, "11": 5},
                "bit_order": "little",
                "timestamp": "2026-08-03T01:02:03+00:00",
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            hardware_cli._write_bundle(Path(temp), "bell", BELL, run)
            with self.assertRaises(FileExistsError):
                hardware_cli._write_bundle(Path(temp), "bell", BELL, run)

    def test_exclusive_json_partial_write_is_removed(self):
        def fail_after_partial(_payload, handle, **_kwargs):
            handle.write("{partial")
            raise OSError("disk full")

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial.json"
            with mock.patch.object(hardware.json, "dump", side_effect=fail_after_partial):
                with self.assertRaises(OSError):
                    hardware.write_json(path, {"safe": True}, exclusive=True)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
