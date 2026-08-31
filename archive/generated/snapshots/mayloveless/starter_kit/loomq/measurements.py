"""平台无关的测量映射与经典位序转换。"""

from typing import Dict, List, Mapping, Sequence, Tuple

from .ir import (
    Circuit,
    ClassicalBitRef,
    ClassicalRegisterRef,
    MeasureOperation,
    QubitRef,
    QuantumRegisterRef,
)


def _register_offsets(registers: Sequence[object]) -> Dict[str, int]:
    offsets: Dict[str, int] = {}
    offset = 0
    for register in registers:
        name = getattr(register, "name")
        size = getattr(register, "size")
        offsets[name] = offset
        offset += size
    return offsets


def quantum_bit_indices(circuit: Circuit) -> Dict[QubitRef, int]:
    """按量子寄存器声明顺序生成 QubitRef 到全局索引的映射。"""
    indices: Dict[QubitRef, int] = {}
    offset = 0
    for register in circuit.quantum_registers:
        for index in range(register.size):
            indices[QubitRef(register.name, index)] = offset + index
        offset += register.size
    return indices


def classical_bit_count(circuit: Circuit) -> int:
    """返回所有经典寄存器包含的经典位总数。"""
    return sum(register.size for register in circuit.classical_registers)


def measurement_mapping(circuit: Circuit) -> List[Tuple[int, int]]:
    """返回 (量子位全局索引, 经典位全局索引) 测量映射。"""
    quantum_offsets = _register_offsets(circuit.quantum_registers)
    classical_offsets = _register_offsets(circuit.classical_registers)
    quantum_sizes = {
        register.name: register.size for register in circuit.quantum_registers
    }
    mapping: List[Tuple[int, int]] = []
    written_classical_bits = set()

    for operation in circuit.operations:
        if not isinstance(operation, MeasureOperation):
            continue
        if isinstance(operation.quantum, QubitRef) and isinstance(
            operation.classical, ClassicalBitRef
        ):
            quantum_register = operation.quantum.register
            classical_register = operation.classical.register
            pairs = [(operation.quantum.index, operation.classical.index)]
        elif isinstance(operation.quantum, QuantumRegisterRef) and isinstance(
            operation.classical, ClassicalRegisterRef
        ):
            quantum_register = operation.quantum.register
            classical_register = operation.classical.register
            pairs = [(index, index) for index in range(quantum_sizes[quantum_register])]
        else:
            raise ValueError("invalid mixed-width measurement in Circuit IR")

        # 整寄存器测量在此展开，两个 Runner 不再各自计算 offset。
        for quantum_index, classical_index in pairs:
            global_quantum = quantum_offsets[quantum_register] + quantum_index
            global_classical = classical_offsets[classical_register] + classical_index
            if global_classical in written_classical_bits:
                raise ValueError(
                    "classical bit %d is written by more than one measurement"
                    % global_classical
                )
            written_classical_bits.add(global_classical)
            mapping.append((global_quantum, global_classical))
    return mapping


def build_classical_key(
    circuit: Circuit,
    mapping: Sequence[Tuple[int, int]],
    quantum_values: Mapping[int, int],
) -> str:
    """依据测量映射生成官方 c[n-1]...c[0] 格式的 key。"""
    bit_count = classical_bit_count(circuit)
    if bit_count <= 0:
        raise ValueError("circuit must declare at least one classical bit")

    classical_bits = [0] * bit_count
    for quantum_index, classical_index in mapping:
        if quantum_index not in quantum_values:
            raise ValueError(
                "measurement result is missing quantum bit %d" % quantum_index
            )
        value = quantum_values[quantum_index]
        if value not in (0, 1):
            raise ValueError("measurement values must be binary")
        classical_bits[classical_index] = value

    # 未测量经典位保持 0，并按全局经典位索引倒序输出。
    return "".join(str(classical_bits[index]) for index in reversed(range(bit_count)))
