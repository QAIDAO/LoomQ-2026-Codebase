"""Semantic regression tests for the local L1 state-vector executor."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.simulator import run_local  # noqa: E402


BELL_QASM = (STARTER_KIT / "circuits" / "bell.qasm").read_text(encoding="utf-8")


class L1SemanticTests(unittest.TestCase):
    def test_bell_distribution_has_only_correlated_states(self) -> None:
        payload = run_local(BELL_QASM, "spinq", shots=8192)
        self.assertEqual(set(payload["counts"]), {"00", "11"})
        for count in payload["counts"].values():
            self.assertGreater(count, 3500)

    def test_all_targets_share_the_same_normalized_counts(self) -> None:
        counts = [run_local(BELL_QASM, target, shots=512)["counts"] for target in ("spinq", "originq", "braket")]
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(counts[1], counts[2])


if __name__ == "__main__":
    unittest.main()
