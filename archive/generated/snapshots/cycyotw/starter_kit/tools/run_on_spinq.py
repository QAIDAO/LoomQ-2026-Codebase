#!/usr/bin/env python3
"""把电路送上量旋云真机，并把原始结果存成证据（第二个平台）

赛题第五节 1：真机接入证据每个平台 5 分，至多两个平台。本源那一个见
`run_on_hardware.py`；这里是量旋。

**与本源那条路的三处不同**（都不是我挑的，是平台就这样）：

1. **认证方式**：本源用 API Token；量旋用**用户名 + RSA 私钥**，
   拿私钥给用户名签名去登录。私钥文件留在仓库外，路径从环境变量读。
2. **提交的东西**：本源收 OriginIR；量旋收它自己的 IR，由 spinqit 的
   QASM 编译器从 OpenQASM 2.0 编出来。所以这里送上去的是
   **本中间层给 spinq 目标输出的 OpenQASM 2.0**
   （见 target_ir_contract.md：SpinQ 用 OpenQASM 2.0），链条同样是我们的产物。
3. **机器类型**：可用的是**核磁**（NMR）真机，不是超导。核磁机的读出是系综平均，
   噪声特性与超导完全不同，别拿超导的直觉去看这边的数。

同样**不接进 `adapter.run()`**：那条路是评测器直接调的，必须留在无噪声模拟器上。

用法（需要 LOOMQ_SPINQ_USERNAME 与 LOOMQ_SPINQ_KEYFILE，从环境变量或 .env 读）：

    bash loomq.sh spinq --list                      # 只看平台，不提交
    bash loomq.sh spinq --submit --only bell
    bash loomq.sh spinq --collect
"""

import argparse
import json
import os
import pathlib
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.loomq import envfile, qasm_parser  # noqa: E402

try:
    from spinqit import SpinQCloudConfig, get_compiler, get_spinq_cloud
except ImportError:  # 没装也要能 --help
    SpinQCloudConfig = get_compiler = get_spinq_cloud = None

USERNAME_KEY = "LOOMQ_SPINQ_USERNAME"
KEYFILE_KEY = "LOOMQ_SPINQ_KEYFILE"

BACKEND_ID = "spinq_cloud_qpu"     # 官方《后端能力表》里的规范标识
EVIDENCE_DIR = os.path.join(_REPO_ROOT, "starter_kit", "evidence", "files")
TASKS_FILE = os.path.join(EVIDENCE_DIR, "spinq-tasks.json")

POLL_SECONDS = 30
DEFAULT_WAIT_MINUTES = 180
SHOTS = 1024

