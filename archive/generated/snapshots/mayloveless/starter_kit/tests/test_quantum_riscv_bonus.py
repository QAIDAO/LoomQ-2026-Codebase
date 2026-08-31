"""Quantum RISC-V Bonus 的编码、模拟器与完整链路测试。"""

import unittest

try:
    from starter_kit.bonus.quantum_riscv import (
        QuantumInstruction,
        QuantumInstructionError,
        QuantumRISCVEmulator,
        QuantumTranslationError,
        TraceCoprocessor,
        decode_quantum_instruction,
        encode_qcx,
        encode_qh,
        encode_qmeas,
        encode_qx,
        format_instruction,
        quantum_ops_to_words,
    )
    from starter_kit.loomq.l3 import compile_hybrid_source
    from starter_kit.riscv_emulator import TinyRISCVEmulator
except ModuleNotFoundError as error:
    # Starter Kit 的既有 full-test 命令以 starter_kit/ 为模块根。
    if error.name != "starter_kit":
        raise
    from bonus.quantum_riscv import (
        QuantumInstruction,
        QuantumInstructionError,
        QuantumRISCVEmulator,
        QuantumTranslationError,
        TraceCoprocessor,
        decode_quantum_instruction,
        encode_qcx,
        encode_qh,
        encode_qmeas,
        encode_qx,
        format_instruction,
        quantum_ops_to_words,
    )
    from loomq.l3 import compile_hybrid_source
    from riscv_emulator import TinyRISCVEmulator


def word_lines(words):
    return "\n".join(".word 0x%08X" % word for word in words)


class QuantumEncodingTests(unittest.TestCase):
    def test_bit_exact_examples(self):
        self.assertEqual(0x0000000B, encode_qh(0))
        self.assertEqual(0x000F900B, encode_qx(31))
        self.assertEqual(0x0010200B, encode_qcx(0, 1))
        self.assertEqual(0x0000350B, encode_qmeas(0, 10))

    def test_all_instructions_round_trip_at_boundaries(self):
        cases = (
            (encode_qh(0), QuantumInstruction("QH", 0)),
            (encode_qh(31), QuantumInstruction("QH", 31)),
            (encode_qx(0), QuantumInstruction("QX", 0)),
            (encode_qx(31), QuantumInstruction("QX", 31)),
            (encode_qcx(0, 31), QuantumInstruction("QCX", 0, q1=31)),
            (encode_qcx(31, 0), QuantumInstruction("QCX", 31, q1=0)),
            (encode_qmeas(0, 1), QuantumInstruction("QMEAS", 0, rd=1)),
            (encode_qmeas(31, 31), QuantumInstruction("QMEAS", 31, rd=31)),
        )
        for word, expected in cases:
            with self.subTest(word="0x%08x" % word):
                self.assertEqual(expected, decode_quantum_instruction(word))
                self.assertGreaterEqual(word, 0)
                self.assertLessEqual(word, 0xFFFFFFFF)

    def test_independently_constructed_word_and_formatter(self):
        # 不调用 production encoder：按字段手工拼出 QCX q[3], q[17]。
        manual_word = (
            (0 << 25)
            | (17 << 20)
            | (3 << 15)
            | (2 << 12)
            | (0 << 7)
            | 0x0B
        )
        self.assertEqual(0x0111A00B, manual_word)
        instruction = decode_quantum_instruction(manual_word)
        self.assertEqual(QuantumInstruction("QCX", 3, q1=17), instruction)
        self.assertEqual("QCX q[3], q[17]", format_instruction(instruction))

        formatted = (
            (QuantumInstruction("QH", 5), "QH q[5]"),
            (QuantumInstruction("QX", 31), "QX q[31]"),
            (QuantumInstruction("QMEAS", 7, rd=10), "QMEAS q[7] -> x10"),
        )
        for command, expected in formatted:
            with self.subTest(command=command):
                self.assertEqual(expected, format_instruction(command))

    def test_encoder_rejects_invalid_operands(self):
        for value in (-1, 32):
            with self.subTest(qubit=value):
                with self.assertRaises(QuantumInstructionError):
                    encode_qh(value)
        with self.assertRaises(TypeError):
            encode_qx(True)
        with self.assertRaises(QuantumInstructionError):
            encode_qcx(4, 4)
        with self.assertRaises(QuantumInstructionError):
            encode_qmeas(0, 0)
        with self.assertRaises(QuantumInstructionError):
            encode_qmeas(0, 32)

    def test_decoder_rejects_invalid_opcode_funct_and_word_range(self):
        with self.assertRaisesRegex(QuantumInstructionError, "opcode"):
            decode_quantum_instruction(encode_qh(0) ^ 0x01)
        with self.assertRaisesRegex(QuantumInstructionError, "funct3"):
            decode_quantum_instruction((4 << 12) | 0x0B)
        with self.assertRaisesRegex(QuantumInstructionError, "funct7"):
            decode_quantum_instruction((1 << 25) | encode_qh(0))
        for word in (-1, 1 << 32):
            with self.assertRaises(QuantumInstructionError):
                decode_quantum_instruction(word)
        for word in (True, 1.0, "0x0000000B"):
            with self.subTest(word=word):
                with self.assertRaises(TypeError):
                    decode_quantum_instruction(word)

    def test_decoder_does_not_claim_standard_riscv_words(self):
        # ADDI、JAL、BEQ 的标准 opcode 不能被误识别为 custom-0。
        for word in (0x00000013, 0x0000006F, 0x00000063):
            with self.subTest(word="0x%08x" % word):
                with self.assertRaisesRegex(QuantumInstructionError, "opcode"):
                    decode_quantum_instruction(word)

    def test_decoder_rejects_nonzero_reserved_fields(self):
        invalid_words = (
            encode_qh(0) | (1 << 20),
            encode_qx(0) | (1 << 7),
            encode_qcx(0, 1) | (1 << 7),
            encode_qmeas(0, 1) | (1 << 20),
            0x0B | (2 << 15) | (2 << 20) | (2 << 12),
            0x0B | (3 << 12),
        )
        for word in invalid_words:
            with self.subTest(word="0x%08x" % word):
                with self.assertRaises(QuantumInstructionError):
                    decode_quantum_instruction(word)


