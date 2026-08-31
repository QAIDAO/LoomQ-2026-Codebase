import json

from starter_kit import l2_agent
from starter_kit.evaluator import extract_qasm
from starter_kit.l2.normalize import normalize
from starter_kit.l2.simulate import simulate
from starter_kit.l2.verify import fidelity


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;"""


THREE_QUBIT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
x q[2];
measure q -> c;"""


def response(content):
    return {"choices": [{"message": {"content": content}}]}


def structured(task="generate", qasm=BELL_QASM, target=None, constraints=None):
    return json.dumps({
        "task": task,
        "qasm": qasm,
        "target": target or {"kind": "bell", "n": 2, "measure_all": True},
        "constraints": constraints or {},
        "explanation": "测试说明",
    }, ensure_ascii=False)



AGENT_SYSTEM_MARKER = "You are LoomQ Agent"


def generation_calls(calls):
    """Only the main agent turns.

    Target consensus (independent extraction and adjudication) issues its own
    calls with different system prompts; retry assertions are about how many
    times the main agent had to be asked again.
    """
    counted = []
    for call in calls:
        messages = call[0] if isinstance(call, tuple) else call
        if messages and AGENT_SYSTEM_MARKER in messages[0].get("content", ""):
            counted.append(messages)
    return counted

def scripted(answers, calls=None, target=None):
    """Fake completion that scripts the main agent turns only.

    Target-consensus turns use their own system prompts; answering them from the
    same script would silently consume a response meant for the agent.
    """
    stream = iter(answers)
    extraction = response(json.dumps(
        {"target": target or {"kind": "bell", "n": 2, "measure_all": True}},
        ensure_ascii=False,
    ))

    def completion(messages, **_kwargs):
        if calls is not None:
            calls.append([dict(message) for message in messages])
        if AGENT_SYSTEM_MARKER in messages[0].get("content", ""):
            return next(stream)
        return extraction

    return completion


def test_qasm_answer_is_semantically_validated_and_rendered():
    calls = []

    def completion(messages, **kwargs):
        calls.append((messages, kwargs))
        return response(structured())

    answer = l2_agent.agent_chat("生成一个贝尔态", completion=completion)

    assert extract_qasm(answer) is not None
    assert "保真度 1.000" in answer
    assert len(generation_calls(calls)) == 1
    assert calls[0][1]["timeout"] <= 45
    assert "spinq_taurus_simulator" in calls[0][0][0]["content"]


def test_semantically_wrong_qasm_is_retried():
    wrong = BELL_QASM.replace("cx q[0], q[1];", "")
    calls = []
    completion = scripted(
        [response(structured(qasm=wrong)), response(structured())], calls
    )

    answer = l2_agent.agent_chat("修好代码并制备贝尔态", completion=completion)

    assert "保真度 1.000" in answer
    assert len(generation_calls(calls)) == 2
    assert "fidelity" in generation_calls(calls)[1][-1]["content"]


def test_backend_is_selected_locally_from_structured_constraints():
    payload = structured(
        task="backend",
        qasm=None,
        target={},
        constraints={"min_qubits": 15, "queue": "none", "cost": "free", "no_account": True},
    )
    answer = l2_agent.agent_chat("推荐后端", completion=lambda _m, **_k: response(payload))

    # The capability table marks braket_local_simulator as the evaluation default,
    # so it wins ties between otherwise equally valid local simulators.
    assert answer.startswith("braket_local_simulator")
    assert answer.count("braket_local_simulator") == 1


def test_renderer_removes_extra_backend_ids_from_model_explanation():
    payload = json.loads(structured(
        task="backend", qasm=None, target={},
        constraints={"min_qubits": 50, "requires_hardware": True},
    ))
    payload["explanation"] = "不要选 braket_local_simulator。"
    answer = l2_agent.agent_chat(
        "必须使用 50 比特真机",
        completion=lambda _m, **_k: response(json.dumps(payload, ensure_ascii=False)),
    )
    assert "originq_wukong" in answer
    assert "braket_local_simulator" not in answer


def test_empty_prompt_and_api_failure_return_safe_text():
    assert "请求不能为空" in l2_agent.agent_chat("   ", completion=lambda _m: None)
    answer = l2_agent.agent_chat("推荐后端", completion=lambda _m, **_k: {})
    assert "暂时无法完成" in answer


