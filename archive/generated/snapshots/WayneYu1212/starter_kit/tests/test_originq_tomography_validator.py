import unittest
from pathlib import Path

from starter_kit.scripts.validate_originq_tomography import validate_package


class OriginQTomographyValidatorTests(unittest.TestCase):
    def test_completed_package_has_auditable_two_attempt_provenance(self):
        root = Path(__file__).resolve().parents[1] / "evidence" / "files" / "originq-tomography"
        report = validate_package(root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["success_job_id"], "F7287E16E8478E4DB5051105468DB638")
        self.assertEqual(report["failure_job_id"], "EE7D22A38D5A9F246A2031BC7A31C3AD")
        self.assertLess(report["fidelity_absolute_difference"], 1e-6)
        self.assertLess(report["ppt_minimum_eigenvalue"], 0.0)
