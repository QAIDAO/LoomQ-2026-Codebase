"""Tests for local credential configuration and asynchronous hardware jobs."""

from __future__ import annotations

from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import l2_app  # noqa: E402
from loomq import web_hardware  # noqa: E402


QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
"""
PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    + ("A" * 80)
    + "\n-----END PRIVATE KEY-----\n"
)


class InlineThread:
    def __init__(self, *, target, args, **_kwargs):
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


def successful_runner(_qasm, shots, _program, _credentials):
    return {
        "platform": "Mock QPU",
        "backend": "mock-backend",
        "job_id": "provider-job-123",
        "timestamp": "2026-08-17T00:00:00Z",
        "shots": shots,
        "counts": {"0": shots},
        "bit_order": "little",
    }


class WebHardwareTests(unittest.TestCase):
    def _store(self, root: Path, environment=None):
        env_file = root / ".env.hardware.local"
        return web_hardware.HardwareProfiles(
            credentials_dir=root / "local_docs" / "credentials",
            env_file=env_file,
            environ={} if environment is None else environment,
        )

    def _origin_request(self, label="Origin A", token="origin-secret-a"):
        return {
            "label": label,
            "provider": "originq",
            "credentials": {"token": token, "backend": "WK_C180_2"},
        }

    def _job_request(self, profile_id, environment_id="originq_wukong"):
        return {
            "profile_id": profile_id,
            "environment_id": environment_id,
            "qasm": QASM,
            "shots": 32,
            "confirm": True,
            "confirmation_token": (
                web_hardware.ORIGINQ_CONFIRMATION
                if environment_id == "originq_wukong"
                else web_hardware.SPINQ_CONFIRMATION
            ),
        }

    def test_system_profile_is_not_exposed_to_web_users(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_file = root / ".env.hardware.local"
            original = (
                "LOOMQ_ORIGINQ_API_TOKEN=system-secret\n"
                "LOOMQ_ORIGINQ_BACKEND=WK_C180_2\n"
            )
            env_file.write_text(original, encoding="utf-8")
            store = self._store(root)
            profiles = store.list()["profiles"]
            self.assertEqual(profiles, [])
            with self.assertRaises(web_hardware.ProfileNotFoundError):
                store.resolve("system-originq-wukong")
            self.assertEqual(env_file.read_text(encoding="utf-8"), original)

    def test_multiple_user_profiles_are_session_only_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            first = store.create(self._origin_request())
            second = store.create(self._origin_request("Origin B", "origin-secret-b"))
            listed = store.list()["profiles"]
            self.assertEqual({first["id"], second["id"]}, {p["id"] for p in listed})
            serialized = json.dumps(listed)
            self.assertNotIn("origin-secret-a", serialized)
            self.assertNotIn("origin-secret-b", serialized)
            self.assertFalse(store.index_file.exists())
            self.assertFalse(store.credentials_dir.exists())
            restarted_store = self._store(root)
            self.assertEqual(restarted_store.list()["profiles"], [])
            with self.assertRaises(web_hardware.ProfileNotFoundError):
                restarted_store.resolve(first["id"])
            with self.assertRaisesRegex(ValueError, "label"):
                store.create(
                    {
                        "provider": "originq",
                        "credentials": {"token": "secret-token", "backend": "WK"},
                    }
                )
            with self.assertRaisesRegex(ValueError, "unique"):
                store.create(self._origin_request("origin a", "other-secret"))

    def test_update_delete_and_partial_credential_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            created = store.create(self._origin_request())
            updated = store.update(
                created["id"],
                {"label": "Renamed", "credentials": {"backend": "WK_C180_3"}},
            )
            self.assertEqual(updated["label"], "Renamed")
            profile, credentials = store.resolve(created["id"])
            self.assertEqual(profile["metadata"]["backend"], "WK_C180_3")
            self.assertEqual(credentials["token"], "origin-secret-a")
            store.delete(created["id"])
            with self.assertRaises(web_hardware.ProfileNotFoundError):
                store.resolve(created["id"])

    def test_submission_requires_both_confirmation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            profile = store.create(self._origin_request())
            jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                thread_factory=InlineThread,
                profiles=store,
            )
            base = self._job_request(profile["id"])
            for key, replacement in (
                ("confirm", False),
                ("confirmation_token", "wrong-token"),
            ):
                request = dict(base)
                request[key] = replacement
                with self.assertRaisesRegex(ValueError, "confirmation"):
                    jobs.submit(request)

    def test_submission_rejects_profile_environment_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            profile = store.create(self._origin_request())
            jobs = web_hardware.HardwareJobs(thread_factory=InlineThread, profiles=store)
            with self.assertRaisesRegex(ValueError, "does not match"):
                jobs.submit(self._job_request(profile["id"], "spinq_cloud_qpu"))

    def test_jobs_use_independent_credential_snapshots(self) -> None:
        captured = []

        def runner(_qasm, shots, _program, credentials):
            captured.append(dict(credentials))
            return successful_runner(_qasm, shots, _program, credentials)

        class DeferredThread(InlineThread):
            pending = []

            def start(self):
                self.pending.append((self._target, self._args))

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            first = store.create(self._origin_request("A", "secret-token-a"))
            second = store.create(self._origin_request("B", "secret-token-b"))
            jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": runner},
                thread_factory=DeferredThread,
                profiles=store,
            )
            submitted_a = jobs.submit(self._job_request(first["id"]))
            submitted_b = jobs.submit(self._job_request(second["id"]))
            store.update(first["id"], {"credentials": {"token": "new-secret-token"}})
            store.delete(second["id"])
            for target, args in DeferredThread.pending:
                target(*args)
            self.assertEqual(
                {item["token"] for item in captured},
                {"secret-token-a", "secret-token-b"},
            )
            polled = jobs.get(submitted_a["task_id"])
            self.assertEqual(polled["status"], "completed")
            self.assertEqual(polled["profile_label"], "A")
            self.assertNotIn("secret-token", json.dumps(polled))
            self.assertEqual(jobs.get(submitted_b["task_id"])["status"], "completed")

    def test_runner_exception_is_not_exposed_in_failed_status(self) -> None:
        secret = "provider-secret-value"

        def failing_runner(_qasm, _shots, _program, _credentials):
            raise RuntimeError(f"SDK rejected {secret}")

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            profile = store.create(self._origin_request())
            jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": failing_runner},
                thread_factory=InlineThread,
                profiles=store,
            )
            submitted = jobs.submit(self._job_request(profile["id"]))
            polled = jobs.get(submitted["task_id"])
            self.assertEqual(polled["status"], "failed")
            self.assertNotIn(secret, json.dumps(polled))
            self.assertNotIn("SDK rejected", json.dumps(polled))

    def test_safe_hardware_failure_is_exposed_with_code(self) -> None:
        def safe_failure(_qasm, _shots, _program, _credentials):
            raise web_hardware.HardwareExecutionError(
                "provider_offline", "所选真机当前离线。"
            )

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            profile = store.create(self._origin_request())
            jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": safe_failure},
                thread_factory=InlineThread,
                profiles=store,
            )
            submitted = jobs.submit(self._job_request(profile["id"]))
            polled = jobs.get(submitted["task_id"])
            self.assertEqual(polled["status"], "failed")
            self.assertEqual(polled["error_code"], "provider_offline")
            self.assertEqual(polled["error"], "所选真机当前离线。")

    def test_job_history_persists_code_result_and_marks_interrupted(self) -> None:
        class DeferredThread(InlineThread):
            def start(self):
                pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            profile = store.create(self._origin_request())
            completed_jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                thread_factory=InlineThread,
                profiles=store,
            )
            submitted = completed_jobs.submit(self._job_request(profile["id"]))
            detail = completed_jobs.get(submitted["task_id"])
            self.assertEqual(detail["status"], "completed")
            self.assertEqual(detail["qasm"], QASM.strip())
            self.assertEqual(detail["result"]["counts"], {"0": 32})
            summary = completed_jobs.list()["jobs"][0]
            self.assertNotIn("qasm", summary)
            self.assertNotIn("result", summary)
            self.assertTrue(summary["has_qasm"])
            self.assertTrue(summary["has_result"])

            reloaded = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                profiles=store,
            )
            self.assertEqual(
                reloaded.get(submitted["task_id"])["result"]["job_id"],
                "provider-job-123",
            )

            pending_jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                thread_factory=DeferredThread,
                profiles=store,
            )
            pending = pending_jobs.submit(self._job_request(profile["id"]))
            after_restart = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                profiles=store,
            )
            interrupted = after_restart.get(pending["task_id"])
            self.assertEqual(interrupted["status"], "interrupted")
            self.assertTrue(after_restart.database_file.is_file())
            self.assertNotIn(
                b"origin-secret-a",
                after_restart.database_file.read_bytes(),
            )

    def test_sqlite_history_is_owner_scoped_and_migrates_legacy_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            profile = store.create(self._origin_request())
            database_file = root / "local_docs" / "loomq.sqlite3"
            alice = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                thread_factory=InlineThread,
                profiles=store,
                database_file=database_file,
                owner_id="alice",
            )
            submitted = alice.submit(self._job_request(profile["id"]))
            bob = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                profiles=store,
                database_file=database_file,
                owner_id="bob",
            )
            self.assertEqual(bob.list()["jobs"], [])
            self.assertIsNone(bob.get(submitted["task_id"]))

            legacy_id = "1" * 32
            legacy_dir = root / "local_docs" / "hardware_jobs"
            legacy_dir.mkdir()
            legacy = {
                "task_id": legacy_id,
                "environment_id": "originq_wukong",
                "profile_id": profile["id"],
                "profile_label": "Legacy",
                "provider": "originq",
                "status": "completed",
                "stage": "completed",
                "stage_message": "完成",
                "created_at": "2026-08-18T00:00:00Z",
                "updated_at": "2026-08-18T00:00:01Z",
                "completed_at": "2026-08-18T00:00:01Z",
                "shots": 32,
                "qubits": 1,
                "qasm": QASM.strip(),
                "result": successful_runner(QASM, 32, None, {}),
            }
            (legacy_dir / f"{legacy_id}.json").write_text(
                json.dumps(legacy), encoding="utf-8"
            )
            migrated = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                profiles=store,
                database_file=database_file,
                owner_id="alice",
            )
            self.assertEqual(migrated.get(legacy_id)["profile_label"], "Legacy")
            self.assertFalse((legacy_dir / f"{legacy_id}.json").exists())

    def test_http_profile_crud_and_job_polling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            jobs = web_hardware.HardwareJobs(
                runners={"originq_wukong": successful_runner},
                thread_factory=InlineThread,
                profiles=store,
            )
            patches = (
                mock.patch.object(l2_app, "PROFILES", store),
                mock.patch.object(l2_app, "JOBS", jobs),
            )
            for patcher in patches:
                patcher.start()
            server = l2_app.create_server("127.0.0.1", 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port)
                connection.request(
                    "POST",
                    "/api/hardware/profiles",
                    body=json.dumps(self._origin_request()),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                created = json.loads(response.read())
                self.assertEqual(response.status, 201)
                self.assertNotIn("origin-secret", json.dumps(created))

                connection.request("GET", "/api/hardware/profiles")
                response = connection.getresponse()
                listed = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(len(listed["profiles"]), 1)

                connection.request(
                    "PUT",
                    f"/api/hardware/profiles/{created['id']}",
                    body=json.dumps({"label": "HTTP Renamed"}),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 404)

                connection.request(
                    "POST",
                    "/api/hardware/jobs",
                    body=json.dumps(self._job_request(created["id"])),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                submitted = json.loads(response.read())
                self.assertEqual(response.status, 202)

                connection.request(
                    "GET", f"/api/hardware/jobs/{submitted['task_id']}"
                )
                response = connection.getresponse()
                polled = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertEqual(polled["status"], "completed")
                self.assertEqual(polled["profile_id"], created["id"])

                connection.request("GET", "/api/hardware/jobs")
                response = connection.getresponse()
                history = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(history["jobs"][0]["task_id"], submitted["task_id"])
                self.assertNotIn("qasm", history["jobs"][0])
                self.assertTrue(history["jobs"][0]["has_result"])

                connection.request(
                    "DELETE", f"/api/hardware/profiles/{created['id']}"
                )
                response = connection.getresponse()
                deleted = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(deleted["deleted"])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)
                for patcher in reversed(patches):
                    patcher.stop()


if __name__ == "__main__":
    unittest.main()
