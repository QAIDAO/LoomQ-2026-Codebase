"""OpenQASM 2.0 parser — converts QASM text to Circuit IR."""
import re
from .ir import Circuit, Gate, Measurement

GATE_WHITELIST = {
    "h", "x", "s", "sdg", "t", "tdg",
    "rz", "ry",
    "cx", "cu1", "swap",
    "ccx",
}

PARAM_GATES = {"rz", "ry", "cu1"}


class QASMParseError(Exception):
    pass


class QASMParser:
    def parse(self, qasm_str: str) -> Circuit:
        circuit = Circuit()
        lines = self._preprocess(qasm_str)

        for lineno, line in enumerate(lines, 1):
            try:
                self._parse_line(line, circuit)
            except QASMParseError:
                raise
            except Exception as e:
                raise QASMParseError(
                    f"Line {lineno}: failed to parse '{line}': {e}"
                )

        if circuit.num_qubits == 0:
            raise QASMParseError("No qreg declaration found")
        return circuit

    def _preprocess(self, qasm_str: str) -> list:
        lines = []
        for raw in qasm_str.split("\n"):
            line = raw.strip()
            if not line:
                continue
            while ";" in line:
                stmt, _, line = line.partition(";")
                stmt = stmt.strip()
                if stmt:
                    lines.append(stmt)
            if line.strip():
                lines.append(line.strip())
        return lines

    def _parse_line(self, line: str, circuit: Circuit):
        lower = line.lower()

        if lower.startswith("openqasm"):
            return
        if lower.startswith("include"):
            return
        if lower.startswith("//") or lower.startswith("barrier"):
            return

        if lower.startswith("qreg"):
            m = re.match(r"qreg\s+(\w+)\s*\[\s*(\d+)\s*\]", line, re.I)
            if not m:
                raise QASMParseError(f"Invalid qreg: {line}")
            circuit.qreg_name = m.group(1)
            circuit.num_qubits = int(m.group(2))
            return

        if lower.startswith("creg"):
            m = re.match(r"creg\s+(\w+)\s*\[\s*(\d+)\s*\]", line, re.I)
            if not m:
                raise QASMParseError(f"Invalid creg: {line}")
            circuit.creg_name = m.group(1)
            circuit.num_clbits = int(m.group(2))
            return

        if lower.startswith("measure"):
            self._parse_measure(line, circuit)
            return

        self._parse_gate(line, circuit)

    def _parse_measure(self, line: str, circuit: Circuit):
        m = re.match(
            r"measure\s+(\w+)\s*\[\s*(\d+)\s*\]\s*->\s*(\w+)\s*\[\s*(\d+)\s*\]",
            line, re.I,
        )
        if m:
            qubit = int(m.group(2))
            clbit = int(m.group(4))
            circuit.add_measurement(qubit, clbit)
            return

        m = re.match(r"measure\s+(\w+)\s*->\s*(\w+)", line, re.I)
        if m:
            qreg = m.group(1)
            creg = m.group(2)
            n = min(circuit.num_qubits, circuit.num_clbits)
            for i in range(n):
                circuit.add_measurement(i, i)
            return

        raise QASMParseError(f"Invalid measure statement: {line}")

    def _parse_gate(self, line: str, circuit: Circuit):
        m = re.match(r"(\w+)\s*\(([^)]*)\)\s+(.+)", line)
        if m:
            gate_name = m.group(1).lower()
            params = self._parse_params(m.group(2))
            qubit_args = self._parse_qubits(m.group(3), circuit.qreg_name)
        else:
            m = re.match(r"(\w+)\s+(.+)", line)
            if not m:
                raise QASMParseError(f"Cannot parse gate: {line}")
            gate_name = m.group(1).lower()
            params = []
            qubit_args = self._parse_qubits(m.group(2), circuit.qreg_name)

        if gate_name not in GATE_WHITELIST:
            raise QASMParseError(
                f"Gate '{gate_name}' not in whitelist. "
                f"Allowed: {GATE_WHITELIST}"
            )

        expected = {
            "h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
            "rz": 1, "ry": 1, "cx": 2, "cu1": 2, "swap": 2, "ccx": 3,
        }
        n_expected = expected.get(gate_name)
        if n_expected and len(qubit_args) != n_expected:
            raise QASMParseError(
                f"Gate '{gate_name}' expects {n_expected} qubits, "
                f"got {len(qubit_args)}"
            )

        if gate_name in PARAM_GATES and not params:
            raise QASMParseError(f"Gate '{gate_name}' requires parameters")

        circuit.add_gate(gate_name, qubit_args, params)

    def _parse_params(self, param_str: str) -> list:
        param_str = param_str.strip()
        if not param_str:
            return []
        parts = [p.strip() for p in param_str.split(",")]
        result = []
        for p in parts:
            try:
                val = float(eval(p, {"__builtins__": {"pi": 3.141592653589793}}, {}))
            except Exception:
                try:
                    val = float(p)
                except ValueError:
                    raise QASMParseError(f"Cannot parse parameter: {p}")
            result.append(val)
        return result

    def _parse_qubits(self, qubit_str: str, qreg_name: str) -> list:
        parts = [p.strip() for p in qubit_str.split(",")]
        result = []
        for part in parts:
            m = re.match(r"(\w+)\s*\[\s*(\d+)\s*\]", part)
            if m:
                result.append(int(m.group(2)))
            else:
                m = re.match(r"(\w+)$", part)
                if m and m.group(1) == qreg_name:
                    raise QASMParseError(
                        f"Full-register gate not supported for this backend: {part}. "
                        f"Please expand to individual qubits."
                    )
                raise QASMParseError(f"Cannot parse qubit reference: {part}")
        return result
