"""SpinQ Cloud backend adapter."""
import uuid
from .ir import Circuit, Gate, Measurement
from .base_backend import BaseBackend, expand_cu1


class SpinQBackend(BaseBackend):
    name = "spinq"

    def transpile(self, circuit: Circuit) -> str:
        expanded = self._expand_cu1(circuit)
        return expanded.to_qasm2()

    def run(self, circuit: Circuit, shots: int = 8192) -> dict:
        expanded = self._expand_cu1(circuit)
        qasm_str = expanded.to_qasm2()

        try:
            from spinqit import get_compiler, get_basic_simulator, BasicSimulatorConfig
        except ImportError:
            return self._run_fallback(expanded, shots)

        compiler = get_compiler("qasm")
        simulator = get_basic_simulator()
        config = BasicSimulatorConfig()
        config.configure_shots(shots)

        exe = compiler.compile(qasm_str, 0)
        result = simulator.execute(exe, config)

        counts = dict(result.counts) if hasattr(result, "counts") else {}

        return self._build_result(
            "spinq_taurus",
            str(uuid.uuid4())[:16],
            shots,
            counts,
            circuit.num_clbits,
            {"transpiled_gates": len(expanded.gates), "depth": self._estimate_depth(expanded)},
        )

    def _run_fallback(self, circuit: Circuit, shots: int) -> dict:
        return self._build_result(
            "spinq_taurus",
            str(uuid.uuid4())[:16],
            shots,
            {},
            circuit.num_clbits,
            {"error": "spinqit not installed"},
        )

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
