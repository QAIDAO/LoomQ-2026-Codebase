#!/usr/bin/env python3

import argparse
import json
import os
import sys
from typing import Optional
import getpass
try:
    from .loomq_config import (
        get_config_path,
        get_default_shots,
        get_default_target,
        get_llm_api_key,
        get_llm_base_url,
        get_llm_model,
        load_config,
        save_config,
    )
except ImportError:
    from loomq_config import (
        get_config_path,
        get_default_shots,
        get_default_target,
        get_llm_api_key,
        get_llm_base_url,
        get_llm_model,
        load_config,
        save_config,
    )
os.environ.setdefault(
    "OPENBLAS_NUM_THREADS",
    "1",
)

os.environ.setdefault(
    "OMP_NUM_THREADS",
    "1",
)

os.environ.setdefault(
    "MKL_NUM_THREADS",
    "1",
)

os.environ.setdefault(
    "NUMEXPR_NUM_THREADS",
    "1",
)
try:
    from .adapter import (
        agent_chat,
        agent_run,
        agent_run_hybrid_explain,
    )
except ImportError:
    from adapter import (
        agent_chat,
        agent_run,
        agent_run_hybrid_explain,
    )


SUPPORTED_TARGETS = {
    "spinq",
    "originq",
    "braket",
}


# ============================================================
# UI helpers
# ============================================================


def print_banner():
    print()
    print("=" * 72)
    print("                         LoomQ CLI")
    print("              Natural-Language Quantum Computing")
    print("=" * 72)
    print()


def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def build_prompt(
    prompt: str,
    target: Optional[str] = None,
    shots: Optional[int] = None,
) -> str:

    parts = [
        prompt.strip()
    ]

    if target:
        target_names = {
            "spinq": "SpinQ",
            "originq": "OriginQ",
            "braket": "Braket",
        }

        parts.append(
            f"Use the {target_names[target]} target."
        )

    if shots is not None:
        parts.append(
            f"Run exactly {shots} shots."
        )

    return "\n".join(parts)


