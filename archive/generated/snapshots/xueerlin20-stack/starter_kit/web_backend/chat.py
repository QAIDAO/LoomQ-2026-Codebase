"""Chat request validation and learning-profile adaptation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Dict, Optional

from .backend_presentation import BackendPresenter
from .context_builder import (
    EXPLAIN_CURRENT,
    ConversationActionClassifier,
    ConversationContextBuilder,
)
from .conversations import ConversationStore

try:
    from ..l2_agent.factory import create_agent
except ImportError:
    from l2_agent.factory import create_agent  # type: ignore


PROFILE_INSTRUCTIONS = {
    "new": (
        "用户第一次接触量子计算；用日常类比解释必要概念，"
        "避免不加解释的术语。"
    ),
    "some": "用户了解一些量子计算；保留必要术语，重点解释电路逻辑。",
    "expert": "用户有量子背景；直接给出 QASM、后端和运行细节，保持简洁。",
}


class ChatService:
    """Translate browser chat payloads into Agent calls and view-ready responses."""

    def __init__(
        self,
        agent_factory: Optional[Callable[[], Any]] = None,
        local_executor: Optional[Callable[[str, str, int], Dict[str, Any]]] = None,
        backend_presenter: Optional[BackendPresenter] = None,
        conversation_store: Optional[ConversationStore] = None,
        action_classifier: Optional[ConversationActionClassifier] = None,
        context_builder: Optional[ConversationContextBuilder] = None,
    ):
        self.agent_factory = agent_factory or create_agent
        self.local_executor = local_executor
        self.backend_presenter = backend_presenter or BackendPresenter()
        self.conversation_store = conversation_store or ConversationStore()
        self.action_classifier = action_classifier or ConversationActionClassifier()
        self.context_builder = context_builder or ConversationContextBuilder()

    def run_local(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Measure the current server-owned circuit on the local simulator."""
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        conversation_id = payload.get("conversation_id")
        artifact_id = payload.get("active_artifact_id")
        expected_version = payload.get("expected_version")
        shots = payload.get("shots", 1024)
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("缺少当前会话，请先生成一个电路")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError("缺少当前电路，请先生成一个电路")
        if (
            not isinstance(expected_version, int)
            or isinstance(expected_version, bool)
            or expected_version < 1
        ):
            raise ValueError("当前电路版本无效")
        if (
            not isinstance(shots, int)
            or isinstance(shots, bool)
            or shots < 1
            or shots > 8192
        ):
            raise ValueError("shots 必须是 1 到 8192 之间的整数")

        conversation = self.conversation_store.get(conversation_id)
        if conversation is None or conversation.active_artifact is None:
            raise ValueError("当前会话或电路已失效，请重新生成电路")
        artifact = conversation.active_artifact
        if artifact.artifact_id != artifact_id or artifact.version != expected_version:
            raise ValueError("当前电路已变化，请基于最新版本重新运行")

        if self.local_executor is None:
            try:
                from ..adapter import run
            except ImportError:
                from adapter import run  # type: ignore
            executor = run
        else:
            executor = self.local_executor
        execution = executor(artifact.qasm, "spinq", shots)
        counts = execution.get("counts")
        actual_shots = execution.get("shots")
        if (
            not isinstance(counts, dict)
            or not counts
            or not isinstance(actual_shots, int)
            or sum(counts.values()) != actual_shots
        ):
            raise RuntimeError("本地模拟器返回了无效的测量结果")
        return {
            "ok": True,
            "backend": execution.get("backend", "spinq"),
            "job_id": execution.get("job_id", ""),
            "shots": actual_shots,
            "counts": counts,
        }

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt, profile, explain_concepts = self._validate(payload)
        conversation = self.conversation_store.get_or_create(
            payload.get("conversation_id")
        )
        self._validate_artifact_reference(payload, conversation)
        action = self.action_classifier.classify(prompt, conversation)
        learning_instruction = self._learning_instruction(profile, explain_concepts)
        agent_prompt = self.context_builder.build(
            prompt=prompt,
            conversation=conversation,
            action=action,
            learning_instruction=learning_instruction,
        )
        response = asdict(self.agent_factory().execute(agent_prompt))
        response["display_text"] = self._display_text(response)
        if response.get("backend_id"):
            response["backend"] = self.backend_presenter.describe(
                response["backend_id"], response.get("response_language", "zh")
            )
            response["alternative_backends"] = [
                self.backend_presenter.describe(
                    backend_id, response.get("response_language", "zh")
                )
                for backend_id in response.get("alternatives", [])
            ]
        artifact = self.conversation_store.record(
            conversation,
            user_text=prompt,
            assistant_text=response["display_text"],
            action=action,
            qasm=response.get("qasm") if response.get("ok") else None,
        )
        # Explanation turns validate the current circuit internally but should not
        # repeat the full QASM card in the browser.
        if action == EXPLAIN_CURRENT and artifact is not None:
            response["qasm"] = None
            response["validation"] = {}
        response["conversation_id"] = conversation.conversation_id
        response["conversation_action"] = action
        response["active_artifact"] = (
            artifact.public_metadata() if artifact is not None else None
        )
        response["suggestions"] = self._suggestions(action, artifact is not None)
        return response

    def reset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a browser conversation and its active circuit immediately."""
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id must be a non-empty string")
        if len(conversation_id) > 128:
            raise ValueError("invalid conversation_id")
        deleted = self.conversation_store.delete(conversation_id)
        return {"ok": True, "deleted": deleted}

    @staticmethod
    def _validate(payload: Dict[str, Any]) -> tuple[str, Any, bool]:
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if len(prompt) > 12000:
            raise ValueError("prompt is too long")
        profile = payload.get("quantum_profile")
        if profile is not None and profile not in PROFILE_INSTRUCTIONS:
            raise ValueError("invalid quantum knowledge profile")
        explain_concepts = payload.get("explain_concepts", False)
        if not isinstance(explain_concepts, bool):
            raise ValueError("explain_concepts must be a boolean")
        conversation_id = payload.get("conversation_id")
        if conversation_id is not None and (
            not isinstance(conversation_id, str) or len(conversation_id) > 128
        ):
            raise ValueError("invalid conversation_id")
        artifact_id = payload.get("active_artifact_id")
        if artifact_id is not None and (
            not isinstance(artifact_id, str) or len(artifact_id) > 128
        ):
            raise ValueError("invalid active_artifact_id")
        expected_version = payload.get("expected_version")
        if expected_version is not None and (
            not isinstance(expected_version, int)
            or isinstance(expected_version, bool)
            or expected_version < 1
        ):
            raise ValueError("invalid expected_version")
        return prompt.strip(), profile, explain_concepts

    @staticmethod
    def _learning_instruction(profile: Any, explain_concepts: bool) -> Optional[str]:
        if not profile:
            return None
        preference = PROFILE_INSTRUCTIONS[profile]
        if explain_concepts:
            preference += " 在结果说明中补充本次实验涉及的量子概念。"
        return preference

    @staticmethod
    def _with_learning_preference(
        prompt: str, profile: Any, explain_concepts: bool
    ) -> str:
        """Compatibility helper retained for callers outside the web service."""
        instruction = ChatService._learning_instruction(profile, explain_concepts)
        if not instruction:
            return prompt
        return "%s\n\n[讲解偏好：%s]" % (prompt, instruction)

    @staticmethod
    def _validate_artifact_reference(payload: Dict[str, Any], conversation) -> None:
        requested_id = payload.get("active_artifact_id")
        expected_version = payload.get("expected_version")
        artifact = conversation.active_artifact
        if requested_id is not None and (
            artifact is None or requested_id != artifact.artifact_id
        ):
            raise ValueError("当前电路已变化，请刷新会话后重试")
        if expected_version is not None and (
            artifact is None or expected_version != artifact.version
        ):
            raise ValueError("当前电路版本已变化，请基于最新版本重试")

    @staticmethod
    def _suggestions(action: str, has_artifact: bool) -> list[str]:
        if not has_artifact:
            return []
        if action == EXPLAIN_CURRENT:
            return ["修改这个电路", "运行当前电路", "设计一个新电路"]
        return ["解释每个门的作用", "改进当前电路", "再运行一次"]

    @staticmethod
    def _display_text(result: Dict[str, Any]) -> str:
        english = result.get("response_language") == "en"
        if not result.get("ok"):
            return result.get("message") or (
                "The task could not be completed."
                if english
                else "暂时无法完成这个任务。"
            )
        if result.get("backend_id"):
            return result.get("explanation") or (
                "This backend satisfies the stated constraints."
                if english
                else "该后端满足你提出的条件。"
            )
        return result.get("explanation") or (
            "The circuit was generated and run successfully."
            if english
            else "电路已生成并成功运行。"
        )
