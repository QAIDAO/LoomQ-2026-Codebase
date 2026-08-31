from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import generate_verification_manifest as manifest_tool


class _FakeProcess:
    def __init__(self, output, return_code=0, payload=b"combined output\n"):
        self._output = output
        self._return_code = return_code
        self._payload = payload
        self.killed = False

    def wait(self, timeout=None):
        self._output.write(self._payload)
        return self._return_code

    def kill(self):
        self.killed = True


class VerificationManifestTests(unittest.TestCase):
    def test_default_set_is_offline_and_skip_heavy_has_lightweight_work(self):
        commands = manifest_tool.default_commands("python-for-test")
        flattened = " ".join(
            argument.lower() for command in commands for argument in command.argv
        )

        self.assertIn("syntax-check", [command.name for command in commands])
        self.assertNotIn("l2_live", flattened)
        self.assertNotIn("l2-live", flattened)
        self.assertNotIn("experiments", flattened)
        self.assertNotIn("http://", flattened)
        self.assertNotIn("https://", flattened)
        self.assertNotIn("compose build", flattened)
        self.assertTrue(any(command.heavy for command in commands))
        self.assertTrue(any(not command.heavy for command in commands))

    def test_sanitized_environment_never_inherits_secrets(self):
        source = {
            "PATH": "safe-search-path",
            "SYSTEMROOT": "safe-system-root",
            "DEEPSEEK_API_KEY": "do-not-copy-this-secret",
            "AWS_SECRET_ACCESS_KEY": "also-secret",
            "TOKEN": "secret-token",
        }

        child = manifest_tool._sanitized_environment(source)

        self.assertEqual(child["PATH"], "safe-search-path")
        self.assertEqual(child["SYSTEMROOT"], "safe-system-root")
        self.assertNotIn("DEEPSEEK_API_KEY", child)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", child)
        self.assertNotIn("TOKEN", child)
        self.assertNotIn("do-not-copy-this-secret", json.dumps(child))

    def test_git_probe_finds_parent_repo_and_handles_sandbox_ownership(self):
        head = "A" * 40
        probe_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"{head}\n"
        )
        status_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b" M tracked.py\x00"
        )
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            manifest_tool.subprocess,
            "run",
            side_effect=[probe_result, status_result],
        ) as run:
            repository_root = Path(temporary).resolve() / "repository"
            (repository_root / ".git").mkdir(parents=True)
            starter_root = repository_root / "starter_kit"
            starter_root.mkdir()
            result = manifest_tool._collect_git_state(
                starter_root, {"PATH": "safe"}
            )

        self.assertEqual(result["head"], head.lower())
        self.assertTrue(result["dirty"])
        first_argv = run.call_args_list[0].args[0]
        second_argv = run.call_args_list[1].args[0]
        safe_argument = f"safe.directory={repository_root.as_posix()}"
        self.assertIn(safe_argument, first_argv)
        self.assertIn(safe_argument, second_argv)
        self.assertEqual(run.call_args_list[0].kwargs["cwd"], str(repository_root))
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], str(repository_root))
        self.assertNotIn("config", first_argv)

    def test_execute_command_combines_output_and_hashes_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log_path = root / "command-current.txt"

            def fake_popen(*_args, **kwargs):
                self.assertIs(kwargs["stderr"], subprocess.STDOUT)
                self.assertFalse(kwargs["shell"])
                self.assertNotIn("SECRET_TOKEN", kwargs["env"])
                return _FakeProcess(kwargs["stdout"], payload=b"stdout\nstderr\n")

            with mock.patch.object(manifest_tool.subprocess, "Popen", fake_popen):
                result = manifest_tool._execute_command(
                    manifest_tool.CommandSpec("demo", ("fake", "argument")),
                    root,
                    log_path,
                    {"PATH": "safe"},
                    3.0,
                )

            payload = b"stdout\nstderr\n"
            self.assertEqual(log_path.read_bytes(), payload)
            self.assertEqual(result["return_code"], 0)
            self.assertEqual(result["output_bytes"], len(payload))
            self.assertEqual(
                result["output_sha256"], hashlib.sha256(payload).hexdigest()
            )

    def test_failure_still_writes_manifest_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "proof"
            secret_value = "must-never-appear-7f70"

            def fake_execute(command, _root, log_path, environment, _timeout):
                self.assertNotIn("LOOMQ_SECRET", environment)
                payload = b"intentional failure\n"
                log_path.write_bytes(payload)
                return {
                    "name": command.name,
                    "argv": list(command.argv),
                    "started_at_utc": "2026-08-07T00:00:00Z",
                    "duration_seconds": 0.01,
                    "return_code": 9,
                    "timed_out": False,
                    "output_file": log_path.name,
                    "output_sha256": hashlib.sha256(payload).hexdigest(),
                    "output_bytes": len(payload),
                }

            git_state = {
                "available": True,
                "head": "a" * 40,
                "dirty": True,
            }
            environment = {
                "python": {"implementation": "CPython", "version": "3.10.0"},
                "node": {"available": False, "version": None},
                "docker": {"available": False, "version": None},
                "os": {"system": "TestOS", "release": "1", "version": "1.0"},
                "architecture": {"machine": "test-arch", "pointer_bits": 64},
            }
            with mock.patch.dict(
                os.environ, {"LOOMQ_SECRET": secret_value}, clear=True
            ), mock.patch.object(
                manifest_tool, "_collect_git_state", return_value=git_state
            ), mock.patch.object(
                manifest_tool, "_collect_environment", return_value=environment
            ), mock.patch.object(
                manifest_tool, "_execute_command", side_effect=fake_execute
            ):
                return_code = manifest_tool.main(
                    [
                        "--root",
                        str(root),
                        "--output-dir",
                        str(output),
                        "--command",
                        'failing::["fake-program","--offline"]',
                    ]
                )

            manifest_path = output / manifest_tool.MANIFEST_NAME
            manifest_text = manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)
            self.assertEqual(return_code, 1)
            self.assertFalse(manifest["success"])
            self.assertEqual(manifest["repository"]["head"], "a" * 40)
            self.assertTrue(manifest["repository"]["dirty"])
            self.assertTrue(manifest["repository"]["captured_before_commands"])
            self.assertTrue(
                manifest["repository"]["captured_before_evidence_write"]
            )
            self.assertEqual(
                manifest["repository"]["head_role"], "source_snapshot"
            )
            self.assertTrue(
                manifest["execution_policy"]["evidence_outputs_mutate_worktree"]
            )
            self.assertEqual(
                manifest["execution_policy"]["tracked_evidence_finalization"],
                "two_phase_evidence_only_commit",
            )
            self.assertEqual(manifest["commands"][0]["return_code"], 9)
            self.assertRegex(
                manifest["commands"][0]["output_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertNotIn(secret_value, manifest_text)
            self.assertNotIn("LOOMQ_SECRET", manifest_text)

    def test_extra_artifact_hash_and_missing_artifact_affect_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "result.json"
            artifact.write_bytes(b'{"passed":true}\n')

            records = manifest_tool._hash_artifacts(
                ["result.json", "missing.json"], root
            )

            self.assertEqual(records[0]["status"], "ok")
            self.assertEqual(
                records[0]["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest()
            )
            self.assertEqual(records[1]["status"], "missing")
            self.assertIsNone(records[1]["sha256"])

    def test_custom_command_parsing_and_unique_safe_log_names(self):
        first = manifest_tool._parse_custom_command(
            'smoke test::["python","-c","print(1)"]', 1
        )
        second = manifest_tool._parse_custom_command("smoke test::python -V", 2)

        self.assertEqual(first.argv, ("python", "-c", "print(1)"))
        self.assertEqual(second.argv, ("python", "-V"))
        self.assertEqual(
            manifest_tool._allocate_log_names([first, second]),
            ["smoke-test-current.txt", "smoke-test-2-current.txt"],
        )

    def test_help_documents_required_controls(self):
        help_text = manifest_tool.build_parser().format_help()

        self.assertIn("--output-dir", help_text)
        self.assertIn("--skip-heavy", help_text)
        self.assertIn("--artifact", help_text)
        self.assertIn("offline", help_text.lower())
        self.assertIn("two-phase", help_text.lower())
        self.assertIn("source snapshot", help_text.lower())


if __name__ == "__main__":
    unittest.main()
