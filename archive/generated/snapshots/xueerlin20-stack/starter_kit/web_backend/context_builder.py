"""Classify follow-ups and build bounded prompts for the stateless L2 agent."""

from __future__ import annotations

import re
from typing import Optional

from .conversations import Conversation


NEW_CIRCUIT = "new_circuit"
MODIFY_CURRENT = "modify_current"
EXPLAIN_CURRENT = "explain_current"
RUN_CURRENT = "run_current"

_NEW_PATTERN = re.compile(
    r"(?:重新|再)(?:设计|创建|生成)|(?:设计|创建|生成)(?:一个)?(?:全新|新的)|"
    r"另一个|another|new\s+circuit",
    re.IGNORECASE,
)
_MODIFY_PATTERN = re.compile(
    r"改(?:成|为|一下)|修改|调整|增加|减少|替换|换成|优化|改进|"
    r"change|modify|update|replace|improve",
    re.IGNORECASE,
)
_EXPLAIN_PATTERN = re.compile(
    r"为什么|解释|说明|作用|什么意思|看不懂|怎么理解|"
    r"why|explain|what\s+does|how\s+does",
    re.IGNORECASE,
)
_RUN_PATTERN = re.compile(
    r"(?:运行|执行|测量|模拟)(?:它|这个|该|当前|刚才|上述|一遍|一下)?|"
    r"run\s+(?:it|this)|execute\s+(?:it|this)",
    re.IGNORECASE,
)


class ConversationActionClassifier:
    """Use stable language cues before asking the LLM to do circuit work."""

    def classify(self, prompt: str, conversation: Conversation) -> str:
        active = conversation.active_artifact
        if active is None or _NEW_PATTERN.search(prompt):
            return NEW_CIRCUIT
        if _EXPLAIN_PATTERN.search(prompt):
            return EXPLAIN_CURRENT
        if _MODIFY_PATTERN.search(prompt):
            return MODIFY_CURRENT
        if _RUN_PATTERN.search(prompt):
            return RUN_CURRENT
        # With an active circuit, a short follow-up normally refers to it.
        return EXPLAIN_CURRENT


class ConversationContextBuilder:
    """Provide exact current QASM and only a small recent-turn window."""

    def build(
        self,
        *,
        prompt: str,
        conversation: Conversation,
        action: str,
        learning_instruction: Optional[str] = None,
    ) -> str:
        if conversation.active_artifact is None and not conversation.turns:
            return self._append_learning(prompt, learning_instruction)

        # Backend recommendations and other non-circuit requests still need
        # bounded history so phrases such as "what about 30 qubits?" can inherit
        # the earlier cost and queue constraints. Do not attach the circuit-only
        # NEW_CIRCUIT instruction here; let the core agent classify the task.
        if conversation.active_artifact is None:
            parts = [
                "[LoomQ 多轮会话上下文]",
                "最近对话：",
            ]
            for turn in conversation.turns[-3:]:
                parts.append("用户：%s" % turn.user_text)
                parts.append("助手：%s" % turn.assistant_text)
            parts.extend(
                [
                    "[本轮用户请求]",
                    prompt,
                    (
                        "请结合最近对话解析本轮的指代和条件变更，并重新判断任务类型。"
                        "如果是在追问后端，继承未被本轮修改的后端约束；不要因为存在历史"
                        "对话就假定用户要生成电路。"
                    ),
                ]
            )
            if learning_instruction:
                parts.append("[讲解偏好：%s]" % learning_instruction)
            return "\n\n".join(parts)

        parts = [
            "[LoomQ 多轮会话上下文]",
            "本轮动作：%s" % action,
        ]
        artifact = conversation.active_artifact
        if artifact is not None:
            parts.extend(
                [
                    "当前电路：%s v%d" % (artifact.artifact_id, artifact.version),
                    "当前电路目标：%s" % artifact.goal,
                    "当前电路 QASM（这是指代‘它/刚才的电路’时的唯一依据）：",
                    artifact.qasm,
                ]
            )
        if conversation.turns:
            parts.append("最近对话：")
            for turn in conversation.turns[-3:]:
                parts.append("用户：%s" % turn.user_text)
                parts.append("助手：%s" % turn.assistant_text)

        parts.extend(["[本轮用户请求]", prompt, self._action_instruction(action)])
        if learning_instruction:
            parts.append("[讲解偏好：%s]" % learning_instruction)
        return "\n\n".join(parts)

    @staticmethod
    def _append_learning(prompt: str, instruction: Optional[str]) -> str:
        if not instruction:
            return prompt
        return "%s\n\n[讲解偏好：%s]" % (prompt, instruction)

    @staticmethod
    def _action_instruction(action: str) -> str:
        if action == MODIFY_CURRENT:
            return (
                "请基于当前 QASM 完成修改，返回完整的新 QASM；不要把它当成无关的新任务。"
            )
        if action == EXPLAIN_CURRENT:
            return (
                "请直接回答用户对当前电路的疑问，返回 task_type=explain_current，"
                "保持所有 QASM 字段为空，并在 explanation 中给出易懂、具体的解释。"
            )
        if action == RUN_CURRENT:
            return (
                "请保持当前 QASM 的电路逻辑不变，补全必要格式后运行并解释测量结果。"
            )
        return "请把它作为一个新的电路设计请求处理。"
