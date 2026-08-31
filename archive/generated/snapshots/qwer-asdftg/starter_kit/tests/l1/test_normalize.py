import unittest
from datetime import datetime, timedelta, timezone

from starter_kit.loomq_l1.errors import NormalizationError
from starter_kit.loomq_l1.model import RawExecution
from starter_kit.loomq_l1.normalize import build_result, normalize_counts


class NormalizeCountsTests(unittest.TestCase):
    def test_normalizes_integer_decimal_and_spaced_binary_keys(self):
        self.assertEqual(normalize_counts({1: 3}, 3, "integer", False), {"001": 3})
        self.assertEqual(normalize_counts({"3": 2}, 3, "decimal", False), {"011": 2})
        self.assertEqual(normalize_counts({"0 1": 4}, 2, "binary", False), {"01": 4})

    def test_reverses_after_padding_only_when_declared(self):
        self.assertEqual(normalize_counts({"10": 5}, 2, "binary", True), {"01": 5})
        self.assertEqual(normalize_counts({1: 5}, 3, "integer", True), {"100": 5})

    def test_accepts_zero_counts_without_dropping_their_key(self):
        self.assertEqual(normalize_counts({"0": 0}, 1, "binary", False), {"0": 0})

    def test_merges_collisions_in_first_raw_key_appearance_order(self):
        result = normalize_counts({"0 1": 2, "01": 3, "10": 4}, 2, "binary", False)

        self.assertEqual(result, {"01": 5, "10": 4})
        self.assertEqual(list(result), ["01", "10"])

    def test_rejects_empty_and_non_mapping_counts(self):
        for raw_counts in ({}, [], "01", b"01", None):
            with self.subTest(raw_counts=repr(raw_counts)):
                with self.assertRaises(NormalizationError):
                    normalize_counts(raw_counts, 2, "binary", False)

    def test_rejects_negative_boolean_and_float_count_values(self):
        for count in (-1, True, 1.0):
            with self.subTest(count=repr(count)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({"0": count}, 1, "binary", False)

    def test_rejects_invalid_or_overflowing_integer_keys(self):
        for key in (-1, True, "1", 1.0, 4):
            with self.subTest(key=repr(key)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({key: 1}, 2, "integer", False)

    def test_decimal_keys_are_ascii_canonical_without_leading_zeroes(self):
        self.assertEqual(normalize_counts({"0": 1, "3": 2}, 2, "decimal", False), {"00": 1, "11": 2})

        for key in ("", "00", "01", "+1", "-1", "1 ", "\u0661", "4"):
            with self.subTest(key=repr(key)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({key: 1}, 2, "decimal", False)

    def test_rejects_invalid_or_overflowing_binary_keys(self):
        for key in ("", " ", "0\t1", "0\n1", "0\u00a01", "0\uff12", "0b1", "+1", "-1", "02", "100"):
            with self.subTest(key=repr(key)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({key: 1}, 2, "binary", False)

    def test_rejects_unsupported_key_formats(self):
        for key_format in ("hex", 1, None):
            with self.subTest(key_format=repr(key_format)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({"0": 1}, 1, key_format, False)

    def test_rejects_invalid_width_and_reverse_bits_types(self):
        for width in (True, 1.0, 0, -1, 1_000_000):
            with self.subTest(width=repr(width)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({"0": 1}, width, "binary", False)

        for reverse_bits in (0, 1, "false", None):
            with self.subTest(reverse_bits=repr(reverse_bits)):
                with self.assertRaises(NormalizationError):
                    normalize_counts({"0": 1}, 1, "binary", reverse_bits)

    def test_rejects_pathological_key_lengths_with_normalization_error(self):
        huge = "1" * 100_000

        for key_format in ("binary", "decimal"):
            with self.subTest(key_format=key_format):
                with self.assertRaises(NormalizationError):
                    normalize_counts({huge: 1}, 8, key_format, False)


class BuildResultTests(unittest.TestCase):
    def test_builds_exact_schema_with_aware_timestamp_and_calls_clock_once(self):
        calls = []

        def now():
            calls.append(None)
            return datetime(2026, 8, 18, 9, 30, tzinfo=timezone(timedelta(hours=8)))

        raw = RawExecution("spinq_basic_simulator", "job-1", {"00": 4, "11": 4}, metadata={"target": "spinq"})
        result = build_result(raw, width=2, shots=8, now=now)

        self.assertEqual(
            result,
            {
                "backend": "spinq_basic_simulator",
                "job_id": "job-1",
                "shots": 8,
                "counts": {"00": 4, "11": 4},
                "bit_order": "little",
                "timestamp": "2026-08-18T09:30:00+08:00",
                "meta": {"target": "spinq"},
            },
        )
        self.assertEqual(calls, [None])
        self.assertNotIn("is_mock", result)
        self.assertEqual(list(result), ["backend", "job_id", "shots", "counts", "bit_order", "timestamp", "meta"])

    def test_copies_counts_and_nested_metadata_without_mutating_raw_execution(self):
        raw_counts = {"01": 3}
        raw_metadata = {"nested": {"values": [1]}}
        raw = RawExecution("backend", "job", raw_counts, metadata=raw_metadata)

        result = build_result(raw, width=2, shots=3, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
        raw_counts["01"] = 99
        raw_metadata["nested"]["values"].append(2)

        self.assertEqual(result["counts"], {"01": 3})
        self.assertEqual(result["meta"], {"nested": {"values": [1]}})
        self.assertIsNot(result["counts"], raw_counts)
        self.assertIsNot(result["meta"], raw_metadata)

    def test_rejects_true_is_mock_recursively_without_mutating_raw_metadata(self):
        raw_metadata = {
            "nested": {"items": [{"is_mock": True, "keep": 1}]},
            "tuple": ({"keep": 2},),
        }
        raw = RawExecution("backend", "job", {"0": 1}, metadata=raw_metadata)

        with self.assertRaisesRegex(NormalizationError, "mock execution results are not allowed"):
            build_result(raw, width=1, shots=1, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))

        self.assertEqual(raw_metadata, {"nested": {"items": [{"is_mock": True, "keep": 1}]}, "tuple": ({"keep": 2},)})

    def test_preserves_false_is_mock_without_mutating_or_aliasing_raw_metadata(self):
        raw_metadata = {
            "is_mock": False,
            "nested": {"items": [{"is_mock": False, "keep": 1}]},
            "tuple": ({"is_mock": False, "keep": 2},),
        }
        raw = RawExecution("backend", "job", {"0": 1}, metadata=raw_metadata)

        result = build_result(raw, width=1, shots=1, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
        raw_metadata["nested"]["items"][0]["keep"] = 99

        self.assertEqual(
            result["meta"],
            {
                "is_mock": False,
                "nested": {"items": [{"is_mock": False, "keep": 1}]},
                "tuple": ({"is_mock": False, "keep": 2},),
            },
        )
        self.assertFalse(raw_metadata["is_mock"])
        self.assertFalse(raw_metadata["nested"]["items"][0]["is_mock"])
        self.assertIsNot(result["meta"], raw_metadata)

    def test_rejects_true_is_mock_inside_cyclic_metadata(self):
        raw_metadata = {"nested": {"is_mock": True}}
        raw_metadata["self"] = raw_metadata
        raw = RawExecution("backend", "job", {"0": 1}, metadata=raw_metadata)

        with self.assertRaisesRegex(NormalizationError, "mock execution results are not allowed"):
            build_result(raw, width=1, shots=1, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))

        self.assertIs(raw_metadata["self"], raw_metadata)
        self.assertTrue(raw_metadata["nested"]["is_mock"])

    def test_rejects_total_that_does_not_equal_shots(self):
        raw = RawExecution("backend", "job", {"0": 2})

        with self.assertRaises(NormalizationError):
            build_result(raw, width=1, shots=3, now=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))

    def test_rejects_invalid_shots_and_raw_execution_shapes(self):
        raw = RawExecution("backend", "job", {"0": 1})
        for shots in (True, 1.0, 0, -1):
            with self.subTest(shots=repr(shots)):
                with self.assertRaises(NormalizationError):
                    build_result(raw, width=1, shots=shots)

        for field, value in (
            ("backend", 1),
            ("job_id", None),
            ("counts", []),
            ("key_format", "hex"),
            ("reverse_bits", 1),
            ("metadata", []),
        ):
            malformed = RawExecution("backend", "job", {"0": 1})
            object.__setattr__(malformed, field, value)
            with self.subTest(field=field):
                with self.assertRaises(NormalizationError):
                    build_result(malformed, width=1, shots=1)

        with self.assertRaises(NormalizationError):
            build_result(object(), width=1, shots=1)

    def test_rejects_non_callable_naive_and_non_datetime_clock_values(self):
        raw = RawExecution("backend", "job", {"0": 1})

        for now in (
            None,
            lambda: datetime(2026, 8, 18),
            lambda: "2026-08-18T00:00:00+00:00",
        ):
            with self.subTest(now=repr(now)):
                with self.assertRaises(NormalizationError):
                    build_result(raw, width=1, shots=1, now=now)

    def test_rejects_datetime_subclass_with_non_string_isoformat(self):
        class NonStringIsoformatDateTime(datetime):
            def isoformat(self):
                return 7

        raw = RawExecution("backend", "job", {"0": 1})

        with self.assertRaises(NormalizationError):
            build_result(
                raw,
                width=1,
                shots=1,
                now=lambda: NonStringIsoformatDateTime(2026, 8, 18, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