def test_garbage_stops_after_three_attempts_without_raising():
    calls = 0

    def completion(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        return response("not json")

    answer = l2_agent.agent_chat("生成 GHZ", completion=completion)
    assert calls == 3
    assert "暂时无法完成" in answer


GHZ3 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;"""

GHZ3_TARGET = {"kind": "ghz", "n": 3, "measure_all": True}


def test_highest_fidelity_candidate_survives_a_degrading_model():
    """A later, worse answer must never overwrite an earlier, better one."""
    near_miss = GHZ3.replace("measure q -> c;", "ry(0.28) q[0];\nmeasure q -> c;")
    wrong = GHZ3.replace("h q[0];", "x q[0];").replace("cx q[1], q[2];", "")
    answers = iter([
        response(structured(qasm=near_miss, target=GHZ3_TARGET)),
        response(structured(qasm=wrong, target=GHZ3_TARGET)),
        response(structured(qasm=wrong, target=GHZ3_TARGET)),
    ])

    answer = l2_agent.agent_chat("生成 GHZ", completion=lambda _m, **_k: next(answers))

    assert extract_qasm(answer) is not None
    assert "保真度 0.000" not in answer


def test_declared_target_is_rebuilt_locally_when_the_model_keeps_failing():
    """One good structured target is enough to still return a scoring answer."""
    unusable = json.dumps(
        {"task": "generate", "qasm": "not qasm at all", "target": GHZ3_TARGET,
         "explanation": "坏结果"},
        ensure_ascii=False,
    )
    answer = l2_agent.agent_chat(
        "生成一个 3 比特 GHZ 态", completion=lambda _m, **_k: response(unusable)
    )

    program = extract_qasm(answer)
    assert program is not None and "OPENQASM 2.0;" in program
    assert "本地重建" in answer
    assert "保真度 1.000" in answer


def test_fenced_program_inside_the_json_field_is_accepted():
    payload = structured(qasm=f"```qasm\n{BELL_QASM}\n```")
    calls = []

    def completion(messages, **_kwargs):
        calls.append(messages)
        return response(payload)

    answer = l2_agent.agent_chat("生成贝尔态", completion=completion)

    assert "保真度 1.000" in answer
    assert len(generation_calls(calls)) == 1


def test_partial_measurement_violates_measure_all_and_is_retried():
    partial = BELL_QASM.replace("measure q -> c;", "measure q[0] -> c[0];")
    calls = []
    completion = scripted(
        [response(structured(qasm=partial)), response(structured())], calls
    )

    answer = l2_agent.agent_chat("生成贝尔态并全测量", completion=completion)

    assert "保真度 1.000" in answer
    assert len(generation_calls(calls)) == 2
    assert "measuring all" in generation_calls(calls)[1][-1]["content"]


def test_custom_target_without_distribution_does_not_skip_verification():
    payload = structured(target={"kind": "custom", "n": 2})
    calls = []
    completion = scripted(
        [response(payload)] * 3, calls, target={"kind": "custom", "n": 2}
    )

    answer = l2_agent.agent_chat("生成一个自定义态", completion=completion)

    assert len(generation_calls(calls)) == 3
    assert "expected_distribution" in generation_calls(calls)[1][-1]["content"]
    # Still returns the best available program rather than an apology.
    assert extract_qasm(answer) is not None
    assert "未做语义验证" in answer


def test_backend_hint_disagreement_triggers_exactly_one_retry():
    payload = json.loads(structured(
        task="backend", qasm=None, target={},
        constraints={"min_qubits": 15, "queue": "none"},
    ))
    payload["backend_hint"] = "braket_cloud"
    calls = []

    def completion(messages, **_kwargs):
        calls.append([dict(message) for message in messages])
        return response(json.dumps(payload, ensure_ascii=False))

    answer = l2_agent.agent_chat("推荐后端", completion=completion)

    assert len(generation_calls(calls)) == 2
    assert "backend_hint" in calls[1][-1]["content"]
    assert answer.startswith("braket_local_simulator")


def test_legacy_qasm_response_remains_compatible():
    answer = l2_agent.agent_chat(
        "生成电路", completion=lambda _m, **_k: response(f"```qasm\n{BELL_QASM}\n```")
    )
    assert extract_qasm(answer) is not None


MIRROR_WRONG = {"kind": "custom", "n": 3,
                "expected_distribution": {"100": 0.25, "101": 0.25, "110": 0.25, "111": 0.25}}
MIRROR_RIGHT = {"kind": "custom", "n": 3,
                "expected_distribution": {"001": 0.25, "011": 0.25, "101": 0.25, "111": 0.25}}
ORDERING_MARKER = "opposite bit orders"
ADJUDICATION_MARKER = "Compare two candidate measurement targets"
EXTRACTION_MARKER = "Independently extract"


def routed(agent_payload, extraction_target, ordering=None, calls=None):
    """Fake model that answers each stage of the target consensus separately."""

    def completion(messages, **_kwargs):
        system = messages[0].get("content", "")
        if calls is not None:
            calls.append(system)
        if ORDERING_MARKER in system:
            return response(ordering if ordering is not None else "no verdict")
        if ADJUDICATION_MARKER in system:
            return response("{}")
        if EXTRACTION_MARKER in system:
            return response(json.dumps({"target": extraction_target}, ensure_ascii=False))
        return response(agent_payload)

    return completion


def test_mirrored_targets_are_detected_without_asking_anyone():
    assert l2_agent._mirrored(MIRROR_WRONG, MIRROR_RIGHT)
    # A palindromic target cannot be an ordering disagreement.
    ghz = {"kind": "ghz", "n": 3}
    assert not l2_agent._mirrored(ghz, ghz)
    assert not l2_agent._mirrored(MIRROR_WRONG, {"kind": "ghz", "n": 3})


def test_ordering_disagreement_is_settled_by_one_binary_question():
    payload = structured(qasm=THREE_QUBIT_QASM, target=MIRROR_WRONG)
    calls = []
    completion = routed(payload, MIRROR_RIGHT, ordering='{"choice":"B"}', calls=calls)

    answer = l2_agent.agent_chat("q[0] 固定为 1，另外两个比特等概率叠加", completion=completion)

    observed = simulate(normalize(extract_qasm(answer))[1])
    assert fidelity(observed, MIRROR_RIGHT["expected_distribution"]) >= 0.999
    assert sum(ORDERING_MARKER in system for system in calls) == 1
    # The narrow question replaces the generic adjudication; it must not also run.
    assert not any(ADJUDICATION_MARKER in system for system in calls)


def test_unusable_ordering_verdict_keeps_the_generated_target():
    payload = structured(qasm=THREE_QUBIT_QASM, target=MIRROR_WRONG)
    completion = routed(payload, MIRROR_RIGHT, ordering="I cannot decide")

    answer = l2_agent.agent_chat("q[0] 固定为 1，另外两个比特等概率叠加", completion=completion)

    observed = simulate(normalize(extract_qasm(answer))[1])
    assert fidelity(observed, MIRROR_WRONG["expected_distribution"]) >= 0.999
