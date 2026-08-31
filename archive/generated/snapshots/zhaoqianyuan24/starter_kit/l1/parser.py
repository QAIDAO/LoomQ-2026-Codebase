import re

from .ir import (
    Circuit,
    Gate,
    Measurement,
)

from .gates import (
    SUPPORTED_GATES,
    get_gate_arity,
    get_gate_num_params,
)

def get_index(text: str) -> int:
    left = text.index("[")
    right = text.index("]")
    number = text[left + 1:right]
    return int(number)

def validate_qubit_indices(
    qubit_indices: tuple,
    num_qubits: int
):
    for qubit_idx in qubit_indices:
        if qubit_idx < 0 or qubit_idx >= num_qubits:
            raise ValueError(
                f"Invalid qubit index q[{qubit_idx}]. "
                f"Circuit only has {num_qubits} qubits."
            )

def parse_gate(statement: str) -> Gate:
    gate_head, arguments = statement.split(maxsplit=1)

    parameter = None

    if "(" in gate_head:
        left = gate_head.index("(")
        right = gate_head.index(")")

        gate_name = gate_head[:left]
        parameter = gate_head[left + 1:right]
    else:
        gate_name = gate_head

    qubit_texts = arguments.split(",")

    qubit_indices = tuple(
        get_index(text)
        for text in qubit_texts
    )

    return Gate(
        name=gate_name,
        qubit_indices=qubit_indices,
        parameter=parameter
    )

def validate_gate(
    gate: Gate,
    num_qubits: int,
) -> None:

    if gate.name not in SUPPORTED_GATES:
        raise ValueError(
            f"Unsupported gate: {gate.name}"
        )

    # --------------------------------------------------
    # Check qubit arity
    # --------------------------------------------------

    expected_arity = get_gate_arity(
        gate.name
    )

    actual_arity = len(
        gate.qubit_indices
    )

    if actual_arity != expected_arity:
        raise ValueError(
            f"Gate '{gate.name}' expects "
            f"{expected_arity} qubit(s), "
            f"but got {actual_arity}."
        )

    # --------------------------------------------------
    # Check parameter count
    # --------------------------------------------------

    expected_params = get_gate_num_params(
        gate.name
    )

    actual_params = (
        0
        if gate.parameter is None
        else 1
    )

    if actual_params != expected_params:
        raise ValueError(
            f"Gate '{gate.name}' expects "
            f"{expected_params} parameter(s), "
            f"but got {actual_params}."
        )

    # --------------------------------------------------
    # Check qubit indices
    # --------------------------------------------------

    for qubit_idx in gate.qubit_indices:

        if (
            qubit_idx < 0
            or qubit_idx >= num_qubits
        ):
            raise ValueError(
                f"Invalid qubit index q[{qubit_idx}]. "
                f"Circuit only has "
                f"{num_qubits} qubits."
            )

def parse_measurement(
    statement: str,
    num_qubits: int,
    num_clbits: int
    ) -> list[Measurement]:

    body = statement.split(maxsplit=1)[1]

    qubit_text, cbit_text = body.split("->")

    qubit_text = qubit_text.strip()
    cbit_text = cbit_text.strip()

    # 情况 1：单个 qubit 测量
    # measure q[0] -> c[0]
    if "[" in qubit_text:
        return [
            Measurement(
                qubit_idx=get_index(qubit_text),
                cbit_idx=get_index(cbit_text)
            )
        ]

    # 情况 2：整个寄存器测量
    # measure q -> c
    if num_qubits != num_clbits:
        raise ValueError(
            "Whole-register measurement requires "
            "the same number of qubits and classical bits"
        )

    measurements = []

    for idx in range(num_qubits):
        measurements.append(
            Measurement(
                qubit_idx=idx,
                cbit_idx=idx
            )
        )

    return measurements

def validate_measurement(
    measurement: Measurement,
    num_qubits: int,
    num_clbits: int
):
    if (
        measurement.qubit_idx < 0
        or measurement.qubit_idx >= num_qubits
    ):
        raise ValueError(
            f"Invalid measurement qubit "
            f"q[{measurement.qubit_idx}]"
        )

    if (
        measurement.cbit_idx < 0
        or measurement.cbit_idx >= num_clbits
    ):
        raise ValueError(
            f"Invalid classical bit "
            f"c[{measurement.cbit_idx}]"
        )

def parse_qasm2(qasm_str: str) -> Circuit:

    SUPPORTED_GATES = {
    "h",
    "x",
    "s",
    "sdg",
    "t",
    "tdg",
    "rz",
    "ry",
    "cx",
    "cu1",
    "swap",
    "ccx",
    }
    num_qubits = 0
    num_clbits = 0
    operations = []

    statements = qasm_str.split(";")

    for statement in statements:

        statement = statement.strip()

        if not statement:
            continue

        if statement.startswith("OPENQASM"):
            continue

        if statement.startswith("include"):
            continue

        if statement.startswith("qreg"):
            num_qubits = get_index(statement)
            continue

        if statement.startswith("creg"):
            num_clbits = get_index(statement)
            continue

        if statement.startswith("measure "):
           measurements = parse_measurement(
           statement,
           num_qubits,
           num_clbits
           )
           for measurement in measurements:
                validate_measurement(
                measurement,
                num_qubits,
                num_clbits
                )

           operations.extend(measurements)

           continue

        gate = parse_gate(statement)
        
        if gate.name not in SUPPORTED_GATES:
            raise ValueError(
                f"Unsupported gate: {gate.name}"
            )
        validate_gate(
            gate,
            num_qubits
        )
        validate_qubit_indices(
        gate.qubit_indices,
        num_qubits
        )
        operations.append(gate)
    return Circuit(
        num_qubits=num_qubits,
        num_clbits=num_clbits,
        operations=operations
    )
