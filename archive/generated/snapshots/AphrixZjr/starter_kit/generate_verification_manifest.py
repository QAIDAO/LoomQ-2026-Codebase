#!/usr/bin/env python3
"""Run offline verification commands and write a reproducible evidence manifest.

The default command set deliberately excludes live L2/model calls, hardware calls,
network access, Docker builds, and Git mutations.  Child processes receive a small
allowlist of ordinary process variables instead of inheriting the caller's complete
environment, so credentials in variables such as API keys and tokens are neither
available to the commands nor copied into the manifest.

Repository state is captured before commands and evidence files are written.  This
is intentionally a source snapshot, not a self-referential claim that the generated
manifest already belongs to the commit whose hash it records.  Tracked evidence is
finalized in a second, evidence-only commit (or published as an external CI artifact).
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import os
import platform
import re
import shlex
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
DEFAULT_OUTPUT_DIR = Path("evidence") / "files"
MANIFEST_NAME = "verification-manifest.json"

# Values are passed to subprocesses when present, but are never serialized.  In
# particular, do not replace this with os.environ.copy(): default verification
# must not expose provider credentials or other secret environment variables.
SAFE_ENVIRONMENT_KEYS = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "WINDIR",
)


@dataclass(frozen=True)
class CommandSpec:
    """One verification command and its evidence-log name."""

    name: str
    argv: tuple[str, ...]
    heavy: bool = False


def _utc_now() -> str:
    """Return a compact ISO-8601 UTC timestamp."""

    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _sanitized_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a minimal child environment without enumerating secret variables."""

    source = os.environ if source is None else source
    child_environment = {
        key: source[key] for key in SAFE_ENVIRONMENT_KEYS if key in source
    }
    child_environment["PYTHONIOENCODING"] = "utf-8"
    child_environment["PYTHONUNBUFFERED"] = "1"
    return child_environment


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def _run_probe(
    argv: Sequence[str], root: Path, environment: Mapping[str, str]
) -> tuple[bool, str | None, int | None]:
    """Run a small metadata probe without preserving arbitrary error output."""

    try:
        result = subprocess.run(
            list(argv),
            cwd=str(root),
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False, None, None
    output = result.stdout.strip()
    if result.returncode != 0 or not output:
        return False, None, result.returncode
    # Version commands are expected to be one line.  Keeping only that line also
    # prevents an unexpectedly noisy tool from adding unrelated host details.
    return True, output.splitlines()[0].strip(), result.returncode


def _collect_git_state(
    root: Path, environment: Mapping[str, str]
) -> dict[str, Any]:
    repository_root = root
    for candidate in (root, *root.parents):
        if (candidate / ".git").exists():
            repository_root = candidate
            break

    # A per-invocation safe.directory override keeps this read-only probe useful
    # in CI/sandbox mounts whose filesystem owner differs from the runner.  It
    # does not write local or global Git configuration.
    # Git's config parser treats backslashes as escapes, so use slash-separated
    # paths even on Windows.
    git = ("git", "-c", f"safe.directory={repository_root.as_posix()}")
    available, head, _ = _run_probe(
        (*git, "rev-parse", "--verify", "HEAD"), repository_root, environment
    )
    if not available or head is None or re.fullmatch(r"[0-9a-fA-F]{40}", head) is None:
        return {"available": False, "head": None, "dirty": None}

    try:
        status = subprocess.run(
            (*git, "status", "--porcelain", "--untracked-files=normal"),
            cwd=str(repository_root),
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=False,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return {"available": True, "head": head.lower(), "dirty": None}

    dirty = bool(status.stdout) if status.returncode == 0 else None
    return {"available": True, "head": head.lower(), "dirty": dirty}


def _collect_environment(
    root: Path, environment: Mapping[str, str]
) -> dict[str, Any]:
    node_available, node_version, _ = _run_probe(
        ("node", "--version"), root, environment
    )
    docker_available, docker_version, _ = _run_probe(
        ("docker", "--version"), root, environment
    )
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "node": {"available": node_available, "version": node_version},
        "docker": {"available": docker_available, "version": docker_version},
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
        },
        "architecture": {
            "machine": platform.machine(),
            "pointer_bits": struct.calcsize("P") * 8,
        },
    }


