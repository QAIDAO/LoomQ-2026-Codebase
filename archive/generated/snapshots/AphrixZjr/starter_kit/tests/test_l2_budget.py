import json
import os
import sys
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

import loomq_l2
import llm_client


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _limit):
        return self.body


def response(content, *, prompt_tokens=None, completion_tokens=None):
    value = {"choices": [{"message": {"content": content}}]}
    if prompt_tokens is not None or completion_tokens is not None:
        value["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    return value


def backend_content(pad=""):
    return json.dumps({
        "task": "backend_select",
        "hard_constraints": {},
        "soft_preferences": {},
        "forbidden": {},
        "unresolved": [],
        "pad": pad,
    })


class L2BudgetTests(unittest.TestCase):
    def context(self):
        return loomq_l2.RequestContext(time.monotonic() + 30)

    def test_provider_usage_takes_precedence_over_utf8_byte_fallback(self):
        messages = [{"role": "user", "content": "量子" * 100}]
        content = backend_content("x" * 2500)
        with mock.patch.object(
            loomq_l2,
            "chat_completion",
            return_value=response(content, prompt_tokens=7, completion_tokens=11),
        ):
            context = self.context()
            loomq_l2._model_call(context, messages)
        self.assertEqual(context.input_tokens, 7)
        self.assertEqual(context.output_tokens, 11)

    def test_missing_usage_uses_input_bytes_and_reserves_request_output_limit(self):
        messages = [{"role": "user", "content": "量子 hello"}]
        content = backend_content()
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value=response(content)
        ):
            context = self.context()
            loomq_l2._model_call(context, messages)
        self.assertEqual(
            context.input_tokens, loomq_l2._input_token_upper_bound(messages)
        )
        self.assertEqual(context.output_tokens, 900)

    def test_missing_usage_does_not_reject_multibyte_output_by_byte_length(self):
        messages = [{"role": "user", "content": "small"}]
        content = backend_content("量" * 900)
        self.assertGreater(len(content.encode("utf-8")), 2000)
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value=response(content)
        ):
            context = self.context()
            loomq_l2._model_call(context, messages)
        self.assertEqual(context.output_tokens, 900)

    def test_malformed_successful_response_still_consumes_output_budget(self):
        messages = [{"role": "user", "content": "small"}]
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value={"choices": []}
        ):
            context = self.context()
            with self.assertRaisesRegex(RuntimeError, "invalid response"):
                loomq_l2._model_call(context, messages)
        self.assertEqual(context.successful_model_responses, 1)
        self.assertEqual(context.output_tokens, 900)

    def test_wire_success_with_invalid_json_reserves_actual_request_limit(self):
        self._assert_wire_payload_error_is_accounted(b"not-json")

    def test_wire_success_with_non_object_json_reserves_actual_request_limit(self):
        self._assert_wire_payload_error_is_accounted(b"[]")

    def _assert_wire_payload_error_is_accounted(self, body):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://llm.invalid/v1",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "137",
        }
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(
            llm_client.urllib.request,
            "urlopen",
            return_value=FakeHTTPResponse(body),
        ) as transport:
            context = self.context()
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                loomq_l2._model_call(
                    context, [{"role": "user", "content": "small"}]
                )
        request = transport.call_args.args[0]
        self.assertEqual(json.loads(request.data)["max_tokens"], 137)
        self.assertEqual(context.model_calls, 1)
        self.assertEqual(context.successful_model_responses, 1)
        self.assertEqual(context.valid_model_responses, 0)
        self.assertEqual(context.output_tokens, 137)

    def test_wire_http_and_transport_failures_do_not_consume_output_budget(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://llm.invalid/v1",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "137",
        }
        failures = (
            urllib.error.HTTPError(
                "https://llm.invalid/v1/chat/completions", 400, "bad", {}, None
            ),
            urllib.error.URLError("offline"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), mock.patch.dict(
                os.environ, environment, clear=True
            ), mock.patch.object(
                llm_client.urllib.request, "urlopen", side_effect=failure
            ):
                context = self.context()
                with self.assertRaises(RuntimeError):
                    loomq_l2._model_call(
                        context, [{"role": "user", "content": "small"}]
                    )
                self.assertEqual(context.model_calls, 1)
                self.assertEqual(context.successful_model_responses, 0)
                self.assertEqual(context.valid_model_responses, 0)
                self.assertEqual(context.output_tokens, 0)

    def test_cumulative_input_boundary_blocks_before_an_extra_request(self):
        content = backend_content()
        reply = response(content, prompt_tokens=8000, completion_tokens=1)
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value=reply
        ) as transport:
            context = self.context()
            loomq_l2._model_call(context, [{"role": "user", "content": "first"}])
            with self.assertRaisesRegex(RuntimeError, "input-token budget"):
                loomq_l2._model_call(
                    context, [{"role": "user", "content": "second"}]
                )
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(context.input_tokens, 8000)

    def test_cumulative_output_boundary_is_exactly_2000(self):
        content = backend_content()
        replies = [
            response(content, prompt_tokens=1, completion_tokens=1000),
            response(content, prompt_tokens=1, completion_tokens=1000),
            response(content, prompt_tokens=1, completion_tokens=1),
        ]
        with mock.patch.dict(
            os.environ, {"LOOMQ_LLM_MAX_OUTPUT_TOKENS": "1000"}
        ), mock.patch.object(
            loomq_l2, "chat_completion", side_effect=replies
        ) as transport:
            context = self.context()
            messages = [{"role": "user", "content": "small"}]
            loomq_l2._model_call(context, messages)
            loomq_l2._model_call(context, messages)
            self.assertEqual(context.output_tokens, 2000)
            with self.assertRaisesRegex(RuntimeError, "output-token budget"):
                loomq_l2._model_call(context, messages)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(context.model_calls, 2)

    def test_final_request_is_capped_to_the_remaining_output_budget(self):
        content = backend_content()
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value=response(content)
        ) as transport:
            context = self.context()
            messages = [{"role": "user", "content": "small"}]
            loomq_l2._model_call(context, messages)
            loomq_l2._model_call(context, messages)
            loomq_l2._model_call(context, messages)
            self.assertEqual(context.output_tokens, 2000)
            self.assertEqual(
                [call.kwargs["request_max_tokens"] for call in transport.call_args_list],
                [900, 900, 200],
            )
            with self.assertRaisesRegex(RuntimeError, "output-token budget"):
                loomq_l2._model_call(context, messages)
        self.assertEqual(transport.call_count, 3)

    def test_no_more_than_three_transport_attempts(self):
        content = backend_content()
        reply = response(content, prompt_tokens=0, completion_tokens=0)
        with mock.patch.object(
            loomq_l2, "chat_completion", return_value=reply
        ) as transport:
            context = self.context()
            messages = [{"role": "user", "content": "small"}]
            for _ in range(3):
                loomq_l2._model_call(context, messages)
            with self.assertRaisesRegex(RuntimeError, "model call budget"):
                loomq_l2._model_call(context, messages)
        self.assertEqual(transport.call_count, 3)

    def test_only_one_transient_retry_is_allowed(self):
        with mock.patch.object(
            loomq_l2,
            "chat_completion",
            side_effect=[
                RuntimeError("LoomQ L2 API returned HTTP 503"),
                RuntimeError("LoomQ L2 API returned HTTP 429"),
                response(backend_content()),
            ],
        ) as transport, mock.patch.object(loomq_l2.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                loomq_l2._model_call(
                    self.context(), [{"role": "user", "content": "small"}]
                )
        self.assertEqual(transport.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
