import unittest

from loomq.web import ASSETS, _run_payload


class WebTests(unittest.TestCase):
    def test_static_assets_are_bundled(self):
        for relative in (
            "index.html",
            "app.css",
            "app.js",
            "icons/soft-sparkle-twinkle.png",
            "icons/soft-pie-chart.png",
            "icons/soft-accessibility-person.png",
        ):
            self.assertTrue((ASSETS / relative).is_file(), relative)

    def test_api_run_returns_verified_bell_result(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
h q[0]; cx q[0], q[1]; measure q -> c;
'''
        response = _run_payload({"qasm": qasm, "target": "originq", "shots": 4096})
        self.assertEqual(response["result"]["counts"], {"00": 2048, "11": 2048})
        self.assertTrue(response["target_ir"].startswith("QINIT 2\nCREG 2"))
        certificate = response["result"]["meta"]["translation_certificate"]
        self.assertTrue(certificate["verified"])
        self.assertTrue(certificate["operation_trace_equal"])
        self.assertEqual(response["result"]["meta"]["executed_ir"], "independently-reparsed-target")


if __name__ == "__main__":
    unittest.main()
