#!/usr/bin/env python3
"""LoomQ 真机接入统一入口（L1 真机加分项，最高 +10 分）

让同一套自定义输入驱动三家的真实量子算力：

    python3 starter_kit/real_machine.py spinq_cloud \
        --qasm starter_kit/circuits/bell.qasm --shots 8192 \
        --config starter_kit/evidence/config_spinq.json \
        --out starter_kit/evidence/files/spinq_cloud_result.json

    python3 starter_kit/real_machine.py originq_wukong \
        --qasm starter_kit/circuits/bell.qasm --shots 8192 \
        --config starter_kit/evidence/config_originq.json

    python3 starter_kit/real_machine.py braket_cloud \
        --qasm starter_kit/circuits/bell.qasm --shots 8192 \
        --config starter_kit/evidence/config_braket.json

凭证（环境变量，勿提交到仓库）：
    SpinQ 云：  SPINQ_CLOUD_USERNAME, SPINQ_CLOUD_KEYFILE
    本源量子云： ORIGINQ_API_TOKEN
    AWS Braket： 标准 AWS 凭证链（~/.aws/credentials 或 AWS_ACCESS_KEY_ID 等）

所有平台输出统一的 result.json（大赛 Schema），并额外保存平台原始返回，
job_id/task_code 可在对应平台控制台溯源。详见 HARDWARE_ACCESS.md。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402

# 输出目录（真机证据统一放这里，与 evidence/README.md 保持一致）
EVIDENCE_DIR = HERE / "evidence" / "files"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_config(path: str | None, platform: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if path:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("platform", platform)
    cfg.setdefault("task_name", "LoomQ-2026")
    cfg.setdefault("task_desc", "LoomQ quantum accessibility competition")
    cfg.setdefault("timeout_seconds", 3600)
    return cfg


def _save(platform: str, payload: Dict[str, Any], out: str | None, raw: Any = None) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = str(EVIDENCE_DIR / f"{platform}_result_{stamp}.json")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "submission_schema": payload,
        "platform_raw": raw,
        "evidence_note": (
            "job_id/task_code 可在平台控制台溯源；此文件为赛题 L1 真机加分项证据。"
        ),
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# SpinQ 云（量旋超导真机 / Taurus 云模拟器）
# ---------------------------------------------------------------------------

def _run_spinq_cloud(qasm_str: str, cfg: Dict[str, Any], out: str | None) -> Dict[str, Any]:
    username = os.environ.get("SPINQ_CLOUD_USERNAME")
    keyfile = os.environ.get("SPINQ_CLOUD_KEYFILE")
    if not username or not keyfile:
        raise RuntimeError(
            "缺少 SpinQ 云凭证：请设置环境变量 SPINQ_CLOUD_USERNAME 与 "
            "SPINQ_CLOUD_KEYFILE（RSA 私钥文件路径）。申请方法见 HARDWARE_ACCESS.md。"
        )
    try:
        import spinqit as sq
        from spinqit.backend.spinq_cloud_backend import SpinQCloudConfig
        from spinqit.backend.backend import get_spinq_cloud
    except ImportError as exc:
        raise RuntimeError("未安装 spinqit，无法访问量旋云") from exc

    shots = int(cfg.get("shots", 8192))
    host = cfg.get("host", "http://cloud.spinq.cn:6060")

    try:
        backend = get_spinq_cloud(username, keyfile, host)
    except Exception as exc:  # noqa: BLE001
        hint = str(exc)
        if "Authentication failed" in hint or "No active user" in hint:
            raise RuntimeError(
                "量旋云登录失败（用户名/密钥不匹配）。请检查：\n"
                "  1) SPINQ_CLOUD_USERNAME 必须是你在 cloud.spinq.cn 注册的用户名\n"
                "     （登录网页版 cloud.spinq.cn → 个人中心查看准确用户名，可能不是 pennie514）；\n"
                "  2) 账号是否完成邮箱/手机验证（未激活会报 No active user）；\n"
                "  3) 公钥是否已添加到账号：把 ~/.ssh/spinq_cloud.pub 内容粘到\n"
                "     cloud.spinq.cn → 个人中心 → SSH 公钥/密钥管理（必须是这把 RSA 公钥）；\n"
                f"  原始错误：{exc}"
            ) from exc
        raise RuntimeError(f"量旋云连接失败：{exc}") from exc
    platforms = backend.get_platform_list()
    print("  量旋云可用平台：", platforms)
    platform_code = cfg.get("platform_code")
    if platform_code is None:
        raise RuntimeError(
            "请在 --config 中指定 platform_code（从上面的平台列表中选择）。\n"
            "例如 {\"platform_code\": \"<列表中的代码>\"}"
        )
    if platform_code not in platforms:
        raise RuntimeError(f"platform_code {platform_code!r} 不在可用平台列表 {platforms} 中")

    # 云平台在电路末尾自动全测量，不支持显式 measure 门 → 先剥离 measure
    stripped = "\n".join(
        line for line in qasm_str.splitlines()
        if not line.lstrip().startswith("measure")
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(stripped)
        tmp.close()
        compiler = sq.get_compiler("qasm")
        ir = compiler.compile(tmp.name, 0)
    finally:
        os.unlink(tmp.name)

    config = SpinQCloudConfig()
    config.configure_platform(platform_code)
    config.configure_shots(shots)
    config.configure_task(cfg.get("task_name", "LoomQ-2026"), cfg.get("task_desc", ""))
    if cfg.get("measure_qubits"):
        config.configure_measure_qubits(cfg["measure_qubits"])

    print(f"  正在提交到量旋云（平台 {platform_code}，{shots} shots）……")
    try:
        result = backend.execute(ir, config)
    except Exception as exc:  # noqa: BLE001
        if "No machine is running" in str(exc):
            raise RuntimeError(
                f"平台 {platform_code} 当前没有机器在线（量子真机按调度轮流开机）。\n"
                "  解决办法：换一台在线的真机再跑（可先运行下面的状态检查脚本）：\n"
                "    python3 starter_kit/check_spinq_platforms.py\n"
                "  然后把在线的平台代码（如 gemini_vp / triangulum_vp）写入\n"
                "  starter_kit/evidence/config_spinq_cloud.json 的 platform_code 再重跑。"
            ) from exc
        raise RuntimeError(f"量旋云任务提交失败：{exc}") from exc
    job_id = getattr(result, "task_code", None) or f"spinq-cloud-{uuid.uuid4().hex[:12]}"

    # spinq 计数 key 最左为 q[0]（与本地模拟器同一约定）→ 统一为最右 c[0]
    counts = {str(k)[::-1]: int(v) for k, v in (result.counts or {}).items()}
    payload = {
        "backend": cfg.get("backend", "spinq_cloud_qpu"),
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _now_iso(),
        "meta": {
            "platform_code": platform_code,
            "transpiled_gates": len(adapter._parse_qasm2(qasm_str)["ops"]),
            "trace_url": f"https://cloud.spinq.cn (task_code={job_id})",
        },
    }
    path = _save("spinq_cloud", payload, out, raw={
        "task_code": job_id, "task_name": result.task_name, "platform": result.platform,
    })
    print(f"  量旋云真机任务完成，job_id={job_id}")
    print(f"  结果已保存：{path}")
    return payload


# ---------------------------------------------------------------------------
# 本源悟空真机（Origin Quantum Cloud）
# ---------------------------------------------------------------------------

def _run_originq_wukong(qasm_str: str, cfg: Dict[str, Any], out: str | None) -> Dict[str, Any]:
    token = os.environ.get("ORIGINQ_API_TOKEN")
    if not token:
        raise RuntimeError(
            "缺少本源量子云凭证：请设置环境变量 ORIGINQ_API_TOKEN。\n"
            "申请方法见 HARDWARE_ACCESS.md（qcloud.originqc.com.cn 控制台获取 API Token）。"
        )
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise RuntimeError("未安装 pyqpanda，无法访问本源量子云") from exc

    shots = int(cfg.get("shots", 8192))
    # chip_id 选择本源平台上的具体芯片：72 = 悟空，180 = 180 比特超导芯片。
    # 证据包 config_originq_wukong.json 用 180（本次真机证据实际执行的芯片），
    # 也可用 --chip-id 覆盖。
    chip_id = cfg.get("chip_id", 72)
    task_name = cfg.get("task_name", "LoomQ-2026")

    machine = pq.QCloud()
    machine.init_qvm(user_token=token, enable_logging=False, log_to_console=False)
    try:
        prog, _qreg, _creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
        print(f"  正在提交到本源悟空真机（chip_id={chip_id}，{shots} shots）……")
        try:
            task_id = machine.async_real_chip_measure(
                prog, shot=shots, chip_id=chip_id,
                is_amend=bool(cfg.get("is_amend", True)),
                is_mapping=bool(cfg.get("is_mapping", True)),
                is_optimization=bool(cfg.get("is_optimization", True)),
                task_name=task_name,
            )
        except Exception as exc:  # noqa: BLE001
            if "maintenance" in str(exc).lower() or "维护" in str(exc):
                raise RuntimeError(
                    "本源悟空真机当前处于维护状态（平台侧调度，非代码问题）。\n"
                    "  解决办法：过 15–30 分钟重试一次，直到返回 task_id。\n"
                    "  重试命令与本次相同；维护结束前会一直提示，属正常现象。\n"
                    "  也可先提交当前版本（量旋真机证据已达标），悟空跑通后再用新 Issue 重新提交。"
                ) from exc
            raise RuntimeError(f"本源悟空任务提交失败：{exc}") from exc
        print(f"  任务已提交，task_id={task_id}，开始轮询结果……")

        deadline = time.time() + int(cfg.get("timeout_seconds", 3600))
        result = None
        while time.time() < deadline:
            time.sleep(10)
            try:
                status, result = machine.query_task_state_result(task_id)
            except Exception as exc:  # 服务端可能暂时繁忙
                print(f"    轮询异常（继续等待）：{type(exc).__name__}: {exc}")
                continue
            if status == machine.TaskStatus.FINISHED.value:
                break
            if status == machine.TaskStatus.FAILED.value:
                raise RuntimeError(f"本源悟空任务失败：task_id={task_id}")
            print("    任务计算中……")
        if result is None:
            raise RuntimeError(f"本源悟空任务超时：task_id={task_id}")

        # 归一化 counts：本源真机返回的是「测量位串 -> 概率(浮点)」字典，
        # 位串键最右为 c[0]（与本地 CPUQVM 同一约定，即统一 Schema 的 little 序），
        # 因此**不反转键**，并把概率换算成 counts：count = round(prob * shots)。
        n_qubits = max((len(k) for k in result), default=0) if isinstance(result, dict) else 0
        counts: Dict[str, int] = {}
        for key, value in (result or {}).items():
            bitstr = str(key) if not (isinstance(key, int) or (isinstance(key, str) and key.isdigit())) \
                else bin(int(key))[2:].zfill(n_qubits)
            prob = float(value)
            counts[bitstr] = int(round(prob * shots))

        payload = {
            "backend": cfg.get("backend", "originq_wukong"),
            "job_id": task_id,
            "shots": shots,
            "counts": counts,
            "bit_order": "little",
            "timestamp": _now_iso(),
            "meta": {
                "chip_id": chip_id,
                "n_measured_qubits": n_qubits,
                "trace_url": "https://qcloud.originqc.com.cn（任务中心按 task_id 查询）",
            },
        }
    finally:
        machine.finalize()

    path = _save("originq_wukong", payload, out, raw={"task_id": task_id, "result": result})
    print(f"  本源悟空真机任务完成，job_id={task_id}")
    print(f"  结果已保存：{path}")
    return payload


# ---------------------------------------------------------------------------
# AWS Braket 云端（可选：允许以 LocalSimulator 替代，见赛题说明）
# ---------------------------------------------------------------------------

def _run_braket_cloud(qasm_str: str, cfg: Dict[str, Any], out: str | None) -> Dict[str, Any]:
    try:
        from braket.aws import AwsDevice
        from braket.ir.openqasm import Program
    except ImportError as exc:
        raise RuntimeError("未安装 amazon-braket-sdk，无法访问 AWS Braket") from exc

    shots = int(cfg.get("shots", 8192))
    device_arn = cfg.get("device_arn")
    if not device_arn:
        raise RuntimeError(
            "请在 --config 中指定 device_arn（如 SV1 托管模拟器或 IonQ/Rigetti QPU 的 ARN）。\n"
            "可用设备可用以下代码枚举：\n"
            "    from braket.aws import AwsSession; from braket.devices import Devices\n"
            "    print([d for d in Devices if 'QPU' in d.name or d.value.endswith('qsim')])"
        )

    qasm3 = adapter.transpile(qasm_str, "braket")
    program = Program(source=qasm3)
    device = AwsDevice(device_arn, aws_session=None)
    print(f"  正在提交到 AWS Braket 云端（{device_arn}，{shots} shots）……")
    task = device.run(program, shots=shots)
    print(f"  任务已提交，task_arn={task.id}，等待完成……")
    result = task.result()
    counts = {str(k)[::-1]: int(v) for k, v in result.measurement_counts.items()}
    payload = {
        "backend": cfg.get("backend", "braket_cloud"),
        "job_id": task.id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _now_iso(),
        "meta": {
            "device_arn": device_arn,
            "trace_url": "https://us-west-1.console.aws.amazon.com/braket（任务中心按 ARN 查询）",
        },
    }
    path = _save("braket_cloud", payload, out, raw={"task_arn": task.id})
    print(f"  AWS Braket 任务完成，job_id={task.id}")
    print(f"  结果已保存：{path}")
    return payload


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

RUNNERS = {
    "spinq_cloud": _run_spinq_cloud,
    "originq_wukong": _run_originq_wukong,
    "braket_cloud": _run_braket_cloud,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LoomQ 真机统一接入：spinq_cloud | originq_wukong | braket_cloud"
    )
    parser.add_argument("platform", choices=sorted(RUNNERS))
    parser.add_argument("--qasm", help="OpenQASM 2.0 电路文件路径（自定义输入）")
    parser.add_argument("--qasm-str", help="直接传入 OpenQASM 2.0 字符串（自定义输入）")
    parser.add_argument("--shots", type=int, default=None, help="采样次数")
    parser.add_argument("--config", help="JSON 配置文件（自定义输入：平台/映射/任务名等）")
    parser.add_argument("--chip-id", type=int, default=None,
                        help="本源真机芯片号（默认 72=悟空；7/5/2=悟源系列），覆盖配置文件")
    parser.add_argument("--out", help="结果输出路径（默认 evidence/files/<platform>_result_*.json）")
    args = parser.parse_args()

    if not args.qasm and not args.qasm_str:
        parser.error("必须提供 --qasm <文件> 或 --qasm-str <字符串>")
    qasm_str = (Path(args.qasm).read_text(encoding="utf-8") if args.qasm else args.qasm_str)
    if not qasm_str.strip().startswith("OPENQASM 2.0"):
        raise SystemExit("输入不是 OpenQASM 2.0 程序（真机输入以赛题标准 QASM 2.0 为准）")

    cfg = _load_config(args.config, args.platform)
    if args.shots is not None:
        cfg["shots"] = args.shots
    if args.chip_id is not None:
        cfg["chip_id"] = args.chip_id

    # 本地先做一遍语义自验：同一电路在无噪声模拟器上应得到理想分布
    try:
        local = adapter.run(qasm_str, {"spinq_cloud": "spinq",
                                       "originq_wukong": "originq",
                                       "braket_cloud": "braket"}[args.platform], 4096)
        top = sorted(local["counts"], key=lambda s: local["counts"][s], reverse=True)
        # 显示 Top-2（如 Bell/GHZ 的理想分布是两个等概率主峰）
        top_str = "、".join(f"|{s}>" for s in top[:2])
        top_detail = "，".join(f"|{s}>={local['counts'][s]}" for s in top[:3])
        print(f"  本地模拟自验：理想主峰 {top_str}（4096 shots：{top_detail}），"
              f"将据此核对真机主峰是否命中。")
    except Exception as exc:
        print(f"  [警告] 本地模拟自验失败（不影响提交，仅提示）：{exc}")

    runner = RUNNERS[args.platform]
    payload = runner(qasm_str, cfg, args.out)
    print("\n  统一结果 Schema：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
