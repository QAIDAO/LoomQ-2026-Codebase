import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

try:
    from starter_kit.loomq_app import server as app_server
except ModuleNotFoundError:
    from loomq_app import server as app_server


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app_server.LoomQHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_and_frontend_assets(self):
        with urllib.request.urlopen(self.base_url + "/api/health", timeout=2) as response:
            self.assertEqual(json.loads(response.read()), {"status": "ok"})
        with urllib.request.urlopen(self.base_url + "/", timeout=2) as response:
            page = response.read().decode("utf-8")
        self.assertIn("织络", page)
        self.assertIn("/assets/app.js", page)
        self.assertIn("自动识别意图", page)
        self.assertIn("试一个例子", page)
        self.assertIn("本地理想模拟", page)
        self.assertNotIn("适配云平台", page)
        self.assertNotIn("完成后会自动定位到这里", page)
        self.assertNotIn("处理完成后，这里会先用平实的中文解释结果", page)
        self.assertNotIn("data-task=", page)
        with urllib.request.urlopen(
            self.base_url + "/assets/app.js", timeout=2
        ) as response:
            app = response.read().decode("utf-8")
        self.assertIn("scrollIntoView", app)
        with urllib.request.urlopen(
            self.base_url + "/assets/visualizers.js", timeout=2
        ) as response:
            visualizers = response.read().decode("utf-8")
        self.assertIn("response?.artifacts?.circuit", visualizers)
        self.assertIn("理想结果纹样", visualizers)
        self.assertIn("不是云端或真机结果", visualizers)
        self.assertIn("非本次结果", visualizers)
        self.assertNotIn("仅凭这张分布图，不能单独证明纠缠", visualizers)
        self.assertIn("loomq:source-line", visualizers)
        with urllib.request.urlopen(
            self.base_url + "/assets/diagnostics.js", timeout=2
        ) as response:
            diagnostics = response.read().decode("utf-8")
        self.assertIn("missing_operand_comma", diagnostics)
        self.assertIn("定位第", diagnostics)

    def test_chat_transport_is_separate_from_agent_service(self):
        request = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps({
                "prompt": "改成 3 比特",
                "history": [
                    {"role": "user", "content": "生成 Bell 态"},
                    {"role": "assistant", "content": "previous answer"},
                ],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        structured = mock.Mock()
        structured.to_dict.return_value = {
            "schema_version": "1.0",
            "task": "explain",
            "answer": "answer",
            "artifacts": {
                "qasm": None,
                "circuit": None,
                "simulation": None,
                "backend_selection": None,
            },
            "diagnostics": [],
        }
        with mock.patch.object(
            app_server, "respond_structured", return_value=structured
        ) as respond:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read())
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["task"], "explain")
        self.assertEqual(payload["answer"], "answer")
        self.assertIsNone(payload["artifacts"]["qasm"])
        respond.assert_called_once_with(
            "改成 3 比特",
            history=[
                {"role": "user", "content": "生成 Bell 态"},
                {"role": "assistant", "content": "previous answer"},
            ],
            task_hint=None,
        )

    def test_runtime_errors_include_recovery_diagnostic(self):
        request = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps({"prompt": "生成 Bell 态"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with mock.patch.object(
            app_server,
            "respond_structured",
            side_effect=RuntimeError("LoomQ L2 API returned HTTP 401"),
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=2)
        payload = json.loads(caught.exception.read())
        self.assertEqual(payload["diagnostic"]["code"], "authentication_failed")
        self.assertIn("API Key", " ".join(payload["diagnostic"]["actions"]))


if __name__ == "__main__":
    unittest.main()
