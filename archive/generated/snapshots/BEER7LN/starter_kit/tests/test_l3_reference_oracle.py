"""Generated L3 stress corpus compared with an independent source interpreter."""

from __future__ import annotations

from itertools import product
from pathlib import Path
import random
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.gate_policy import PUBLIC_GATE_WHITELIST  # noqa: E402
from loomq.hybrid_oracle import interpret_classical  # noqa: E402
from loomq.hybrid_stress import build_stress_corpus  # noqa: E402
from loomq.qasm import GateOperation, _parse_operation  # noqa: E402
from riscv_emulator import TinyRISCVEmulator  # noqa: E402


class HybridReferenceOracleTests(unittest.TestCase):
    def test_generated_corpus_matches_compiled_riscv(self) -> None:
        corpus = build_stress_corpus()
        self.assertEqual(len(corpus), 48)
        for case in corpus:
            operations, assembly = adapter.compile_hybrid(case.source)
            gate_names = {
                operation.name
                for line in operations
                if isinstance((operation := _parse_operation(line[:-1])), GateOperation)
            }
            self.assertTrue(gate_names <= PUBLIC_GATE_WHITELIST)
            for measurements in _measurement_samples(case.width, case.case_id):
                with self.subTest(case=case.case_id, measurements=measurements):
                    expected = interpret_classical(case.source, measurements)
                    emulator = TinyRISCVEmulator()
                    emulator.load_program(assembly)
                    for index, value in enumerate(measurements):
                        emulator.set_register(f"x{10 + index}", value)
                    observed = emulator.execute()
                    for register in range(1, 10):
                        name = f"x{register}"
                        self.assertEqual(
                            observed.get(name, 0),
                            expected.get(name, 0),
                        )

    def test_oracle_rejects_invalid_measurement_assignments(self) -> None:
        case = build_stress_corpus(cases=1)[0]
        with self.assertRaises(ValueError):
            interpret_classical(case.source, ())
        with self.assertRaises(ValueError):
            interpret_classical(case.source, (2,))


def _measurement_samples(width: int, case_id: str) -> tuple[tuple[int, ...], ...]:
    if width <= 4:
        return tuple(product((0, 1), repeat=width))
    rng = random.Random(case_id)
    samples = {
        (0,) * width,
        (1,) * width,
        tuple(index % 2 for index in range(width)),
        tuple((index + 1) % 2 for index in range(width)),
    }
    while len(samples) < 12:
        samples.add(tuple(rng.randrange(2) for _ in range(width)))
    return tuple(sorted(samples))


if __name__ == "__main__":
    unittest.main()
