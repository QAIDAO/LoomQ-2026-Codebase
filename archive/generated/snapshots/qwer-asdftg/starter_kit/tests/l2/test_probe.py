import importlib.util
import unittest


class ProbeTests(unittest.TestCase):
    def test_local_probe_module_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec("starter_kit.l2_probe"))

    def test_ghz_probe_requires_the_expected_distribution(self):
        from starter_kit.l2_probe import probe_cases, validate_reply

        ghz = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
'''
        case = next(case for case in probe_cases() if case.name == "ghz_3")

        self.assertIsNone(validate_reply(case, ghz))

    def test_bell_probe_rejects_a_parseable_but_nonentangled_circuit(self):
        from starter_kit.l2_probe import probe_cases, validate_reply

        product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q -> c;
'''
        case = next(case for case in probe_cases() if case.name == "repair_bell")

        self.assertIn("distribution", validate_reply(case, product_state))

    def test_backend_probe_accepts_only_a_qualified_canonical_id(self):
        from starter_kit.l2_probe import probe_cases, validate_reply

        case = next(case for case in probe_cases() if case.name == "backend_free_15")

        self.assertIsNone(validate_reply(case, "Use originq_local_simulator."))
        self.assertIn("canonical backend id", validate_reply(case, "Use originq_wukong."))

    def test_probe_continues_after_an_untrusted_invocation_error(self):
        from starter_kit.l2_probe import probe_models

        report = probe_models(["model-a"], lambda _model, _prompt: (_ for _ in ()).throw(RuntimeError("secret")))

        self.assertEqual(len(report.models[0].tasks), 3)
        self.assertTrue(all(task.error == "model invocation failed" for task in report.models[0].tasks))

    def test_semantics_validates_only_explicit_ghz_and_bell_requests(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
measure q -> c;
'''

        self.assertIn(
            "distribution",
            validate_prompt_reply("生成一个三量子比特 GHZ OpenQASM 2.0 电路。", product_state),
        )
        self.assertIsNone(validate_prompt_reply("生成一个演示 H 门的电路。", product_state))

    def test_semantics_accepts_ghz_four_with_chinese_and_english_width_variants(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        ghz_four = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];
measure q -> c;
'''

        for prompt in (
            "生成一个4量子比特 GHZ 电路。",
            "Generate a 4-qubit GHZ circuit.",
            "Generate a 4 qubit GHZ circuit.",
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(validate_prompt_reply(prompt, ghz_four))

    def test_semantics_infers_chinese_adjacent_ghz_and_bell_state_requests(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        ghz_product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
measure q -> c;
'''
        bell_product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q -> c;
'''

        self.assertIn("distribution", validate_prompt_reply("生成一个 GHZ态 电路。", ghz_product_state))
        self.assertIn("distribution", validate_prompt_reply("生成一个 Bell态 电路。", bell_product_state))

    def test_semantics_recognizes_explicit_epr_and_bell_pair_circuit_requests(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q -> c;
'''

        for prompt in (
            "制备一个 EPR 对并全测量。",
            "Generate a two-qubit EPR pair circuit with full measurement.",
            "生成一个 Bell pair 的两量子比特 OpenQASM 电路。",
            "制备一个二量子比特最大纠缠态并全测量。",
            "Create a 2-qubit maximally entangled state circuit.",
        ):
            with self.subTest(prompt=prompt):
                self.assertIn("distribution", validate_prompt_reply(prompt, product_state))

    def test_semantics_leaves_epr_explanations_and_ambiguous_maximal_entanglement_unchecked(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIsNone(validate_prompt_reply("用通俗语言解释 EPR pair 是什么。", "说明文字"))
        self.assertIsNone(validate_prompt_reply("生成一段 Bell pair 的科普说明。", "说明文字"))
        self.assertIsNone(
            validate_prompt_reply(
                "Write a short article on EPR pairs for high-school students.",
                "An EPR pair is a useful example of quantum entanglement.",
            )
        )
        self.assertIsNone(validate_prompt_reply("解释最大纠缠态的概念。", "说明文字"))
        self.assertIsNone(validate_prompt_reply("生成一个最大纠缠态的科普说明。", "说明文字"))

    def test_semantics_prioritizes_explicit_bell_generation_over_an_explanation_clause(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        product_state = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q -> c;
'''

        self.assertIn(
            "distribution",
            validate_prompt_reply("Generate a Bell circuit and explain it.", product_state),
        )

    def test_semantics_leaves_ghz_tutorials_as_prose(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIsNone(
            validate_prompt_reply(
                "Write a tutorial about GHZ states.",
                "A GHZ state is a multipartite entangled state.",
            )
        )

    def test_semantics_rejects_circuits_wider_than_the_safe_simulation_limit(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        oversized = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[17];
creg c[17];
measure q -> c;
'''

        self.assertEqual(
            "circuit width exceeds safe semantic simulation limit",
            validate_prompt_reply("生成一个 17 量子比特 GHZ 电路。", oversized),
        )

    def test_semantics_rejects_a_sixteen_qubit_circuit_over_the_work_budget(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        excessive_operations = "\n".join("h q[0];" for _ in range(31))
        excessive = f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[16];
creg c[16];
{excessive_operations}
measure q -> c;
'''

        self.assertEqual(
            "circuit semantic simulation work exceeds safe limit",
            validate_prompt_reply("生成一个 16 量子比特 GHZ 电路。", excessive),
        )

    def test_semantics_enforces_explicit_backend_capability_constraints(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        prompt = "选择一个至少 15 比特、free、queue=none 的规范后端 ID。"

        self.assertIsNone(validate_prompt_reply(prompt, "Use originq_local_simulator."))
        self.assertIn("canonical backend id", validate_prompt_reply(prompt, "Use originq_wukong."))

    def test_semantics_recognizes_platform_as_an_explicit_backend_selection(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIn(
            "canonical backend id",
            validate_prompt_reply("选择一个至少15比特、免费、零排队的平台。", "originq_wukong"),
        )

    def test_semantics_recognizes_zero_waiting_synonyms_for_explicit_backend_selection(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        for prompt in (
            "推荐一个至少 15 比特、零等待的平台。",
            "选择一个至少15量子比特、无需等待的后端。",
            "Recommend a backend with at least 15 qubits and no waiting.",
            "Select a simulator with at least 15 qubits and zero wait.",
        ):
            with self.subTest(prompt=prompt):
                self.assertIn(
                    "canonical backend id",
                    validate_prompt_reply(prompt, "originq_wukong"),
                )

    def test_semantics_treats_use_backend_with_capabilities_as_a_selection_request(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIn(
            "canonical backend id",
            validate_prompt_reply(
                "Use a backend with at least 15 qubits and no waiting.",
                "originq_wukong",
            ),
        )

    def test_semantics_prioritizes_backend_recommendation_over_an_explanation_clause(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIn(
            "canonical backend id",
            validate_prompt_reply(
                "Recommend a free 15-qubit backend and explain why.",
                "originq_wukong",
            ),
        )

    def test_semantics_leaves_zero_waiting_prose_without_backend_selection_unchecked(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIsNone(validate_prompt_reply("解释什么是零等待量子计算。", "说明文字"))
        self.assertIsNone(validate_prompt_reply("写一段无需等待的量子未来科普。", "说明文字"))
        self.assertIsNone(
            validate_prompt_reply(
                "Use a quantum backend and write an article about no waiting.",
                "No-waiting can make a workflow feel more immediate.",
            )
        )

    def test_semantics_leaves_unknown_intent_and_empty_reply_to_shape_validation(self):
        from starter_kit.l2_semantics import validate_prompt_reply

        self.assertIsNone(validate_prompt_reply("解释量子叠加。", ""))

    def test_backend_probe_rejects_an_explicit_requirement_with_no_qualified_backend(self):
        from starter_kit.l2_probe import ProbeCase, validate_reply

        case = ProbeCase(
            name="backend_impossible",
            prompt="选择一个至少 999 比特、free、queue=none 的规范后端 ID。",
            category="backend_free_15",
        )

        self.assertIn("no configured backend", validate_reply(case, "originq_local_simulator"))

    def test_probe_delegates_to_the_shared_semantic_validator(self):
        from starter_kit.l2_probe import probe_cases, validate_reply

        malformed_ghz = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
measure q -> c;
'''
        case = next(case for case in probe_cases() if case.name == "ghz_3")

        self.assertIn("distribution", validate_reply(case, malformed_ghz))

    def test_probe_report_does_not_expose_model_supplied_parser_text(self):
        from starter_kit.l2_probe import probe_models

        marker = "MALICIOUS_UNIQUE_MARKER"
        malformed = f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
{marker};
'''
        report = probe_models(["model-safe"], lambda _model, _prompt: malformed)
        ghz_result = next(task for task in report.models[0].tasks if task.case == "ghz_3")

        self.assertEqual("invalid circuit syntax or unsupported operation", ghz_result.error)
        self.assertNotIn(marker, ghz_result.error)


if __name__ == "__main__":
    unittest.main()