def print_counts(counts):
    if not counts:
        print("(no counts)")
        return

    total = sum(
        counts.values()
    )

    width = 40

    for state, count in sorted(
        counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        probability = (
            count / total
            if total
            else 0.0
        )

        bar_length = int(
            probability * width
        )

        bar = "#" * bar_length

        print(
            f"{state:>12} | "
            f"{count:>7} | "
            f"{probability:>7.3%} | "
            f"{bar}"
        )


# ============================================================
# Commands
# ============================================================


def command_quantum(
    prompt,
    target=None,
    shots=None,
):
    if target is None:
        target = (
            get_default_target()
        )

    if shots is None:
        shots = (
            get_default_shots()
        )
    full_prompt = build_prompt(
        prompt,
        target,
        shots,
    )

    print_section(
        "Running Quantum Task"
    )

    print(full_prompt)

    print()
    print("LoomQ is generating and executing the circuit...")

    result = agent_run(
        full_prompt
    )

    print_section(
        "Generated OpenQASM"
    )

    print(
        result["qasm"]
    )

    print_section(
        "Execution"
    )

    print(
        "Target:",
        result["target"],
    )

    print(
        "Shots :",
        result["shots"],
    )

    execution = result[
        "execution"
    ]

    counts = execution.get(
        "counts",
        {},
    )

    print()
    print_counts(
        counts
    )

    return result


def command_hybrid(
    prompt,
    target=None,
    shots=None,
):
    if target is None:
        target = (
            get_default_target()
        )

    if shots is None:
        shots = (
            get_default_shots()
        )
    full_prompt = build_prompt(
        prompt,
        target,
        shots,
    )

    full_prompt += (
        "\nExplain the result after execution."
    )

    print_section(
        "Running Hybrid Quantum-Classical Task"
    )

    print(full_prompt)

    print()
    print(
        "LoomQ is generating Hybrid-QASM, "
        "running the quantum backend, "
        "and executing RISC-V..."
    )

    output = (
        agent_run_hybrid_explain(
            full_prompt
        )
    )

    execution = output[
        "execution"
    ]

    runtime = execution[
        "result"
    ]

    print_section(
        "Generated Hybrid-QASM"
    )

    print(
        execution[
            "hybrid_qasm"
        ]
    )

    print_section(
        "Quantum Measurement"
    )

    counts = runtime[
        "quantum_result"
    ].get(
        "counts",
        {},
    )

    print_counts(
        counts
    )

    print_section(
        "Classical Outcomes"
    )

    for index, outcome in enumerate(
        runtime.get(
            "classical_outcomes",
            []
        ),
        start=1,
    ):
        print(
            f"Outcome {index}"
        )

        print(
            "  count       =",
            outcome[
                "count"
            ],
        )

        print(
            "  probability =",
            round(
                outcome[
                    "probability"
                ],
                6,
            ),
        )

        registers = outcome[
            "registers"
        ]

        active = {
            key: value
            for key, value
            in registers.items()
            if value != 0
        }

        if active:
            print(
                "  registers   =",
                active,
            )
        else:
            print(
                "  registers   = all zero"
            )

        print()

    print_section(
        "LoomQ Explanation"
    )

    print(
        output[
            "explanation"
        ]
    )

    return output


def command_backend(
    prompt,
):
    print_section(
        "Backend Advisor"
    )

    print(prompt)

    print()
    print(
        "LoomQ is consulting the official "
        "backend capability table..."
    )

    result = agent_chat(
        prompt
    )

    print_section(
        "Recommendation"
    )

    print(result)

    return result


def command_chat(
    prompt,
):
    print_section(
        "LoomQ Agent"
    )

    result = agent_chat(
        prompt
    )

    print(result)

    return result

def command_configure():

    print_section(
        "LoomQ Configuration"
    )

    current = load_config()

    print(
        "Configuration file:"
    )

    print(
        get_config_path()
    )

    print()
    print(
        "Press Enter to keep the "
        "current/default value."
    )

    # ========================================================
    # LLM Base URL
    # ========================================================

    current_base_url = (
        current.get(
            "llm_base_url"
        )
        or "https://api.deepseek.com"
    )

    value = input(
        f"LLM Base URL "
        f"[{current_base_url}]: "
    ).strip()

    if value:
        base_url = value
    else:
        base_url = current_base_url

    # ========================================================
    # Model
    # ========================================================

    current_model = (
        current.get(
            "llm_model"
        )
        or "deepseek-v4-flash"
    )

    value = input(
        f"LLM Model "
        f"[{current_model}]: "
    ).strip()

    if value:
        model = value
    else:
        model = current_model

    # ========================================================
    # API Key
    #
    # Do not echo the key to the terminal.
    # ========================================================

    existing_key = bool(
        current.get(
            "llm_api_key"
        )
    )

    if existing_key:
        key_prompt = (
            "LLM API Key "
            "[configured; Enter to keep]: "
        )
    else:
        key_prompt = (
            "LLM API Key: "
        )

    api_key = getpass.getpass(
        key_prompt
    ).strip()

    if (
        not api_key
        and existing_key
    ):
        api_key = current[
            "llm_api_key"
        ]

    # ========================================================
    # Default target
    # ========================================================

    current_target = (
        current.get(
            "default_target"
        )
        or "originq"
    )

    value = input(
        "Default target "
        f"(spinq/originq/braket) "
        f"[{current_target}]: "
    ).strip().lower()

    if value:
        target = value
    else:
        target = current_target

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            "Default target must be one of: "
            "spinq, originq, braket."
        )

    # ========================================================
    # Default shots
    # ========================================================

    current_shots = (
        current.get(
            "default_shots"
        )
        or 1024
    )

    value = input(
        f"Default shots "
        f"[{current_shots}]: "
    ).strip()

    if value:
        shots = int(
            value
        )
    else:
        shots = int(
            current_shots
        )

    if shots <= 0:
        raise ValueError(
            "Default shots must be positive."
        )

    # ========================================================
    # Save
    # ========================================================

    config = {
        "llm_base_url": base_url,
        "llm_api_key": api_key,
        "llm_model": model,
        "default_target": target,
        "default_shots": shots,
    }

    save_config(
        config
    )

    print()
    print(
        "LoomQ configuration saved."
    )

    print(
        "Path:",
        get_config_path(),
    )

    print()
    print(
        "Default target:",
        target,
    )

    print(
        "Default shots :",
        shots,
    )

    print(
        "LLM model     :",
        model,
    )

    print(
        "API key       :",
        (
            "configured"
            if api_key
            else "not configured"
        ),
    )
def command_doctor():
    print_section(
        "LoomQ System Check"
    )

    checks = []
    base_url = (
        get_llm_base_url()
    )
    
    model = (
        get_llm_model()
    )
    
    api_key = (
        get_llm_api_key()
    )

    checks.append(
        (
            "LLM Base URL",
            bool(base_url),
            base_url or "not configured",
        )
    )

    checks.append(
        (
            "LLM Model",
            bool(model),
            model or "not configured",
        )
    )

    checks.append(
        (
            "LLM API Key",
            bool(api_key),
            (
                "configured"
                if api_key
                else "not configured"
            ),
        )
    )

    try:
        import spinqit  # noqa: F401

        checks.append(
            (
                "SpinQit",
                True,
                "available",
            )
        )

    except Exception as exc:
        checks.append(
            (
                "SpinQit",
                False,
                str(exc),
            )
        )

    try:
        import pyqpanda  # noqa: F401

        checks.append(
            (
                "pyQPanda",
                True,
                "available",
            )
        )

    except Exception as exc:
        checks.append(
            (
                "pyQPanda",
                False,
                str(exc),
            )
        )

    try:
        import braket  # noqa: F401

        checks.append(
            (
                "Amazon Braket",
                True,
                "available",
            )
        )

    except Exception as exc:
        checks.append(
            (
                "Amazon Braket",
                False,
                str(exc),
            )
        )

    all_ok = True

    for name, ok, message in checks:

        status = (
            "OK"
            if ok
            else "FAIL"
        )

        if not ok:
            all_ok = False

        print(
            f"[{status:4}] "
            f"{name:20} "
            f"{message}"
        )

    print()

    if all_ok:
        print(
            "LoomQ environment looks ready."
        )
    else:
        print(
            "Some LoomQ components need attention."
        )

    return all_ok


