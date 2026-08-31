"""Real-socket integration checks for the local workbench HTTP surface."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict

from loomq.ui.server import create_server


class WorkbenchServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.server = create_server("127.0.0.1", 0, self.temporary.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = "http://%s:%d" % (host, port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def get(self, path: str) -> tuple[int, Dict[str, str], bytes]:
        request = urllib.request.Request(self.base_url + path, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + "/api/run",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read())

    def test_static_shell_health_and_route_allowlist(self) -> None:
        status, headers, html = self.get("/")
        self.assertEqual(status, 200)
        decoded = html.decode("utf-8")
        self.assertIn("LoomQ Pegasus", decoded)
        self.assertIn("LoomQ local reference", decoded)
        self.assertNotIn("https://", decoded)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

        for asset in ("/styles.css", "/app.js", "/mark.svg"):
            self.assertEqual(self.get(asset)[0], 200)
        status, _, payload = self.get("/api/health")
        health = json.loads(payload)
        self.assertEqual(status, 200)
        self.assertEqual(health["binding"], "loopback")
        self.assertEqual(health["components"]["reference_runtime"], "ready")
        self.assertEqual(self.get("/../README.md")[0], 404)

    def test_local_concept_guide_and_visualization_contract(self) -> None:
        status, _, html = self.get("/")
        self.assertEqual(status, 200)
        decoded = html.decode("utf-8")
        self.assertIn('id="circuit-diagram"', decoded)
        self.assertIn('id="top-states"', decoded)
        self.assertIn('id="concept-panel"', decoded)
        self.assertIn('href="/guide/QUANTUM_101.md"', decoded)
        self.assertIn("仅实际观测 counts", decoded)

        guide_status, guide_headers, guide = self.get("/guide/QUANTUM_101.md")
        self.assertEqual(guide_status, 200)
        self.assertIn("text/markdown", guide_headers["Content-Type"])
        self.assertIn("qubit", guide.decode("utf-8").lower())
        self.assertEqual(self.get("/guide/../README.md")[0], 404)

        app_status, _, javascript = self.get("/app.js")
        self.assertEqual(app_status, 200)
        script = javascript.decode("utf-8")
        self.assertIn("function renderCircuit", script)
        self.assertIn("function renderTopStates", script)
        self.assertIn("normalized?.operations", script)

    def test_bell_run_produces_real_counts_all_dialects_and_evidence(self) -> None:
        _, _, example_payload = self.get("/api/examples")
        example = json.loads(example_payload)["examples"][0]
        example["shots"] = 128
        result = self.post(example)
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized"]["qubit_count"], 2)
        self.assertEqual(result["normalized"]["operation_count"], 4)
        self.assertEqual(sum(result["result"]["counts"].values()), 128)
        self.assertEqual(result["result"]["bit_order"], "little")
        self.assertEqual(
            result["result"]["meta"]["execution_engine"],
            "loomq_reference_statevector",
        )
        self.assertFalse(result["result"]["meta"]["native_sdk_used"])
        self.assertEqual(set(result["ir"]), {"spinq", "originq", "braket"})
        self.assertIn("OPENQASM 2.0", result["ir"]["spinq"])
        self.assertIn("QINIT 2", result["ir"]["originq"])
        self.assertIn("OPENQASM 3.0", result["ir"]["braket"])
        self.assertEqual(result["verification"]["status"], "passed")

        names = {item["name"] for item in result["manifest"]["artifacts"]}
        required = {
            "request.json",
            "intent.json",
            "normalized.json",
            "ir/index.json",
            "ir/spinq.qasm",
            "ir/originq.originir",
            "ir/braket.qasm",
            "result.json",
            "verification.json",
            "manifest.json",
        }
        self.assertTrue(required.issubset(names))
        run_path = self.server.service.workspace.path / result["run_id"]
        self.assertEqual(run_path.parent, self.server.service.workspace.path)
        self.assertFalse(list(run_path.rglob("*.tmp")))

        query = urllib.parse.urlencode(
            {"run_id": result["run_id"], "name": "result.json"}
        )
        artifact_status, _, artifact = self.get("/api/artifact?" + query)
        self.assertEqual(artifact_status, 200)
        self.assertEqual(json.loads(artifact)["shots"], 128)

    def test_structured_qasm_failure_is_located_and_sealed(self) -> None:
        result = self.post(
            {
                "task": "simulate",
                "target": "spinq",
                "shots": 32,
                "prompt": "broken input",
                "qasm": "OPENQASM 2.0;\nqreg q[2]\ncreg c[2];\nh q[0];",
            }
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "QASM_ADMISSION_ERROR")
        self.assertIsInstance(result["error"]["line"], int)
        self.assertIsInstance(result["error"]["column"], int)
        self.assertTrue(result["error"]["suggestion"])
        self.assertEqual(result["manifest"]["status"], "failed")
        names = {item["name"] for item in result["manifest"]["artifacts"]}
        self.assertTrue(
            {"request.json", "intent.json", "normalized.json", "ir/index.json", "result.json", "verification.json", "manifest.json"}.issubset(names)
        )

    def test_conservative_repair_and_hybrid_compile(self) -> None:
        repaired = self.post(
            {
                "task": "repair",
                "target": "originq",
                "shots": 16,
                "prompt": "add only missing syntax",
                "qasm": "qreg q[1]\ncreg c[1]\nh q[0]\nmeasure q -> c",
            }
        )
        self.assertTrue(repaired["ok"])
        self.assertIn("OPENQASM 2.0;", repaired["source"])
        self.assertIn("measure q -> c;", repaired["source"])
        self.assertEqual(repaired["result"]["status"], "not_run")

        _, _, example_payload = self.get("/api/examples")
        hybrid = json.loads(example_payload)["examples"][2]
        compiled = self.post(hybrid)
        self.assertTrue(compiled["ok"])
        self.assertEqual(set(compiled["ir"]), {"quantum", "tinyriscv"})
        self.assertIn("bne", compiled["ir"]["tinyriscv"])
        self.assertEqual(compiled["verification"]["status"], "passed")

    def test_secrets_and_artifact_traversal_are_not_exposed(self) -> None:
        secret = "fixture-secret-abcdefghijklmnopqrstuvwxyz"
        result = self.post(
            {
                "task": "transpile",
                "target": "spinq",
                "shots": 8,
                "prompt": "Authorization: Bearer abcdefghijklmnop",
                "qasm": "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;",
                "api_key": secret,
            }
        )
        self.assertTrue(result["ok"])
        request_file = (
            self.server.service.workspace.path / result["run_id"] / "request.json"
        ).read_text(encoding="utf-8")
        self.assertNotIn(secret, request_file)
        self.assertNotIn("abcdefghijklmnop", request_file)
        self.assertIn("[REDACTED]", request_file)

        query = urllib.parse.urlencode(
            {"run_id": result["run_id"], "name": "../request.json"}
        )
        status, _, _ = self.get("/api/artifact?" + query)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
