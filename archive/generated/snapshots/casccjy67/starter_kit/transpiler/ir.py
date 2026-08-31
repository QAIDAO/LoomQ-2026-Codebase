"""Intermediate representation for quantum circuits."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Gate:
    name: str
    qubits: List[int]
    params: List[float] = field(default_factory=list)

    def __repr__(self):
        q_str = ", ".join(f"q[{i}]" for i in self.qubits)
        if self.params:
            p_str = ", ".join(f"{p:.6f}" for p in self.params)
            return f"{self.name}({p_str}) {q_str}"
        return f"{self.name} {q_str}"


@dataclass
class Measurement:
    qubit: int
    clbit: int

    def __repr__(self):
        return f"measure q[{self.qubit}] -> c[{self.clbit}]"


@dataclass
class Circuit:
    num_qubits: int = 0
    num_clbits: int = 0
    qreg_name: str = "q"
    creg_name: str = "c"
    instructions: list = field(default_factory=list)

    def add_gate(self, name, qubits, params=None):
        self.instructions.append(Gate(name, qubits, params or []))

    def add_measurement(self, qubit, clbit):
        self.instructions.append(Measurement(qubit, clbit))

    @property
    def gates(self):
        return [i for i in self.instructions if isinstance(i, Gate)]

    @property
    def measurements(self):
        return [i for i in self.instructions if isinstance(i, Measurement)]

    def to_qasm2(self) -> str:
        lines = [
            'OPENQASM 2.0;',
            'include "qelib1.inc";',
            f'qreg {self.qreg_name}[{self.num_qubits}];',
            f'creg {self.creg_name}[{self.num_clbits}];',
        ]
        for inst in self.instructions:
            if isinstance(inst, Gate):
                q_str = ", ".join(f"{self.qreg_name}[{i}]" for i in inst.qubits)
                if inst.params:
                    p_str = ", ".join(f"{p:.10f}" for p in inst.params)
                    lines.append(f"{inst.name}({p_str}) {q_str};")
                else:
                    lines.append(f"{inst.name} {q_str};")
            elif isinstance(inst, Measurement):
                lines.append(
                    f"measure {self.qreg_name}[{inst.qubit}] -> "
                    f"{self.creg_name}[{inst.clbit}];"
                )
        return "\n".join(lines)
