"""End-to-end tests for the official TinyRISCV quantum extension."""

from __future__ import annotations

import json
import math
import unittest

from loomq.bonus import QuantumRISCVEmulator, assemble_quantum_line
from loomq.bonus.statevector import QuantumStateError
from riscv_emulator import TinyRISCVEmulator


class BonusEmulatorTests(unittest.TestCase):
    def test_subclasses_official_emulator_and_preserves_classical_behavior(self) -> None:
        program = """
        li x1, 5
        li x2, 10
        add x3, x1, x2
        addi x4, x3, -2
        bne x3, x4, DONE
        li x5, 999
        DONE:
        sub x6, x3, x1
        """
        official = TinyRISCVEmulator()
        official.load_program(program)
        extended = QuantumRISCVEmulator()
        extended.load_program(program)
        self.assertIsInstance(extended, TinyRISCVEmulator)
        self.assertEqual(extended.execute(), official.execute())

    def test_bell_program_has_correlated_measurements_and_auditable_log(self) -> None:
        program = """
        li x1, 0
        li x2, 1
        qh x1
        qcx x1, x2
        qmeasure x3, x1
        qmeasure x4, x2
        add x5, x3, x4
        """
        for seed in range(64):
            emulator = QuantumRISCVEmulator(seed=seed)
            emulator.load_program(program)
            emulator.execute()
            self.assertEqual(emulator.get_register("x3"), emulator.get_register("x4"))
            report = emulator.execution_report()
            self.assertFalse(report["hardware_execution"])
            self.assertEqual(len(report["quantum_operations"]), 4)
            self.assertEqual(len(report["measurements"]), 2)
            self.assertAlmostEqual(
                sum(report["basis_probabilities"].values()), 1.0, places=12
            )
            json.dumps(report)  # contract is JSON serializable

    def test_register_values_select_qubits_at_runtime(self) -> None:
        program = """
        li x10, 2
        li x11, 1
        qx x10
        qswap x10, x11
        qmeasure x20, x11
        qmeasure x21, x10
        """
        emulator = QuantumRISCVEmulator(seed=1)
        emulator.load_program(program)
        emulator.execute()
        self.assertEqual(emulator.get_register("x20"), 1)
        self.assertEqual(emulator.get_register("x21"), 0)
        self.assertEqual(
            emulator.quantum_log[1]["resolved_qubits"], [2, 1]
        )

    def test_qinit_qry_qrz_and_qccx_have_real_statevector_semantics(self) -> None:
        program = """
        li x1, 0
        li x2, 1
        li x3, 2
        li x10, 3
        li x11, 205887
        qinit x10
        qry x3, x11
        qrz x3, x11
        qx x1
        qx x2
        qccx x1, x2, x3
        qmeasure x20, x3
        """
        emulator = QuantumRISCVEmulator(seed=7)
        emulator.load_program(program)
        emulator.execute()
        # RY(pi)|0> is |1>; RZ only changes phase, then active CCX flips it to |0>.
        self.assertEqual(emulator.get_register("x20"), 0)
        self.assertEqual(emulator.quantum_state.num_qubits, 3)
        self.assertEqual(emulator.quantum_log[0]["initialized_qubits"], 3)
        self.assertAlmostEqual(
            emulator.quantum_log[1]["angle_radians"],
            math.pi,
            delta=1.0 / 65536.0,
        )
        self.assertEqual(emulator.quantum_log[5]["resolved_qubits"], [0, 1, 2])
        # RZ(pi)|1> contributes phase +i; CCX moves that amplitude to |011>.
        self.assertAlmostEqual(emulator.quantum_state.amplitudes[3].real, 0.0, places=5)
        self.assertAlmostEqual(emulator.quantum_state.amplitudes[3].imag, 1.0, places=5)

    def test_encoded_words_and_mnemonics_execute_identically(self) -> None:
        quantum_lines = ["qh x1", "qcx x1, x2", "qmeasure x3, x1", "qmeasure x4, x2"]
        mnemonic_program = "li x1, 0\nli x2, 1\n" + "\n".join(quantum_lines)
        encoded_program = "li x1, 0\nli x2, 1\n" + "\n".join(
            f".word 0x{assemble_quantum_line(line):08x}" for line in quantum_lines
        )
        mnemonic = QuantumRISCVEmulator(seed=19)
        encoded = QuantumRISCVEmulator(seed=19)
        mnemonic.load_program(mnemonic_program)
        encoded.load_program(encoded_program)
        self.assertEqual(mnemonic.execute(), encoded.execute())
        self.assertEqual(mnemonic.quantum_log, encoded.quantum_log)
        self.assertEqual(
            mnemonic.quantum_state.probabilities(), encoded.quantum_state.probabilities()
        )

    def test_quantum_instruction_can_be_controlled_by_classical_branch(self) -> None:
        program = """
        li x1, 0
        li x2, 1
        beq x7, x0, SKIP
        qx x1
        SKIP:
        qmeasure x3, x1
        """
        skipped = QuantumRISCVEmulator(seed=0)
        skipped.load_program(program)
        skipped.execute()
        taken = QuantumRISCVEmulator(seed=0)
        taken.load_program(program)
        taken.set_register("x7", 1)
        taken.execute()
        self.assertEqual(skipped.get_register("x3"), 0)
        self.assertEqual(taken.get_register("x3"), 1)

    def test_reload_resets_quantum_and_classical_execution_state(self) -> None:
        emulator = QuantumRISCVEmulator(seed=3)
        emulator.load_program("li x1, 0\nqx x1\nqmeasure x2, x1")
        emulator.execute()
        self.assertEqual(emulator.get_register("x2"), 1)
        emulator.load_program("li x1, 0\nqmeasure x2, x1")
        emulator.execute()
        self.assertEqual(emulator.get_register("x2"), 0)
        self.assertEqual(len(emulator.quantum_log), 1)

    def test_qinit_resets_entanglement_but_keeps_an_audit_trail(self) -> None:
        emulator = QuantumRISCVEmulator(seed=9)
        emulator.load_program(
            "li x1, 0\nli x2, 1\nli x10, 2\n"
            "qh x1\nqcx x1, x2\nqinit x10\nqmeasure x3, x1\nqmeasure x4, x2"
        )
        emulator.execute()
        self.assertEqual(emulator.get_register("x3"), 0)
        self.assertEqual(emulator.get_register("x4"), 0)
        self.assertEqual([item["mnemonic"] for item in emulator.quantum_log], [
            "qh", "qcx", "qinit", "qmeasure", "qmeasure"
        ])

    def test_rejects_invalid_machine_word_qubits_and_duplicate_operands(self) -> None:
        emulator = QuantumRISCVEmulator(max_qubits=3)
        with self.assertRaises(ValueError):
            emulator.load_program(".word 0x00000013")
        emulator.load_program("li x1, 3\nqh x1")
        with self.assertRaises(QuantumStateError):
            emulator.execute()
        emulator.load_program("li x1, 1\nqcx x1, x1")
        with self.assertRaises(QuantumStateError):
            emulator.execute()
        emulator.load_program("li x1, 1\nqccx x1, x1, x1")
        with self.assertRaises(QuantumStateError):
            emulator.execute()
        emulator.load_program("li x10, 0\nqinit x10")
        with self.assertRaises(QuantumStateError):
            emulator.execute()
        emulator.load_program("li x1, 0\nli x2, 4294967296\nqry x1, x2")
        with self.assertRaises(ValueError):
            emulator.execute()


if __name__ == "__main__":
    unittest.main()
