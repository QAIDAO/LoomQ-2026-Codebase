"""Archive-contained regression tests for the official quantum RISC-V path.

Run directly::

    python tests/test_quantum_riscv_e2e.py -v

or through discovery::

    python -m unittest discover -s tests -p "test_quantum_riscv_e2e.py" -v
"""

import os
import sys
import unittest


STARTER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STARTER not in sys.path:
    sys.path.insert(0, STARTER)

from riscv_emulator import (  # noqa: E402
    OP_QCTRL,
    OP_QGATE,
    QuantumRISCVEmulator,
    TinyRISCVEmulator,
    assemble,
    decode,
    reference_backend,
)


class OfficialQuantumRISCVE2ETests(unittest.TestCase):
    def test_official_module_owns_custom_encoding_and_execution(self):
        self.assertEqual(assemble.__module__, "riscv_emulator")
        self.assertEqual(decode.__module__, "riscv_emulator")
        self.assertEqual(QuantumRISCVEmulator.__module__, "riscv_emulator")

        gate_word = assemble("qgate x, 3")[0]
        self.assertEqual(gate_word & 0x7F, OP_QGATE)
        self.assertEqual(decode(gate_word).op, "x")
        self.assertEqual(decode(gate_word).q0, 3)

        measure_word = assemble("qmeasure 3, 2")[0]
        self.assertEqual(measure_word & 0x7F, OP_QCTRL)
        self.assertEqual(decode(measure_word).op, "qmeasure")
        self.assertEqual((decode(measure_word).q0, decode(measure_word).aux), (3, 2))

    def test_machine_words_submit_read_and_drive_classical_branch(self):
        source = """qreset
qgate x, 0
qmeasure 0, 0
qsubmit
qread x5, 0
beq x5, x0, zero
li x1, 7
j end
zero: li x1, 3
end:
"""
        words = assemble(source)

        self.assertTrue(words)
        self.assertTrue(all(type(word) is int and 0 <= word <= 0xFFFFFFFF for word in words))
        operations = [decode(word, index * 4).op for index, word in enumerate(words)]
        self.assertEqual(operations[:5], ["qreset", "x", "qmeasure", "qsubmit", "qread"])

        state = QuantumRISCVEmulator(reference_backend).execute(words)
        self.assertEqual(state["x5"], 1)
        self.assertEqual(state["x1"], 7)

    def test_parameter_gate_reaches_backend_as_q16_16_angle(self):
        calls = []

        def backend(gates, measurements):
            calls.append((gates, measurements))
            return {4: 0}

        words = assemble(
            "qreset\n"
            "qgate rz, 2, x6, -1.5\n"
            "qmeasure 2, 4\n"
            "qsubmit\n"
            "qread x7, 4\n"
        )
        QuantumRISCVEmulator(backend).execute(words)

        self.assertEqual(len(calls), 1)
        gates, measurements = calls[0]
        self.assertEqual(measurements, {4: 2})
        self.assertEqual(gates[0][:2], ("rz", (2,)))
        self.assertAlmostEqual(gates[0][2], -1.5)

    def test_tiny_text_emulator_keeps_l3_python_integer_semantics(self):
        emulator = TinyRISCVEmulator()
        emulator.load_program("li x1, 4294967295\naddi x1, x1, 2")
        self.assertEqual(emulator.execute()["x1"], 4294967297)


if __name__ == "__main__":
    unittest.main()
