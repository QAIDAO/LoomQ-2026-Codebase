import pytest

from starter_kit import l2_cli
from starter_kit.l2.render import fallback


BELL_REPLY = '''已生成两个比特结果相同的电路。
已通过本地模拟验证，保真度 1.000。
```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
```'''

ONE_HOT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];"""


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("LOOMQ_LLM_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("LOOMQ_LLM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("LOOMQ_LLM_MODEL", "test-model")


@pytest.fixture
def unconfigured(monkeypatch):
    for name in l2_cli.REQUIRED_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


def test_outcomes_are_described_in_words_using_loomq_bit_order():
    # Keys are c[n-1]...c[0], so the middle character of a 3-bit string is q[1].
    assert l2_cli._describe("010") == "只有 q[1] 是 1"
    assert l2_cli._describe("001") == "只有 q[0] 是 1"
    assert l2_cli._describe("101") == "只有 q[0]、q[2] 是 1"
    assert l2_cli._describe("000") == "全部是 0"
    assert l2_cli._describe("111") == "全部是 1"


def test_histogram_names_the_outcomes_that_never_appear():
    picture = l2_cli.histogram(ONE_HOT_QASM)
    assert "只有 q[1] 是 1" in picture
    assert "一次都不会出现" in picture


def test_answer_leads_with_meaning_and_ends_with_the_code(configured):
    result = l2_cli.handle("两个粒子结果相同", completion=lambda _prompt: BELL_REPLY)
    assert result.index("如果真的运行") < result.index("OPENQASM")
    assert "全部是 0" in result and "全部是 1" in result
    assert "01、10 一次都不会出现" in result
    assert "本机模拟" in result and "真机上会有误差" in result


def test_backend_answer_passes_through_without_a_histogram():
    answer = "braket_local_simulator — 本地模拟器。无需账号。"
    assert l2_cli.handle("推荐后端", completion=lambda _prompt: answer) == answer


def test_failure_explains_what_to_check_and_keeps_the_question():
    def fail(_prompt):
        raise RuntimeError("offline")

    result = l2_cli.handle("GHZ", completion=fail)
    assert "LOOMQ_LLM_BASE_URL" in result
    assert "你刚才的问题我留着了" in result
    assert "RuntimeError: offline" in result


def test_preflight_reports_exactly_what_is_missing(unconfigured):
    lines, ready = l2_cli.preflight()
    report = "\n".join(lines)
    assert ready is False
    for name in l2_cli.REQUIRED_ENVIRONMENT:
        assert name in report
    assert "export LOOMQ_LLM_BASE_URL" in report


def test_preflight_never_prints_the_key(configured):
    lines, ready = l2_cli.preflight()
    assert ready is True
    assert "not-a-real-key" not in "\n".join(lines)


def test_offline_demo_needs_no_model_service(unconfigured):
    demo = l2_cli.offline_demo()
    assert "不经过模型服务" in demo
    assert "全部是 0" in demo and "全部是 1" in demo


def test_every_menu_entry_maps_to_a_prompt():
    for choice in ("1", "2", "3", "4", "5", "6"):
        assert l2_cli.prompt_for(choice)
    assert l2_cli.prompt_for("7") is None
    assert l2_cli.prompt_for("x") is None


def test_menu_previews_the_outcome_of_every_example():
    text = l2_cli.menu()
    for example in l2_cli.EXAMPLES:
        assert example["title"] in text
        assert example["preview"] in text


def test_interactive_shows_the_checks_then_runs_an_example(monkeypatch, capsys, configured):
    answers = iter(["1", "q"])
    monkeypatch.setattr(l2_cli, "handle", lambda prompt: "完成：" + prompt)
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    output = capsys.readouterr().out
    assert "环境自检" in output
    assert "完成：" + l2_cli.EXAMPLES[0]["prompt"] in output


def test_interactive_offers_the_offline_demo_when_unconfigured(capsys, unconfigured):
    answers = iter(["1", "q"])
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    output = capsys.readouterr().out
    assert "离线演示" in output
    assert "还没配置模型服务" in output


def test_interactive_answers_the_glossary_and_hardware_questions(capsys, configured):
    answers = iter(["?", "h", "q"])
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    output = capsys.readouterr().out
    assert "量子比特 qubit" in output
    assert "真机怎么接" in output


def test_unknown_example_number_does_not_reach_the_model(monkeypatch, capsys, configured):
    answers = iter(["9", "q"])
    monkeypatch.setattr(
        l2_cli, "handle", lambda prompt: pytest.fail("should not ask the model")
    )
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    assert "没有第 9 个例子" in capsys.readouterr().out


def test_check_flag_exits_nonzero_when_unconfigured(capsys, unconfigured):
    assert l2_cli.main(["--check"]) == 1
    assert "环境自检" in capsys.readouterr().out


def test_glossary_and_hardware_flags_need_no_configuration(capsys, unconfigured):
    assert l2_cli.main(["--glossary"]) == 0
    assert l2_cli.main(["--hardware"]) == 0
    output = capsys.readouterr().out
    assert "保真度 fidelity" in output
    assert "本源悟空 180" in output


def test_one_shot_prompt_refuses_early_when_unconfigured(capsys, unconfigured):
    assert l2_cli.main(["--prompt", "生成 GHZ"]) == 1
    assert "还缺" in capsys.readouterr().err


def test_qasm_only_prints_just_the_program(monkeypatch, capsys, configured):
    monkeypatch.setattr(l2_cli, "agent_chat", lambda _prompt: BELL_REPLY)
    assert l2_cli.main(["--example", "1", "--qasm-only"]) == 0
    output = capsys.readouterr().out
    assert output.startswith("OPENQASM 2.0;")
    assert "保真度" not in output


def test_real_requests_are_never_held_back():
    for text in ("GHZ 3", "贝尔态", "bell state", "我想要两个粒子结果相同", "7"):
        assert l2_cli.looks_like_a_request(text), text


def test_stray_keystrokes_do_not_spend_a_model_call(monkeypatch, capsys, configured):
    answers = iter(["abc", "q"])
    monkeypatch.setattr(
        l2_cli, "handle", lambda prompt: pytest.fail("should not ask the model")
    )
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    output = capsys.readouterr().out
    assert "我不太确定「abc」是什么意思" in output
    assert "再输入一次" in output


def test_repeating_the_same_input_forces_it_through(monkeypatch, capsys, configured):
    answers = iter(["abc", "abc", "q"])
    monkeypatch.setattr(l2_cli, "handle", lambda prompt: "问了：" + prompt)
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    assert "问了：abc" in capsys.readouterr().out


def test_every_advertised_letter_is_actually_selectable(monkeypatch, capsys, configured):
    """A / B / C are printed as choices, so typing them must do something."""
    answers = iter(["A", "b", "C", "q"])
    monkeypatch.setattr(
        l2_cli, "handle", lambda prompt: pytest.fail("a category is not a request")
    )
    assert l2_cli.interactive(lambda _label: next(answers)) == 0
    output = capsys.readouterr().out
    assert "A · 把你的话变成量子程序" in output
    assert "B · 修好一段报错的程序" in output
    assert "C · 告诉你该用哪台机器" in output


def test_category_view_lists_its_own_examples():
    for letter, (_title, choices, _hint) in l2_cli.CATEGORIES.items():
        view = l2_cli.category_view(letter)
        for choice in choices:
            assert l2_cli.prompt_title(choice) in view
            assert l2_cli.example_preview(choice) in view


def test_menu_only_advertises_keys_the_loop_accepts():
    text = l2_cli.menu()
    for letter in l2_cli.CATEGORIES:
        assert letter.upper() in text


def test_agent_failure_text_is_turned_into_the_same_recovery_help():
    """agent_chat returns this sentence instead of raising; it must not leak raw."""
    answer = fallback("ConnectionError: Connection refused")
    result = l2_cli.handle("生成 GHZ", completion=lambda _prompt: answer)
    assert "按顺序检查三件事" in result
    assert "curl -sI $LOOMQ_LLM_BASE_URL" in result
    assert "你刚才的问题我留着了" in result
    assert "Connection refused" in result


def test_recovery_prefix_still_matches_the_agent_fallback():
    assert fallback("x").startswith(l2_cli.AGENT_FAILURE_PREFIX)


def test_preflight_names_every_variable_when_configured(configured):
    lines, ready = l2_cli.preflight()
    report = "\n".join(lines)
    assert ready is True
    for name in l2_cli.REQUIRED_ENVIRONMENT:
        assert name in report
    assert "LOOMQ_LLM_TIMEOUT_SECONDS" in report
    assert "https://example.invalid" in report
    assert "not-a-real-key" not in report

