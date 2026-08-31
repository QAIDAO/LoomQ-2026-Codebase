from starter_kit.l3_compiler import compile_hybrid, emit_quantum_riscv
import pytest

from starter_kit.riscv_emulator import (
    CUSTOM0_OPCODE,
    GATE_ARITY,
    TinyRISCVEmulator,
    decode_quantum_instruction,
    encode_quantum_instruction,
)


def test_hybrid_source_reaches_quantum_trace_and_classical_result():
    source = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical { if (c[0] == c[1]) { r1 = 1; } else { r1 = 0; } }
'''
    operations, classical = compile_hybrid(source)
    assembly = emit_quantum_riscv(operations) + classical
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    emulator.set_register("x10", 1)
    emulator.set_register("x11", 1)
    state = emulator.execute()
    assert state["x1"] == 1
    assert emulator.quantum_trace == [
        {"op": "gate", "gate": "h", "qubits": [0]},
        {"op": "gate", "gate": "cx", "qubits": [0, 1]},
        {"op": "measure", "qubit": 0, "bit": 0},
        {"op": "measure", "qubit": 1, "bit": 1},
    ]
    assert assembly.splitlines()[0].startswith(".word 0x")


@pytest.mark.parametrize("gate,arity", GATE_ARITY.items())
def test_all_gate_encodings_round_trip(gate, arity):
    operation = {"op": "gate", "gate": gate, "qubits": list(range(arity))}
    word = encode_quantum_instruction(operation)
    assert 0 <= word <= 0xFFFFFFFF
    assert word & 0x7F == CUSTOM0_OPCODE
    assert decode_quantum_instruction(word) == operation


def test_measure_encoding_round_trip():
    operation = {"op": "measure", "qubit": 17, "bit": 9}
    assert decode_quantum_instruction(encode_quantum_instruction(operation)) == operation


def test_decoder_rejects_wrong_opcode_and_nonzero_reserved_fields():
    with pytest.raises(ValueError, match="custom-0"):
        decode_quantum_instruction(0)
    valid = encode_quantum_instruction({"op": "measure", "qubit": 1, "bit": 2})
    with pytest.raises(ValueError, match="reserves"):
        decode_quantum_instruction(valid | (1 << 20))
