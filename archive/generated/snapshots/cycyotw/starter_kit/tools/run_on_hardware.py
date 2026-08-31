#!/usr/bin/env python3
"""把电路送上本源悟空真机，并把原始结果存成证据

赛题第五节 1「真机接入证据（10 分）」要求提交真机返回的原始 `result.json`，
评测组核验 Schema、Top-K 主导态、以及 **job_id 能在平台控制台溯源**
（"评测组将抽样登录平台复核 job_id，无法溯源的记录按无效处理"）。

**这个脚本刻意不接进 `adapter.run()`。** 那个函数是评测器直接调的，
必须稳定跑在无噪声模拟器上（阈值 0.97，真机噪声必然不达标）。
真机是另一件事：出证据，不参与自动评测。

送上去的是**我们自己中间层转译出来的 OriginIR**，不是原始 QASM——
这一点是有意的：它证明这套中间层真的能驱动真实硬件，而不只是能驱动模拟器。

用法（需要 LOOMQ_ORIGINQ_TOKEN，从环境变量或 .env 读）：

    python3 starter_kit/tools/run_on_hardware.py            # 提交并等结果
    python3 starter_kit/tools/run_on_hardware.py --submit   # 只提交，存下 task_id
    python3 starter_kit/tools/run_on_hardware.py --collect  # 取回之前提交的任务

平台维护时提交会被直接挡回来（实测原话："Quantum computer under maintenance"）。
这种失败不建任务、不扣机时，所以可以让它盯着重试：

    ... --submit --only bell --shots 1000 --retry-minutes 240

排队是小时级的，所以提交和取回分开：**task_id 一拿到就落盘**，
中途断网、关机、换一台机器都不会把任务弄丢。
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

# ★ 用 pyqpanda3（新一代 SDK），不用提交环境里那个 pyqpanda 3.8.5。
#
# 旧 SDK 只认数字 chip_id，枚举里最新的是 `origin_72`（第三代 72 比特悟空），
# 官方教程也还写着"最新的悟空72比特芯片"。但平台早换代了：实际在线的是
# WK_C180 / WK_C180_2（第四代 180 比特），而 72 那颗返回
# "Quantum computer under maintenance"——**不是平台在维护，是打错了门。**
# 这一条是看控制台截图才发现的，赛题的《后端能力表》里写的也还是 72。
#
# 新 SDK 用**后端名字**而不是数字，并且有 backends() 可以先查在线状态——
# 投之前就能确认目标活着，正好补上"猜 chip_id 会白烧机时"这个风险。
try:
    from pyqpanda3 import intermediate_compiler as ic
    from pyqpanda3.qcloud import JobStatus, QCloudJob, QCloudService
except ImportError:  # 没装也要能 --help
    ic = QCloudService = QCloudJob = JobStatus = None

# 优先用第四代，退到备机。名字来自 backends() 的实际返回，不是猜的。
PREFERRED_BACKENDS = ("WK_C180", "WK_C180_2")

BACKEND_ID = "originq_wukong"          # 与官方《后端能力表》里的规范标识一致

# 新注册用户只有 60 秒机时，所以默认值按**省着用**定，不按模拟器那套定。
# 真机证据的判据是"Top-K 主导态与理想分布一致"（真机允许噪声，只查主峰），
# 不是 0.97 保真度——2000 次采样足够把主峰和噪声分开，8192 只是浪费机时。
SHOTS = 2000
EVIDENCE_DIR = os.path.join(_REPO_ROOT, "starter_kit", "evidence", "files")
TASKS_FILE = os.path.join(EVIDENCE_DIR, "originq-tasks.json")

POLL_SECONDS = 30
DEFAULT_WAIT_MINUTES = 180


# 要跑哪几条。前两条是官方公开电路（评测组核验主导态用），
# 第三条是我们自己加的：**它不对称，所以能验位序**。
#
# Bell 和 GHZ 的分布都是回文的（00/11、000/111），位序错了看不出来——
# 这个盲区在模拟器上已经吃过一次亏。|01> 只有一个比特是 1，
# 按赛题规范（key 最右是 c[0]）正确结果必须是 "01"，反了就是 "10"。
CIRCUITS = [
    ("bell", os.path.join(_REPO_ROOT, "starter_kit", "circuits", "bell.qasm"), None),
    ("ghz3", os.path.join(_REPO_ROOT, "starter_kit", "circuits", "ghz3.qasm"), None),
    ("bitorder", None, """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""),
]