# 电路 -> 需要几个比特。平台按比特数选：2 比特的走 gemini_vp，3 比特的走 triangulum_vp。
# 名字与本源那边保持一致，两个平台的证据文件才能一眼对上。
CIRCUITS = [
    ("bell", os.path.join(_REPO_ROOT, "starter_kit", "circuits", "bell.qasm"), None),
    ("ghz3", os.path.join(_REPO_ROOT, "starter_kit", "circuits", "ghz3.qasm"), None),
    # 不对称电路，用来验位序。理由同本源那边：Bell 和 GHZ 的理想分布都是回文的，
    # 位序反了看不出来。
    ("bitorder", None, """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""),
]

EXPECTED_PEAKS = {
    "bell": {"00", "11"},
    "ghz3": {"000", "111"},
    "bitorder": {"01"},
}


def strip_measures(qasm):
    """去掉 measure 语句。

    量旋云**不接受显式 measure**：
        "SpinQ Cloud currently does not support explicit invocation of measure gates.
         A measure will be done automatically at the end of the circuit."
    这与本源正好相反（那边必须写 measure），也与赛题契约相反
    （transpile 的产物按 target_ir_contract 必须是完整可执行程序，含测量）。

    所以剥离只发生在**提交给量旋的那一刻**：
    `adapter.transpile()` 的产物一字不改，证据里存的也是带 measure 的原始产物；
    这里剥掉的只是送进它 SDK 的那一份副本。
    """
    kept = [line for line in qasm.splitlines()
            if not line.strip().lower().startswith("measure")]
    return "\n".join(kept) + "\n"


def load_qasm(path, inline):
    if inline is not None:
        return inline
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def connect():
    if get_spinq_cloud is None:
        raise RuntimeError(
            "没装 spinqit，跑不了量旋真机。用 `bash loomq.sh spinq ...` 启动，"
            "它会单独建一个环境，不动提交用的那套锁定依赖。")
    envfile.load()
    username = os.environ.get(USERNAME_KEY)
    keyfile = os.environ.get(KEYFILE_KEY)
    missing = [k for k, v in ((USERNAME_KEY, username), (KEYFILE_KEY, keyfile)) if not v]
    if missing:
        raise RuntimeError(
            "缺少 %s。量旋用「用户名 + RSA 私钥」登录，不是 API Token：\n"
            "    %s=<你的量旋用户名>\n"
            "    %s=<私钥文件路径，例如 ~/.spinq_key>\n"
            "私钥文件请留在仓库外，只把路径写进 .env。"
            % ("、".join(missing), USERNAME_KEY, KEYFILE_KEY))
    keyfile = os.path.expanduser(keyfile)
    if not os.path.isfile(keyfile):
        raise RuntimeError("私钥文件不存在：%s" % keyfile)
    return get_spinq_cloud(username, keyfile)


def show_platforms(cloud):
    print("量旋云平台：")
    usable = []
    for p in cloud.platforms:
        kind = "模拟器" if p.simu else "真机"
        # machine_count 为 0 表示当前没有可用机器——投上去也只是排队等一台不存在的机器
        free = p.machine_count > 0
        print("   %-20s %-24s %2d 比特  %s  可用机器 %d %s"
              % (p.code, p.name, p.max_bitnum, kind, p.machine_count,
                 "" if free else "（暂无可用机器）"))
        if free and not p.simu:
            usable.append(p)
    return usable


def pick_platform(cloud, qubits, wanted=None):
    """按比特数挑一台**有可用机器**的真机，挑最小够用的那台。

    挑最小的，是因为核磁机的比特越多、退相干越难压，小机器上的数据反而更干净。
    """
    candidates = [p for p in cloud.platforms
                  if not p.simu and p.machine_count > 0 and p.max_bitnum >= qubits]
    if wanted:
        candidates = [p for p in candidates if p.code == wanted]
    if not candidates:
        raise RuntimeError(
            "没有满足 %d 比特且当前有可用机器的真机。"
            "（machine_count 为 0 的平台投上去只是排队等一台不存在的机器。）" % qubits)
    return min(candidates, key=lambda p: p.max_bitnum)


def submit(cloud, only=None, shots=SHOTS, platform_code=None):
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    # 先读已有的再追加。本源那边踩过：第二次提交把整个文件覆盖，上一批 task id 全丢。
    tasks = []
    if os.path.isfile(TASKS_FILE):
        try:
            with open(TASKS_FILE, encoding="utf-8") as handle:
                tasks = json.load(handle)
        except (OSError, ValueError):
            tasks = []

    compiler = get_compiler("qasm")
    selected = [c for c in CIRCUITS if only is None or c[0] == only]
    if not selected:
        raise RuntimeError("没有叫 %r 的电路。可选：%s"
                           % (only, "、".join(c[0] for c in CIRCUITS)))

    for name, path, inline in selected:
        qasm = load_qasm(path, inline)
        # ★ 送上去的是我们中间层给 spinq 目标输出的 OpenQASM 2.0
        emitted = adapter.transpile(qasm, "spinq")
        circuit = qasm_parser.parse(qasm)
        platform = pick_platform(cloud, circuit.num_qubits, platform_code)

        # spinqit 的编译器只接受文件路径，所以先落到临时文件
        scratch = os.path.join(EVIDENCE_DIR, ".spinq-%s.qasm" % name)
        with open(scratch, "w", encoding="utf-8") as handle:
            handle.write(strip_measures(emitted))
        try:
            ir = compiler.compile(scratch, 0)
        finally:
            os.remove(scratch)

        config = SpinQCloudConfig()
        config.configure_platform(platform.code)
        config.configure_shots(shots)

        print("提交 %s → %s（%s，%d 比特，shots=%d）…"
              % (name, platform.code, platform.name, circuit.num_qubits, shots))
        task = cloud.submit_task(ir, config)
        task_id = _task_id(task)
        print("   task_id = %s" % task_id)

        tasks = [t for t in tasks if t.get("name") != name]
        tasks.append({
            "name": name,
            "task_id": str(task_id),
            "shots": shots,
            "platform_code": platform.code,
            "platform_name": platform.name,
            "qasm": qasm,
            "emitted_qasm": emitted,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        with open(TASKS_FILE, "w", encoding="utf-8") as handle:
            json.dump(tasks, handle, ensure_ascii=False, indent=2)

    print("\n%d 个任务在册，task_id 存在 %s" % (len(tasks), TASKS_FILE))
    return tasks


def top_k(counts, expected):
    """理想分布里有几个峰，就取实测的前几名来比。

    赛题第五节 1 的原话是「counts 的 **Top-K 主导态**与理想分布一致
    （真机允许噪声，只查主峰）」。K 就是理想分布里非零态的个数。

    原先我用的是"占比 ≥5% 即算主峰"——那是我自己发明的判据，比赛题严。
    在超导机上两者结论相同，一上核磁机就露馅了：量旋的 2 比特核磁机
    Bell 实测 00 55.8% / 11 30.3% / **10 13.2%**，按 5% 判就"多出一个峰"，
    按 Top-2 判则正确。核磁的读出是系综平均，噪声本来就比超导大一个量级。
    """
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return {key for key, _ in ranked[:len(expected)]}


def _task_id(task):
    """把 submit_task 的返回值里的任务号抠出来。

    实测它返回的是一个元组 `(200, '', 'G-260806-0003')`——状态码、消息、任务号。
    照 str() 存下来就是整个元组，取结果时对不上。
    对象形态（有 task_id / id 属性）也一并处理，免得平台哪天改了返回类型。
    """
    for attr in ("task_id", "id"):
        value = getattr(task, attr, None)
        if value:
            return str(value)
    if isinstance(task, (tuple, list)) and task:
        return str(task[-1])
    return str(task)


def normalize(raw, qasm, shots):
    """归一成赛题规范：key = c[n-1]…c[0]，最右是 c[0]；值折算成计数。

    平台返回概率还是计数，先看再说——本源那边就是返回概率而 get_counts() 是空的，
    这类事**不要凭上一个平台的经验去猜**。
    """
    circuit = qasm_parser.parse(qasm)
    width = max((op.clbit for op in circuit.measurements), default=0) + 1
    values = list(raw.values())
    kind = "counts"
    if values and all(isinstance(v, float) for v in values) and abs(sum(values) - 1.0) < 1e-3:
        kind = "probabilities"
    out = {}
    for key, value in raw.items():
        text = key if isinstance(key, str) else format(int(key), "0%db" % width)
        text = text.zfill(width)
        # ★ 量旋的位串顺序与赛题规范**相反**，必须翻过来。
        #
        # 赛题规定 counts 的 key = c[n-1]…c[0]，最右一位是 c[0]。
        # 量旋返回的是从 q0 往右排。实测证据：电路 `x q[0]`（只把比特 0 翻成 1），
        # 按规范主峰应为 "01"，量旋给的是 "10" 占 95.31%。
        #
        # **这件事 Bell 和 GHZ 永远测不出来**：它们的理想分布是回文的
        # （00/11、000/111），翻不翻都一样。所以才专门跑了这条不对称电路。
        # 位序归一化本来就是"通用中间层"的职责之一（赛题第四节原文）。
        text = text[::-1]
        out[text] = out.get(text, 0) + (
            int(round(value * shots)) if kind == "probabilities" else int(value))
    return out, kind


def collect(cloud, tasks, wait_minutes):
    deadline = time.monotonic() + wait_minutes * 60
    pending = {t["task_id"]: t for t in tasks}
    while pending and time.monotonic() < deadline:
        for task_id in list(pending):
            task = pending[task_id]
            try:
                result = cloud.get_task_result(task_id)
            except Exception as exc:  # noqa: BLE001
                print("%s 还在排队/运行，或查询出错：%s" % (task["name"], str(exc)[:160]))
                continue
            raw = getattr(result, "probabilities", None) or getattr(result, "counts", None) or result
            if not raw or not isinstance(raw, dict):
                print("%s 还没有可用结果（拿到 %r）" % (task["name"], type(raw).__name__))
                continue

            counts, kind = normalize(raw, task["qasm"], task["shots"])
            payload = {
                "backend": BACKEND_ID,
                "job_id": task["task_id"],
                "shots": task["shots"],
                "counts": counts,
                "bit_order": "little",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "meta": {
                    "platform_code": task["platform_code"],
                    "platform_name": task["platform_name"],
                    "submitted_at": task["submitted_at"],
                    "platform_raw_kind": kind,
                    "bit_order_note": "量旋返回的位串是 q0 在左，与赛题规范相反；"
                                      "本文件的 counts 已按规范翻转为 c[n-1]…c[0]。"
                                      "原始未翻转的数据见 platform_raw。",
                    "platform_raw": raw,
                    "submitted_ir": "OpenQASM 2.0（由本提交的中间层输出，spinq 目标）",
                    "emitted_qasm": task["emitted_qasm"],
                },
            }
            out = os.path.join(EVIDENCE_DIR, "spinq-%s-result.json" % task["name"])
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            print("\n✅ %s 完成 → %s" % (task["name"], os.path.relpath(out, _REPO_ROOT)))
            total = sum(counts.values()) or 1
            for key, value in sorted(counts.items(), key=lambda kv: -kv[1])[:6]:
                print("     %s  %6.2f%%  (%d)" % (key, 100.0 * value / total, value))
            expected = EXPECTED_PEAKS.get(task["name"])
            if expected:
                top = top_k(counts, expected)
                print("     主峰 %s，应为 %s  %s"
                      % ("/".join(sorted(top)), "/".join(sorted(expected)),
                         "✅" if top == expected else "❌"))
            pending.pop(task_id)
        if pending:
            time.sleep(POLL_SECONDS)

    if pending:
        print("\n还有 %d 个没回来：%s" % (len(pending), "、".join(t["name"] for t in pending.values())))
        print("稍后再跑 --collect 即可，task_id 已经存好了。")


def main():
    parser = argparse.ArgumentParser(description="把电路送上量旋云真机并存下证据")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="只列平台，不提交（不花额度）")
    group.add_argument("--submit", action="store_true", help="只提交，存下 task_id 就退出")
    group.add_argument("--collect", action="store_true", help="只取回之前提交的任务")
    parser.add_argument("--only", choices=[c[0] for c in CIRCUITS], help="只跑其中一条")
    parser.add_argument("--platform", help="指定平台代号（默认按比特数挑最小够用且有机器的）")
    parser.add_argument("--shots", type=int, default=SHOTS, help="采样次数（默认 %d）" % SHOTS)
    parser.add_argument("--wait", type=int, default=DEFAULT_WAIT_MINUTES,
                        help="最多等多少分钟（默认 %d）" % DEFAULT_WAIT_MINUTES)
    args = parser.parse_args()

    try:
        cloud = connect()
    except RuntimeError as exc:
        print(exc)
        return 2

    if args.list:
        show_platforms(cloud)
        return 0

    if args.collect:
        if not os.path.isfile(TASKS_FILE):
            print("没有找到 %s，先跑一次 --submit。" % TASKS_FILE)
            return 2
        with open(TASKS_FILE, encoding="utf-8") as handle:
            tasks = json.load(handle)
    else:
        show_platforms(cloud)
        print()
        try:
            tasks = submit(cloud, only=args.only, shots=args.shots,
                           platform_code=args.platform)
        except RuntimeError as exc:
            print("\n提交失败：%s" % exc)
            return 1
        if args.submit:
            print("\n稍后用 --collect 取结果。")
            return 0

    collect(cloud, tasks, args.wait)
    return 0


if __name__ == "__main__":
    sys.exit(main())
