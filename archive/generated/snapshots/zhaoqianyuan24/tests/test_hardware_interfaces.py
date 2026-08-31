import unittest

from starter_kit.hardware.api import run_hardware
from starter_kit.hardware.common import (
    HardwareInterfaceError,
    extract_counts,
    extract_job_id,
    normalize_counts,
)


class HardwareResultTests(unittest.TestCase):
    def test_normalizes_probability_result_to_exact_shots(self):
        counts = normalize_counts(
            {"00": 0.5, "11": 0.5},
            width=2,
            shots=9,
        )
        self.assertEqual(sum(counts.values()), 9)
        self.assertEqual(set(counts), {"00", "11"})

    def test_normalizes_integer_and_hex_keys(self):
        counts = normalize_counts(
            {0: 3, "0x3": 1},
            width=2,
            shots=4,
        )
        self.assertEqual(counts, {"00": 3, "11": 1})

    def test_extracts_nested_provider_payload(self):
        payload = {"obj": {"taskResult": {"00": 2, "11": 2}}}
        self.assertEqual(extract_counts(payload), {"00": 2, "11": 2})
        self.assertEqual(extract_job_id({"obj": {"taskId": "origin-task"}}), "origin-task")

    def test_extracts_spinq_task_id_and_run_module(self):
        payload = {"status": 200, "task": {"tid": 61489, "tstatus": "Q"}}
        self.assertEqual(extract_job_id(payload), "61489")
        self.assertEqual(
            extract_counts({"run": {"module": {"0": 0.0, "1": 1.0}}}),
            {"0": 0.0, "1": 1.0},
        )

    def test_dispatcher_rejects_unknown_target_without_loading_sdk(self):
        with self.assertRaises(HardwareInterfaceError):
            run_hardware("OPENQASM 2.0;", "unknown", 10)


if __name__ == "__main__":
    unittest.main()
