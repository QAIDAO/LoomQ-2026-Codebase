import time
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starter_kit.scripts.campaign_watchdog import run
from starter_kit.scripts import l2_extended_campaign as campaign
from starter_kit.scripts.l2_extended_campaign import _child
def _hang(queue): time.sleep(10); queue.put({'status':'ok'})
def _ok(value,queue): queue.put({'status':'ok','value':value})
def _raise_child(queue): raise ValueError('child boom')
class WatchdogTests(unittest.TestCase):
 def test_missing_real_model_env_blocks_without_running_a_case(self):
  with tempfile.TemporaryDirectory() as temp:
   evidence = Path(temp)
   summary = evidence / campaign.SUMMARY_FILENAME
   summary.write_text(json.dumps({
    'schema_version': 2, 'campaign_version': 2, 'corpus_version': 'v2', 'seed': campaign.SEED,
    'partial': True, 'case_count': 0, 'api_request_count': 0,
    'pass_count': 1, 'fail_count': 0, 'records': [],
   }), encoding='utf-8')
   with patch.object(campaign, 'FILES', evidence), \
       patch.dict(campaign.os.environ, {}, clear=True), \
       patch.object(campaign, 'run_case_with_watchdog', side_effect=AssertionError('must not call model')):
    result = campaign.resume_smoke(1, output_dir=evidence)
   self.assertEqual(result['status'], 'REAL_MODEL_ENV_BLOCKED')
   self.assertEqual(result['environment']['LOOMQ_LLM_BASE_URL'], 'MISSING')
   self.assertEqual(result['environment']['LOOMQ_LLM_API_KEY'], 'MISSING')
   self.assertEqual(result['environment']['LOOMQ_LLM_MODEL'], 'MISSING')

 def test_default_run_uses_the_guarded_resume_path(self):
  with patch.object(campaign, 'resume_smoke', return_value={'status': 'fixture'}) as resume:
   self.assertEqual(campaign.run(7, 3, False), {'status': 'fixture'})
  resume.assert_called_once_with(7, output_dir=None)

 def test_terminates_hanging_child(self):
  start=time.monotonic(); self.assertEqual(run(_hang,(),1)['status'],'timeout'); self.assertLess(time.monotonic()-start,5)
 def test_returns_child_payload(self): self.assertEqual(run(_ok,('x',),2),{'status':'ok','value':'x'})
 def test_propagates_child_exception(self):
  result = run(_raise_child,(),2)
  self.assertEqual(result['status'],'child_exception')
  self.assertEqual(result['exception_type'],'ValueError')
  self.assertIn('child boom',result['exception_message'])
 def test_child_fixture_error_preserves_message_and_counts_attempt(self):
  result=run(_child,({'prompt':'x','_local_fixture_exception':'transport failed'},),2)
  self.assertFalse(result['pass_']); self.assertEqual(result['attempts'],1)
  self.assertEqual(result['exception_type'],'RuntimeError'); self.assertIn('transport failed',result['exception_message'])

 def test_child_fixture_error_does_not_call_transport_when_budget_is_exhausted(self):
  result=run(_child,({'prompt':'x','_local_fixture_exception':'transport failed','_request_budget':0},),2)
  self.assertFalse(result['pass_']); self.assertEqual(result['attempts'],0)
  self.assertIn('request cap',result['exception_message'])

 def test_resume_skips_attempted_ids_and_checkpoints_each_case(self):
  with tempfile.TemporaryDirectory() as temp:
   evidence = Path(temp)
   summary = evidence / campaign.SUMMARY_FILENAME
   summary.write_text(json.dumps({
    'schema_version': 2, 'campaign_version': 2, 'corpus_version': 'v2', 'seed': campaign.SEED,
    'partial': True, 'case_count': 1, 'api_request_count': 1,
    'pass_count': 1, 'fail_count': 0, 'records': [{
     'case_id': 'v2-generation-000', 'category': 'generation', 'seed': campaign.SEED,
     'prompt_hash': 'old', 'pass_': True, 'attempts': 1, 'latency_ms': 1,
     'response_model': 'deepseek-v4-flash', 'output_hash': 'old',
    }],
   }, ensure_ascii=False), encoding='utf-8')
   calls = []
   def fake_case(case, request_budget=None):
    calls.append((case['case_id'], request_budget))
    return {'pass_': True, 'attempts': 1, 'model': 'fixture', 'output_hash': 'new'}
   with patch.object(campaign, 'FILES', evidence), \
       patch.dict(campaign.os.environ, {'LOOMQ_LLM_BASE_URL':'fixture','LOOMQ_LLM_API_KEY':'fixture','LOOMQ_LLM_MODEL':'deepseek-v4-flash'}, clear=False), \
       patch.object(campaign, 'run_case_with_watchdog', side_effect=fake_case):
    result = campaign.resume_smoke(2, output_dir=evidence)
   saved = json.loads(summary.read_text(encoding='utf-8'))
   self.assertEqual([item[0] for item in calls], ['v2-generation-001', 'v2-generation-002'])
   self.assertEqual([item[1] for item in calls], [539, 538])
   self.assertEqual(result['api_attempts'], 3)
   self.assertEqual(saved['api_request_count'], 3)
   self.assertEqual(saved['case_count'], 3)

 def test_resume_pauses_after_two_provider_timeouts(self):
  with tempfile.TemporaryDirectory() as temp:
   evidence = Path(temp)
   summary = evidence / campaign.SUMMARY_FILENAME
   summary.write_text(json.dumps({
    'schema_version': 2, 'campaign_version': 2, 'corpus_version': 'v2', 'seed': campaign.SEED,
    'partial': True, 'case_count': 0, 'api_request_count': 0,
    'pass_count': 0, 'fail_count': 0, 'records': [],
   }), encoding='utf-8')
   with patch.object(campaign, 'FILES', evidence), \
       patch.dict(campaign.os.environ, {'LOOMQ_LLM_BASE_URL':'fixture','LOOMQ_LLM_API_KEY':'fixture','LOOMQ_LLM_MODEL':'deepseek-v4-flash'}, clear=False), \
       patch.object(campaign, 'run_case_with_watchdog', return_value={'status': 'timeout'}), \
       patch.object(campaign.time, 'sleep') as sleep:
    result = campaign.resume_smoke(3, output_dir=evidence)
   self.assertEqual(result['case_count'], 3)
   self.assertEqual(result['api_attempts'], 3)
   sleep.assert_called_once_with(60)
   saved = json.loads(summary.read_text(encoding='utf-8'))
   self.assertEqual(saved['campaign_status'], 'PROVIDER_UNSTABLE')
