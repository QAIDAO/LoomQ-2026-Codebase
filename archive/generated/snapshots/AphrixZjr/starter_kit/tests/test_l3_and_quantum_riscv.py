import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTER = ROOT
if STARTER not in sys.path:
    sys.path.insert(0, STARTER)

from loomq_l3 import HybridQASMError, compile_hybrid
from quantum_riscv import QISAError, QuantumRISCVEmulator, assemble, decode, reference_backend
from riscv_emulator import TinyRISCVEmulator


class L3Tests(unittest.TestCase):
    SOURCE = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
h q[0]; measure q[0] -> c[0];
classical {
  r1 = 4; r2 = r1 + 3;
  if (c[0] != 0) { r3 = r2 - 1; } else { r3 = r2 + 2; }
}
cx q[0],q[1]; measure q[1] -> c[1];'''

    def test_compile_and_execute_both_branches(self):
        operations, assembly = compile_hybrid(self.SOURCE)
        self.assertEqual([line.split()[0] for line in operations], ["h", "measure", "cx", "measure"])
        for measured, expected in ((0, 9), (1, 6)):
            emulator = TinyRISCVEmulator(); emulator.load_program(assembly)
            emulator.set_register("x10", measured)
            self.assertEqual(emulator.execute().get("x3"), expected)

    def test_rejects_missing_else_and_out_of_range(self):
        bad = self.SOURCE.replace(" else { r3 = r2 + 2; }", "")
        with self.assertRaises(HybridQASMError): compile_hybrid(bad)
        with self.assertRaises(HybridQASMError): compile_hybrid(self.SOURCE.replace("c[0] !=", "c[2] !="))
        oversized = self.SOURCE.replace("creg c[2]", "creg c[23]")
        with self.assertRaisesRegex(HybridQASMError, "at most 22 classical bits"):
            compile_hybrid(oversized)


class QuantumRISCVTests(unittest.TestCase):
    def test_base_encode_decode_and_control_flow(self):
        words = assemble("li x1, 5\nli x2, 5\nbeq x1,x2,yes\nli x3,1\nj end\nyes: li x3,7\nend:")
        self.assertTrue(all(type(word) is int and 0 <= word <= 0xffffffff for word in words))
        self.assertEqual(decode(words[0]).op, "addi")
        state = QuantumRISCVEmulator(reference_backend).execute(words)
        self.assertEqual(state["x3"], 7)

    def test_quantum_to_classical_branch_end_to_end(self):
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
        self.assertEqual(QuantumRISCVEmulator(reference_backend).execute(words)["x1"], 7)

    def test_quantum_spy_and_reserved_encoding(self):
        calls = []
        def spy(gates, measurements):
            calls.append((gates, measurements)); return {0: 0}
        words = assemble("qreset\nqgate h,0\nqmeasure 0,0\nqsubmit\nqread x1,0")
        QuantumRISCVEmulator(spy).execute(words)
        self.assertEqual(calls[0][0][0][0], "h")
        with self.assertRaises(QISAError): decode(13 << 25 | 0x0b)

    def test_parameter_gate_q16_16(self):
        calls = []
        words = assemble("qgate rz,0,x6,1.5\nqmeasure 0,0\nqsubmit")
        QuantumRISCVEmulator(lambda g, m: calls.append(g) or {0: 0}).execute(words)
        self.assertAlmostEqual(calls[0][0][2], 1.5)


if __name__ == "__main__":
    unittest.main()
