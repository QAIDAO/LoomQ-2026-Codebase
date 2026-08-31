"""public artifact 契约审计与厂商 SDK 语义边界测试。"""

import importlib.util
import os
import unittest
from typing import Dict

import adapter
from evaluator import calculate_hellinger_fidelity
from loomq.parser import parse_qasm
from loomq.serializers.braket import serialize_braket
from scripts.l1_native import execute_native_artifact, normalized_native_counts
from tests.test_l1_hidden_like import (
    DETERMINISTIC_SHOTS,
    GateRecord,
    basis_preparation,
    build_qasm,
    grover_3_operations,
    inverse_operations,
    oracle_cases,
    qft_operations,
    random_identity_case,
)


NATIVE_SHOTS = 4096
SPINQ_CONFIGURED = bool(os.environ.get("LOOMQ_SPINQ_PYTHON"))
ORIGINQ_CONFIGURED = bool(os.environ.get("LOOMQ_ORIGINQ_PYTHON"))
BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None


def probabilities(payload: Dict[str, object], shots: int) -> Dict[str, float]:
    counts = normalized_native_counts(payload, shots)
    return {str(key): int(value) / shots for key, value in counts.items()}


class NativeArtifactShapeTests(unittest.TestCase):
    def test_all_public_artifacts_are_complete_target_programs(self) -> None:
        source = build_qasm(
            3,
            (
                GateRecord("x", (0,)),
                GateRecord("h", (1,)),
                GateRecord("sdg", (1,)),
                GateRecord("tdg", (1,)),
                GateRecord("cu1", (0, 1), "pi/2"),
                GateRecord("ccx", (0, 1, 2)),
            ),
        )
        artifacts = {
            target: adapter.transpile(source, target)
            for target in ("spinq", "originq", "braket")
        }

        self.assertTrue(artifacts["spinq"].startswith("OPENQASM 2.0;"))
        self.assertIn("qreg q[3];", artifacts["spinq"])
        self.assertIn("measure q -> c;", artifacts["spinq"])
        self.assertTrue(artifacts["originq"].startswith("QINIT 3\nCREG 3\n"))
        self.assertIn("MEASURE q[2], c[2]", artifacts["originq"])
        self.assertTrue(artifacts["braket"].startswith("OPENQASM 3.0;"))
        self.assertIn('include "stdgates.inc";', artifacts["braket"])
        self.assertIn("qubit[3] q;", artifacts["braket"])
        self.assertIn("sdg q[1];", artifacts["braket"])
        self.assertIn("tdg q[1];", artifacts["braket"])
        self.assertIn("cp(1.5707963267948966) q[0], q[1];", artifacts["braket"])
        self.assertIn("ccx q[0], q[1], q[2];", artifacts["braket"])
        self.assertNotIn("cphaseshift", artifacts["braket"])
        self.assertNotIn("ccnot", artifacts["braket"])
        self.assertIn("c = measure q;", artifacts["braket"])

    def test_braket_public_and_sdk_execution_dialects_are_separate(self) -> None:
        source = build_qasm(
            3,
            (
                GateRecord("sdg", (0,)),
                GateRecord("tdg", (1,)),
                GateRecord("cu1", (0, 1), "pi/2"),
                GateRecord("ccx", (0, 1, 2)),
            ),
        )
        public = adapter.transpile(source, "braket")
        execution = serialize_braket(
            parse_qasm(source), include_stdgates=False, execution_mode=True
        )

        self.assertIn('include "stdgates.inc";', public)
        self.assertIn("sdg q[0];", public)
        self.assertIn("tdg q[1];", public)
        self.assertIn("cp(1.5707963267948966) q[0], q[1];", public)
        self.assertIn("ccx q[0], q[1], q[2];", public)
        self.assertNotIn('include "stdgates.inc";', execution)
        self.assertNotIn("sdg ", execution)
        self.assertNotIn("tdg ", execution)
        self.assertIn("cphaseshift(1.5707963267948966) q[0], q[1];", execution)
        self.assertNotIn("ccx ", execution)
        # pinned LocalSimulator 与 canonical stdgates artifact 存在 parser 方言差异；
        # execution-mode 的 SDK 语义通过不等同于 public artifact 的 evaluator 验收。

    def test_public_artifacts_preserve_cross_register_measurement_mapping(self) -> None:
        case = next(
            item
            for item in oracle_cases()
            if item.case_id == "multiple_classical_registers"
        )
        spinq = adapter.transpile(case.source, "spinq")
        originq = adapter.transpile(case.source, "originq")
        braket = adapter.transpile(case.source, "braket")

        self.assertIn("measure left[0] -> high[1];", spinq)
        self.assertIn("measure right[0] -> low[0];", spinq)
        # q: left[0..1], right[0]；c: low[0..1], high[0..1]。
        self.assertIn("MEASURE q[0], c[3]", originq)
        self.assertIn("MEASURE q[2], c[0]", originq)
        self.assertIn("high[1] = measure left[0];", braket)
        self.assertIn("low[0] = measure right[0];", braket)

    def test_cu1_artifacts_keep_source_operand_order(self) -> None:
        source = build_qasm(
            2,
            (GateRecord("cu1", (0, 1), "pi/2"),),
        )
        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                artifact = adapter.transpile(source, target)
                gate_line = next(
                    line
                    for line in artifact.splitlines()
                    if "q[0]" in line
                    and "q[1]" in line
                    and "measure" not in line.lower()
                )
                self.assertLess(gate_line.index("q[0]"), gate_line.index("q[1]"))
        # CU1/controlled-phase 的矩阵对两操作数对称，方向只能静态检查；
        # CX Oracle 负责对可观测的 control/target 方向做语义攻击。


