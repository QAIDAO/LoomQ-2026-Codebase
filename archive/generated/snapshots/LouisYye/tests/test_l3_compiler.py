import itertools

import pytest

from starter_kit.adapter import compile_hybrid
from starter_kit.l3_compiler import HybridSyntaxError
from starter_kit.riscv_emulator import TinyRISCVEmulator


QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
'''


def run(classical, bits):
    operations, assembly = compile_hybrid(QASM + "classical {" + classical + "}")
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(bits):
        emulator.set_register(f"x{10 + index}", value)
    return operations, emulator.execute()


def test_public_branch_and_quantum_operations():
    operations, zero = run("if (c[0] == 1) { r1 = 7; } else { r1 = 3; }", (0, 0, 0))
    _, one = run("if (c[0] == 1) { r1 = 7; } else { r1 = 3; }", (1, 0, 0))
    assert zero["x1"] == 3
    assert one["x1"] == 7
    assert operations == [
        "h q[0];",
        "cx q[0],q[1];",
        "measure q[0] -> c[0];",
        "measure q[1] -> c[1];",
        "measure q[2] -> c[2];",
    ]


def test_all_measurements_match_reference_interpreter():
    program = """
        r1 = c[0] + c[1] - c[2];
        r2 = 4;
        if (c[0] != c[2]) {
            r2 = r2 + r1;
            if (c[1] == 1) { r3 = 9; } else { r3 = -2; }
        } else {
            r2 = r2 - 3;
            r3 = r1 + 8;
        }
        r4 = r2 + r3;
    """
    for bits in itertools.product((0, 1), repeat=3):
        _, state = run(program, bits)
        r1 = bits[0] + bits[1] - bits[2]
        if bits[0] != bits[2]:
            r2 = 4 + r1
            r3 = 9 if bits[1] == 1 else -2
        else:
            r2 = 1
            r3 = r1 + 8
        assert state.get("x1", 0) == r1
        assert state.get("x2", 0) == r2
        assert state.get("x3", 0) == r3
        assert state.get("x4", 0) == r2 + r3


@pytest.mark.parametrize(
    "classical",
    [
        "r0 = 1;",
        "r10 = 1;",
        "r1 = c[22];",
        "r1 = 1 * 2;",
        "while (c[0] == 1) { r1 = 2; }",
        "if (c[0] < 1) { r1 = 2; }",
    ],
)
def test_rejects_programs_outside_the_supported_subset(classical):
    with pytest.raises(HybridSyntaxError):
        compile_hybrid(QASM + "classical {" + classical + "}")


def test_requires_one_final_classical_block():
    operations, assembly = compile_hybrid(QASM)
    assert operations
    assert assembly == ""
    with pytest.raises(Exception):
        compile_hybrid(QASM + "classical { r1 = 1; } trailing")
    with pytest.raises(HybridSyntaxError):
        compile_hybrid(QASM + "classical { }")


def test_ignores_the_word_classical_in_a_qasm_comment():
    operations, state = run("r1 = 5;", (0, 0, 0))
    source = QASM + "// classical { not the program }\nclassical { r1 = 5; }"
    commented_operations, assembly = compile_hybrid(source)
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    assert emulator.execute()["x1"] == state["x1"]
    assert commented_operations == operations


def test_quantum_operations_after_classical_block_keep_source_order():
    source = QASM + "classical { r1 = 1; }\nx q[2];\ncx q[0],q[1];"
    operations, assembly = compile_hybrid(source)
    assert operations[-2:] == ["x q[2];", "cx q[0],q[1];"]
    assert "li x1, 1" in assembly


def test_long_left_associative_chain_uses_constant_scratch_space():
    expression = " + ".join(["c[0]"] + ["1"] * 100)
    _, assembly = compile_hybrid(QASM + f"classical {{ r1 = {expression}; }}")
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    emulator.set_register("x10", 1)
    assert emulator.execute()["x1"] == 101


def test_peephole_keeps_400_assignments_below_step_limit():
    statements = "\n".join("r1 = r1 + 1;" for _ in range(400))
    _, assembly = compile_hybrid(QASM + "classical {" + statements + "}")
    assert len([line for line in assembly.splitlines() if line.strip()]) == 400
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    assert emulator.execute()["x1"] == 400


def test_destination_aliases_preserve_expression_inputs():
    _, state = run("r1 = 5; r2 = 3; r1 = r2 + r1 + r1;", (0, 0, 0))
    assert state["x1"] == 13