def load_qasm(path, inline):
    if inline is not None:
        return inline
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def connect():
    if QCloudService is None:
        raise RuntimeError(
            "没装 pyqpanda3，跑不了真机。用 `bash loomq.sh hardware ...` 启动，"
            "它会单独建一个环境装 pyqpanda3，不动提交用的那套锁定依赖。")
    envfile.load()
    token = os.environ.get(envfile.HARDWARE_KEY)
    if not token:
        raise RuntimeError(
            "缺少 %s。去本源量子云个人中心申请 API Token，写进 .env（不要写进源码，"
            "也不要提交进仓库）：\n    %s=<你的 Token>"
            % (envfile.HARDWARE_KEY, envfile.HARDWARE_KEY)
        )
    return QCloudService(token)


def pick_backend(service, wanted=None):
    """挑一台在线的真机。**投之前先确认它活着**，这是新 SDK 才有的保险。"""
    available = service.backends()
    print("平台后端状态：")
    for name, online in sorted(available.items()):
        print("   %-24s %s" % (name, "在线" if online else "不可用"))
    order = (wanted,) if wanted else PREFERRED_BACKENDS
    for name in order:
        if available.get(name):
            print("\n选用 %s" % name)
            return service.backend(name), name
    raise RuntimeError(
        "想用的真机都不在线（%s）。在线的有：%s"
        % ("、".join(order), "、".join(n for n, ok in available.items() if ok) or "无"))


# 平台把请求挡回来时的说法。命中这些就**重试**，因为这类失败是平台侧的，
# 任务根本没建起来，不扣机时——重试是免费的。
#
# 实测撞到过：`Quantum computer under maintenance. Please try again later.`
# 维护窗口可能是几小时，而这一步失败就是白等，所以值得自动盯着。
TRANSIENT_HINTS = (
    "maintenance", "try again", "busy", "timeout", "timed out",
    "temporarily", "unavailable", "503", "502",
)

RETRY_SECONDS = 120


def is_transient(exc):
    text = str(exc).lower()
    return any(hint in text for hint in TRANSIENT_HINTS)


def submit_one(backend, prog, shots, name, retry_minutes):
    """提交一条，被平台临时挡回来就等一会再试。

    只重试**临时性**失败。Token 错、程序不合法这类问题重试一万次也一样，
    那种直接抛出来，别把人晾在一个永远转圈的循环里。
    """
    deadline = time.monotonic() + retry_minutes * 60
    attempt = 0
    while True:
        attempt += 1
        try:
            job = backend.run([prog], shots)
            return job.job_id()
        except Exception as exc:  # noqa: BLE001
            if not is_transient(exc):
                raise
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "%s：平台一直没恢复，已重试 %d 次。原话：%s" % (name, attempt, exc)
                ) from exc
            left = int((deadline - time.monotonic()) / 60)
            print("   平台暂时不收（第 %d 次）：%s" % (attempt, exc))
            print("   %d 秒后重试，还会再试 %d 分钟。任务没建起来，不扣机时。"
                  % (RETRY_SECONDS, left))
            time.sleep(RETRY_SECONDS)


