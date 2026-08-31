import os
from pathlib import Path
import unittest

from loomq.hardware.errors import ConfigurationError, HardwareQualificationError, VendorExecutionError
from loomq.hardware.spinq import SpinQBindings, SpinQCredentials, build_dry_run, execute, load_credentials


QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


class FakeSpinQ:
    def __init__(self, simulator=False, online=1):
        self.simulator = simulator
        self.online = online
        self.submissions = []
        self.queries = []

    def get_platforms(self):
        return {
            "items": [
                {
                    "pcode": "gemini-live",
                    "pname": "Gemini",
                    "simu": self.simulator,
                    "countOnlineMachine": self.online,
                    "maxBitNum": 2,
                }
            ]
        }

    def qasm_submit(self, qasm, task_name, platform_code):
        self.submissions.append((qasm, task_name, platform_code))
        return {"status": 202, "msg": "accepted", "task": {"tcode": "spin-job-1"}}

    def result(self, task_code):
        self.queries.append(task_code)
        return {"taskStatus": "S", "shots": 1000, "run": {"count": {"00": 501, "11": 499}}}

    def bindings(self):
        return SpinQBindings(self.get_platforms, self.qasm_submit, self.result, "0.0.2")


class SpinQCredentialTests(unittest.TestCase):
    def test_missing_credentials_fail_without_secret_or_job_id(self):
        with self.assertRaises(ConfigurationError) as caught:
            load_credentials({})
        message = str(caught.exception)
        self.assertNotIn("job_id", message)
        self.assertIn("PRIVATEKEYPATH", message)

    def test_repr_redacts_all_values(self):
        credentials = SpinQCredentials("sensitive-user", Path("sensitive-key"), "https://sensitive-host")
        rendered = repr(credentials)
        self.assertNotIn("sensitive", rendered)


class SpinQExecutionTests(unittest.TestCase):
    def setUp(self):
        self.credentials = SpinQCredentials("user", Path("not-read-by-test"), "https://cloud.example")

    def test_real_platform_and_complete_result_are_admitted(self):
        fake = FakeSpinQ()
        names = ("PRIVATEKEYPATH", "SPINQCLOUDUSERNAME", "SPINQCLOUDHOST")
        before = {name: os.environ.get(name) for name in names}
        bundle = execute(
            QASM,
            1000,
            "gemini-live",
            "loomq-test",
            credentials=self.credentials,
            bindings=fake.bindings(),
            sleep=lambda _: None,
        )
        self.assertEqual(bundle.normalized_result["job_id"], "spin-job-1")
        self.assertEqual(bundle.normalized_result["counts"], {"00": 501, "11": 499})
        self.assertEqual(bundle.metadata["execution_kind"], "qpu")
        self.assertTrue(bundle.metadata["qpu_verified"])
        self.assertEqual(fake.submissions[0][2], "gemini-live")
        self.assertEqual({name: os.environ.get(name) for name in names}, before)

    def test_simulator_and_offline_platforms_are_rejected_before_submit(self):
        for fake in (FakeSpinQ(simulator=True), FakeSpinQ(online=0)):
            with self.subTest(simulator=fake.simulator, online=fake.online):
                with self.assertRaises(HardwareQualificationError):
                    execute(
                        QASM,
                        1000,
                        "gemini-live",
                        "loomq-test",
                        credentials=self.credentials,
                        bindings=fake.bindings(),
                    )
                self.assertEqual(fake.submissions, [])

    def test_fixed_shot_contract_is_not_silently_changed(self):
        fake = FakeSpinQ()
        with self.assertRaises(ConfigurationError):
            execute(
                QASM,
                8192,
                "gemini-live",
                "loomq-test",
                credentials=self.credentials,
                bindings=fake.bindings(),
            )
        self.assertEqual(fake.submissions, [])

    def test_vendor_exception_message_does_not_echo_secret(self):
        bindings = SpinQBindings(
            lambda: (_ for _ in ()).throw(RuntimeError("credential-secret-value")),
            lambda *_: None,
            lambda *_: None,
            "0.0.2",
        )
        with self.assertRaises(VendorExecutionError) as caught:
            execute(
                QASM,
                1000,
                "gemini-live",
                "loomq-test",
                credentials=self.credentials,
                bindings=bindings,
            )
        self.assertNotIn("credential-secret-value", str(caught.exception))

    def test_dry_run_contains_no_job_id_and_needs_no_credentials(self):
        plan = build_dry_run(QASM, 1000, "gemini-live", "loomq-test")
        self.assertNotIn("job_id", plan)
        self.assertFalse(plan["network_called"])
        self.assertFalse(plan["vendor_imported"])

    def test_explicit_measurement_is_rejected_per_official_submitter(self):
        with self.assertRaises(ConfigurationError):
            build_dry_run(QASM + "measure q[0] -> c[0];\n", 1000, "gemini-live", "loomq-test")


if __name__ == "__main__":
    unittest.main()
