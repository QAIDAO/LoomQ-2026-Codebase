#!/usr/bin/env python3
"""Local checks for the beginner CLI.

These tests monkeypatch ``adapter.agent_chat`` and never call a real model API.
"""

from __future__ import annotations

import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import beginner_cli  # noqa: E402


class FakeInput:
    def __init__(self, values):
        self.values = list(values)

    def __call__(self, prompt: str = "") -> str:
        if not self.values:
            raise EOFError
        return self.values.pop(0)


class RaisingInput:
    def __init__(self, exc):
        self.exc = exc

    def __call__(self, prompt: str = "") -> str:
        raise self.exc


class Capture:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        self.lines.append(str(text))

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class EnvGuard:
    KEYS = [
        "LOOMQ_LLM_BASE_URL",
        "LOOMQ_LLM_API_KEY",
        "LOOMQ_LLM_MODEL",
        "LOOMQ_LLM_TIMEOUT_SECONDS",
        "LOOMQ_DEBUG",
    ]

    def __enter__(self):
        self.saved = {key: os.environ.get(key) for key in self.KEYS}
        for key in self.KEYS:
            os.environ.pop(key, None)
        return self

    def __exit__(self, exc_type, exc, tb):
        for key in self.KEYS:
            os.environ.pop(key, None)
            if self.saved[key] is not None:
                os.environ[key] = self.saved[key]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def install_fake_agent(response: str = "raw response"):
    calls = []
    original = beginner_cli.adapter.agent_chat

    def fake_agent(prompt: str) -> str:
        calls.append(prompt)
        return response

    beginner_cli.adapter.agent_chat = fake_agent
    return calls, original


def restore_agent(original) -> None:
    beginner_cli.adapter.agent_chat = original


def with_key() -> None:
    os.environ["LOOMQ_LLM_BASE_URL"] = "https://example.invalid"
    os.environ["LOOMQ_LLM_MODEL"] = "test-model"
    os.environ["LOOMQ_LLM_API_KEY"] = "test-key"


def test_generate_prompt_passthrough() -> None:
    with EnvGuard():
        with_key()
        prompt = "Generate a Bell state and measure both qubits."
        calls, original = install_fake_agent("OPENQASM 2.0;\nqreg q[2];")
        try:
            beginner_cli.run_generate(FakeInput([prompt]), Capture())
            require(calls == [prompt], "generate prompt was not passed through exactly")
        finally:
            restore_agent(original)


def test_chinese_prompt_passthrough() -> None:
    with EnvGuard():
        with_key()
        prompt = "生成一个五比特 GHZ 态，并测量所有量子比特。"
        calls, original = install_fake_agent("OK")
        try:
            beginner_cli.run_generate(FakeInput([prompt]), Capture())
            require(calls == [prompt], "Chinese prompt was modified")
        finally:
            restore_agent(original)


def test_repair_wraps_multiline_qasm() -> None:
    with EnvGuard():
        with_key()
        qasm_lines = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            "qreg q[2];",
            "H q[0];",
            "CX q[0] q[1]",
            "END",
        ]
        calls, original = install_fake_agent("fixed")
        try:
            beginner_cli.run_repair(FakeInput(qasm_lines), Capture())
            require(len(calls) == 1, "repair did not call agent once")
            require("Please repair the following OpenQASM" in calls[0], "repair prompt missing instruction")
            for line in qasm_lines[:-1]:
                require(line in calls[0], f"repair prompt lost line: {line}")
        finally:
            restore_agent(original)


def test_backend_prompt_passthrough() -> None:
    with EnvGuard():
        with_key()
        prompt = "I need at least 15 qubits, zero queue, and a free backend."
        calls, original = install_fake_agent("backend: braket_local_simulator")
        try:
            beginner_cli.run_backend(FakeInput([prompt]), Capture())
            require(calls == [prompt], "backend prompt was not passed through exactly")
        finally:
            restore_agent(original)


def test_quick_example_calls_agent() -> None:
    with EnvGuard():
        with_key()
        calls, original = install_fake_agent("example response")
        try:
            beginner_cli.run_quick_examples(FakeInput(["1"]), Capture())
            require(len(calls) == 1, "quick example did not call agent")
            require("Bell" in calls[0], "quick example prompt did not request Bell")
        finally:
            restore_agent(original)


def test_formatter_normal_response() -> None:
    capture = Capture()
    response = """Done.
Source: LLM intent + deterministic known-task handler
Validation passed.
counts: {"00": 128, "11": 128}
```openqasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
```
backend braket_local_simulator
"""
    beginner_cli.format_response(response, "Result", capture)
    text = capture.text
    require("OpenQASM" in text, "formatter did not show OpenQASM section")
    require("Validation" in text, "formatter did not show validation section")
    require("braket_local_simulator" in text, "formatter did not show backend ID")
    require("```openqasm" not in text and "```qasm" not in text, "formatter left an empty QASM fence behind")
    require(text.count("Validation passed.") == 1, "formatter repeated validation line")
    require(text.count('counts: {"00": 128, "11": 128}') == 1, "formatter repeated counts line")


def test_formatter_fallback() -> None:
    capture = Capture()
    beginner_cli.format_response("strange unexpected response", "Result", capture)
    require("strange unexpected response" in capture.text, "formatter fallback lost raw response")