def submit(backend, backend_name, only=None, shots=SHOTS, retry_minutes=0):
    """提交电路，task_id 立刻落盘。

    `only` 用来先只投一条：真机是要扣额度的，而我查不到官方公开的计费细则，
    所以正确做法是**先花最小的一笔把真实代价问出来**，而不是照着猜的数字一次投完。
    """
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # ★ 先把已有的读进来，**不要从空列表开始**。
    #   踩过：第二次 --submit 把整个文件覆盖了，上一批的 job_id 全没了。
    #   那次运气好（结果已经取回来了），但如果被覆盖的是还在排队的任务，
    #   job_id 一丢就再也找不回来——而"不弄丢 job_id"正是这个文件存在的理由。
    tasks = []
    if os.path.isfile(TASKS_FILE):
        try:
            with open(TASKS_FILE, encoding="utf-8") as handle:
                tasks = json.load(handle)
        except (OSError, ValueError):
            tasks = []

    selected = [c for c in CIRCUITS if only is None or c[0] == only]
    if not selected:
        raise RuntimeError("没有叫 %r 的电路。可选：%s"
                           % (only, "、".join(c[0] for c in CIRCUITS)))
    for name, path, inline in selected:
        qasm = load_qasm(path, inline)
        # ★ 送上去的是我们自己转译出来的 OriginIR，不是原始 QASM。
        originir = adapter.transpile(qasm, "originq")

        # 用 SDK 自己的解析器把 OriginIR 变成 QProg 再提交。
        # 证据链条完整：我们的 QASM → 我们的 OriginIR → SDK 解析 → 真机。
        # （已本地验证过来回转换一字不差，这一步不花机时。）
        prog = ic.convert_originir_string_to_qprog(originir)

        print("提交 %s（shots=%d）…" % (name, shots))
        task_id = submit_one(backend, prog, shots, name, retry_minutes)
        print("   task_id = %s" % task_id)
        # 同名的旧记录换掉（重投同一条电路），其余一概保留
        tasks = [t for t in tasks if t.get("name") != name]
        tasks.append({
            "name": name,
            "task_id": str(task_id),
            "shots": shots,
            "backend_name": backend_name,
            "qasm": qasm,
            "originir": originir,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        # 每提交一条就写一次盘，不攒到最后——中途出事也不会把已提交的任务弄丢
        with open(TASKS_FILE, "w", encoding="utf-8") as handle:
            json.dump(tasks, handle, ensure_ascii=False, indent=2)
    print("\n%d 个任务已提交，task_id 存在 %s" % (len(tasks), TASKS_FILE))
    print("→ 现在去本源量子云控制台看一眼**机时还剩多少**，再决定后面投不投。")
    return tasks


def normalize(counts, qasm, shots, source="counts"):
    """把平台返回的结果归一成赛题规范：key = c[n-1]…c[0]，最右是 c[0]。

    悟空 180 实际返回的是**概率**（和为 1 的浮点），不是计数。这里统一折算成计数，
    并把原始形态记进 meta——**不要猜，把看到的东西如实记下来**。
    """
    circuit = qasm_parser.parse(qasm)
    width = max((op.clbit for op in circuit.measurements), default=0) + 1

    raw_kind = source
    if source == "counts":
        total = sum(counts.values())
        if total and abs(total - 1.0) < 1e-6 and all(isinstance(v, float) for v in counts.values()):
            raw_kind = "probabilities"

    as_counts = {}
    for key, value in counts.items():
        text = key if isinstance(key, str) else format(int(key), "0%db" % width)
        text = text.zfill(width)
        as_counts[text] = as_counts.get(text, 0) + (
            int(round(value * shots)) if raw_kind == "probabilities" else int(value)
        )
    return as_counts, raw_kind


def _safe(getter):
    """取平台的可选字段。取不到就记 None——有的字段平台压根不返回。"""
    try:
        return getter()
    except Exception as exc:  # noqa: BLE001
        return "（平台未返回：%s）" % exc


def collect(tasks, wait_minutes):
    """按存下来的 job_id 取结果。

    job_id 能单独重建成 QCloudJob，所以取回**不依赖提交时那个进程**——
    关机、换机器、隔一天再来都行，这正是排队小时级时必须有的性质。
    """
    deadline = time.monotonic() + wait_minutes * 60
    pending = {task["task_id"]: task for task in tasks}
    done = []

    while pending and time.monotonic() < deadline:
        for task_id in list(pending):
            task = pending[task_id]
            try:
                job = QCloudJob(task_id)
                status = job.status()
            except Exception as exc:  # noqa: BLE001
                print("查询 %s 出错（稍后重试）：%s" % (task["name"], exc))
                continue

            if status == JobStatus.FAILED:
                print("❌ %s 平台判失败（job_id %s），不再等它。" % (task["name"], task_id))
                pending.pop(task_id)
                continue
            if status != JobStatus.FINISHED:
                print("%s：%s" % (task["name"], status.name))
                continue

            # query() 取已完成的结果，不阻塞（result() 会阻塞等待）
            res = job.query()

            # ★ 悟空 180 返回的是**概率**，`get_counts()` 是空字典。
            #   实测：get_counts() -> {}，而 get_probs() -> {'00': 0.381, '11': 0.599, ...}
            #   所以两个都要试，并且如实记下拿到的是哪一种——不要默默当成 counts。
            raw = res.get_counts()
            source = "counts"
            if not raw:
                raw = res.get_probs()
                source = "probabilities"
            if not raw:
                print("%s 状态已完成但两种取法都是空：%s"
                      % (task["name"], res.error_message() or "（平台没给错误信息）"))
                continue

            counts, raw_kind = normalize(raw, task["qasm"], task["shots"], source)
            payload = {
                "backend": BACKEND_ID,
                "job_id": task_id,
                "shots": task["shots"],
                "counts": counts,
                "bit_order": "little",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "meta": {
                    "backend_name": task["backend_name"],
                    "chip": "本源悟空 180（第四代超导，180 计算比特）",
                    "submitted_at": task["submitted_at"],
                    "platform_raw_kind": raw_kind,
                    "platform_raw": raw,
                    # 平台自己的原始应答与计时。job_id 的可溯源性靠这一段——
                    # 评测组会抽样登录平台复核，这里存的是平台原话，不是我们的转述。
                    "platform_origin_data": _safe(res.origin_data),
                    "platform_timing_info": _safe(res.timing_info),
                    "submitted_ir": "OriginIR（由本提交的中间层从 OpenQASM 2.0 转译）",
                    "originir": task["originir"],
                },
            }
            out = os.path.join(EVIDENCE_DIR, "originq-wukong-%s-result.json" % task["name"])
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            print("\n✅ %s 完成 → %s" % (task["name"], os.path.relpath(out, _REPO_ROOT)))
            for key, value in sorted(counts.items(), key=lambda kv: -kv[1])[:6]:
                print("     %s  %6.2f%%  (%d)" % (key, 100.0 * value / max(1, task["shots"]), value))
            done.append(task["name"])
            pending.pop(task_id)

        if pending:
            time.sleep(POLL_SECONDS)

    if pending:
        print("\n还有 %d 个没回来：%s" % (len(pending), "、".join(t["name"] for t in pending.values())))
        print("排队是小时级的，稍后再跑 --collect 即可，job_id 已经存好了。")
    return done


# 各电路的理想主峰。真机允许噪声，评测组只核验 Top-K 主导态是否命中
# （赛题第五节 1），所以这里比的是"主峰是不是这几个"，不是保真度。
EXPECTED_PEAKS = {
    "bell": {"00", "11"},
    "ghz3": {"000", "111"},
    "bitorder": {"01"},          # x q[0] 之后，key 最右为 c[0] -> 主峰必须是 01
}


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


def verify():
    """把每份结果与平台自己导出的那份逐位对一遍，并核验主峰。

    为什么值得单独做成一个命令：`result.json` 是我们的程序抓的，
    平台导出的那份是使用者从控制台点下来的——**两条独立路径**。
    逐位一致，就排除了"我们在归一化时把数据弄坏了"这一整类问题；
    而评测组抽样复核 job_id 时，看到的也是同一组数。评委可以自己跑这条命令。
    """
    results = sorted(pathlib.Path(EVIDENCE_DIR).glob("originq-wukong-*-result.json"))
    if not results:
        print("还没有任何真机结果。先跑 --submit / --collect。")
        return 1

    all_ok = True
    for path in results:
        name = path.name[len("originq-wukong-"):-len("-result.json")]
        ours = json.loads(path.read_text(encoding="utf-8"))
        counts = ours["counts"]
        expected_peaks = EXPECTED_PEAKS.get(name)
        top = top_k(counts, expected_peaks) if expected_peaks else set()

        print("=== %s（job_id %s）===" % (name, ours["job_id"]))
        expected = expected_peaks
        if expected:
            ok = top == expected
            all_ok &= ok
            print("  主峰 %s，应为 %s  %s"
                  % ("/".join(sorted(top)), "/".join(sorted(expected)), "✅" if ok else "❌"))

        export = path.with_name("originq-wukong-%s-platform-export.json" % name)
        if not export.exists():
            print("  （没有平台导出文件，跳过逐位比对）")
            continue
        plat = json.loads(export.read_text(encoding="utf-8"))
        if plat.get("taskId") != ours["job_id"]:
            print("  ❌ 平台导出的 taskId 与本文件的 job_id 不是同一个任务")
            all_ok = False
            continue
        sub = plat["subTaskList"][0]["result"]
        plat_probs = dict(zip(sub["key"], sub["value"]))
        same = plat_probs == ours["meta"]["platform_raw"]
        all_ok &= same
        print("  与平台导出逐位一致  %s（%d 个基态）%s"
              % ("✅" if same else "❌", len(plat_probs),
                 "，平台记机时 %s 秒" % plat["machineTime"] if "machineTime" in plat else ""))

    print("\n%s" % ("全部通过 ✅" if all_ok else "有不通过项 ❌"))
    return 0 if all_ok else 1


def check_bitorder():
    """位序自检。Bell/GHZ 是回文的，验不出位序，所以专门跑了 |01>。"""
    path = os.path.join(EVIDENCE_DIR, "originq-wukong-bitorder-result.json")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        counts = json.load(handle)["counts"]
    top = max(counts, key=counts.get)
    print("\n位序自检（电路是 x q[0]，按规范 key 最右为 c[0]，主导态应为 01）")
    print("   实测主导态：%s —— %s" % (
        top, "✅ 位序正确" if top == "01" else "❌ 位序反了，中间层归一化有问题"))


def main():
    parser = argparse.ArgumentParser(description="把电路送上本源悟空真机并存下证据")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--submit", action="store_true", help="只提交，存下 task_id 就退出")
    group.add_argument("--collect", action="store_true", help="只取回之前提交的任务")
    group.add_argument("--verify", action="store_true",
                       help="核验已有证据：主峰是否命中，并与平台导出的文件逐位比对")
    parser.add_argument("--wait", type=int, default=DEFAULT_WAIT_MINUTES,
                        help="最多等多少分钟（默认 %d）" % DEFAULT_WAIT_MINUTES)
    parser.add_argument("--only", choices=[c[0] for c in CIRCUITS],
                        help="只提交其中一条（先花最小的一笔，把真实扣费问出来）")
    parser.add_argument("--backend", help="指定后端名（默认按 %s 顺序挑在线的）"
                                          % "、".join(PREFERRED_BACKENDS))
    parser.add_argument("--retry-minutes", type=int, default=0, dest="retry_minutes",
                        help="平台维护/繁忙时，最多盯着重试多少分钟（默认 0，即不重试）。"
                             "被挡回来的请求不建任务、不扣机时，所以重试是免费的")
    parser.add_argument("--shots", type=int, default=SHOTS,
                        help="采样次数（默认 %d）。真机证据只核验主峰命中，"
                             "额度紧张时可以调小" % SHOTS)
    args = parser.parse_args()

    if args.verify:
        # 只读本地文件，不连平台、不花机时
        return verify()

    try:
        service = connect()
    except RuntimeError as exc:
        print(exc)
        return 2

    if args.collect:
        if not os.path.isfile(TASKS_FILE):
            print("没有找到 %s，先跑一次 --submit。" % TASKS_FILE)
            return 2
        with open(TASKS_FILE, encoding="utf-8") as handle:
            tasks = json.load(handle)
    else:
        try:
            backend, backend_name = pick_backend(service, args.backend)
        except RuntimeError as exc:
            print("\n%s" % exc)
            return 1
        try:
            tasks = submit(backend, backend_name, only=args.only, shots=args.shots,
                           retry_minutes=args.retry_minutes)
        except RuntimeError as exc:
            # 不把 traceback 甩给使用者——这是个要反复跑的工具
            print("\n提交失败：%s" % exc)
            return 1
        if args.submit:
            print("\n稍后用 --collect 取结果。")
            return 0

    collect(tasks, args.wait)
    check_bitorder()
    return 0


if __name__ == "__main__":
    sys.exit(main())
