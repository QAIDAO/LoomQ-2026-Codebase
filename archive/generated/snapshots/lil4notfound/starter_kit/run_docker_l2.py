#!/usr/bin/env python3
"""Run the L2 public evaluator in Docker with runtime-only credentials."""

import argparse
import getpass
import os
import subprocess
from pathlib import Path
from typing import Dict, List


REQUIRED_ENVIRONMENT = (
    "LOOMQ_LLM_BASE_URL",
    "LOOMQ_LLM_API_KEY",
    "LOOMQ_LLM_MODEL",
)

RUNTIME_DIRECTORY = Path(__file__).resolve().parent / ".runtime"


def collect_environment() -> Dict[str, str]:
    environment = os.environ.copy()
    for name in REQUIRED_ENVIRONMENT:
        if environment.get(name):
            continue
        if name == "LOOMQ_LLM_API_KEY":
            value = getpass.getpass(f"{name}: ").strip()
        else:
            value = input(f"{name}: ").strip()
        if not value:
            raise RuntimeError(f"{name} is required")
        environment[name] = value
    return environment


def docker_command(
    image: str,
    quality_eval: bool = False,
    quality_versions: str = "legacy,v2",
    quality_mode: str = "raw",
    quality_report: str = "prompt-quality.json",
) -> List[str]:
    command = ["docker", "run", "--rm"]
    for name in REQUIRED_ENVIRONMENT:
        command.extend(["-e", name])
    if quality_eval:
        RUNTIME_DIRECTORY.mkdir(parents=True, exist_ok=True)
        command.extend(["-v", f"{RUNTIME_DIRECTORY}:/results"])
    command.extend(
        (
            [
                image,
                "python",
                "prompt_quality.py",
                "--versions",
                quality_versions,
                "--mode",
                quality_mode,
                "--json-out",
                "/results/" + quality_report,
            ]
            if quality_eval
            else [image, "python", "evaluator.py", "--level", "l2"]
        )
    )
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LoomQ L2 in Docker")
    parser.add_argument("--image", default="loomq-submission:local")
    parser.add_argument(
        "--quality-eval",
        action="store_true",
        help="compare the legacy and v2 prompts after the public L2 check",
    )
    parser.add_argument("--quality-versions", default="legacy,v2")
    parser.add_argument("--quality-mode", choices=("raw", "agent"), default="raw")
    parser.add_argument("--quality-report", default="prompt-quality.json")
    arguments = parser.parse_args()
    if not arguments.quality_report.replace("-", "").replace("_", "").replace(".", "").isalnum():
        parser.error("--quality-report must be a file name without directory components")
    environment = collect_environment()
    public_check = subprocess.run(
        docker_command(arguments.image),
        env=environment,
        check=False,
    )
    if public_check.returncode or not arguments.quality_eval:
        return public_check.returncode
    quality_check = subprocess.run(
        docker_command(
            arguments.image,
            quality_eval=True,
            quality_versions=arguments.quality_versions,
            quality_mode=arguments.quality_mode,
            quality_report=arguments.quality_report,
        ),
        env=environment,
        check=False,
    )
    return quality_check.returncode


if __name__ == "__main__":
    raise SystemExit(main())