def test_api_key_hidden_not_printed() -> None:
    secret = "test-secret-not-real"
    with EnvGuard():
        os.environ["LOOMQ_LLM_BASE_URL"] = "https://example.invalid"
        os.environ["LOOMQ_LLM_MODEL"] = "test-model"
        calls, original = install_fake_agent("OK")
        original_getpass = beginner_cli.getpass.getpass

        def fake_getpass(prompt: str) -> str:
            return secret

        beginner_cli.getpass.getpass = fake_getpass
        capture = Capture()
        try:
            beginner_cli.run_generate(FakeInput(["Generate a Bell state."]), capture)
            require(os.environ["LOOMQ_LLM_API_KEY"] == secret, "API key was not set in process env")
            require(secret not in capture.text, "API key was printed")
            require(calls == ["Generate a Bell state."], "agent was not called after API key prompt")
        finally:
            beginner_cli.getpass.getpass = original_getpass
            restore_agent(original)


def test_missing_model_config_friendly() -> None:
    with EnvGuard():
        os.environ["LOOMQ_LLM_API_KEY"] = "test-key"
        calls, original = install_fake_agent("OK")
        capture = Capture()
        try:
            beginner_cli.run_generate(FakeInput(["Generate a Bell state."]), capture)
            require(calls == [], "agent should not be called when model config is missing")
            require("Model service configuration is incomplete" in capture.text, "missing config message was not friendly")
            require("LOOMQ_LLM_BASE_URL" in capture.text, "missing config message did not mention base URL")
            require("LOOMQ_LLM_MODEL" in capture.text, "missing config message did not mention model")
        finally:
            restore_agent(original)


def check_friendly_error(message: str, snippet: str) -> None:
    capture = Capture()
    beginner_cli.show_friendly_error(RuntimeError(message), capture)
    require(snippet in capture.text, f"friendly error missing snippet for {message}")


def test_error_401() -> None:
    check_friendly_error("HTTP 401", "Authentication failed")


def test_masked_api_key_suffix_redacted() -> None:
    with EnvGuard():
        os.environ["LOOMQ_LLM_API_KEY"] = "full-secret-not-real-f8ef"
        capture = Capture()
        beginner_cli.show_friendly_error(
            RuntimeError(
                'LoomQ L2 API returned HTTP 401: {"error":{"message":"Authentication Fails, Your api key: ****f8ef is invalid"}}'
            ),
            capture,
        )
        require("Authentication failed" in capture.text, "401 friendly message changed")
        require("[REDACTED]" in capture.text, "masked API key was not redacted")
        require("f8ef" not in capture.text, "masked API key suffix leaked")
        require("****f8ef" not in capture.text, "masked API key leaked")
        require(os.environ["LOOMQ_LLM_API_KEY"] not in capture.text, "full API key leaked")


def test_error_402() -> None:
    check_friendly_error("HTTP 402", "balance is insufficient")


def test_error_429() -> None:
    check_friendly_error("HTTP 429", "rate limited")


def test_error_500() -> None:
    check_friendly_error("HTTP 500", "temporarily unavailable")


def test_error_503() -> None:
    check_friendly_error("HTTP 503", "temporarily unavailable")


def test_error_551() -> None:
    check_friendly_error("HTTP 551", "temporarily unavailable")


def test_menu_exit() -> None:
    capture = Capture()
    result = beginner_cli.main_loop(FakeInput(["5"]), capture)
    require(result == 0, "menu exit returned nonzero")
    require("Goodbye from LoomQ." in capture.text, "normal exit did not say goodbye")


def test_eof_graceful_exit() -> None:
    capture = Capture()
    result = beginner_cli.main_loop(FakeInput([]), capture)
    require(result == 0, "EOF exit returned nonzero")
    require("Goodbye from LoomQ." in capture.text, "EOF exit did not say goodbye")


def test_keyboard_interrupt_graceful_exit() -> None:
    capture = Capture()
    result = beginner_cli.main_loop(RaisingInput(KeyboardInterrupt()), capture)
    require(result == 0, "Ctrl+C exit returned nonzero")
    require("Goodbye from LoomQ." in capture.text, "Ctrl+C exit did not say goodbye")


def main() -> int:
    tests = [
        ("generate prompt passthrough", test_generate_prompt_passthrough),
        ("Chinese prompt passthrough", test_chinese_prompt_passthrough),
        ("repair wraps multiline QASM", test_repair_wraps_multiline_qasm),
        ("backend prompt passthrough", test_backend_prompt_passthrough),
        ("quick example calls agent", test_quick_example_calls_agent),
        ("formatter normal response", test_formatter_normal_response),
        ("formatter fallback", test_formatter_fallback),
        ("API key hidden", test_api_key_hidden_not_printed),
        ("missing model config friendly", test_missing_model_config_friendly),
        ("401 friendly error", test_error_401),
        ("masked API key suffix redacted", test_masked_api_key_suffix_redacted),
        ("402 friendly error", test_error_402),
        ("429 friendly error", test_error_429),
        ("500 friendly error", test_error_500),
        ("503 friendly error", test_error_503),
        ("551 friendly error", test_error_551),
        ("menu exit", test_menu_exit),
        ("EOF graceful exit", test_eof_graceful_exit),
        ("Ctrl+C graceful exit", test_keyboard_interrupt_graceful_exit),
    ]
    print("Running beginner CLI checks...")
    for name, test in tests:
        test()
        print(f"[PASS] {name}")
    print(f"All beginner CLI checks passed. total={len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