class NativeNormalizationTests(unittest.TestCase):
    def test_spinq_vendor_q0_first_counts_are_reversed_to_little_key(self) -> None:
        payload = {
            "counts": {"01": 4},
            "count_key_order": "q0_to_qn",
        }

        self.assertEqual({"10": 4}, normalized_native_counts(payload, 4))


class _NativeTargetMixin:
    TARGET = ""

    def sdk_artifact(self, source: str) -> str:
        """SpinQ/OriginQ 直接使用 public transpile artifact。"""
        return adapter.transpile(source, self.TARGET)

    def run_native(
        self, source: str, shots: int = DETERMINISTIC_SHOTS
    ) -> Dict[str, float]:
        artifact = self.sdk_artifact(source)
        payload = execute_native_artifact(self.TARGET, artifact, shots)
        return probabilities(payload, shots)

    def assert_deterministic(self, source: str, expected_key: str) -> None:
        observed = self.run_native(source)
        self.assertGreaterEqual(  # type: ignore[attr-defined]
            observed.get(expected_key, 0.0), 0.999
        )

    def test_sdk_semantic_oracle_subset(self) -> None:
        for case in oracle_cases():
            if case.case_id == "multiple_classical_registers":
                # 厂商结果对象未统一暴露未测量经典位，映射由 adapter.run 覆盖。
                continue
            with self.subTest(case_id=case.case_id):  # type: ignore[attr-defined]
                self.assert_deterministic(case.source, case.expected_key)

    def test_sdk_semantic_hidden_like_representatives(self) -> None:
        ghz_source = build_qasm(
            5,
            (GateRecord("h", (0,)),)
            + tuple(GateRecord("cx", (index, index + 1)) for index in range(4)),
        )
        ghz = self.run_native(ghz_source, NATIVE_SHOTS)
        self.assertGreaterEqual(  # type: ignore[attr-defined]
            calculate_hellinger_fidelity(
                ghz, {"00000": 0.5, "11111": 0.5}
            ),
            0.97,
        )

        qft = qft_operations(4)
        qft_source = build_qasm(
            4, basis_preparation("1010") + qft + inverse_operations(qft)
        )
        self.assert_deterministic(qft_source, "1010")

        grover = self.run_native(
            build_qasm(3, grover_3_operations()), NATIVE_SHOTS
        )
        self.assertEqual(  # type: ignore[attr-defined]
            "111", max(grover, key=grover.__getitem__)
        )
        self.assertGreaterEqual(grover.get("111", 0.0), 0.70)  # type: ignore[attr-defined]

        random_source, initial_key, _operations = random_identity_case(20260801)
        self.assert_deterministic(random_source, initial_key)


@unittest.skipUnless(SPINQ_CONFIGURED, "LOOMQ_SPINQ_PYTHON is not configured")
class SpinQNativeArtifactIntegrationTests(_NativeTargetMixin, unittest.TestCase):
    TARGET = "spinq"


@unittest.skipUnless(
    ORIGINQ_CONFIGURED, "LOOMQ_ORIGINQ_PYTHON is not configured"
)
class OriginQNativeArtifactIntegrationTests(_NativeTargetMixin, unittest.TestCase):
    TARGET = "originq"


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class BraketExecutionModeSDKIntegrationTests(_NativeTargetMixin, unittest.TestCase):
    TARGET = "braket"

    def sdk_artifact(self, source: str) -> str:
        """只验证 Runner 方言；不声称执行了 canonical public artifact。"""
        return serialize_braket(
            parse_qasm(source), include_stdgates=False, execution_mode=True
        )


if __name__ == "__main__":
    unittest.main()
