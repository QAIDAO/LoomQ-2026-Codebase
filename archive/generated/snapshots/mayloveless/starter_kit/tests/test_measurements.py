"""共享测量映射测试。"""

import unittest

from loomq.measurements import (
    build_classical_key,
    classical_bit_count,
    measurement_mapping,
    quantum_bit_indices,
)
from loomq.parser import parse_qasm


def qasm(body: str, qreg: str = "qreg q[2];", creg: str = "creg c[2];") -> str:
    return 'OPENQASM 2.0; include "qelib1.inc"; %s %s %s' % (
        qreg,
        creg,
        body,
    )


class MeasurementMappingTests(unittest.TestCase):
    def test_register_measurement_expands_to_global_pairs(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        self.assertEqual([(0, 0), (1, 1)], measurement_mapping(circuit))

    def test_single_bit_and_crossed_mapping(self) -> None:
        circuit = parse_qasm(
            qasm("measure q[0] -> c[1]; measure q[1] -> c[0];")
        )

        mapping = measurement_mapping(circuit)

        self.assertEqual([(0, 1), (1, 0)], mapping)
        self.assertEqual("10", build_classical_key(circuit, mapping, {0: 1, 1: 0}))

    def test_multiple_register_offsets_follow_declaration_order(self) -> None:
        circuit = parse_qasm(
            qasm(
                "measure right[0] -> high[0]; measure left[1] -> low[0];",
                qreg="qreg left[2]; qreg right[1];",
                creg="creg low[1]; creg high[1];",
            )
        )

        self.assertEqual(3, len(quantum_bit_indices(circuit)))
        self.assertEqual(2, classical_bit_count(circuit))
        self.assertEqual([(2, 1), (1, 0)], measurement_mapping(circuit))

    def test_duplicate_classical_write_is_rejected(self) -> None:
        circuit = parse_qasm(
            qasm("measure q[0] -> c[0]; measure q[1] -> c[0];")
        )

        with self.assertRaisesRegex(ValueError, "more than one measurement"):
            measurement_mapping(circuit)


if __name__ == "__main__":
    unittest.main()
