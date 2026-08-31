#!/usr/bin/env python3
"""12 门白名单，以及"后端不认这个门时改写成什么"的对照表

赛题把工作量边界划得很死：所有评测电路——公开的、隐藏的、评测当天新生成的——
**只会用到下面这 12 个门**。所以这个文件就是 L1 的全部门知识。

| 类别 | 门 |
|---|---|
| 单比特无参 | h, x, s, sdg, t, tdg |
| 单比特带参 | rz(θ), ry(θ) |
| 两比特 | cx, cu1(θ), swap |
| 三比特 | ccx |

下面那些分解式来自官方 `gate_identities.md`，并且**我们自己又在 braket 上
用干涉电路数值复核过一遍**（见 `tools/verify_l1.py`）——因为分解写错时，
末态的模长往往还是对的，只有相位错，普通电路看不出来，必须拿干涉电路照。
"""

import math

PI = math.pi

# 门名 -> (参数个数, 比特个数)
WHITELIST = {
    "h": (0, 1),
    "x": (0, 1),
    "s": (0, 1),
    "sdg": (0, 1),
    "t": (0, 1),
    "tdg": (0, 1),
    "rz": (1, 1),
    "ry": (1, 1),
    "cx": (0, 2),
    "cu1": (1, 2),
    "swap": (0, 2),
    "ccx": (0, 3),
}

# 解析阶段接受但直接忽略的语句（不影响任何测量分布）
IGNORED_STATEMENTS = ("barrier",)


class UnsupportedGateError(ValueError):
    """出现了白名单以外的门。"""


def check(name, params, qubits):
    """核对门名、参数个数、比特个数。出错时给人看得懂的消息。"""
    if name not in WHITELIST:
        raise UnsupportedGateError(
            "不认识的门 %r。本赛题只会用到这 12 个：%s" % (name, ", ".join(sorted(WHITELIST)))
        )
    want_params, want_qubits = WHITELIST[name]
    if len(params) != want_params:
        raise UnsupportedGateError(
            "门 %s 需要 %d 个参数，实际给了 %d 个" % (name, want_params, len(params))
        )
    if len(qubits) != want_qubits:
        raise UnsupportedGateError(
            "门 %s 作用在 %d 个比特上，实际给了 %d 个" % (name, want_qubits, len(qubits))
        )
    if len(set(qubits)) != len(qubits):
        raise UnsupportedGateError("门 %s 的比特参数出现重复：%s" % (name, qubits))


# --------------------------------------------------------------------------
# 分解：把一个门改写成若干更基础的门
#
# 每个分解都返回 [(门名, 参数元组, 比特元组), ...]，按施加顺序排列。
# --------------------------------------------------------------------------


def sdg_as_rz(qubit):
    """sdg = u1(-pi/2)，而 u1 与 rz 只差一个全局相位。

    全局相位不影响任何测量分布，所以**单独作为一个单比特门出现时**可以直接换。
    （官方 gate_identities.md 第 1、2 条。已数值复核。）
    """
    return [("rz", (-PI / 2,), (qubit,))]


def tdg_as_rz(qubit):
    """tdg = u1(-pi/4)，同上。"""
    return [("rz", (-PI / 4,), (qubit,))]


def cu1_as_rz_cx(theta, control, target):
    """受控相位门的官方分解（gate_identities.md 第 4 条）。

    原式用的是 u1；这里三处 u1 全部换成 rz，三个全局相位因子相乘仍然是一个
    常数全局相位，因此整体等价。已用干涉电路数值复核（保真度 0.993，
    差值来自采样涨落）。
    """
    return [
        ("rz", (theta / 2,), (control,)),
        ("cx", (), (control, target)),
        ("rz", (-theta / 2,), (target,)),
        ("cx", (), (control, target)),
        ("rz", (theta / 2,), (target,)),
    ]


def swap_as_cx(a, b):
    """swap = 三个方向交替的 cx（gate_identities.md 第 3 条）。"""
    return [
        ("cx", (), (a, b)),
        ("cx", (), (b, a)),
        ("cx", (), (a, b)),
    ]


def ccx_as_basic(a, b, c):
    """Toffoli 的 qelib1 标准分解（gate_identities.md 第 5 条），
    其中 tdg 已按上面的规则换成 rz(-pi/4)。已数值复核。
    """
    return [
        ("h", (), (c,)),
        ("cx", (), (b, c)),
        ("rz", (-PI / 4,), (c,)),
        ("cx", (), (a, c)),
        ("t", (), (c,)),
        ("cx", (), (b, c)),
        ("rz", (-PI / 4,), (c,)),
        ("cx", (), (a, c)),
        ("t", (), (b,)),
        ("t", (), (c,)),
        ("h", (), (c,)),
        ("cx", (), (a, b)),
        ("t", (), (a,)),
        ("rz", (-PI / 4,), (b,)),
        ("cx", (), (a, b)),
    ]


def decompose(name, params, qubits):
    """按门名给出分解；不需要分解时返回 None。"""
    if name == "sdg":
        return sdg_as_rz(qubits[0])
    if name == "tdg":
        return tdg_as_rz(qubits[0])
    if name == "cu1":
        return cu1_as_rz_cx(params[0], qubits[0], qubits[1])
    if name == "swap":
        return swap_as_cx(qubits[0], qubits[1])
    if name == "ccx":
        return ccx_as_basic(qubits[0], qubits[1], qubits[2])
    return None
