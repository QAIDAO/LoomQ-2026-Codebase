#!/usr/bin/env python3
"""Start the local LoomQ interface with runtime-only LLM credentials."""

import argparse
import getpass
import os
from typing import Set

try:
    from .loomq_app.server import serve
except ImportError:
    from loomq_app.server import serve


REQUIRED_ENVIRONMENT = (
    "LOOMQ_LLM_BASE_URL",
    "LOOMQ_LLM_API_KEY",
    "LOOMQ_LLM_MODEL",
)


def configure_environment() -> Set[str]:
    added = set()
    for name in REQUIRED_ENVIRONMENT:
        if os.environ.get(name):
            continue
        if name == "LOOMQ_LLM_API_KEY":
            value = getpass.getpass(f"{name}: ").strip()
        else:
            value = input(f"{name}: ").strip()
        if not value:
            raise RuntimeError(f"{name} is required")
        os.environ[name] = value
        added.add(name)
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local LoomQ web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    added = configure_environment()
    try:
        serve(arguments.host, arguments.port)
    finally:
        for name in added:
            os.environ.pop(name, None)


if __name__ == "__main__":
    main()
