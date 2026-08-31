import json
import os
import threading
import time
import urllib.error
import urllib.request
import unittest
from unittest import mock

from starter_kit import llm_client, loomq_l2
from starter_kit.l2_errors import L2TransportError, L2ValidationError
from starter_kit.loomq_l2 import agent_chat


CASE_TIMEOUT_SECONDS = 120.0


BELL_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


def completion(content):
    return {"choices": [{"message": {"content": content}}]}


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(completion("ok")).encode("utf-8")


class _SlowChunkedResponse:
    def __init__(self, release: threading.Event):
        self.release = release
        self.read_started = threading.Event()
        self.read_finished = threading.Event()
        self.chunks_received = 0
        self.read_thread_is_daemon = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        self.read_thread_is_daemon = threading.current_thread().daemon
        self.read_started.set()
        while not self.release.wait(0.002):
            self.chunks_received += 1
        self.read_finished.set()
        return json.dumps(completion("late response")).encode("utf-8")


class DeadlineTests(unittest.TestCase):
    def test_agent_chat_passes_the_absolute_case_deadline_to_repair(self):
        with mock.patch("starter_kit.loomq_l2.time", create=True) as clock:
            clock.monotonic.return_value = 1000.0
            with mock.patch(
                "starter_kit.loomq_l2._request",
                side_effect=[completion("not a circuit"), completion(BELL_QASM)],
            ) as request:
                self.assertEqual(agent_chat("generate a Bell circuit"), BELL_QASM.strip())

        deadlines = [call.kwargs.get("deadline_monotonic") for call in request.call_args_list]
        self.assertEqual(deadlines, [1120.0, 1120.0])

    def test_expired_budget_prevents_a_second_remote_call(self):
        with mock.patch("starter_kit.loomq_l2.time", create=True) as clock:
            clock.monotonic.side_effect = [1000.0, 1000.0, 1120.0]
            with mock.patch(
                "starter_kit.loomq_l2._request",
                return_value=completion("not a circuit"),
            ) as request:
                with self.assertRaises(L2ValidationError) as caught:
                    agent_chat("generate a Bell circuit")

        self.assertEqual(caught.exception.reason, "l2_case_deadline_exhausted")
        self.assertEqual(request.call_count, 1)

    def test_transport_clamps_to_the_smaller_call_budget(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.invalid",
            "LOOMQ_LLM_API_KEY": "private-test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "30",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch("starter_kit.llm_client._open_request", return_value=_Response()) as open_request:
                llm_client.chat_completion(
                    [{"role": "user", "content": "hello"}], timeout_seconds=5.0
                )

        self.assertEqual(open_request.call_args.args[1], 5.0)

    def test_transport_rechecks_deadline_after_request_construction(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.invalid",
            "LOOMQ_LLM_API_KEY": "private-test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "120",
        }
        actual_request = urllib.request.Request

        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch("starter_kit.llm_client.time", create=True) as clock:
                clock.monotonic.return_value = 1000.0

                def request_that_consumes_the_budget(*args, **kwargs):
                    clock.monotonic.return_value = 1120.0
                    return actual_request(*args, **kwargs)

                with mock.patch(
                    "starter_kit.llm_client.urllib.request.Request",
                    side_effect=request_that_consumes_the_budget,
                ):
                    with mock.patch(
                        "starter_kit.llm_client._open_request", return_value=_Response()
                    ) as open_request:
                        with self.assertRaises(L2ValidationError) as caught:
                            llm_client.chat_completion(
                                [{"role": "user", "content": "hello"}],
                                deadline_monotonic=1120.0,
                            )

        self.assertEqual(caught.exception.reason, "l2_case_deadline_exhausted")
        open_request.assert_not_called()

    def test_deadline_mode_transport_error_keeps_its_effective_timeout(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.invalid",
            "LOOMQ_LLM_API_KEY": "private-test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "30",
        }
        deadline = time.monotonic() + 5.0

        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch(
                "starter_kit.llm_client._open_request",
                side_effect=urllib.error.URLError("unreachable"),
            ):
                with self.assertRaises(L2TransportError) as caught:
                    llm_client.chat_completion(
                        [{"role": "user", "content": "hello"}],
                        deadline_monotonic=deadline,
                    )

        self.assertEqual(caught.exception.host, "example.invalid")
        self.assertGreater(caught.exception.timeout_seconds, 0.0)
        self.assertLessEqual(caught.exception.timeout_seconds, 5.0)

    def test_agent_chat_stops_waiting_at_deadline_during_a_slow_chunked_read(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.invalid",
            "LOOMQ_LLM_API_KEY": "private-test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "120",
        }
        release = threading.Event()
        response = _SlowChunkedResponse(release)
        try:
            with mock.patch.dict(os.environ, environment, clear=True):
                with mock.patch("starter_kit.loomq_l2.CASE_TIMEOUT_SECONDS", 0.05):
                    with mock.patch(
                        "starter_kit.llm_client._open_request", return_value=response
                    ):
                        started = time.monotonic()
                        with self.assertRaises(L2ValidationError) as caught:
                            agent_chat("解释量子叠加是什么")
                        elapsed = time.monotonic() - started
        finally:
            release.set()

        self.assertEqual(caught.exception.reason, "l2_case_deadline_exhausted")
        self.assertTrue(response.read_started.is_set())
        self.assertGreater(response.chunks_received, 0)
        self.assertTrue(response.read_thread_is_daemon)
        self.assertTrue(response.read_finished.wait(0.5))
        self.assertLess(elapsed, 0.5)

    def test_agent_chat_supports_a_simple_monkeypatched_client(self):
        def simple_client(messages):
            self.assertEqual(messages[-1]["content"], "解释量子叠加是什么")
            return completion("量子叠加是多个可能状态的组合。")

        with mock.patch("starter_kit.llm_client.chat_completion", new=simple_client):
            reply = agent_chat("解释量子叠加是什么")

        self.assertIn("多个可能状态", reply)

    def test_request_does_not_retry_a_type_error_from_the_client(self):
        calls = []

        def client_that_raises(messages, *, deadline_monotonic=None):
            calls.append((messages, deadline_monotonic))
            raise TypeError("client internal type error")

        with mock.patch(
            "starter_kit.llm_client.chat_completion", side_effect=client_that_raises
        ):
            with self.assertRaisesRegex(TypeError, "client internal type error"):
                loomq_l2._request([{"role": "user", "content": "hello"}], deadline_monotonic=1.0)

        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