def default_commands(python_executable: str | None = None) -> list[CommandSpec]:
    """Return the deterministic, offline default verification set."""

    python = python_executable or sys.executable
    syntax_source = (
        "from pathlib import Path; "
        "files=('adapter.py','evaluator.py','loomq_l1.py','loomq_l2.py',"
        "'loomq_l3.py','prepare_submission.py','quantum_riscv.py',"
        "'riscv_emulator.py'); "
        "[compile(Path(name).read_bytes(), name, 'exec') for name in files]"
    )
    return [
        CommandSpec(
            "syntax-check",
            (python, "-B", "-c", syntax_source),
        ),
        CommandSpec(
            "unittest",
            (python, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"),
            heavy=True,
        ),
        CommandSpec(
            "l1-regression",
            (python, "-B", "l1_regression.py", "--target", "spinq,originq,braket"),
            heavy=True,
        ),
        CommandSpec(
            "evaluator-l1",
            (
                python,
                "-B",
                "evaluator.py",
                "--level",
                "l1",
                "--target",
                "spinq,originq,braket",
            ),
            heavy=True,
        ),
        CommandSpec(
            "evaluator-l3",
            (python, "-B", "evaluator.py", "--level", "l3"),
            heavy=True,
        ),
    ]


def _split_command(value: str) -> tuple[str, ...]:
    """Parse either a JSON argv array or a conventional quoted command string."""

    stripped = value.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON command array: {exc.msg}") from None
        if not isinstance(parsed, list) or not parsed or not all(
            isinstance(item, str) and item for item in parsed
        ):
            raise ValueError("a JSON command must be a non-empty array of strings")
        return tuple(parsed)

    try:
        # POSIX-style quoting is intentionally consistent on every host.  JSON
        # argv arrays remain available for Windows paths containing backslashes.
        parsed_text = shlex.split(stripped, posix=True)
    except ValueError as exc:
        raise ValueError(f"invalid command quoting: {exc}") from None
    if not parsed_text:
        raise ValueError("command must not be empty")
    return tuple(parsed_text)


def _parse_custom_command(value: str, index: int) -> CommandSpec:
    name = f"command-{index}"
    command_text = value
    if "::" in value:
        possible_name, command_text = value.split("::", 1)
        if not possible_name.strip():
            raise ValueError("command name before '::' must not be empty")
        name = possible_name.strip()
    return CommandSpec(name=name, argv=_split_command(command_text), heavy=False)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "command"


def _allocate_log_names(commands: Iterable[CommandSpec]) -> list[str]:
    names: list[str] = []
    counts: dict[str, int] = {}
    for command in commands:
        stem = _slug(command.name)
        counts[stem] = counts.get(stem, 0) + 1
        suffix = "" if counts[stem] == 1 else f"-{counts[stem]}"
        names.append(f"{stem}{suffix}-current.txt")
    return names


def _execute_command(
    command: CommandSpec,
    root: Path,
    log_path: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    started_at = _utc_now()
    started_clock = time.perf_counter()
    return_code = 126
    timed_out = False
    error: str | None = None

    with log_path.open("wb") as output:
        try:
            process = subprocess.Popen(
                list(command.argv),
                cwd=str(root),
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                shell=False,
            )
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                error = "timeout"
                process.kill()
                process.wait()
                return_code = 124
                output.write(
                    f"\n[verification runner: timed out after {timeout_seconds:g} seconds]\n".encode(
                        "utf-8"
                    )
                )
        except FileNotFoundError:
            error = "executable_not_found"
            return_code = 127
            output.write(b"[verification runner: executable not found]\n")
        except OSError:
            error = "process_start_failed"
            return_code = 126
            output.write(b"[verification runner: process could not be started]\n")

    digest, byte_count = _sha256_file(log_path)
    duration = max(0.0, time.perf_counter() - started_clock)
    result: dict[str, Any] = {
        "name": command.name,
        "argv": list(command.argv),
        "started_at_utc": started_at,
        "duration_seconds": round(duration, 6),
        "return_code": return_code,
        "timed_out": timed_out,
        "output_file": log_path.name,
        "output_sha256": digest,
        "output_bytes": byte_count,
    }
    if error is not None:
        result["error"] = error
    return result


def _display_path(path: Path, root: Path, original: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        # An absolute outside-root path was explicitly supplied by the caller.
        return original.replace("\\", "/")


def _hash_artifacts(arguments: Iterable[str], root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for argument in arguments:
        requested = Path(argument)
        path = requested if requested.is_absolute() else root / requested
        path = path.resolve()
        displayed = _display_path(path, root, argument)
        if not path.exists():
            artifacts.append(
                {
                    "path": displayed,
                    "status": "missing",
                    "sha256": None,
                    "bytes": None,
                }
            )
            continue
        if not path.is_file():
            artifacts.append(
                {
                    "path": displayed,
                    "status": "not_a_file",
                    "sha256": None,
                    "bytes": None,
                }
            )
            continue
        try:
            digest, byte_count = _sha256_file(path)
        except OSError:
            artifacts.append(
                {
                    "path": displayed,
                    "status": "unreadable",
                    "sha256": None,
                    "bytes": None,
                }
            )
            continue
        artifacts.append(
            {
                "path": displayed,
                "status": "ok",
                "sha256": digest,
                "bytes": byte_count,
            }
        )
    return artifacts


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run LoomQ's offline verification set, capture combined stdout/stderr, "
            "and write a SHA-256 evidence manifest."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Custom commands replace the defaults. Repeat --command to run several.\n"
            "Use NAME::COMMAND for a stable log name, or a JSON argv array when\n"
            "quoting Windows paths, for example:\n"
            "  --command 'quick::[\"python\",\"-m\",\"unittest\",\"tests.test_l1_core\"]'\n\n"
            "Defaults are offline only: no L2 live/model calls, hardware calls,\n"
            "network commands, Docker builds, or Git writes are performed.\n\n"
            "Tracked evidence uses two-phase finalization: run on a clean source\n"
            "commit, then create an evidence-only commit. repository.head names\n"
            "the pre-run source snapshot, never the later commit containing the manifest."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent),
        help="starter_kit root used as each command's working directory",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="evidence directory, relative to --root unless absolute",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        metavar="[NAME::]COMMAND",
        help="custom command; when present, replaces the default command set",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="PATH",
        help="additional file to hash (repeatable; relative paths use --root)",
    )
    parser.add_argument(
        "--skip-heavy",
        action="store_true",
        help="with defaults, run only the lightweight syntax check",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900.0,
        help="per-command timeout in seconds (default: 900)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")

    root = Path(arguments.root).resolve()
    if not root.is_dir():
        parser.error(f"--root is not a directory: {arguments.root}")

    output_argument = Path(arguments.output_dir)
    output_dir = (
        output_argument if output_argument.is_absolute() else root / output_argument
    ).resolve()

    try:
        commands = (
            [
                _parse_custom_command(command, index)
                for index, command in enumerate(arguments.command, start=1)
            ]
            if arguments.command
            else [
                command
                for command in default_commands()
                if not (arguments.skip_heavy and command.heavy)
            ]
        )
    except ValueError as exc:
        parser.error(str(exc))

    child_environment = _sanitized_environment()

    # Snapshot repository state before evidence files from this run are touched.
    # A generated manifest cannot name the later commit that will contain itself;
    # keep this provenance explicit instead of presenting HEAD as a final-evidence
    # commit identity.
    git_state = _collect_git_state(root, child_environment)
    git_state.update({
        "captured_before_commands": True,
        "captured_before_evidence_write": True,
        "head_role": "source_snapshot",
    })
    environment = _collect_environment(root, child_environment)
    generated_at = _utc_now()
    output_dir.mkdir(parents=True, exist_ok=True)

    command_results = []
    for command, log_name in zip(commands, _allocate_log_names(commands)):
        command_results.append(
            _execute_command(
                command,
                root,
                output_dir / log_name,
                child_environment,
                arguments.timeout_seconds,
            )
        )

    artifact_results = _hash_artifacts(arguments.artifact, root)
    success = all(item["return_code"] == 0 for item in command_results) and all(
        item["status"] == "ok" for item in artifact_results
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "success": success,
        "repository": git_state,
        "environment": environment,
        "execution_policy": {
            "automatic_commit": False,
            "default_l2_live": False,
            "default_network_access": False,
            "child_environment": "sanitized_allowlist_values_not_recorded",
            "evidence_outputs_mutate_worktree": True,
            "tracked_evidence_finalization": "two_phase_evidence_only_commit",
        },
        "commands": command_results,
        "artifacts": artifact_results,
    }
    _write_manifest(output_dir / MANIFEST_NAME, manifest)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
