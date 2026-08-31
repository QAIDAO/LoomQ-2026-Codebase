"""Braket ``braket_sv`` 上的白名单全门真实集成测试。"""

import importlib.util
import unittest
from typing import Dict

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema


BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None
SHOTS = 4096


def qasm(body: str, qubits: int = 1) -> str:
    """构造只供真实 Runner 使用的最小 OpenQASM 2 程序。"""
    return (
        'OPENQASM 2.0; include "qelib1.inc"; '
        "qreg q[%d]; creg c[%d]; %s measure q -> c;" % (qubits, qubits, body)
    )


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class BraketFullGateIntegrationTests(unittest.TestCase):
    """通过 adapter.run 验证 Parser、IR、Serializer 和真实模拟器链路。"""

    def run_qasm(self, source: str) -> Dict[str, float]:
        result = adapter.run(source, "braket", SHOTS)
        valid, reason = validate_schema(result)
        self.assertTrue(valid, reason)
        self.assertEqual("little", result["bit_order"])
        self.assertEqual(SHOTS, result["shots"])
        self.assertEqual(SHOTS, sum(result["counts"].values()))
        return {key: value / SHOTS for key, value in result["counts"].items()}

    def assert_probability(self, probabilities: Dict[str, float], key: str, minimum: float) -> None:
        self.assertGreaterEqual(probabilities.get(key, 0.0), minimum)

    def assert_equivalent(self, original: str, decomposed: str) -> None:
        observed = self.run_qasm(original)
        expected = self.run_qasm(decomposed)
        self.assertGreaterEqual(
            calculate_hellinger_fidelity(observed, expected), 0.97
        )

    def test_x_flips_computational_basis_state(self) -> None:
        self.assert_probability(self.run_qasm(qasm("x q[0];")), "1", 0.999)

    def test_h_creates_balanced_superposition(self) -> None:
        probabilities = self.run_qasm(qasm("h q[0];"))
        self.assertGreaterEqual(probabilities.get("0", 0.0), 0.45)
        self.assertGreaterEqual(probabilities.get("1", 0.0), 0.45)

    def test_phase_gates_are_observable_by_interference(self) -> None:
        # 相位门夹在两个 H 之间，避免直接测量 |0> 的无效覆盖。
        cases = {
            "s": ("s q[0];", 0.45),
            "sdg": ("sdg q[0];", 0.45),
            "t": ("t q[0];", 0.10),
            "tdg": ("tdg q[0];", 0.10),
            "rz": ("rz(-pi/4) q[0];", 0.10),
        }
        for gate, (operation, minimum_one) in cases.items():
            with self.subTest(gate=gate):
                probabilities = self.run_qasm(qasm("h q[0]; %s h q[0];" % operation))
                self.assert_probability(probabilities, "1", minimum_one)

        # 成对逆门也应恢复初态，覆盖 pi/2 参数表达式。
        restored = self.run_qasm(qasm("h q[0]; rz(pi/2) q[0]; rz(-pi/2) q[0]; h q[0];"))
        self.assert_probability(restored, "0", 0.999)

    def test_ry_supports_pi_and_nontrivial_angle(self) -> None:
        self.assert_probability(self.run_qasm(qasm("ry(pi) q[0];")), "1", 0.999)
        probabilities = self.run_qasm(qasm("ry(pi/2) q[0];"))
        self.assertGreaterEqual(probabilities.get("0", 0.0), 0.45)
        self.assertGreaterEqual(probabilities.get("1", 0.0), 0.45)

    def test_cx_bell_regression(self) -> None:
        probabilities = self.run_qasm(qasm("h q[0]; cx q[0], q[1];", 2))
        self.assertGreaterEqual(
            calculate_hellinger_fidelity(probabilities, {"00": 0.5, "11": 0.5}),
            0.97,
        )

    def test_swap_matches_official_decomposition(self) -> None:
        self.assert_equivalent(
            qasm("x q[0]; swap q[0], q[1];", 2),
            qasm("x q[0]; cx q[0], q[1]; cx q[1], q[0]; cx q[0], q[1];", 2),
        )
        self.assert_probability(self.run_qasm(qasm("x q[0]; swap q[0], q[1];", 2)), "10", 0.999)

    def test_ccx_matches_official_decomposition_and_controls(self) -> None:
        decomposition = (
            "h q[2]; cx q[1], q[2]; tdg q[2]; cx q[0], q[2]; t q[2]; "
            "cx q[1], q[2]; tdg q[2]; cx q[0], q[2]; t q[1]; t q[2]; h q[2]; "
            "cx q[0], q[1]; t q[0]; tdg q[1]; cx q[0], q[1];"
        )
        self.assert_equivalent(
            qasm("h q[0]; h q[1]; ccx q[0], q[1], q[2];", 3),
            qasm("h q[0]; h q[1]; %s" % decomposition, 3),
        )
        self.assert_probability(self.run_qasm(qasm("x q[0]; x q[1]; ccx q[0], q[1], q[2];", 3)), "111", 0.999)
        self.assert_probability(self.run_qasm(qasm("x q[0]; ccx q[0], q[1], q[2];", 3)), "001", 0.999)

    def test_cu1_maps_to_cp_and_matches_official_decomposition(self) -> None:
        # theta=pi/2 时，官方 u1 分解中的 u1(±theta/2) 分别是 t/tdg。
        original = qasm("h q[0]; h q[1]; cu1(pi/2) q[0], q[1]; h q[0]; h q[1];", 2)
        decomposed = qasm(
            "h q[0]; h q[1]; t q[0]; cx q[0], q[1]; tdg q[1]; "
            "cx q[0], q[1]; t q[1]; h q[0]; h q[1];",
            2,
        )
        self.assert_equivalent(original, decomposed)


if __name__ == "__main__":
    unittest.main()
