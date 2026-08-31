#!/usr/bin/env python3
"""backend_selector 单元测试 - 任务书 §11/§12/§13/§14/§35。

覆盖确定性规则提取 + 硬约束精确匹配 + 无精确匹配时的 alternatives 红线。
全部测试不调用 LLM、不联网。
"""

from __future__ import annotations

from starter_kit import adapter
from starter_kit.quantumhelper_web import backend_selector
from starter_kit.quantumhelper_web.backend_selector import (
    BackendRequirements,
    extract_requirements,
    match_backends,
)


def _backend_ids():
    return {backend.id for backend in adapter.load_backends()}


# ---------------------------------------------------------------------------
# extract_requirements：确定性规则提取
# ---------------------------------------------------------------------------

def test_extract_hardware_free_zero_queue_no_account():
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    assert req.backend_type == "hardware"
    assert req.free is True
    assert req.zero_queue is True
    assert req.account_required is False


def test_extract_qubits_zero_queue_free():
    req = extract_requirements("我需要运行一个 15 比特电路，要求零排队并且免费")
    assert req.min_qubits == 15
    assert req.zero_queue is True
    assert req.free is True
    # 未提及真机/模拟器/账号
    assert req.backend_type is None
    assert req.account_required is None


def test_extract_simulator():
    req = extract_requirements("我想用本地模拟器跑")
    assert req.backend_type == "simulator"


def test_extract_free_not_required_is_false_not_none():
    # “不要求免费/免费可选”是“明确不要求”，必须区别于未指定（None）。
    req = extract_requirements("免费可选，我都可以")
    assert req.free is False
    assert req.free is not None


def test_extract_to_hard_constraints_shape():
    req = extract_requirements("我要真机、免费、零排队、无需账号，15 比特")
    payload = req.to_hard_constraints()
    assert set(payload) == {"hard_constraints", "preferences"}
    assert payload["hard_constraints"]["backend_type"] == "hardware"
    assert payload["hard_constraints"]["free"] is True
    assert payload["hard_constraints"]["zero_queue"] is True
    assert payload["hard_constraints"]["account_required"] is False
    assert payload["hard_constraints"]["min_qubits"] == 15


# ---------------------------------------------------------------------------
# match_backends：hard filter 先行 + §12/§13/§35 红线
# ---------------------------------------------------------------------------

def test_impossible_hardware_request_has_no_exact_match():
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    result = match_backends(req)
    assert result.no_exact_match is True
    assert result.exact_matches == ()
    assert len(result.alternatives) > 0


def test_no_backend_claimed_fully_satisfied():
    # 红线：无精确匹配时，绝不把任何后端标成“完全满足全部条件”。
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    result = match_backends(req)
    for _backend, unmet in result.alternatives:
        assert len(unmet) > 0, f"{_backend.id} 被误标为完全满足"


def test_simulator_alternatives_flagged_not_hardware():
    # 真机请求下，simulator 类备选必须明确标注“不是真机”。
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    result = match_backends(req)
    flagged = [
        (_backend.id, unmet)
        for _backend, unmet in result.alternatives
        if _backend.kind == "simulator"
    ]
    assert flagged, "expected at least one simulator alternative"
    for _bid, unmet in flagged:
        assert any("不是真机" in u for u in unmet), f"{_bid} 未标注“不是真机”: {unmet}"


def test_backend_ids_come_from_catalog():
    # 结果里的 id 只允许是能力表 Backend.id，绝不硬编码。
    valid_ids = _backend_ids()
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    result = match_backends(req)
    for _backend, _unmet in result.alternatives:
        assert _backend.id in valid_ids
    assert result.best_match is not None
    assert result.best_match.id in valid_ids


def test_satisfiable_simulator_request_has_exact_match():
    # 可满足的请求应走精确匹配分支，且不把真机/云端混进来。
    req = extract_requirements("模拟器、免费、零排队、无需账号")
    result = match_backends(req)
    assert result.no_exact_match is False
    assert len(result.exact_matches) > 0
    assert all(b.kind == "simulator" for b in result.exact_matches)
    assert result.best_match is not None


def test_15_qubit_free_zero_queue_exact_matches():
    # 15 比特 + 免费 + 零排队：三个本地模拟器都应精确满足（>=15、free、none）。
    req = extract_requirements("我需要运行一个 15 比特电路，要求零排队并且免费")
    result = match_backends(req)
    assert result.no_exact_match is False
    matched_ids = {b.id for b in result.exact_matches}
    for b in result.exact_matches:
        assert b.kind == "simulator"
        assert b.max_qubits >= 15
        assert b.cost == "free"
        assert b.queue == "none"
    assert "braket_local_simulator" in matched_ids


def test_alternative_explains_unmet_each_condition():
    # 对“真机+免费+零排队+无需账号”，真机备选应同时标注收费/排队/账号等牺牲。
    req = extract_requirements("我要真机、免费、零排队、无需账号")
    result = match_backends(req)
    qpu_alts = [(b, unmet) for b, unmet in result.alternatives if b.kind == "qpu"]
    assert qpu_alts, "expected qpu alternatives"
    for b, unmet in qpu_alts:
        joined = "|".join(unmet)
        assert "不是完全免费" in joined
        assert "需要排队" in joined
        assert "需要账号" in joined