# ============================================================
# Interactive mode
# ============================================================


def ask_multiline(
    message,
):
    print()
    print(message)
    print(
        "Finish with an empty line."
    )
    print()

    lines = []

    while True:

        try:
            line = input("> ")

        except EOFError:
            break

        if not line.strip():
            break

        lines.append(
            line
        )

    return "\n".join(
        lines
    ).strip()


def interactive_mode():

    print_banner()

    while True:

        print(
            "1. Quantum Run"
        )
        print(
            "2. Hybrid Run"
        )
        print(
            "3. Backend Advisor"
        )
        print(
            "4. Agent Chat"
        )
        print(
            "5. System Check"
        )
        print(
            "0. Exit"
        )

        print()

        choice = input(
            "LoomQ > "
        ).strip()

        try:

            if choice == "0":
                print(
                    "Bye."
                )
                return

            if choice == "1":

                prompt = ask_multiline(
                    "Describe the quantum task:"
                )

                if prompt:
                    command_quantum(
                        prompt
                    )

            elif choice == "2":

                prompt = ask_multiline(
                    "Describe the hybrid task:"
                )

                if prompt:
                    command_hybrid(
                        prompt
                    )

            elif choice == "3":

                prompt = ask_multiline(
                    "Describe backend requirements:"
                )

                if prompt:
                    command_backend(
                        prompt
                    )

            elif choice == "4":

                prompt = ask_multiline(
                    "Ask LoomQ:"
                )

                if prompt:
                    command_chat(
                        prompt
                    )

            elif choice == "5":

                command_doctor()

            else:

                print(
                    "Unknown command."
                )

        except KeyboardInterrupt:

            print()
            print(
                "Operation cancelled."
            )

        except Exception as exc:

            print()
            print_section(
                "ERROR"
            )

            print(
                type(exc).__name__
                + ":",
                exc,
            )

        print()
        input(
            "Press Enter to continue..."
        )

        print()
        print("-" * 72)
        print()


# ============================================================
# argparse mode
# ============================================================


def build_parser():

    parser = argparse.ArgumentParser(
        prog="loomq",
        description=(
            "Natural-language quantum and "
            "hybrid computing with LoomQ."
        ),
    )

    subparsers = (
        parser.add_subparsers(
            dest="command"
        )
    )

    # --------------------------------------------------------
    # quantum
    # --------------------------------------------------------

    quantum = subparsers.add_parser(
        "quantum",
        help=(
            "Generate and execute "
            "a quantum circuit."
        ),
    )

    quantum.add_argument(
        "prompt",
        nargs="+",
    )

    quantum.add_argument(
        "--target",
        choices=sorted(
            SUPPORTED_TARGETS
        ),
    )

    quantum.add_argument(
        "--shots",
        type=int,
    )

    # --------------------------------------------------------
    # hybrid
    # --------------------------------------------------------

    hybrid = subparsers.add_parser(
        "hybrid",
        help=(
            "Generate and execute a hybrid "
            "quantum-classical program."
        ),
    )

    hybrid.add_argument(
        "prompt",
        nargs="+",
    )

    hybrid.add_argument(
        "--target",
        choices=sorted(
            SUPPORTED_TARGETS
        ),
    )

    hybrid.add_argument(
        "--shots",
        type=int,
    )

    # --------------------------------------------------------
    # backend
    # --------------------------------------------------------

    backend = subparsers.add_parser(
        "backend",
        help="Recommend a backend.",
    )

    backend.add_argument(
        "prompt",
        nargs="+",
    )

    # --------------------------------------------------------
    # chat
    # --------------------------------------------------------

    chat = subparsers.add_parser(
        "chat",
        help="Use the LoomQ L2 agent.",
    )

    chat.add_argument(
        "prompt",
        nargs="+",
    )

    # --------------------------------------------------------
    # doctor
    # --------------------------------------------------------

    subparsers.add_parser(
        "doctor",
        help=(
            "Check LoomQ environment."
        ),
    )
    subparsers.add_parser(
        "configure",
        help=(
            "Configure LoomQ API and "
            "default runtime settings."
        ),
    )
    
    return parser


def main():

    parser = build_parser()

    args = parser.parse_args()

    if args.command is None:

        interactive_mode()
        return

    if args.command == "doctor":

        command_doctor()
        return
        
    if args.command == "configure":
        command_configure()
        return
        
    prompt = " ".join(
        args.prompt
    )

    if args.command == "quantum":

        command_quantum(
            prompt,
            target=args.target,
            shots=args.shots,
        )

        return

    if args.command == "hybrid":

        command_hybrid(
            prompt,
            target=args.target,
            shots=args.shots,
        )

        return

    if args.command == "backend":

        command_backend(
            prompt
        )

        return

    if args.command == "chat":

        command_chat(
            prompt
        )

        return


if __name__ == "__main__":
    main()
