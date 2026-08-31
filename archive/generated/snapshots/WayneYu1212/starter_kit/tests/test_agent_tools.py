import unittest


try:
    from starter_kit.loomq.agent.prompts import SYSTEM_PROMPT
    from starter_kit.loomq.agent.response import (
        AgentPlan,
        BackendConstraints,
        ModelResponseError,
        parse_agent_plan,
    )
    from starter_kit.loomq.agent.selector import select_backends
except ImportError:
    SYSTEM_PROMPT = None
    AgentPlan = None
    BackendConstraints = None
    ModelResponseError = ValueError
    parse_agent_plan = None
    select_backends = None


GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""


class AgentResponseProtocolTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(parse_agent_plan, "Agent response protocol is missing")

    def test_parses_raw_and_fenced_generation_plan_without_losing_qasm(self):
        raw = (
            '{"task":"generate","qasm":'
            + repr(GHZ_QASM).replace("'", '"').replace("\\n", "\\n")
            + ',"constraints":null,"explanation":"三个量子比特会一起被测量"}'
        )
        # json.dumps would hide the literal we intend to protect; this fixture is hand-checked JSON.
        raw = '{"task":"generate","qasm":"OPENQASM 2.0;\\ninclude \\"qelib1.inc\\";\\nqreg q[3];\\ncreg c[3];\\nh q[0];\\ncx q[0],q[1];\\ncx q[1],q[2];\\nmeasure q -> c;\\n","constraints":null,"explanation":"三个量子比特会一起被测量"}'

        direct = parse_agent_plan(raw)
        fenced = parse_agent_plan("```json\n" + raw + "\n```")

        self.assertEqual(direct.task, "generate")
        self.assertEqual(direct.qasm, GHZ_QASM)
        self.assertEqual(fenced, direct)

    def test_parses_backend_constraints_with_strict_types(self):
        plan = parse_agent_plan(
            '{"task":"recommend","qasm":null,"constraints":'
            '{"qubits":15,"kind":"simulator","zero_queue":true,'
            '"avoid_paid":true,"accountless":true},'
            '"explanation":"筛选本地模拟器"}'
        )

        self.assertEqual(
            plan.constraints,
            BackendConstraints(
                qubits=15,
                kind="simulator",
                zero_queue=True,
                avoid_paid=True,
                accountless=True,
            ),
        )

    def test_rejects_malformed_ambiguous_or_extra_model_output(self):
        cases = (
            "not json",
            '{"task":"unknown","qasm":null,"constraints":null,"explanation":"x"}',
            '{"task":"generate","qasm":null,"constraints":null,"explanation":"x"}',
            '{"task":"recommend","qasm":null,"constraints":{"qubits":true},"explanation":"x"}',
            '{"task":"recommend","qasm":null,"constraints":{"kind":"local"},"explanation":"x"}',
            '{"task":"generate","qasm":"OPENQASM 2.0;","constraints":null,"explanation":"x","secret":"x"}',
            'prefix {"task":"generate"}',
        )
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ModelResponseError):
                parse_agent_plan(source)

    def test_system_prompt_declares_machine_protocol_and_official_limits(self):
        self.assertIsInstance(SYSTEM_PROMPT, str)
        self.assertIn("JSON", SYSTEM_PROMPT)
        self.assertIn("OPENQASM 2.0", SYSTEM_PROMPT)
        self.assertIn("backend_capabilities", SYSTEM_PROMPT)
        self.assertIn("cu1", SYSTEM_PROMPT)


class BackendSelectorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(select_backends, "backend selector is missing")

    def ids(self, constraints):
        return [backend["id"] for backend in select_backends(constraints)]

    def test_selects_all_15_qubit_zero_queue_local_simulators(self):
        selected = self.ids(
            BackendConstraints(
                qubits=15,
                kind="simulator",
                zero_queue=True,
                avoid_paid=True,
                accountless=True,
            )
        )
        self.assertEqual(
            selected,
            [
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            ],
        )

    def test_selects_free_quota_real_hardware_for_five_qubits(self):
        selected = self.ids(
            BackendConstraints(qubits=5, kind="qpu", avoid_paid=True)
        )
        self.assertEqual(selected, ["spinq_cloud_qpu", "originq_wukong"])

    def test_returns_empty_when_no_backend_meets_qubit_requirement(self):
        self.assertEqual(self.ids(BackendConstraints(qubits=80)), [])


if __name__ == "__main__":
    unittest.main()