class QuantumTranslatorTests(unittest.TestCase):
    def test_supported_quantum_ops_translate_in_order(self):
        words = quantum_ops_to_words(
            ["h q[0];", "x q[31];", "cx q[0], q[1];", "measure q[0] -> c[0];"]
        )
        self.assertEqual(
            [encode_qh(0), encode_qx(31), encode_qcx(0, 1), encode_qmeas(0, 10)],
            words,
        )

    def test_unsupported_gate_fails_without_silent_drop(self):
        with self.assertRaisesRegex(
            QuantumTranslationError, "unsupported by Quantum RISC-V Bonus ISA"
        ):
            quantum_ops_to_words(["h q[0];", "rz(pi / 2) q[0];"])

    def test_classical_mapping_range_is_enforced(self):
        self.assertEqual(
            [encode_qmeas(31, 31)],
            quantum_ops_to_words(["measure q[31] -> c[21];"]),
        )
        with self.assertRaises(QuantumInstructionError):
            quantum_ops_to_words(["measure q[0] -> c[22];"])

    def test_quantum_mapping_range_is_enforced(self):
        self.assertEqual([encode_qh(31)], quantum_ops_to_words(["h q[31];"]))
        for operation in ("h q[32];", "cx q[0], q[32];", "measure q[32] -> c[0];"):
            with self.subTest(operation=operation):
                with self.assertRaises(QuantumInstructionError):
                    quantum_ops_to_words([operation])


