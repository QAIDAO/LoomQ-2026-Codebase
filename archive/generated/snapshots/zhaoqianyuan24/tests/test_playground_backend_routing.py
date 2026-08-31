import os
import unittest
from unittest.mock import patch

from starter_kit import adapter
import starter_kit.product_service as product_service
from starter_kit.product_service import (
    get_backend_catalog,
    get_local_backend_catalog,
    parse_backend_recommendation,
)


class PlaygroundBackendRoutingTests(unittest.TestCase):
    def test_catalog_contains_remote_ids_but_local_preflight_stays_local(self):
        catalog_ids = {backend["id"] for backend in get_backend_catalog()}
        local_ids = {backend["id"] for backend in get_local_backend_catalog()}
        self.assertIn("originq_wukong", catalog_ids)
        self.assertIn("spinq_cloud_qpu", catalog_ids)
        self.assertIn("braket_cloud", catalog_ids)
        self.assertNotIn("originq_wukong", local_ids)

    def test_l2_remote_recommendation_is_exposed_to_playground(self):
        response = parse_backend_recommendation(
            "我需要在本源真机上运行这个实验。",
            "Recommended backend: originq_wukong\nReason: 72 比特悟空真机。",
        )
        self.assertEqual(
            response["backend_recommendation"]["backend_id"],
            "originq_wukong",
        )
        selected = next(
            backend
            for backend in response["backends"]
            if backend["id"] == "originq_wukong"
        )
        self.assertEqual(selected["run_mode"], "remote")

    def test_adapter_run_routes_canonical_local_id_to_l1(self):
        expected = {"backend": "braket_local_simulator"}
        with patch.object(adapter, "run_l1", return_value=expected) as run_l1:
            self.assertIs(adapter.run("qasm", "braket_local_simulator", 1000), expected)
        run_l1.assert_called_once_with("qasm", "braket", 1000)

    def test_adapter_run_routes_canonical_remote_id_to_provider_layer(self):
        expected = {"backend": "originq_wukong"}
        with patch.object(adapter, "run_hardware", return_value=expected) as run_hardware:
            self.assertIs(adapter.run("qasm", "originq_wukong", 1000), expected)
        run_hardware.assert_called_once_with("qasm", "originq_wukong", 1000)

    def test_product_run_passes_selected_backend_id_to_one_adapter_path(self):
        backend = {
            "id": "originq_wukong",
            "name": "OriginQ Wukong",
            "run_mode": "remote",
            "runtime_available": True,
            "runtime_message": "ready",
        }
        captured = {}

        handler = object.__new__(product_service.ProductRequestHandler)
        handler._send_json = lambda status, payload: captured.update(
            {"status": status, "payload": payload}
        )
        expected = {
            "backend": "originq_wukong",
            "job_id": "origin-task",
            "shots": 1000,
            "counts": {"00": 500, "11": 500},
        }
        with patch.object(product_service, "get_backend_catalog", return_value=[backend]), patch.object(
            product_service.adapter, "run", return_value=expected
        ) as run:
            handler._handle_run(
                {
                    "qasm": "OPENQASM 2.0;",
                    "shots": 1000,
                    "backend_id": "originq_wukong",
                }
            )

        run.assert_called_once_with("OPENQASM 2.0;", "originq_wukong", 1000)
        self.assertEqual(captured["status"], product_service.HTTPStatus.OK)
        self.assertEqual(captured["payload"]["result"]["job_id"], "origin-task")

    def test_unready_remote_backend_falls_back_to_ready_local_simulator(self):
        remote = {
            "id": "originq_wukong",
            "platform": "originq",
            "name": "OriginQ Wukong",
            "run_mode": "remote",
            "runtime_available": False,
            "runtime_message": "缺少真机 Token",
        }
        local = {
            "id": "braket_local_simulator",
            "platform": "braket",
            "name": "AWS Braket LocalSimulator",
            "run_mode": "local",
            "runtime_available": True,
            "runtime_message": "ready",
        }
        captured = {}
        handler = object.__new__(product_service.ProductRequestHandler)
        handler._send_json = lambda status, payload: captured.update(
            {"status": status, "payload": payload}
        )
        expected = {
            "backend": "braket_local_simulator",
            "job_id": "local-task",
            "shots": 1000,
            "counts": {"00": 500, "11": 500},
        }
        with patch.object(product_service, "get_backend_catalog", return_value=[remote, local]), patch.object(
            product_service.adapter, "run", return_value=expected
        ) as run:
            handler._handle_run(
                {
                    "qasm": "OPENQASM 2.0;",
                    "shots": 1000,
                    "backend_id": "originq_wukong",
                }
            )

        run.assert_called_once_with("OPENQASM 2.0;", "braket_local_simulator", 1000)
        result = captured["payload"]["result"]
        self.assertEqual(captured["status"], product_service.HTTPStatus.OK)
        self.assertTrue(result["fallback"])
        self.assertEqual(result["requested_backend_id"], "originq_wukong")
        self.assertEqual(result["backend_id"], "braket_local_simulator")

    def test_remote_fallback_defaults_to_local_and_supports_strict_mode(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(product_service._remote_fallback_enabled())
        with patch.dict(os.environ, {"LOOMQ_REMOTE_FALLBACK": "error"}, clear=False):
            self.assertFalse(product_service._remote_fallback_enabled())


if __name__ == "__main__":
    unittest.main()
