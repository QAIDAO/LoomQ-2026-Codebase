#!/usr/bin/env python3
"""Beginner-facing LoomQ CLI.

This file is intentionally thin: every real L2 capability goes through the
public ``adapter.agent_chat(prompt)`` entry point.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
import traceback
from typing import Callable

try:
    from . import adapter
except ImportError:
    import adapter


Output = Callable[[str], None]
Input = Callable[[str], str]


OPTIONAL_ENV_DEFAULTS = {
    "LOOMQ_LLM_TIMEOUT_SECONDS": "60",
}


def main() -> int:
    configure_stdio()
    return main_loop()


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main_loop(input_func: Input = input, output: Output = print) -> int:
    show_banner(output)
    while True:
        try:
            choice = input_func("Enter 1-5: ").strip()
            if choice == "1":
                run_generate(input_func, output)
            elif choice == "2":
                run_repair(input_func, output)
            elif choice == "3":
                run_backend(input_func, output)
            elif choice == "4":
                run_quick_examples(input_func, output)
            elif choice == "5":
                output("Goodbye from LoomQ.")
                return 0
            else:
                output("Please enter a number from 1 to 5.")
            output("")
            show_menu(output)
        except (KeyboardInterrupt, EOFError):
            output("")
            output("Goodbye from LoomQ.")
            return 0


def show_banner(output: Output = print) -> None:
    output("=============================================")
    output("           LoomQ Beginner Assistant")
    output("=============================================")
    output("")
    output("Turn plain language into quantum programs.")
    output("")
    show_menu(output)


def show_menu(output: Output = print) -> None:
    output("What would you like to do?")
    output("")
    output("1. Generate a quantum circuit")
    output("2. Repair OpenQASM")
    output("3. Choose a quantum backend")
    output("4. Try a quick example")
    output("5. Exit")
    output("")


def ensure_l2_environment() -> None:
    for name, value in OPTIONAL_ENV_DEFAULTS.items():
        os.environ.setdefault(name, value)
    missing = [name for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_MODEL") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Model service configuration is incomplete.\n\n"
            "Please set:\n"
            + "\n".join(f"- {name}" for name in missing)
            + "\n\nThe API key can be entered securely when requested."
        )
    if not os.environ.get("LOOMQ_LLM_API_KEY"):
        key = getpass.getpass("DeepSeek API key (input hidden): ")
        if not key.strip():
            raise ValueError("DeepSeek API key was empty")
        os.environ["LOOMQ_LLM_API_KEY"] = key


def run_generate(input_func: Input = input, output: Output = print) -> None:
    output("")
    output("Describe the circuit you want in normal language.")
    output("")
    output("Example:")
    output("Create a five-qubit GHZ state and measure all qubits.")
    output("")
    prompt = input_func("Prompt: ")
    execute_prompt(prompt, "Result", output)


def run_repair(input_func: Input = input, output: Output = print) -> None:
    output("")
    output("Paste your OpenQASM below.")
    output("When finished, enter a line containing only:")
    output("")
    output("END")
    output("")
    qasm = read_multiline_until_end(input_func)
    prompt = "Please repair the following OpenQASM and return a valid circuit:\n\n" + qasm
    execute_prompt(prompt, "Repair result", output)


def run_backend(input_func: Input = input, output: Output = print) -> None:
    output("")
    output("Describe what you need.")
    output("")
    output("Examples:")
    output("")
    output("I need at least 15 qubits, zero queue, and a free backend.")
    output("I want a local simulator without registration.")
    output("我需要真实量子硬件。")
    output("")
    prompt = input_func("Prompt: ")
    execute_prompt(prompt, "Recommended backend", output)


def run_quick_examples(input_func: Input = input, output: Output = print) -> None:
    examples = {
        "1": ("Bell state", "Generate a Bell state and measure both qubits."),
        "2": ("Five-qubit GHZ", "Generate a five-qubit GHZ state and measure all qubits."),
        "3": (
            "Repair broken QASM",
            "Please repair the following OpenQASM and return a valid circuit:\n\n"
            "OPENQASM 2.0;\n"
            'include "qelib1.inc";\n'
            "qreg q[2];\n"
            "H q[0];\n"
            "CX q[0] q[1]",
        ),
        "4": ("Find a free local backend", "I want a free local simulator without registration."),
    }
    output("")
    output("Choose an example:")
    output("")
    output("1. Bell state")
    output("2. Five-qubit GHZ")
    output("3. Repair broken QASM")
    output("4. Find a free local backend")
    output("5. Back")
    output("")
    choice = input_func("Enter 1-5: ").strip()
    if choice == "5":
        return
    if choice not in examples:
        output("Please enter a number from 1 to 5.")
        return
    title, prompt = examples[choice]
    execute_prompt(prompt, title, output)


def read_multiline_until_end(input_func: Input = input) -> str:
    lines: list[str] = []
    while True:
        line = input_func("")
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def execute_prompt(prompt: str, title: str, output: Output = print) -> None:
    if not prompt.strip():
        output("[!] Nothing to send.")
        return
    try:
        ensure_l2_environment()
        output("")
        output("Understanding your request...")
        response = adapter.agent_chat(prompt)
        format_response(response, title, output)
    except Exception as exc:
        show_friendly_error(exc, output)


def format_response(response: str, title: str = "Result", output: Output = print) -> None:
    try:
        text = str(response)
        output("")
        output("---------------------------------------------")
        output(title)
        output("---------------------------------------------")
        qasm = extract_qasm(text)
        backend_ids = extract_backend_ids(text)
        validation = extract_lines(text, ("validation", "validated", "fidelity", "pass", "passed"))
        counts = extract_lines(text, ("counts",))

        if qasm:
            output("")
            output("OpenQASM")
            output("---------")
            output(qasm)
        if backend_ids:
            output("")
            output("Recommended backend ID(s)")
            output("-------------------------")
            for backend_id in backend_ids:
                output(f"- {backend_id}")
        if validation:
            output("")
            output("Validation")
            output("----------")
            output(validation)
        if counts:
            output("")
            output("Local result")
            output("------------")
            output(counts)
        if not any((qasm, backend_ids, validation, counts)):
            output("")
            output(text)
        else:
            remainder = remove_extracted_qasm(text, qasm).strip()
            remainder = remove_displayed_lines(remainder, validation, counts, backend_ids).strip()
            if remainder and len(remainder) <= 3000:
                output("")
                output("Agent response")
                output("--------------")
                output(remainder)
    except Exception:
        output(str(response))


def extract_qasm(text: str) -> str:
    fenced = re.search(r"```(?:openqasm|qasm)?\s*(OPENQASM\s+2\.0;.*?)(?:```)", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start = re.search(r"OPENQASM\s+2\.0;", text, re.IGNORECASE)
    if not start:
        return ""
    tail = text[start.start() :]
    end = re.search(r"\n\s*(?:Validation|Local result|Result|Recommended backend|$)", tail, re.IGNORECASE)
    if end and end.start() > 0:
        return tail[: end.start()].strip()
    return tail.strip()


def remove_extracted_qasm(text: str, qasm: str) -> str:
    if not qasm:
        return text
    def remove_qasm_fence(match: re.Match[str]) -> str:
        body = match.group(1)
        return "" if "OPENQASM" in body.upper() else match.group(0)

    cleaned = re.sub(r"```(?:openqasm|qasm)?\s*(.*?)```", remove_qasm_fence, text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = cleaned.replace(qasm, "")
    cleaned = re.sub(r"```(?:openqasm|qasm)?\s*```", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def remove_displayed_lines(text: str, validation: str, counts: str, backend_ids: list[str]) -> str:
    displayed = {line.strip() for line in (validation + "\n" + counts).splitlines() if line.strip()}
    cleaned = []
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            cleaned.append(line)
            continue
        if stripped in displayed:
            continue
        if lower.startswith(("validation:", "local counts:", "counts:")):
            continue
        if lower in {"recommended backend id(s):", "recommended backend ids:", "recommended backend id:"}:
            continue
        if any(backend_id in stripped for backend_id in backend_ids):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_backend_ids(text: str) -> list[str]:
    pattern = r"\b(?:spinq|originq|braket|aws|ibm)[a-z0-9_]*(?:_[a-z0-9]+)+\b"
    ids = []
    for match in re.finditer(pattern, text, re.IGNORECASE):
        value = match.group(0)
        if value not in ids:
            ids.append(value)
    return ids


def extract_lines(text: str, keywords: tuple[str, ...]) -> str:
    lines = []
    for line in text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            lines.append(line)
    return "\n".join(lines).strip()


def show_friendly_error(exc: Exception, output: Output = print) -> None:
    message = sanitize_error(str(exc))
    output("")
    output("[!] The request could not be completed.")
    output("")
    output("Reason:")
    output(friendly_reason(message))
    output("")
    output("Try:")
    output("- check your API key")
    output("- check your network connection")
    output("- simplify the request")
    output("- try again later")
    if message:
        output("")
        output("Technical details:")
        output(message[:1000])
    if os.environ.get("LOOMQ_DEBUG") == "1":
        output("")
        output("Debug traceback:")
        output(sanitize_error(traceback.format_exc())[:4000])


def friendly_reason(message: str) -> str:
    if "Model service configuration is incomplete" in message:
        return "Model service configuration is incomplete."
    if "401" in message:
        return "Authentication failed. Please check your DeepSeek API key."
    if "402" in message:
        return "DeepSeek API balance is insufficient."
    if "429" in message:
        return "The model service is temporarily rate limited. Please try again later."
    if any(code in message for code in ("500", "503", "551")):
        return "The model service appears temporarily unavailable. Your LoomQ code may still be fine. Please try again later."
    return message or "Unknown error."


def sanitize_error(message: str) -> str:
    sanitized = message
    api_key = os.environ.get("LOOMQ_LLM_API_KEY")
    if api_key:
        sanitized = sanitized.replace(api_key, "[REDACTED]")
    sanitized = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", sanitized)
    sanitized = re.sub(
        r"(your\s+api\s+key\s*:\s*)(?:\*+|[A-Za-z0-9_-]*\*+)[A-Za-z0-9_-]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(api\s+key\s*:\s*)(?:\*+|[A-Za-z0-9_-]*\*+)[A-Za-z0-9_-]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"Authorization\s*:\s*\S+", "Authorization: [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


if __name__ == "__main__":
    raise SystemExit(main())