class QuantumEmulatorTests(unittest.TestCase):
    def test_trace_backend_requires_integer_bits(self):
        for invalid in (True, 1.0, -1, 2):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    TraceCoprocessor([invalid])

    def test_classical_programs_match_official_emulator(self):
        programs = {
            "alu_negative_x0": """
                li x0, 99
                li x1, -7
                addi x2, x1, -5
                sub x3, x0, x2
                add x4, x1, x3
            """,
            "beq_taken_bne_not_taken": """
                li x1, -4
                li x2, -4
                beq x1, x2, A
                li x3, 91
                A: bne x1, x2, B
                addi x3, x0, 7
                B: addi x4, x3, 1
            """,
            "beq_not_taken_bne_taken": """
                li x1, 2
                li x2, 3
                beq x1, x2, BAD
                bne x1, x2, OK
                BAD: li x3, 99
                OK: addi x3, x0, -8
            """,
            "jump_and_multiple_labels": """
                li x1, 1
                j SECOND
                FIRST: li x2, 80
                j END
                SECOND: addi x1, x1, 2
                j FIRST
                END: add x3, x1, x2
            """,
            "sequential_branches": """
                li x1, 3
                li x2, 3
                beq x1, x2, SAME
                li x3, 99
                SAME: addi x2, x2, 1
                bne x1, x2, DIFFERENT
                li x4, 99
                DIFFERENT: sub x5, x2, x1
            """,
        }
        for name, program in programs.items():
            with self.subTest(name=name):
                official = TinyRISCVEmulator()
                official.load_program(program)
                extended = QuantumRISCVEmulator(TraceCoprocessor())
                extended.load_program(program)

                self.assertEqual(official.execute(), extended.execute())
                self.assertEqual(official.registers, extended.registers)
                self.assertEqual(official.pc, extended.pc)
                self.assertEqual(official.labels, extended.labels)
                self.assertEqual([], extended.quantum_trace)

    def test_classical_loop_limit_matches_official_emulator(self):
        official = TinyRISCVEmulator()
        extended = QuantumRISCVEmulator(TraceCoprocessor())
        for emulator in (official, extended):
            emulator.max_steps = 7
            emulator.load_program("LOOP: j LOOP")

        for emulator in (official, extended):
            with self.assertRaisesRegex(RuntimeError, "最大步数"):
                emulator.execute()
        self.assertEqual(official.pc, extended.pc)
        self.assertEqual(official.registers, extended.registers)

    def test_classical_repeat_execute_and_reload_match_official(self):
        program = "li x1, 4\naddi x1, x1, 3"
        official = TinyRISCVEmulator()
        extended = QuantumRISCVEmulator(TraceCoprocessor())
        for emulator in (official, extended):
            emulator.load_program(program)

        self.assertEqual(official.execute(), extended.execute())
        self.assertEqual(official.execute(), extended.execute())

        for emulator in (official, extended):
            emulator.load_program("addi x2, x0, -9")
        self.assertEqual(official.execute(), extended.execute())
        self.assertEqual(official.registers, extended.registers)

    def test_measurement_writeback_controls_beq_and_bne(self):
        measurement_word = encode_qmeas(3, 10)
        program = """
        .word 0x%08X
        beq x10, x0, ZERO_PATH
        bne x10, x0, ONE_PATH
        li x1, 999
        ZERO_PATH:
        li x1, 100
        j END
        ONE_PATH:
        li x1, 200
        END:
        addi x2, x1, 1
        """ % measurement_word

        for measurement, expected in ((0, 100), (1, 200)):
            with self.subTest(measurement=measurement):
                backend = TraceCoprocessor([measurement])
                emulator = QuantumRISCVEmulator(backend)
                emulator.load_program(program)
                state = emulator.execute()
                self.assertEqual(measurement, state.get("x10", 0))
                self.assertEqual(expected, state["x1"])
                self.assertEqual(expected + 1, state["x2"])
                expected_trace = [QuantumInstruction("QMEAS", 3, rd=10)]
                self.assertEqual(expected_trace, emulator.quantum_trace)
                self.assertEqual(expected_trace, backend.trace)

    def test_raw_word_must_decode_and_backend_result_must_be_bit(self):
        emulator = QuantumRISCVEmulator(TraceCoprocessor())
        emulator.load_program(".word 0x00000013")
        with self.assertRaises(QuantumInstructionError):
            emulator.execute()

        class InvalidMeasurementCoprocessor:
            def __init__(self, result):
                self.result = result

            def apply_gate(self, command):
                pass

            def measure(self, command):
                return self.result

        for invalid in (True, 1.0, 2):
            with self.subTest(invalid=invalid):
                emulator = QuantumRISCVEmulator(
                    InvalidMeasurementCoprocessor(invalid)
                )
                emulator.load_program(".word 0x%08X" % encode_qmeas(0, 10))
                with self.assertRaisesRegex(ValueError, "measurement"):
                    emulator.execute()

    def test_malformed_and_reserved_words_fail_fast(self):
        cases = (
            (".word", ValueError),
            (".word 0x0000000B 0x0000000B", ValueError),
            (".word not-a-number", ValueError),
            (".word -1", QuantumInstructionError),
            (".word 0x100000000", QuantumInstructionError),
            (".word 0x0200000B", QuantumInstructionError),
            (".word 0x0000400B", QuantumInstructionError),
        )
        for program, error_type in cases:
            with self.subTest(program=program):
                emulator = QuantumRISCVEmulator(TraceCoprocessor())
                emulator.load_program(program)
                with self.assertRaises(error_type):
                    emulator.execute()

    def test_dispatch_order_and_multiple_measurements(self):
        # 固定 raw words 验证真实 decoder 路径和测量值的顺序消费。
        program = """
            .word 0x0000000B
            .word 0x0000100B
            .word 0x0010200B
            .word 0x0000350B
            .word 0x0000B58B
        """
        backend = TraceCoprocessor([1, 0])
        emulator = QuantumRISCVEmulator(backend)
        emulator.load_program(program)
        state = emulator.execute()

        expected = [
            QuantumInstruction("QH", 0),
            QuantumInstruction("QX", 0),
            QuantumInstruction("QCX", 0, q1=1),
            QuantumInstruction("QMEAS", 0, rd=10),
            QuantumInstruction("QMEAS", 1, rd=11),
        ]
        self.assertEqual(expected, backend.trace)
        self.assertEqual(expected, emulator.quantum_trace)
        self.assertEqual(1, state["x10"])
        self.assertNotIn("x11", state)

    def test_classical_branch_can_skip_and_reach_quantum_words(self):
        program = """
            li x1, 0
            beq x1, x0, AFTER_SKIPPED
            .word 0x0000100B
            AFTER_SKIPPED:
            .word 0x0000000B
            bne x1, x0, END
            .word 0x0010200B
            END:
            addi x2, x0, 7
        """
        backend = TraceCoprocessor()
        emulator = QuantumRISCVEmulator(backend)
        emulator.load_program(program)
        state = emulator.execute()

        self.assertEqual(
            [
                QuantumInstruction("QH", 0),
                QuantumInstruction("QCX", 0, q1=1),
            ],
            backend.trace,
        )
        self.assertEqual(7, state["x2"])

    def test_same_quantum_program_is_deterministic_with_same_measurement(self):
        program = ".word 0x0000350B\naddi x1, x10, 9"
        outcomes = []
        for _ in range(2):
            emulator = QuantumRISCVEmulator(TraceCoprocessor([1]))
            emulator.load_program(program)
            outcomes.append((emulator.execute(), list(emulator.quantum_trace)))
        self.assertEqual(outcomes[0], outcomes[1])


class QuantumRISCVE2ETests(unittest.TestCase):
    def test_quantum_ops_to_words_to_emulator_to_trace(self):
        source = """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[2];
        creg c[1];
        h q[0];
        cx q[0], q[1];
        measure q[0] -> c[0];
        classical {
          if (c[0] == 1) { r1 = 200; } else { r1 = 100; }
          r2 = r1 + 1;
        }
        """
        quantum_ops, classical_assembly = compile_hybrid_source(source)
        words = quantum_ops_to_words(quantum_ops)
        program = word_lines(words) + "\n" + classical_assembly
        backend = TraceCoprocessor([1])
        emulator = QuantumRISCVEmulator(backend)
        emulator.load_program(program)
        state = emulator.execute()

        self.assertEqual([0x0000000B, 0x0010200B, 0x0000350B], words)
        self.assertEqual(
            [
                QuantumInstruction("QH", 0),
                QuantumInstruction("QCX", 0, q1=1),
                QuantumInstruction("QMEAS", 0, rd=10),
            ],
            backend.trace,
        )
        self.assertEqual(1, state["x10"])
        self.assertEqual(200, state["x1"])
        self.assertEqual(201, state["x2"])


if __name__ == "__main__":
    unittest.main()
