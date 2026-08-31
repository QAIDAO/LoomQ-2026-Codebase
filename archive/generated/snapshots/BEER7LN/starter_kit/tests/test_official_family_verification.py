"""Round-trip contracts for all eight published L1 circuit families."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.gate_policy import PUBLIC_GATE_WHITELIST  # noqa: E402
from loomq.qasm import GateOperation, parse_openqasm2  # noqa: E402
from loomq.verification import (  # noqa: E402
    official_family_circuits,
    verify_official_family_roundtrips,
)


class OfficialFamilyVerificationTests(unittest.TestCase):
    def test_suite_matches_the_eight_published_families(self) -> None:
        circuits = official_family_circuits()
        self.assertEqual(
            set(circuits),
            {
                "bell",
                "ghz3",
                "ghz5",
                "qft4",
                "grover3",
                "random1",
                "random2",
                "random3",
            },
        )
        for name, source in circuits.items():
            with self.subTest(case=name):
                program = parse_openqasm2(source)
                gates = {
                    operation.name
                    for operation in program.operations
                    if isinstance(operation, GateOperation)
                }
                self.assertTrue(gates <= PUBLIC_GATE_WHITELIST)

    def test_all_family_target_roundtrips_preserve_semantics(self) -> None:
        records = verify_official_family_roundtrips()
        self.assertEqual(len(records), 8 * 3)
        self.assertTrue(all(record.status == "pass" for record in records))


if __name__ == "__main__":
    unittest.main()
