"""AWS Braket backend adapter."""
import uuid
from .ir import Circuit, Gate, Measurement
from .base_backend import BaseBackend, expand_cu1


class BraketBackend(BaseBackend):
    name = "braket"

    GATE_MAP = {
        "h": "h", "x": "x", "s": "s", "sdg": "si",
        "t": "t", "tdg": "ti", "rz": "rz", "ry": "ry",
        "cx": "cnot", "cu1": "cu1", "swap": "swap", "ccx": "ccnot",
    }

    def transpile(self, circuit: Circuit) -> str:
        return self._to_qasm3(circuit)

    def run(self, circuit: Circuit, shots: int = 8192) -> dict:
        try:
            from braket.circuits import Circuit
            from braket.devices import LocalSimulator
        except ImportError:
            return self._run_fallback(circuit, shots)

        braket_circuit = self._to_braket_circuit(circuit)
        device = LocalSimulator()
        task = device.run(braket_circuit, shots=shots)
        result = task.result()
        counts = dict(result.measurement_counts)

        return self._build_result(
            "braket_local_simulator",
            str(uuid.uuid4())[:16],
            shots,
            counts,
            circuit.num_clbits,
            {"transpiled_gates": len(circuit.gates), "depth": self._estimate_depth(circuit)},
        )

    def _to_braket_circuit(self, circuit: Circuit):
        from braket.circuits import Circuit
        braket_circ = Circuit()

        for inst in circuit.instructions:
            if isinstance(inst, Gate):
                if inst.name == "cu1":
                    for g in expand_cu1(inst.qubits[0], inst.qubits[1], inst.params[0]):
                        self._apply_gate(braket_circ, g)
                else:
                    self._apply_gate(braket_circ, inst)
            elif isinstance(inst, Measurement):
                braket_circ.measure(inst.qubit)

        if not circuit.measurements:
            for i in range(circuit.num_qubits):
                braket_circ.measure(i)

        return braket_circ

    def _apply_gate(self, circ, gate: Gate):
        method_name = self.GATE_MAP.get(gate.name)
        if not method_name:
            raise ValueError(f"Unsupported gate: {gate.name}")
        method = getattr(circ, method_name)
        if gate.params:
            method(*gate.qubits, *gate.params)
        else:
            method(*gate.qubits)

    def _to_qasm3(self, circuit: Circuit) -> str:
        expanded = self._expand_cu1(circuit)
        lines = [
            "OPENQASM 3;",
            f"qubit[{expanded.num_qubits}] q;",
            f"bit[{expanded.num_clbits}] c;",
        ]
        for inst in expanded.instructions:
            if isinstance(inst, Gate):
                q_str = ", ".join(f"q[{i}]" for i in inst.qubits)
                if inst.params:
                    p_str = ", ".join(f"{p:.10f}" for p in inst.params)
                    lines.append(f"{inst.name}({p_str}) {q_str};")
                else:
                    lines.append(f"{inst.name} {q_str};")
            elif isinstance(inst, Measurement):
                lines.append(f"c[{inst.clbit}] = measure q[{inst.qubit}];")
        return "\n".join(lines)

    @staticmethod
    def _expand_cu1(circuit: Circuit) -> Circuit:
        expanded = Circuit(
            num_qubits=circuit.num_qubits,
            num_clbits=circuit.num_clbits,
            qreg_name=circuit.qreg_name,
            creg_name=circuit.creg_name,
        )
        for inst in circuit.instructions:
            if isinstance(inst, Gate) and inst.name == "cu1":
                c, t = inst.qubits[0], inst.qubits[1]
                for g in expand_cu1(c, t, inst.params[0]):
                    expanded.instructions.append(g)
            else:
                expanded.instructions.append(inst)
        return expanded

    @staticmethod
    def _estimate_depth(circuit: Circuit) -> int:
        if not circuit.gates:
            return 0
        layers = [0] * circuit.num_qubits
        for g in circuit.gates:
            max_layer = max(layers[q] for q in g.qubits)
            for q in g.qubits:
                layers[q] = max_layer + 1
        return max(layers) if layers else 0

    def _run_fallback(self, circuit: Circuit, shots: int) -> dict:
        return self._build_result(
            "braket_local_simulator",
            str(uuid.uuid4())[:16],
            shots,
            {},
            circuit.num_clbits,
            {"error": "amazon-braket-sdk not installed"},
        )
