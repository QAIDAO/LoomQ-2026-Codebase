#!/usr/bin/env python3
"""Deterministic backend requirement extraction and hard-constraint matching.

任务书 §11 / §12 / §13 / §14 / §35 的后端需求模型。

* ``extract_requirements`` 用确定性规则/正则把自然语言转成
  :class:`BackendRequirements`（真机/模拟器、免费、零排队、账号、比特数）。
  不调用 LLM；LLM 只能输出结构化需求是任务书 §14 的要求，本模块预留
  ``BackendRequirements`` 这一结构化入口即可，Wave 3 可把 LLM 的结构化
  结果直接映射成 :class:`BackendRequirements` 再交给 :func:`match_backends`。
* ``match_backends`` 先做精确匹配（全部硬约束满足）；无精确匹配时绝不把
  LocalSimulator 之类说成“完全满足”，而是返回带“牺牲了哪些条件”标注的
  alternatives（任务书 §12/§13/§35 红线）。
* 后端 id 唯一来源是 ``adapter.load_backends()`` 返回的 ``Backend.id``，
  绝不硬编码任何 id。过滤/排序优先复用 ``adapter.filter_backend_candidates`` /
  ``adapter.choose_backend`` / ``adapter._closest_backend``（及其排序键
  ``adapter._violation_score``），本模块只负责把用户需求映射成
  ``adapter.BackendRequest``，以及为解释性输出计算每个备选的未满足项。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- 定位并导入 starter_kit.adapter（与 web_agent.py / server.py 同款引导） ---
APP_DIR = Path(__file__).resolve().parent
if (APP_DIR.parent / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent
elif (APP_DIR / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR / "starter_kit"
elif (APP_DIR.parent / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent / "starter_kit"
else:  # pragma: no cover - mirrors server.py bootstrap
    raise RuntimeError("Cannot locate the LoomQ starter_kit adapter")
for _root in (str(STARTER_KIT_ROOT.parent), str(STARTER_KIT_ROOT)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

try:
    from starter_kit import adapter  # type: ignore  # noqa: E402
except ModuleNotFoundError as exc:  # extracted submission root has no outer package
    if exc.name != "starter_kit":
        raise
    import adapter  # type: ignore  # noqa: E402


__all__ = [
    "BackendRequirements",
    "MatchResult",
    "extract_requirements",
    "match_backends",
]


# ---------------------------------------------------------------------------
# 需求模型
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BackendRequirements:
    """从自然语言抽取出的后端硬约束（规则提取，不经过 LLM）。

    字段语义（与任务书 §11 对齐）：
    * ``backend_type``：``None``=未指定，``"hardware"``=真机，``"simulator"``=模拟器，
      额外支持 ``"cloud"``=云端（kind 单独标注，见任务书 §5 的 kind 语义）。
    * ``free``：``True``=必须免费，``False``=明确不要求免费（区别于未指定），
      ``None``=未指定。
    * ``zero_queue``：``True``=必须零排队，``False``=明确不要求零排队，``None``=未指定。
    * ``account_required``：``False``=必须无需账号，``True``=可接受账号，``None``=未指定。
    * ``min_qubits``：电路需要的最少量子比特数，``None``=未指定。
    """

    backend_type: str | None = None
    free: bool | None = None
    zero_queue: bool | None = None
    account_required: bool | None = None
    min_qubits: int | None = None

    def to_hard_constraints(self) -> dict:
        """输出任务书 §11 的 JSON 形状：``{"hard_constraints": {...}, "preferences": {...}}``。

        只有已明确抽取（非 ``None``）的字段才进入 hard_constraints；preferences
        当前为空，预留 LLM 结构化偏好入口。
        """
        hard: dict = {}
        if self.backend_type is not None:
            hard["backend_type"] = self.backend_type
        if self.free is not None:
            hard["free"] = self.free
        if self.zero_queue is not None:
            hard["zero_queue"] = self.zero_queue
        if self.account_required is not None:
            hard["account_required"] = self.account_required
        if self.min_qubits is not None:
            hard["min_qubits"] = self.min_qubits
        return {"hard_constraints": hard, "preferences": {}}


@dataclass(frozen=True)
class MatchResult:
    """``match_backends`` 的返回结果。

    * ``exact_matches``：满足全部硬约束的后端（来自 ``adapter.filter_backend_candidates``）。
    * ``alternatives``：无精确匹配时的兜底列表，每项为 ``(Backend, 未满足条件列表)``。
      未满足条件是中文描述（例如 ``"不是真机（模拟器）"``、``"需要排队"``、``"需要账号"``），
      明确告诉调用方该备选牺牲了什么，绝不声称“完全满足”。
    * ``best_match``：单个推荐后端。有精确匹配时复用 ``adapter.choose_backend``；
      无精确匹配时复用 ``adapter._closest_backend``。
    * ``conflict_explanation``：无精确匹配时的冲突说明（结构化文本，不含硬编码事实）。
    * ``no_exact_match``：是否存在精确匹配。
    """

    exact_matches: tuple[adapter.Backend, ...] = ()
    alternatives: tuple[tuple[adapter.Backend, tuple[str, ...]], ...] = ()
    best_match: adapter.Backend | None = None
    conflict_explanation: str = ""
    no_exact_match: bool = False


# ---------------------------------------------------------------------------
# 规则提取的正则（确定性，不调用 LLM）
# ---------------------------------------------------------------------------

_KIND_WORD = {
    "simulator": "模拟器",
    "qpu": "真机",
    "cloud": "云端",
}

_HARDWARE_PATTERN = re.compile(
    r"真机|实机|硬件|(?<![a-z0-9_])qpu(?![a-z0-9_])|(?<![a-z0-9_])hardware(?![a-z0-9_])",
    re.IGNORECASE,
)
_SIMULATOR_PATTERN = re.compile(
    r"模拟器|仿真|(?<![a-z0-9_])simulator(?![a-z0-9_])", re.IGNORECASE
)
_CLOUD_PATTERN = re.compile(
    r"云端|云平台|(?<![a-z0-9_])cloud(?![a-z0-9_])", re.IGNORECASE
)

_FREE_NEGATED = re.compile(
    r"不要求(?:必须)?免费|免费(?:不是必须|可选|均可|无所谓)|不必免费|无需免费",
    re.IGNORECASE,
)
_FREE_POSITIVE = re.compile(
    r"免费|零费用|完全免费|(?<![a-z0-9_])free(?![a-z0-9_])", re.IGNORECASE
)

_ZERO_QUEUE_NEGATED = re.compile(
    r"不要求(?:必须)?(?:零排队|无排队)|(?:零排队|无排队)(?:也)?(?:不是必须|可选|均可)|"
    r"排队(?:也)?(?:可选|均可)",
    re.IGNORECASE,
)
_ZERO_QUEUE_POSITIVE = re.compile(
    r"零排队|无排队|无需排队|不用排队|(?<![a-z0-9_])no\s+queue(?![a-z0-9_])",
    re.IGNORECASE,
)

_ACCOUNT_NOT_REQUIRED = re.compile(
    r"无需账号|不用账号|免账号|不需要账号|无需注册|不用注册|免注册|无需登录",
    re.IGNORECASE,
)
_ACCOUNT_ACCEPTABLE = re.compile(
    r"需要账号|要求账号|必须账号|需注册|须注册|需要注册|需登录|可接受账号|可注册",
    re.IGNORECASE,
)

# 关键词前的否定窗口（“不要真机”“不免费”“不用排队”之类不当作需求）。
_NEGATION_PREFIX = re.compile(r"(?:不要|不需要|无需|不用|不是|别要|非|不)\s*$")


def _mentioned_positive(text: str, pattern: re.Pattern) -> bool:
    """pattern 命中的关键词若紧邻否定词则忽略，返回是否存在非否定提及。"""
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 8):match.start()]
        if _NEGATION_PREFIX.search(prefix):
            continue
        return True
    return False


def _extract_min_qubits(prompt: str) -> int | None:
    """提取用户声明的量子比特规模；复用 adapter 的去序数/中文数词解析。"""
    extract = getattr(adapter, "_extract_explicit_qubit_counts", None)
    if extract is not None:
        counts = extract(prompt)
        if counts:
            return max(int(v) for v in counts)
    # 兜底：阿拉伯数字 + 比特/位/qubit 单位。
    raw = re.findall(
        r"(\d+)\s*(?:个?\s*)?(?:量子)?(?:比特|位|qubits?)", prompt, re.IGNORECASE
    )
    if raw:
        return max(int(v) for v in raw)
    return None


def extract_requirements(prompt: str) -> BackendRequirements:
    """确定性规则提取后端需求（不调用 LLM）。"""
    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")
    text = prompt.strip()

    backend_type: str | None = None
    if _mentioned_positive(text, _HARDWARE_PATTERN):
        backend_type = "hardware"
    elif _mentioned_positive(text, _SIMULATOR_PATTERN):
        backend_type = "simulator"
    elif _mentioned_positive(text, _CLOUD_PATTERN):
        backend_type = "cloud"

    free: bool | None = None
    if _FREE_NEGATED.search(text):
        free = False  # 明确不要求免费（区别于未指定）
    elif _mentioned_positive(text, _FREE_POSITIVE):
        free = True

    zero_queue: bool | None = None
    if _ZERO_QUEUE_NEGATED.search(text):
        zero_queue = False
    elif _mentioned_positive(text, _ZERO_QUEUE_POSITIVE):
        zero_queue = True

    account_required: bool | None = None
    if _ACCOUNT_NOT_REQUIRED.search(text):
        account_required = False
    elif _ACCOUNT_ACCEPTABLE.search(text):
        account_required = True

    return BackendRequirements(
        backend_type=backend_type,
        free=free,
        zero_queue=zero_queue,
        account_required=account_required,
        min_qubits=_extract_min_qubits(text),
    )


# ---------------------------------------------------------------------------
# 需求 -> adapter.BackendRequest 的映射（复用 adapter 的过滤门面）
# ---------------------------------------------------------------------------

def _to_backend_request(req: BackendRequirements) -> adapter.BackendRequest:
    """把需求模型映射成 adapter 认识的硬约束请求。

    * ``backend_type`` -> ``device_types``（hardware=qpu / simulator=simulator / cloud=cloud）。
    * ``free=True`` -> ``cost_mode="free_only"``（免费严格指 cost=="free"，不包含 free_quota）。
    * ``zero_queue=True`` -> ``queue_exact="none"``。
    * ``account_required=False`` -> ``requires_account=False``；``True``（可接受账号）
      是软约束，不映射为硬约束 ``requires_account=True``（后者表示“必须要求账号”）。
    """
    device_types: tuple[str, ...] = ()
    if req.backend_type == "hardware":
        device_types = ("qpu",)
    elif req.backend_type == "simulator":
        device_types = ("simulator",)
    elif req.backend_type == "cloud":
        device_types = ("cloud",)

    cost_mode = "free_only" if req.free is True else None
    queue_exact = "none" if req.zero_queue is True else None
    requires_account = False if req.account_required is False else None

    return adapter.BackendRequest(
        required_qubits=req.min_qubits,
        device_types=device_types,
        queue_exact=queue_exact,
        cost_mode=cost_mode,
        requires_account=requires_account,
    )


def _unmet_conditions(backend: adapter.Backend, req: BackendRequirements) -> list[str]:
    """逐个硬约束说明该后端牺牲/未满足的条件（仅用于解释性输出，不参与过滤）。"""
    unmet: list[str] = []
    if req.backend_type == "hardware":
        if backend.kind != "qpu":
            label = _KIND_WORD.get(backend.kind, backend.kind)
            unmet.append(f"不是真机（{label}）")
    elif req.backend_type == "simulator":
        if backend.kind != "simulator":
            label = _KIND_WORD.get(backend.kind, backend.kind)
            unmet.append(f"不是模拟器（{label}）")
    elif req.backend_type == "cloud":
        if backend.kind != "cloud":
            label = _KIND_WORD.get(backend.kind, backend.kind)
            unmet.append(f"不是云端（{label}）")

    if req.free is True and backend.cost != "free":
        unmet.append("不是完全免费")
    if req.zero_queue is True and backend.queue != "none":
        unmet.append("需要排队")
    if req.account_required is False and backend.requires_account:
        unmet.append("需要账号")
    if req.min_qubits is not None and backend.max_qubits < req.min_qubits:
        unmet.append(f"最多支持 {backend.max_qubits} 比特，不足 {req.min_qubits} 比特")
    return unmet


def _conflict_explanation(req: BackendRequirements) -> str:
    parts: list[str] = []
    if req.backend_type == "hardware":
        parts.append("真机")
    elif req.backend_type == "simulator":
        parts.append("模拟器")
    elif req.backend_type == "cloud":
        parts.append("云端")
    if req.free is True:
        parts.append("免费")
    if req.zero_queue is True:
        parts.append("零排队")
    if req.account_required is False:
        parts.append("无需账号")
    if req.min_qubits is not None:
        parts.append(f"至少 {req.min_qubits} 比特")
    joined = "、".join(parts) if parts else "给定约束"
    return (
        f"能力表中没有任何后端同时满足硬约束（{joined}）；"
        "以下为最接近的备选，并逐一标注各自牺牲的条件。"
    )


# ---------------------------------------------------------------------------
# 匹配主入口
# ---------------------------------------------------------------------------

def match_backends(req: BackendRequirements, backends=None) -> MatchResult:
    """先做硬约束精确匹配；无精确匹配时返回带未满足标注的 alternatives。

    ``backends`` 默认取 ``adapter.load_backends()``；测试可注入自定义列表。
    结果中的所有 id 只可能来自能力表（``adapter.Backend.id``）。
    """
    if not isinstance(req, BackendRequirements):
        raise TypeError("req must be a BackendRequirements")

    if backends is None:
        backends = adapter.load_backends()
    else:
        backends = tuple(backends)

    request = _to_backend_request(req)

    # 1) 精确匹配：复用 adapter 的硬过滤，绝不另写一套过滤。
    exact = adapter.filter_backend_candidates(backends, request)

    if exact:
        return MatchResult(
            exact_matches=exact,
            alternatives=(),
            best_match=adapter.choose_backend(exact, request, backends),
            conflict_explanation="",
            no_exact_match=False,
        )

    # 2) 无精确匹配：构建带“未满足条件”标注的 alternatives，
    #    排序复用 adapter 的兜底排序键（_violation_score，与 _closest_backend 一致）。
    alternatives = [(backend, tuple(_unmet_conditions(backend, req))) for backend in backends]
    alternatives.sort(key=lambda pair: adapter._violation_score(pair[0], request, backends))

    return MatchResult(
        exact_matches=(),
        alternatives=tuple(alternatives),
        best_match=adapter._closest_backend(backends, request),
        conflict_explanation=_conflict_explanation(req),
        no_exact_match=True,
    )
