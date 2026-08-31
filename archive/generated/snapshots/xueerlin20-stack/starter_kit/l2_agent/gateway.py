"""OpenAI-compatible LLM gateway for the LoomQ L2 agent."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any, Dict

try:
    from ..llm_client import chat_completion
except ImportError:
    from llm_client import chat_completion

from .models import AgentIntent
from .prompts import MAIN_SYSTEM_PROMPT, REPAIR_SYSTEM_PROMPT


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_QASM_FENCE = re.compile(
    r"```(?:openqasm|qasm)?\s*(OPENQASM\s+2\.0;.*?)```",
    re.IGNORECASE | re.DOTALL,
)


class OpenAICompatibleLLMGateway:
    """Translate model responses into the agent's typed work orders."""

    def __init__(self) -> None:
        self._request_state = threading.local()

    def begin_request(self) -> None:
        try:
            total_timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
        except ValueError as exc:
            raise RuntimeError("invalid LOOMQ_LLM_TIMEOUT_SECONDS") from exc
        if total_timeout <= 0:
            raise RuntimeError("LOOMQ_LLM_TIMEOUT_SECONDS must be positive")
        self._request_state.deadline = time.monotonic() + total_timeout
        self._request_state.call_count = 0

    def understand(self, prompt: str) -> AgentIntent:
        payload = self._call(
            [
                {"role": "system", "content": MAIN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            reserve_seconds=35.0,
        )
        data = self._parse_json_object(self._content(payload))
        return self._intent_from_dict(data)

    def repair_qasm(
        self,
        *,
        user_goal: str,
        broken_qasm: str,
        validation_error: str,
        source_qasm: str | None = None,
    ) -> str:
        repair_input = {
            "user_goal": user_goal,
            "original_source_qasm": source_qasm,
            "invalid_candidate_qasm": broken_qasm,
            "validator_error": validation_error,
        }
        payload = self._call(
            [
                {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(repair_input, ensure_ascii=False),
                },
            ],
            reserve_seconds=2.0,
        )
        content = self._content(payload)
        try:
            data = self._parse_json_object(content)
            qasm = data.get("qasm")
        except RuntimeError:
            match = _QASM_FENCE.search(content)
            qasm = match.group(1).strip() if match else None
        if not isinstance(qasm, str) or not qasm.strip():
            raise RuntimeError("LoomQ LLM repair response contains no QASM")
        return qasm.strip()

    def _call(self, messages, reserve_seconds: float) -> Dict[str, Any]:
        if not hasattr(self._request_state, "deadline"):
            self.begin_request()
        call_count = getattr(self._request_state, "call_count", 0)
        if call_count >= 2:
            raise RuntimeError("LoomQ L2 model-call limit exceeded")

        remaining = self._request_state.deadline - time.monotonic()
        # Preserve a repair opportunity without making short local test
        # timeouts unusable.  Formal first calls are capped at 75 seconds.
        reserve = min(reserve_seconds, max(0.0, remaining * 0.35))
        request_timeout = remaining - reserve
        if call_count == 0:
            request_timeout = min(request_timeout, 75.0)
        if request_timeout <= 0:
            raise RuntimeError("LoomQ L2 request time budget exhausted")

        self._request_state.call_count = call_count + 1
        return chat_completion(
            messages,
            request_timeout_seconds=request_timeout,
        )

    @staticmethod
    def _content(payload: Dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("invalid LoomQ LLM response structure") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LoomQ LLM returned empty content")
        return content.strip()

    @staticmethod
    def _parse_json_object(content: str) -> Dict[str, Any]:
        candidate = content.strip()
        fenced = _JSON_FENCE.fullmatch(candidate)
        if fenced:
            candidate = fenced.group(1).strip()
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LoomQ LLM returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("LoomQ LLM JSON response must be an object")
        return data

    @staticmethod
    def _intent_from_dict(data: Dict[str, Any]) -> AgentIntent:
        task_type = data.get("task_type")
        user_goal = data.get("user_goal")
        response_language = data.get("response_language", "zh")
        circuit = data.get("circuit")
        constraints = data.get("backend_constraints")
        candidate_qasm = data.get("candidate_qasm")
        source_qasm = data.get("source_qasm")
        explanation = data.get("explanation")

        if not isinstance(task_type, str):
            raise RuntimeError("LoomQ LLM intent has no task_type")
        if not isinstance(user_goal, str) or not user_goal.strip():
            raise RuntimeError("LoomQ LLM intent has no user_goal")
        if response_language not in {"zh", "en"}:
            raise RuntimeError("LoomQ LLM response_language must be zh or en")
        if circuit is not None and not isinstance(circuit, dict):
            raise RuntimeError("LoomQ LLM circuit intent must be an object")
        if constraints is not None and not isinstance(constraints, dict):
            raise RuntimeError("LoomQ LLM backend constraints must be an object")
        for field_name, value in (
            ("candidate_qasm", candidate_qasm),
            ("source_qasm", source_qasm),
            ("explanation", explanation),
        ):
            if value is not None and not isinstance(value, str):
                raise RuntimeError("LoomQ LLM %s must be a string or null" % field_name)

        return AgentIntent(
            task_type=task_type.strip(),
            user_goal=user_goal.strip(),
            response_language=response_language,
            candidate_qasm=candidate_qasm,
            source_qasm=source_qasm,
            circuit=circuit or {},
            backend_constraints=constraints or {},
            explanation=explanation,
        )
