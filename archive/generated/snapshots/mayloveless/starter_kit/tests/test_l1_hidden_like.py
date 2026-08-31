"""L1 隐藏用例风格的三平台真实组合电路回归测试。"""

import importlib.util
import os
import random
import unittest
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema


SHOTS = 4096
DETERMINISTIC_SHOTS = 256
RANDOM_SEEDS = (20260801, 20260802, 20260803)
ALL_GATES = (
    "h",
    "x",
    "s",
    "sdg",
    "t",
    "tdg",
    "ry",
    "rz",
    "cx",
    "cu1",
    "swap",
    "ccx",
)
PARAMETER_ANGLES = ("pi/2", "-pi/4", "3*pi/8")
QUBIT_COUNTS = {
    "h": 1,
    "x": 1,
    "s": 1,
    "sdg": 1,
    "t": 1,
    "tdg": 1,
    "ry": 1,
    "rz": 1,
    "cx": 2,
    "cu1": 2,
    "swap": 2,
    "ccx": 3,
}
INVERSE_GATES = {
    "h": "h",
    "x": "x",
    "s": "sdg",
    "sdg": "s",
    "t": "tdg",
    "tdg": "t",
    "ry": "ry",
    "rz": "rz",
    "cx": "cx",
    "cu1": "cu1",
    "swap": "swap",
    "ccx": "ccx",
}

BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None
SPINQ_WORKER_CONFIGURED = bool(os.environ.get("LOOMQ_SPINQ_PYTHON"))
ORIGINQ_WORKER_CONFIGURED = bool(os.environ.get("LOOMQ_ORIGINQ_PYTHON"))


@dataclass(frozen=True)
class GateRecord:
    """测试侧结构化门记录，避免对 QASM 字符串做逆序处理。"""

    name: str
    qubits: Tuple[int, ...]
    parameter: Optional[str] = None


@dataclass(frozen=True)
class OracleCase:
    """测试侧手算 Oracle，不依赖 production simulator 生成期望值。"""

    case_id: str
    source: str
    expected_key: str


def render_gate(operation: GateRecord) -> str:
    parameter = "(%s)" % operation.parameter if operation.parameter else ""
    operands = ", ".join("q[%d]" % qubit for qubit in operation.qubits)
    return "%s%s %s;" % (operation.name, parameter, operands)


def build_qasm(
    qubits: int,
    operations: Iterable[GateRecord],
    measurements: Optional[Sequence[str]] = None,
) -> str:
    """从结构化门记录构造完整 OpenQASM 2.0 程序。"""
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % qubits,
        "creg c[%d];" % qubits,
    ]
    lines.extend(render_gate(operation) for operation in operations)
    lines.extend(measurements or ("measure q -> c;",))
    return "\n".join(lines) + "\n"


def negate_angle(angle: str) -> str:
    """保留参数表达式结构，并生成 Parser 可处理的负角。"""
    return "-(%s)" % angle


def inverse_operations(operations: Sequence[GateRecord]) -> List[GateRecord]:
    """按逆序和逐门逆规则生成 U 的逆操作。"""
    inverse: List[GateRecord] = []
    for operation in reversed(operations):
        parameter = (
            negate_angle(operation.parameter)
            if operation.parameter is not None
            else None
        )
        inverse.append(
            GateRecord(
                INVERSE_GATES[operation.name],
                operation.qubits,
                parameter,
            )
        )
    return inverse


def basis_preparation(key: str) -> List[GateRecord]:
    """将 c[n-1]...c[0] 形式的 key 转为对应 X 门。"""
    return [
        GateRecord("x", (index,))
        for index, value in enumerate(reversed(key))
        if value == "1"
    ]


