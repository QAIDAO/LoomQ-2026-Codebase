from datetime import datetime
import unittest

from starter_kit import adapter
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.emitters import emit
from starter_kit.tests.test_parser_validator import BELL_QASM


try:
    from starter_kit.loomq.runners.result import build_result, normalize_counts
except ImportError:
    build_result = None
    normalize_counts = None


class CountNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(normalize_counts, "result normalizer is missing")

    def test_normalizes_binary_decimal_and_integer_keys_without_losing_width(self):
        self.assertEqual(normalize_counts({"00": 4, "11": 6}, width=2), {"00": 4, "11": 6})
        self.assertEqual(normalize_counts({3: 2, "3": 3}, width=2), {"11": 5})
        self.assertEqual(normalize_counts({"0b1": 7}, width=2), {"01": 7})
        self.assertEqual(normalize_counts({1: 2, "01": 3}, width=2), {"01": 5})

    def test_reverses_only_when_runner_declares_native_msb_order(self):
        self.assertEqual(
            normalize_counts({"01": 9, "10": 3}, width=2, reverse_bits=True),
            {"01": 3, "10": 9},
        )

    def test_rejects_ambiguous_keys_or_invalid_count_values(self):
        cases = (
            ({"101": 1}, 2),
            ({"2x": 1}, 2),
            ({"00": -1}, 2),
            ({"00": 1.5}, 2),
            ({"00": True}, 2),
        )
        for raw, width in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                normalize_counts(raw, width=width)


class UnifiedResultTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(build_result, "unified result builder is missing")

    def test_builds_official_schema_with_utc_timestamp_and_backend_id(self):
        result = build_result(
            target="originq",
            job_id="local-123",
            shots=10,
            counts={"00": 4, "11": 6},
            width=2,
            meta={"engine": "pyqpanda", "depth": 2},
        )

        self.assertEqual(result["backend"], "originq_local_simulator")
        self.assertEqual(result["job_id"], "local-123")
        self.assertEqual(result["counts"], {"00": 4, "11": 6})
        self.assertEqual(result["shots"], 10)
        self.assertEqual(result["bit_order"], "little")
        self.assertEqual(result["meta"]["engine"], "pyqpanda")
        self.assertTrue(result["timestamp"].endswith("Z"))
        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))

    def test_rejects_shot_total_or_unknown_target(self):
        with self.assertRaisesRegex(ValueError, "sum"):
            build_result("spinq", "job", 10, {"00": 9}, 2, {})
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            build_result("unknown", "job", 1, {"0": 1}, 1, {})


class AdapterTranspileTests(unittest.TestCase):
    def test_adapter_uses_shared_parser_and_emitter_for_every_target(self):
        parsed = parse_qasm(BELL_QASM)
        for target in adapter.SUPPORTED_TARGETS:
            with self.subTest(target=target):
                self.assertEqual(adapter.transpile(BELL_QASM, target), emit(parsed, target))

    def test_adapter_rejects_unknown_target_before_transpilation(self):
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            adapter.transpile(BELL_QASM, "unknown")


if __name__ == "__main__":
    unittest.main()
