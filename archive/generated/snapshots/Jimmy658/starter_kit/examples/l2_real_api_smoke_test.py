#!/usr/bin/env python3
"""Tiny real-API smoke test for LoomQ L2.

The API key is read with getpass and stored only in this Python process. This
script does not write secrets to disk, .env files, git config, or shell profile.
"""

from __future__ import annotations

import getpass
import os
import sys
import time
from typing import Any


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import adapter  # noqa: E402
from llm_client import chat_completion  # noqa: E402


DEFAULTS = {
    "LOOMQ_LLM_BASE_URL": "https://api.deepseek.com",
    "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
    "LOOMQ_LLM_TIMEOUT_SECONDS": "60",
}


def configure_process_environment() -> bool:
    for name, value in DEFAULTS.items():
        os.environ.setdefault(name, value)

    if not os.environ.get("LOOMQ_LLM_API_KEY"):
        key = getpass.getpass("DeepSeek API Key: ")
        if not key.strip():
            print("No API key entered; stopping.")
            return False
        os.environ["LOOMQ_LLM_API_KEY"] = key.strip()
    return True


def response_content(response: dict[str, Any]) -> str:
    return response["choices"][0]["message"]["content"]


def connectivity_test() -> bool:
    print("Running minimal API connectivity test...")
    messages = [{"role": "user", "content": "Reply with exactly: LoomQ API works"}]
    try:
        response = chat_completion(messages, max_tokens=16)
        print("Connectivity response:")
        print(response_content(response))
        return True
    except Exception as exc:
        print("Connectivity test failed.")
        print("Error type:", type(exc).__name__)
        print("Error message:", str(exc))
        return False


def run_agent_case(index: int, name: str, prompt: str) -> None:
    print("=" * 50)
    print(f"TEST {index}: {name}")
    print("Prompt:")
    print(prompt)
    print("Response:")
    start = time.perf_counter()
    try:
        print(adapter.agent_chat(prompt))
    except Exception as exc:
        print("Case failed.")
        print("Error type:", type(exc).__name__)
        print("Error message:", str(exc))
    elapsed = time.perf_counter() - start
    print(f"Elapsed time: {elapsed:.2f} s")
    print("=" * 50)


def main() -> int:
    if not configure_process_environment():
        return 1
    if not connectivity_test():
        return 1

    cases = [
        (1, "Bell", "Generate a Bell state and measure both qubits."),
        (2, "GHZ-5", "生成一个五比特 GHZ 态，并测量所有量子比特。"),
        (3, "Backend", "I need at least 15 qubits, no queue, and a free backend. Which backend should I use?"),
    ]
    for index, name, prompt in cases:
        run_agent_case(index, name, prompt)

    print("Completed real API smoke test.")
    print("Check DeepSeek usage/balance after this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
