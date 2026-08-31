from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from starter_kit import riscv_emulator


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "starter_kit" / "examples" / "quantum_riscv_demo.py"


class QuantumRISCVEncodingTests(unittest.TestCase):
    def setUp(self):
        self.encode = getattr(riscv_emulator, "encode_quantum_instruction", None)
        self.decode = getattr(riscv_emulator, "decode_quantum_word", None)
        self.assertTrue(callable(self.encode), "quantum instruction encoder is missing")
        self.assertTrue(callable(self.decode), "quantum instruction decoder is missing")

    def test_known_32_bit_encodings_are_stable(self):
        cases = {
            ("qinit", (3,)): 0x0000018B,
            ("qh", (3,)): 0x0000118B,
            ("qx", (4,)): 0x0000220B,
            ("qrz", (2, -1571)): 0x9DD0310B,
            ("qcx", (1, 2)): 0x0020C00B,
            ("qmeasure", (2, 5)): 0x0001528B,
        }
        for (mnemonic, operands), expected in cases.items():
            with self.subTest(mnemonic=mnemonic):
                word = self.encode(mnemonic, *operands)
                self.assertEqual(word, expected)
                self.assertEqual(self.decode(word), (mnemonic, list(operands)))

    def test_encoder_and_decoder_reject_invalid_or_reserved_forms(self):
        invalid_calls = (
            ("unknown", 0),
            ("qinit", -1),
            ("qh", 32),
            ("qrz", 0, 2048),
            ("qrz", 0, -2049),
            ("qcx", 1, 1),
            ("qmeasure", 0, 32),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                self.encode(*call)
        with self.assertRaises(ValueError):
            self.decode(0x00000013)  # stock addi, not a custom quantum word
        with self.assertRaises(ValueError):
            self.decode(0x0000610B)  # reserved funct3


class QuantumRISCVEmulatorTests(unittest.TestCase):
    def test_mnemonics_and_encoded_words_produce_the_same_trace(self):
        encode = riscv_emulator.encode_quantum_instruction
        source = """qinit 0
qh 0
qx 1
qrz 1, -785
qcx 0, 1
qmeasure 1, 3
"""
        words = "\n".join(
            f".word 0x{encode(name, *operands):08x}"
            for name, operands in (
                ("qinit", (0,)),
                ("qh", (0,)),
                ("qx", (1,)),
                ("qrz", (1, -785)),
                ("qcx", (0, 1)),
                ("qmeasure", (1, 3)),
            )
        )
        expected = [
            {"op": "qinit", "qubit": 0},
            {"op": "qh", "qubit": 0},
            {"op": "qx", "qubit": 1},
            {"op": "qrz", "qubit": 1, "angle_milliradians": -785},
            {"op": "qcx", "control": 0, "target": 1},
            {"op": "qmeasure", "qubit": 1, "result_slot": 3},
        ]

        traces = []
        for program in (source, words):
            emulator = riscv_emulator.TinyRISCVEmulator()
            emulator.load_program(program)
            self.assertEqual(emulator.execute(), {})
            traces.append(emulator.quantum_trace)
        self.assertEqual(traces, [expected, expected])

    def test_stock_program_is_backward_compatible_and_has_no_quantum_trace(self):
        emulator = riscv_emulator.TinyRISCVEmulator()
        emulator.load_program("li x1, 5\naddi x2, x1, -2\nadd x3, x1, x2\n")

        self.assertEqual(emulator.execute(), {"x1": 5, "x2": 3, "x3": 8})
        self.assertEqual(emulator.quantum_trace, [])

    def test_demo_runs_end_to_end_and_emits_reviewable_json(self):
        self.assertTrue(DEMO.is_file(), "quantum RISC-V demo is missing")
        completed = subprocess.run(
            [sys.executable, str(DEMO)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload[0], {"op": "qinit", "qubit": 0})
        self.assertEqual(payload[-1], {"op": "qmeasure", "qubit": 1, "result_slot": 0})


if __name__ == "__main__":
    unittest.main()
