import unittest

from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator


PUBLIC_HYBRID = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; } else { r1 = 10; }
  r1 = r1 + 5;
}
cx q[0], q[1];
'''


class HybridQasmBoundaryTests(unittest.TestCase):
    def test_preserves_quantum_order_across_classical_block(self):
        quantum_ops, assembly = adapter.compile_hybrid(PUBLIC_HYBRID)

        self.assertEqual(
            quantum_ops,
            ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];"],
        )
        self.assertTrue(assembly.strip())

    def test_public_branch_uses_measurement_register_x10(self):
        _ops, assembly = adapter.compile_hybrid(PUBLIC_HYBRID)
        for measured, expected in ((0, 15), (1, 105)):
            emulator = TinyRISCVEmulator()
            emulator.load_program(assembly)
            emulator.set_register("x10", measured)
            self.assertEqual(emulator.execute().get("x1", 0), expected)

    def test_unclosed_classical_block_is_rejected(self):
        malformed = PUBLIC_HYBRID.replace("}\ncx", "\ncx", 1)
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(malformed)


if __name__ == "__main__":
    unittest.main()
