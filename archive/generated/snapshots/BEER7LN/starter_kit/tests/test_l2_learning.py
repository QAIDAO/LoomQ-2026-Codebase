"""Curriculum, L1 learning bridge, and formal L2 HTTP API tests."""

from __future__ import annotations

import http.client
import json
import math
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import l2_app  # noqa: E402
import learning  # noqa: E402
from loomq.qasm import MeasureOperation, parse_openqasm2  # noqa: E402


H_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
"""


class CurriculumTests(unittest.TestCase):
    def test_six_lessons_are_ordered_and_have_valid_prerequisites(self) -> None:
        lessons = learning.load_curriculum()["lessons"]
        self.assertEqual([lesson["order"] for lesson in lessons], list(range(1, 7)))
        self.assertEqual(len({lesson["id"] for lesson in lessons}), 6)
        seen: set[str] = set()
        for lesson in lessons:
            self.assertTrue(set(lesson["prerequisites"]).issubset(seen))
            self.assertGreaterEqual(
                len(lesson["experiments"]),
                2,
                f"{lesson['id']} must offer a real learner-controlled comparison",
            )
            self.assertGreaterEqual(
                len({experiment["qasm"] for experiment in lesson["experiments"]}),
                2,
            )
            seen.add(lesson["id"])

    def test_catalog_hides_qasm_and_experiments_use_measured_l1_programs(self) -> None:
        self.assertNotIn("qasm", str(learning.lesson_catalog()))
        for lesson in learning.load_curriculum()["lessons"]:
            for experiment in lesson["experiments"]:
                program = parse_openqasm2(experiment["qasm"])
                self.assertTrue(
                    any(isinstance(operation, MeasureOperation) for operation in program.operations)
                )

    def test_every_lesson_has_zero_background_story_and_result_explanations(self) -> None:
        for lesson in learning.load_curriculum()["lessons"]:
            self.assertTrue(lesson["hook"].strip())
            self.assertTrue(lesson["plain_goal"].strip())
            self.assertIn(
                lesson["animation"],
                {"paths", "shots", "pair", "phase", "chain", "noise"},
            )
            for experiment in lesson["experiments"]:
                self.assertTrue(experiment["plain_title"].strip())
                self.assertTrue(experiment["plain_prompt"].strip())
                self.assertTrue(experiment["result_hint"].strip())

    def test_h_phase_bell_and_ghz_semantics_come_from_l1(self) -> None:
        cases = [
            ("bit-vs-qubit", "hadamard-measure", {"0": 0.5, "1": 0.5}),
            ("phase-interference", "phase-flip", {"0": 0.0, "1": 1.0}),
        ]
        for lesson_id, experiment_id, expected in cases:
            payload = learning.simulate_lesson_experiment(
                lesson_id, experiment_id, 128, nonce=lesson_id
            )
            probabilities = {
                item["basis"]: item["probability"] for item in payload["statevector"]
            }
            for basis, value in expected.items():
                self.assertTrue(math.isclose(probabilities[basis], value, abs_tol=1e-12))
            self.assertEqual(sum(payload["result"]["counts"].values()), 128)

        for lesson_id, experiment_id, support in [
            ("bell-correlation", "bell-state", {"00", "11"}),
            ("ghz-three", "ghz-3", {"000", "111"}),
        ]:
            payload = learning.simulate_lesson_experiment(
                lesson_id, experiment_id, 512, nonce=lesson_id
            )
            observed = {
                item["basis"]
                for item in payload["statevector"]
                if item["probability"] > 1e-12
            }
            self.assertEqual(observed, support)
            self.assertEqual(set(payload["result"]["counts"]), support)


class StepDiagramSourceTests(unittest.TestCase):
    def test_all_experiments_have_explicit_step_diagrams(self) -> None:
        source = (STARTER_KIT / "motion" / "remotion" / "src" / "LoomQMotion.jsx").read_text(
            encoding="utf-8"
        )
        for lesson in learning.load_curriculum()["lessons"]:
            for experiment in lesson["experiments"]:
                self.assertIn(f"'{experiment['id']}'", source)
        self.assertIn("stepIndex", source)
        self.assertNotIn("useCurrentFrame", source)
        self.assertNotIn("Math.random", source)

    def test_step_diagrams_do_not_expose_internal_video_hud(self) -> None:
        source = (STARTER_KIT / "motion" / "remotion" / "src" / "LoomQMotion.jsx").read_text(
            encoding="utf-8"
        )
        for forbidden in ["VISUAL LAB", "poster-cue", "lqm-scan", "frame / 2.4"]:
            self.assertNotIn(forbidden, source)
        self.assertIn("步骤 {step + 1}", source)

    def test_hardware_counts_are_never_replaced_by_placeholder_results(self) -> None:
        source = (STARTER_KIT / "motion" / "remotion" / "src" / "LoomQMotion.jsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("真机证据未载入", source)
        self.assertNotIn("没有 GHZ 真机 result.json", source)
        self.assertNotIn("lqm-evidence-boundary", source)
        self.assertNotIn("{'00':509", source)
        self.assertNotIn("{'00':360", source)


class FormalL2HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = l2_app.create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method: str, path: str, payload: object | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        decoded = json.loads(raw) if content_type.startswith("application/json") else raw
        return response.status, decoded

    def test_health_catalog_and_simulation_endpoints(self) -> None:
        status, health = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["learning_engine"], "loomq.l1.statevector")

        status, catalog = self.request("GET", "/api/lessons")
        self.assertEqual(status, 200)
        self.assertEqual(len(catalog["lessons"]), 6)
        self.assertNotIn("qasm", str(catalog))

        status, environments = self.request("GET", "/api/environments")
        self.assertEqual(status, 200)
        self.assertIn("local_reference", [item["id"] for item in environments["environments"]])

        status, validation = self.request(
            "POST",
            "/api/validate-qasm",
            {
                "qasm": (
                    'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
                    "qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];"
                )
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(validation["validation"]["qubits"], 1)

        status, evidence = self.request("GET", "/api/evidence/hardware/bell")
        self.assertEqual(status, 200)
        self.assertEqual(
            {item["platform"] for item in evidence["runs"]},
            {"Origin Quantum Cloud", "SpinQ Cloud"},
        )
        for run in evidence["runs"]:
            self.assertEqual(sum(run["counts"].values()), run["shots"])
            self.assertTrue(run["job_id"])
        self.assertNotIn("website", str(evidence))

        status, motion_bundle = self.request(
            "GET", "/motion/loomq-motion.iife.js"
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(motion_bundle), 1_000)

        status, result = self.request(
            "POST",
            "/api/simulate",
            {
                "lesson_id": "bell-correlation",
                "experiment_id": "bell-state",
                "shots": 64,
                "nonce": "formal-http",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["engine"], "loomq.l1.statevector")
        self.assertEqual(sum(result["result"]["counts"].values()), 64)

    def test_chat_mode_reaches_shared_agent_and_returns_l1_validation(self) -> None:
        agent = mock.Mock(return_value=f"Ready.\n```qasm\n{H_QASM}```")
        with mock.patch.object(l2_app, "agent_chat", agent):
            status, payload = self.request(
                "POST",
                "/api/chat",
                {"mode": "generate", "prompt": "做一枚量子硬币"},
            )
        self.assertEqual(status, 200)
        self.assertIn("Task mode: generate", agent.call_args.args[0])
        self.assertEqual(sum(payload["simulation"]["counts"].values()), 1024)

    def test_invalid_mode_shots_and_json_are_recoverable(self) -> None:
        status, payload = self.request(
            "POST", "/api/chat", {"mode": "unknown", "prompt": "hello"}
        )
        self.assertEqual(status, 400)
        self.assertIn("mode", payload["error"])

        status, payload = self.request(
            "POST",
            "/api/simulate",
            {
                "lesson_id": "bit-vs-qubit",
                "experiment_id": "hadamard-measure",
                "shots": 0,
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("shots", payload["error"])

        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(
            "POST",
            "/api/simulate",
            body=b"{bad",
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 400)
        self.assertIn("JSON", payload["error"])


if __name__ == "__main__":
    unittest.main()
