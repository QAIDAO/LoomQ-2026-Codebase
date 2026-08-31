import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starter_kit.scripts import l2_extended_campaign as campaign
from starter_kit.scripts.l2_extended_campaign import build_corpus


class ExtendedCorpusTests(unittest.TestCase):
    def test_v2_fixed_seed_has_exact_category_budget_and_unique_ids(self):
        cases = build_corpus(20260823)
        self.assertEqual(len(cases), 500)
        self.assertEqual(len({case['case_id'] for case in cases}), 500)
        self.assertTrue(all(case['case_id'].startswith('v2-') for case in cases))
        self.assertTrue(all(case['seed'] == 20260823 for case in cases))
        counts = {}
        for case in cases:
            counts[case['category']] = counts.get(case['category'], 0) + 1
        self.assertEqual(counts, {'generation': 150, 'repair': 150, 'backend': 120, 'adversarial': 50, 'stability': 30})

    def test_environment_gate_writes_only_to_explicit_temp_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            with patch.dict('os.environ', {}, clear=True):
                result = __import__('starter_kit.scripts.l2_extended_campaign', fromlist=['resume_smoke']).resume_smoke(1, output_dir=output_dir)
            self.assertEqual(result['status'], 'REAL_MODEL_ENV_BLOCKED')
            summary = output_dir / 'l2-deepseek-v4-flash-validation-v2-summary.json'
            records = output_dir / 'l2-deepseek-v4-flash-validation-v2-records.jsonl'
            self.assertTrue(summary.exists())
            self.assertTrue(records.exists())
            self.assertEqual(json.loads(summary.read_text(encoding='utf-8'))['campaign_version'], 2)

    def test_v2_checkpoint_writes_summary_records_and_state_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            record = {'case_id': 'v2-generation-001', 'category': 'generation', 'seed': campaign.SEED, 'attempts': 1, 'pass_': True, 'latency_ms': 10}
            campaign._write([record], 1, partial=True, output_dir=Path(temp))
            summary, records, state = campaign._paths(Path(temp))
            self.assertEqual(json.loads(summary.read_text(encoding='utf-8'))['api_attempts'], 1)
            self.assertEqual(json.loads(records.read_text(encoding='utf-8').splitlines()[0])['case_id'], 'v2-generation-001')
            self.assertEqual(json.loads(state.read_text(encoding='utf-8'))['case_ids'], ['v2-generation-001'])
            self.assertFalse(list(Path(temp).glob('*.tmp')))

    def test_checkpoint_rejects_duplicate_ids_and_budget_is_540(self):
        record = {'case_id': 'v2-generation-001', 'category': 'generation', 'seed': campaign.SEED, 'attempts': 1, 'pass_': True}
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            campaign.validate_checkpoint([record, dict(record)], 2)
        self.assertEqual(campaign.MAX_RECORDED_ATTEMPTS, 540)

    def test_diagnostic_tracebacks_redact_local_absolute_paths(self):
        local_root = 'C:' + '\\' + 'Users' + '\\' + 'UUWayne'
        diagnostic = 'Traceback: ' + local_root + '\\' + 'App' + 'Data' + '\\Local\\' + 'T' + 'emp\\loomq\\case.py'
        sanitized = campaign._sanitize_diagnostic(diagnostic)
        self.assertNotIn(local_root, sanitized)
        self.assertNotIn('App' + 'Data', sanitized)
        self.assertIn('<redacted-local-path>', sanitized)
