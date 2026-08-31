"""Origin Quantum backend adapter (pyQPanda3)."""
import uuid
from .ir import Circuit, Gate, Measurement
from .base_backend import BaseBackend


class OriginQBackend(BaseBackend):
    name = "originq"

    def transpile(self, circuit: Circuit) -> str:
        qasm_str = circuit.to_qasm2()
        try:
            from pyqpanda3.intermediate_compiler import convert_qasm_string_to_qprog
            prog = convert_qasm_string_to_qprog(qasm_str)
            return prog.originir()
        except ImportError:
            return self._generate_originir_fallback(circuit)

    def run(self, circuit: Circuit, shots: int = 8192) -> dict:
        qasm_str = circuit.to_qasm2()

        try:
            from pyqpanda3.intermediate_compiler import convert_qasm_string_to_qprog
            from pyqpanda3 import core
        except ImportError:
            return self._run_fallback(circuit, shots)

        prog = convert_qasm_string_to_qprog(qasm_str)
        machine = core.CPUQVM()
        machine.run(prog, shots=shots)
        counts = machine.result().get_counts()

        return self._build_result(
            "originq_simulator",
            str(uuid.uuid4())[:16],
            shots,
            counts,
            circuit.num_clbits,
            {"transpiled_gates": len(circuit.gates), "depth": self._estimate_depth(circuit)},
        )

    def _run_fallback(self, circuit: Circuit, shots: int) -> dict:
        return self._build_result(
            "originq_simulator",
            str(uuid.uuid4())[:16],
            shots,
            {},
            circuit.num_clbits,
            {"error": "pyqpanda3 not installed"},
        )

    @staticmethod
    def _generate_originir_fallback(circuit: Circuit) -> str:
        lines = [
            f"QINIT {circuit.num_qubits}",
            f"CREG {circuit.num_clbits}",
        ]
        for inst in circuit.instructions:
            if isinstance(inst, Gate):
                q_str = ", ".join(f"q[{i}]" for i in inst.qubits)
                gate_map = {
                    "h": "H", "x": "X", "s": "S", "sdg": "Sdg",
                    "t": "T", "tdg": "Tdg", "rz": "RZ", "ry": "RY",
                    "cx": "CNOT", "cu1": "CP", "swap": "SWAP", "ccx": "TOFFOLI",
                }
                gate_name = gate_map.get(inst.name, inst.name.upper())
                if inst.params:
                    param_str = ", ".join(f"{p:.10f}" for p in inst.params)
                    lines.append(f"{gate_name}({param_str}) {q_str}")
                else:
                    lines.append(f"{gate_name} {q_str}")
            elif isinstance(inst, Measurement):
                lines.append(f"MEASURE q[{inst.qubit}], c[{inst.clbit}]")
        return "\n".join(lines)

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