def qft_operations(qubits: int) -> List[GateRecord]:
    """生成 QFT；控制位从高位指向当前目标位，末尾反转位序。"""
    operations: List[GateRecord] = []
    for target in range(qubits):
        operations.append(GateRecord("h", (target,)))
        for control in range(target + 1, qubits):
            denominator = 2 ** (control - target)
            operations.append(
                GateRecord("cu1", (control, target), "pi/%d" % denominator)
            )
    for left in range(qubits // 2):
        operations.append(GateRecord("swap", (left, qubits - left - 1)))
    return operations


def grover_3_operations() -> List[GateRecord]:
    """生成标记 |111> 的一轮三比特 Grover 电路。"""
    operations = [GateRecord("h", (qubit,)) for qubit in range(3)]
    operations.extend(
        (
            GateRecord("h", (2,)),
            GateRecord("ccx", (0, 1, 2)),
            GateRecord("h", (2,)),
        )
    )
    # 标准 diffuser：H、X、多控 Z、X、H。
    operations.extend(GateRecord("h", (qubit,)) for qubit in range(3))
    operations.extend(GateRecord("x", (qubit,)) for qubit in range(3))
    operations.extend(
        (
            GateRecord("h", (2,)),
            GateRecord("ccx", (0, 1, 2)),
            GateRecord("h", (2,)),
        )
    )
    operations.extend(GateRecord("x", (qubit,)) for qubit in range(3))
    operations.extend(GateRecord("h", (qubit,)) for qubit in range(3))
    return operations


def random_identity_case(
    seed: int,
) -> Tuple[str, str, Tuple[GateRecord, ...]]:
    """按固定种子生成非零基态上的随机 U+U^-1 电路。"""
    generator = random.Random(seed)
    qubits = 3 + generator.randrange(3)
    initial_value = generator.randrange(1, 2**qubits)
    initial_key = format(initial_value, "0%db" % qubits)

    # 每个种子都打乱一次全门集，再追加随机门，确保合计覆盖不会退化。
    gate_names = list(ALL_GATES)
    generator.shuffle(gate_names)
    gate_names.extend(generator.choice(ALL_GATES) for _ in range(4))
    forward: List[GateRecord] = []
    for gate_name in gate_names:
        operands = tuple(
            generator.sample(range(qubits), QUBIT_COUNTS[gate_name])
        )
        parameter = (
            generator.choice(PARAMETER_ANGLES)
            if gate_name in ("ry", "rz", "cu1")
            else None
        )
        forward.append(GateRecord(gate_name, operands, parameter))

    operations = basis_preparation(initial_key)
    operations.extend(forward)
    operations.extend(inverse_operations(forward))
    return build_qasm(qubits, operations), initial_key, tuple(forward)


def oracle_cases() -> Tuple[OracleCase, ...]:
    """返回针对方向、位序和相位符号的确定性手算用例。"""
    return (
        OracleCase(
            "cx_direction",
            build_qasm(
                2,
                (GateRecord("x", (0,)), GateRecord("cx", (0, 1))),
            ),
            # q0=1 控制 q1 从 0 翻到 1；key 为 c1c0。
            "11",
        ),
        OracleCase(
            "swap_asymmetric_basis",
            build_qasm(
                2,
                (GateRecord("x", (0,)), GateRecord("swap", (0, 1))),
            ),
            # |q1 q0>=|01> 经 SWAP 后为 |10>。
            "10",
        ),
        OracleCase(
            "ccx_two_controls",
            build_qasm(
                3,
                (
                    GateRecord("x", (0,)),
                    GateRecord("x", (1,)),
                    GateRecord("ccx", (0, 1, 2)),
                ),
            ),
            # 两个 control 均为 1，target q2 必须翻转。
            "111",
        ),
        OracleCase(
            "ry_positive_sign",
            build_qasm(
                1,
                (GateRecord("ry", (0,), "pi/2"), GateRecord("h", (0,))),
            ),
            # RY(+pi/2)|0>=|+>，随后 H 得到 |0>；负号会得到 |1>。
            "0",
        ),
        OracleCase(
            "rz_positive_phase",
            build_qasm(
                1,
                (
                    GateRecord("h", (0,)),
                    GateRecord("rz", (0,), "pi/2"),
                    GateRecord("sdg", (0,)),
                    GateRecord("h", (0,)),
                ),
            ),
            # +pi/2 相位经 Sdg、H 回到 |0>；-pi/2 会落到 |1>。
            "0",
        ),
        OracleCase(
            "cu1_controlled_phase",
            build_qasm(
                2,
                (
                    GateRecord("x", (0,)),
                    GateRecord("h", (1,)),
                    GateRecord("cu1", (0, 1), "pi/2"),
                    GateRecord("sdg", (1,)),
                    GateRecord("h", (1,)),
                ),
            ),
            # control=1 时 CU1(+pi/2) 施加到 target；Sdg、H 将其还原为 0。
            "01",
        ),
        OracleCase(
            "multiple_classical_registers",
            """OPENQASM 2.0;
include "qelib1.inc";
qreg left[2]; qreg right[1];
creg low[2]; creg high[2];
x left[0]; x right[0];
measure left[0] -> high[1];
measure right[0] -> low[0];
""",
            # 全局经典位为 high[1] high[0] low[1] low[0]，未测量位保持 0。
            "1001",
        ),
    )


class HiddenLikeGeneratorTests(unittest.TestCase):
    def test_qft_inverse_is_generated_from_reverse_operations(self) -> None:
        forward = qft_operations(4)
        inverse = inverse_operations(forward)

        self.assertEqual(len(forward), len(inverse))
        self.assertEqual(forward[-1].qubits, inverse[0].qubits)
        self.assertEqual("swap", inverse[0].name)
        cu1_pairs = [
            (original.parameter, inverted.parameter)
            for original, inverted in zip(forward, reversed(inverse))
            if original.name == "cu1"
        ]
        self.assertTrue(cu1_pairs)
        self.assertTrue(
            all(inverted == "-(%s)" % original for original, inverted in cu1_pairs)
        )

    def test_random_generators_cover_all_gates_and_valid_operands(self) -> None:
        covered: Set[str] = set()
        for seed in RANDOM_SEEDS:
            _source, initial_key, forward = random_identity_case(seed)
            self.assertNotEqual(set(initial_key), {"0"})
            self.assertGreaterEqual(len(forward), 12)
            self.assertLessEqual(len(forward), 24)
            for operation in forward:
                covered.add(operation.name)
                self.assertEqual(len(operation.qubits), len(set(operation.qubits)))

        self.assertEqual(set(ALL_GATES), covered)


class _HiddenLikeTargetMixin:
    """同一组 hidden-like/Oracle 通过正式 Adapter 入口验证一个 target。"""

    TARGET = ""

    def run_target(
        self, source: str, shots: int = SHOTS
    ) -> Dict[str, float]:
        result = adapter.run(source, self.TARGET, shots)
        valid, reason = validate_schema(result)
        self.assertTrue(valid, reason)  # type: ignore[attr-defined]
        self.assertEqual("little", result["bit_order"])  # type: ignore[attr-defined]
        self.assertEqual(shots, result["shots"])  # type: ignore[attr-defined]
        self.assertEqual(  # type: ignore[attr-defined]
            shots, sum(result["counts"].values())
        )
        return {
            key: count / shots for key, count in result["counts"].items()
        }

    def assert_target_distribution(
        self,
        observed: Dict[str, float],
        expected: Dict[str, float],
    ) -> None:
        self.assertGreaterEqual(  # type: ignore[attr-defined]
            calculate_hellinger_fidelity(observed, expected), 0.97
        )

    def assert_deterministic(
        self, probabilities: Dict[str, float], key: str
    ) -> None:
        self.assertGreaterEqual(  # type: ignore[attr-defined]
            probabilities.get(key, 0.0), 0.999
        )

    def test_ghz_5_distribution_and_cross_backend_fidelity(self) -> None:
        operations = [GateRecord("h", (0,))]
        operations.extend(
            GateRecord("cx", (control, control + 1)) for control in range(4)
        )
        source = build_qasm(5, operations)
        expected = {"00000": 0.5, "11111": 0.5}

        observed = self.run_target(source)

        self.assertTrue(set(observed).issubset(expected))  # type: ignore[attr-defined]
        self.assert_target_distribution(observed, expected)

    def test_qft_4_round_trip_restores_two_nonzero_states(self) -> None:
        qft = qft_operations(4)
        inverse_qft = inverse_operations(qft)
        for initial_key in ("0001", "1010"):
            with self.subTest(initial_key=initial_key):  # type: ignore[attr-defined]
                operations = basis_preparation(initial_key) + qft + inverse_qft
                observed = self.run_target(
                    build_qasm(4, operations), DETERMINISTIC_SHOTS
                )
                self.assert_deterministic(observed, initial_key)

    def test_grover_3_amplifies_111(self) -> None:
        probabilities = self.run_target(build_qasm(3, grover_3_operations()))

        self.assertEqual(  # type: ignore[attr-defined]
            "111", max(probabilities, key=probabilities.__getitem__)
        )
        self.assertGreaterEqual(  # type: ignore[attr-defined]
            probabilities.get("111", 0.0), 0.70
        )

    def test_three_random_u_inverse_cases_restore_initial_state(self) -> None:
        covered: Set[str] = set()
        for seed in RANDOM_SEEDS:
            with self.subTest(seed=seed):  # type: ignore[attr-defined]
                source, initial_key, forward = random_identity_case(seed)
                covered.update(operation.name for operation in forward)
                observed = self.run_target(source, DETERMINISTIC_SHOTS)
                self.assert_deterministic(observed, initial_key)

        self.assertEqual(set(ALL_GATES), covered)  # type: ignore[attr-defined]

    def test_multiple_registers_cross_measurement_and_unmeasured_bits(self) -> None:
        source = """OPENQASM 2.0;
// 多寄存器声明顺序决定全局索引，经典位未写入时应保持 0。
include "qelib1.inc";
qreg qb[2]; qreg qa[1];

creg ca[2]; creg cb[2];
x qb[1]; ry(pi) qa[0]; rz(-pi/4) qb[1];
ccx qb[1], qa[0], qb[0];
measure qa[0] -> cb[0]; measure qb[0] -> ca[1];
"""

        observed = self.run_target(source, DETERMINISTIC_SHOTS)

        self.assert_deterministic(observed, "0110")

    def test_hand_calculated_oracle_cases(self) -> None:
        for case in oracle_cases():
            with self.subTest(case_id=case.case_id):  # type: ignore[attr-defined]
                observed = self.run_target(case.source, DETERMINISTIC_SHOTS)
                self.assert_deterministic(observed, case.expected_key)


@unittest.skipUnless(
    SPINQ_WORKER_CONFIGURED,
    "LOOMQ_SPINQ_PYTHON is not configured",
)
class SpinQHiddenLikeIntegrationTests(
    _HiddenLikeTargetMixin, unittest.TestCase
):
    TARGET = "spinq"


@unittest.skipUnless(
    ORIGINQ_WORKER_CONFIGURED,
    "LOOMQ_ORIGINQ_PYTHON is not configured",
)
class OriginQHiddenLikeIntegrationTests(
    _HiddenLikeTargetMixin, unittest.TestCase
):
    TARGET = "originq"


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class BraketHiddenLikeIntegrationTests(
    _HiddenLikeTargetMixin, unittest.TestCase
):
    TARGET = "braket"


if __name__ == "__main__":
    unittest.main()
