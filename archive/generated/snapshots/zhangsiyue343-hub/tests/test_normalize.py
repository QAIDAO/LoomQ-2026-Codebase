"""Endianness normalization: every raw SDK convention -> little-endian clbit keys."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.normalize import (merge_counts, normalize_counts,
                                   raw_key_to_clbit_key, top_states)

IDENTITY = [(0, 0), (1, 1)]


class TestRawKeyMapping(unittest.TestCase):
    def test_big_endian_input_reverses_into_little_endian_key(self):
        # braket/spinq style: leftmost char is qubit 0.  Identity measure map,
        # so the little-endian clbit key is the reversed string.
        self.assertEqual(raw_key_to_clbit_key("01", True, IDENTITY, 2), "10")
        self.assertEqual(raw_key_to_clbit_key("10", True, IDENTITY, 2), "01")

    def test_little_endian_pyqpanda_style(self):
        # pyqpanda: rightmost char is qubit 0 -> keys pass through unchanged
        self.assertEqual(raw_key_to_clbit_key("10", False, IDENTITY, 2), "10")
        self.assertEqual(raw_key_to_clbit_key("01", False, IDENTITY, 2), "01")

    def test_unmeasured_clbits_read_zero(self):
        # q0->c2 only, raw "11": c2=1, others 0 -> key c3..c0 = "0100"
        self.assertEqual(
            raw_key_to_clbit_key("11", True, [(0, 2)], 4), "0100")

    def test_partial_measure_map(self):
        # only qubit 2 measured into c0; braket key '010' -> q2=0
        self.assertEqual(raw_key_to_clbit_key("010", True, [(2, 0)], 1, 3), "0")

    def test_measure_declaration_order_irrelevant(self):
        a = raw_key_to_clbit_key("10", True, [(0, 0), (1, 1)], 2)
        b = raw_key_to_clbit_key("10", True, [(1, 1), (0, 0)], 2)
        self.assertEqual(a, b)

    def test_reversed_measures(self):
        # cross mapping q0->c1, q1->c0: raw "10" has q0=1,q1=0
        # -> c1=1, c0=0 -> key "10"
        self.assertEqual(
            raw_key_to_clbit_key("10", True, [(0, 1), (1, 0)], 2), "10")

    def test_errors(self):
        with self.assertRaises(ValueError):
            raw_key_to_clbit_key("101", True, IDENTITY, 2, n_qubits=2)
        with self.assertRaises(ValueError):
            raw_key_to_clbit_key("10", True, [(5, 0)], 2)   # qubit not in key
        with self.assertRaises(ValueError):
            raw_key_to_clbit_key("10", True, [(0, 7)], 2)   # clbit out of range


class TestNormalizeCounts(unittest.TestCase):
    def test_distinct_raw_spellings_merge_into_one_clbit_key(self):
        merged = normalize_counts({"00": 3, "01": 4}, True, [(0, 0)], 2)
        self.assertEqual(merged, {"00": 7})     # q0=0 in both, c1 unmeasured
        merged = normalize_counts({"10": 3, "11": 4}, True, [(0, 0)], 2)
        self.assertEqual(merged, {"01": 7})     # q0=1 in both -> c0 rightmost

    def test_zero_count_keys_dropped(self):
        self.assertEqual(normalize_counts({"00": 0, "11": 2}, True, IDENTITY, 2),
                         {"11": 2})


class TestMergeAndTop(unittest.TestCase):
    def test_merge_counts_sums_backends(self):
        combined = merge_counts({"00": 10, "11": 9}, {"11": 1})
        self.assertEqual(combined, {"00": 10, "11": 10})

    def test_top_states_descending_with_tiebreak(self):
        top = top_states({"00": 4, "11": 8, "01": 6, "10": 4}, k=3)
        self.assertEqual([key for key, _ in top], ["11", "01", "00"])


if __name__ == "__main__":
    unittest.main()
