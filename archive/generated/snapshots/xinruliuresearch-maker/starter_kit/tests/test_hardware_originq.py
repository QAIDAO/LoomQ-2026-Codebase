import json
import unittest

from loomq.hardware.errors import ConfigurationError, HardwareQualificationError, VendorExecutionError
from loomq.hardware.originq import (
    OriginQBindings,
    OriginQCredentials,
    build_dry_run,
    execute,
    load_credentials,
)


QASM = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
    'h q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n'
)


class FakeChipInfo:
    def chip_id(self):
        return "WK_TEST_CHIP"

    def qubits_num(self):
        return 72


class FakeResult:
    def job_id(self):
        return "origin-job-1"

    def get_counts(self, base=None):
        if base != "binary-enum":
            raise AssertionError("DataBase.Binary was not used")
        return {"00": 508, "11": 492}

    def origin_data(self):
        return json.dumps({"success": True, "apiKey": "credential-secret-value", "probCount": {"00": 508}})

    def job_status(self):
        return "SUCCESS"

    def error_message(self):
        return ""


class FakeJob:
    def job_id(self):
        return "origin-job-1"

    def result(self):
        return FakeResult()


class FakeBackend:
    def __init__(self, chip_failure=False):
        self.chip_failure = chip_failure
        self.runs = []

    def chip_info(self):
        if self.chip_failure:
            raise RuntimeError("credential-secret-value")
        return FakeChipInfo()

    def run(self, prog, shots):
        self.runs.append((prog, shots))
        return FakeJob()


class FakeService:
    def __init__(self, backend, available=True):
        self._backend = backend
        self._available = available

    def backends(self):
        return {"WK_C180_2": self._available}

    def backend(self, name):
        if name != "WK_C180_2":
            raise AssertionError("wrong backend")
        return self._backend


def bindings(backend, available=True):
    return OriginQBindings(
        service_class=lambda *args: FakeService(backend, available),
        convert_qasm_string_to_qprog=lambda source: ("QProg", source),
        database_binary="binary-enum",
        version="0.4.0",
    )


class OriginQCredentialTests(unittest.TestCase):
    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(ConfigurationError) as caught:
            load_credentials(environ={})
        self.assertNotIn("job_id", str(caught.exception))

    def test_repr_redacts_api_key_and_url(self):
        rendered = repr(OriginQCredentials("credential-secret-value", "WK_C180_2", "https://secret-host"))
        self.assertNotIn("credential-secret-value", rendered)
        self.assertNotIn("secret-host", rendered)


class OriginQExecutionTests(unittest.TestCase):
    def setUp(self):
        self.credentials = OriginQCredentials("credential-secret-value", "WK_C180_2")

    def test_chip_qualified_qpu_result_is_admitted_and_redacted(self):
        backend = FakeBackend()
        bundle = execute(QASM, 1000, credentials=self.credentials, bindings=bindings(backend))
        self.assertEqual(bundle.normalized_result["job_id"], "origin-job-1")
        self.assertEqual(bundle.normalized_result["counts"], {"00": 508, "11": 492})
        self.assertEqual(bundle.metadata["chip_id"], "WK_TEST_CHIP")
        self.assertEqual(backend.runs[0][1], 1000)
        self.assertNotIn("credential-secret-value", json.dumps(bundle.raw_result))

    def test_unavailable_backend_is_rejected_before_run(self):
        backend = FakeBackend()
        with self.assertRaises(HardwareQualificationError):
            execute(QASM, 1000, credentials=self.credentials, bindings=bindings(backend, available=False))
        self.assertEqual(backend.runs, [])

    def test_chip_info_failure_is_safely_reported_and_not_submitted(self):
        backend = FakeBackend(chip_failure=True)
        with self.assertRaises(VendorExecutionError) as caught:
            execute(QASM, 1000, credentials=self.credentials, bindings=bindings(backend))
        self.assertNotIn("credential-secret-value", str(caught.exception))
        self.assertEqual(backend.runs, [])

    def test_dry_run_has_no_job_id_or_vendor_import(self):
        plan = build_dry_run(QASM, 1000, "WK_C180_2")
        self.assertNotIn("job_id", plan)
        self.assertFalse(plan["network_called"])
        self.assertFalse(plan["vendor_imported"])


if __name__ == "__main__":
    unittest.main()
