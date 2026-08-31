"""Contract tests for LoomQ's optional custom quantum RISC-V extension."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.riscv_quantum_extension import (  # noqa: E402
    CUSTOM0_OPCODE,
    ExtendedTinyRISCVEmulator,
    QuantumOpcodeError,
    compile_quantum_operations,
    decode_qop,
    encode_qparam,
    encode_qop,
)


class QuantumOpcodeEncodingTests(unittest.TestCase):
    def test_custom0_round_trip_for_all_gate_arities_and_measure(self) -> None:
        cases = (
            ("h", (3,), None), ("s", (2,), None), ("tdg", (7,), None),
            ("cx", (0, 1), None), ("swap", (4, 5), None),
            ("cu1", (6, 7), None), ("ccx", (0, 1, 2), None),
            ("measure", (2,), 5),
        )
        for gate, qubits, cbit in cases:
            word = encode_qop(gate, *qubits, cbit=cbit)
            decoded = decode_qop(word)
            self.assertEqual(word & 0x7F, CUSTOM0_OPCODE)
            self.assertEqual(decoded.gate, gate)
            self.assertEqual(decoded.qubits, qubits)
            self.assertEqual(decoded.cbit, cbit)

    def test_parameter_word_round_trip_is_fixed_point_and_explicit(self) -> None:
        decoded = decode_qop(encode_qparam(-0.75))
        self.assertEqual(decoded.gate, "param")
        self.assertAlmostEqual(decoded.parameter, -0.75, places=5)

    def test_rejects_invalid_gate_register_field_and_opcode(self) -> None:
        with self.assertRaises(QuantumOpcodeError):
            encode_qop("not-a-gate", 0)
        with self.assertRaises(QuantumOpcodeError):
            encode_qop("h", 32)
        with self.assertRaises(QuantumOpcodeError):
            decode_qop(0)


class QuantumOpcodeEndToEndTests(unittest.TestCase):
    def test_measurement_writes_classical_mapping_and_drives_branch(self) -> None:
        program = "\n".join((
            f"qop 0x{encode_qop('h', 0):08x}",
            f"qop 0x{encode_qop('cx', 0, 1):08x}",
            f"qop 0x{encode_qop('measure', 0, cbit=0):08x}",
            f"qop 0x{encode_qop('measure', 1, cbit=1):08x}",
            "bne x10, x11, bad",
            "li x1, 7",
            "j end",
            "bad: li x1, -3",
            "end:",
        ))
        emulator = ExtendedTinyRISCVEmulator()
        emulator.load_program(program)
        state = emulator.execute()
        self.assertEqual(state.get("x1"), 7)
        self.assertEqual(state.get("x10"), state.get("x11"))
        self.assertEqual(
            [item.gate for item in emulator.quantum_trace],
            ["h", "cx", "measure", "measure"],
        )

    def test_all_l1_gates_and_parameter_gate_compile_into_executable_trace(self) -> None:
        operations = [
            "h q[0];",
            "x q[1];",
            "s q[0];", "sdg q[0];", "t q[0];", "tdg q[0];",
            "rz(pi/3) q[0];", "ry(-pi/7) q[1];",
            "cx q[0], q[1];", "cu1(pi/5) q[0], q[1];", "swap q[0], q[1];",
            "ccx q[0], q[1], q[2];",
            "measure q[1] -> c[2];",
        ]
        assembly = compile_quantum_operations(operations)
        emulator = ExtendedTinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.execute()
        self.assertEqual(
            [item.gate for item in emulator.quantum_trace if item.gate != "param"],
            ["h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx", "measure"],
        )

    def test_classical_subset_remains_identical_to_official_emulator(self) -> None:
        from riscv_emulator import TinyRISCVEmulator

        programs = (
            "li x1, 5\naddi x1, x1, -2\n",
            "li x1, 3\nli x2, 3\nbeq x1, x2, yes\nli x4, 0\nyes: add x3, x1, x2\n",
            "li x1, 8\nli x2, 3\nbne x1, x2, yes\nli x4, 0\nyes: sub x3, x1, x2\n",
        )
        for program in programs:
            with self.subTest(program=program):
                official, extended = TinyRISCVEmulator(), ExtendedTinyRISCVEmulator()
                official.load_program(program); extended.load_program(program)
                self.assertEqual(extended.execute(), official.execute())


if __name__ == "__main__":
    unittest.main()