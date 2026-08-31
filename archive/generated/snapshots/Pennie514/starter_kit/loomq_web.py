#!/usr/bin/env python3
"""LoomQ Web 界面（零依赖：只用 Python 标准库，无需联网、无需 npm）

「让不懂黑话的人，也能指挥最前沿的算力」——面向**零量子背景**用户的引导式
教学界面（L2 交互体验 + 新手引导 / 无门槛可视化）。

交互设计（见 web/ 目录 + tutor.py）：
    - 8 章引导课，全程「预测 → 实验 → 揭示」：先让学习者押一个答案，
      再跑真实电路，最后解释。猜错的地方就是直觉与量子分岔处；
    - 第 5 章并排跑「真纠缠」与「经典事先约好」两组对照，让经典方案当场失败，
      而不是空口说「量子很神奇」；
    - 第 7 章上真机：有凭证跑实时任务，无凭证回放**已存证的真实芯片数据**
      （带可溯源 job_id），保证零配置也有真机体验；
    - 结课测验（检索练习）+ 应用场景 + 明确说清「量子不能做什么」。

启动：
    python3 starter_kit/loomq_web.py            # 默认 http://127.0.0.1:8080
    python3 starter_kit/loomq_web.py --port 9000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402
import real_machine  # noqa: E402   # 真机接入（Web 一键上真实量子机）
import tutor  # noqa: E402          # 课程数据（教学引擎）

WEB = HERE / "web"

# 无凭证时回放的真机存证：本源 180 超导真机跑 Bell 态的真实结果
REPLAY_SOURCES = [
    ("originq", HERE / "evidence" / "files" / "originq_wukong_result.json",
     "本源 180 比特超导真机 · 存证回放"),
    ("spinq", HERE / "evidence" / "files" / "spinq_cloud_result.json",
     "量旋云真机 · 存证回放"),
]

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "LoomQ"

    def log_message(self, *args):  # 静默访问日志
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    # ── GET ──────────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/config-status":
            self._config_status()
        elif path == "/api/curriculum":
            self._json(tutor.curriculum())
        elif path == "/api/real-replay":
            self._real_replay()
        else:
            self._static(path)

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        target = (WEB / rel).resolve()
        # 目录穿越防护：必须真正落在 web/ 目录内（is_relative_to 是路径语义比较，
        # 比 startswith 字符串比较严谨——后者会被同名前缀目录绕过）
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ctype = MIME.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _config_status(self):
        self._json({
            "llm": bool(os.environ.get("LOOMQ_LLM_BASE_URL")
                        and os.environ.get("LOOMQ_LLM_API_KEY")),
            "spinq": bool(os.environ.get("SPINQ_CLOUD_USERNAME")
                          and os.environ.get("SPINQ_CLOUD_KEYFILE")),
            "originq": bool(os.environ.get("ORIGINQ_API_TOKEN")),
            "model": os.environ.get("LOOMQ_LLM_MODEL", ""),
        })

    def _real_replay(self):
        """回放已存证的真机运行结果（零配置也能完成真机章节）。

        这不是模拟：数据来自真实超导芯片的历史任务，job_id 可在平台控制台溯源。
        两台机器一起返回——它们的噪声水平差异很大（本源180 几乎无噪声、量旋约 24%），
        这个真实差异本身就是最好的教学素材：不同真机的保真度不一样。
        """
        results = []
        for _name, fp, label in REPLAY_SOURCES:
            if not fp.is_file():
                continue
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                sub = doc.get("submission_schema") or {}
                counts = {str(k): int(v) for k, v in (sub.get("counts") or {}).items()}
                if not counts:
                    continue
            except Exception:  # noqa: BLE001
                continue
            results.append({
                "counts": counts,
                "backend": sub.get("backend", ""),
                "shots": sub.get("shots", sum(counts.values())),
                "job_id": sub.get("job_id", ""),
                "label": label,
                "timestamp": sub.get("timestamp", ""),
            })
        if not results:
            self._json({"error": "本地没有找到真机存证文件（evidence/files/*.json）。"})
            return
        self._json({
            "results": results,
            "note": "以下是真实量子芯片跑出来的历史数据（非模拟），"
                    "每条 job_id 都可在对应平台控制台溯源。",
        })

    # ── POST ─────────────────────────────────────────────────────────
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001
            self._json({"error": "bad request"}, 400)
            return
        routes = {
            "/api/chat": self._handle_chat,
            "/api/run": self._handle_run,
            "/api/run-real": self._handle_run_real,
            "/api/config": self._save_config,
        }
        if self.path == "/api/config-clear":
            self._clear_config()
        elif self.path in routes:
            routes[self.path](payload)
        else:
            self._json({"error": "unknown api"}, 404)

    def _save_config(self, payload):
        """把页面填的配置写入进程环境变量（仅内存，不落盘、不入库）。"""
        llm = payload.get("llm") or {}
        spinq = payload.get("spinq") or {}
        originq = payload.get("originq") or {}
        if llm.get("base_url"):
            os.environ["LOOMQ_LLM_BASE_URL"] = str(llm["base_url"]).rstrip("/")
        if llm.get("api_key"):
            os.environ["LOOMQ_LLM_API_KEY"] = str(llm["api_key"])
        if llm.get("model"):
            os.environ["LOOMQ_LLM_MODEL"] = str(llm["model"])
        if spinq.get("username"):
            os.environ["SPINQ_CLOUD_USERNAME"] = str(spinq["username"])
        if spinq.get("keyfile"):
            os.environ["SPINQ_CLOUD_KEYFILE"] = str(
                Path(str(spinq["keyfile"])).expanduser())
        if originq.get("api_token"):
            os.environ["ORIGINQ_API_TOKEN"] = str(originq["api_token"])
        self._json({
            "ok": True,
            "llm": bool(os.environ.get("LOOMQ_LLM_API_KEY")),
            "spinq": bool(os.environ.get("SPINQ_CLOUD_KEYFILE")),
            "originq": bool(os.environ.get("ORIGINQ_API_TOKEN")),
        })

    def _clear_config(self):
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL",
                     "SPINQ_CLOUD_USERNAME", "SPINQ_CLOUD_KEYFILE", "ORIGINQ_API_TOKEN"):
            os.environ.pop(name, None)
        self._json({"ok": True})

    def _handle_run_real(self, payload):
        """在真实量子机上运行电路（零基础用户一键上真机）。"""
        backend = str(payload.get("backend", "spinq_cloud"))
        qasm = str(payload.get("qasm", ""))
        shots = max(1, min(8192, int(payload.get("shots", 2048))))  # 限幅，防烧真机额度
        try:
            if backend == "spinq_cloud":
                if not (os.environ.get("SPINQ_CLOUD_USERNAME")
                        and os.environ.get("SPINQ_CLOUD_KEYFILE")):
                    self._json({"error": "量旋真机凭证未配置。在 ⚙️ 配置里填用户名和私钥路径，"
                                         "或启动前设置 SPINQ_CLOUD_USERNAME / SPINQ_CLOUD_KEYFILE"
                                         "（见 HARDWARE_ACCESS.md）。"})
                    return
                cfg = json.loads((HERE / "evidence" / "config_spinq_cloud.json")
                                 .read_text(encoding="utf-8"))
                cfg["shots"] = shots
                result = real_machine._run_spinq_cloud(qasm, cfg, None)
            elif backend == "originq_wukong":
                if not os.environ.get("ORIGINQ_API_TOKEN"):
                    self._json({"error": "本源量子云凭证未配置。在 ⚙️ 配置里填 API Token，"
                                         "或启动前设置 ORIGINQ_API_TOKEN（见 HARDWARE_ACCESS.md）。"})
                    return
                cfg = json.loads((HERE / "evidence" / "config_originq_wukong.json")
                                 .read_text(encoding="utf-8"))
                cfg["shots"] = shots
                cfg.setdefault("chip_id", 180)  # 本源180 当前在线（悟空72 维护中）
                result = real_machine._run_originq_wukong(qasm, cfg, None)
            else:
                self._json({"error": "unknown real backend"}, 400)
                return
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}"})
            return
        self._json({"result": result})

    def _handle_chat(self, payload):
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self._json({"error": "prompt 不能为空"}, 400)
            return
        try:
            reply = adapter.agent_chat(prompt)
            self._json({"reply": reply, "qasm": _extract_qasm(reply)})
        except Exception as exc:  # noqa: BLE001
            self._json({"error": _friendly_llm_error(exc)})

    def _handle_run(self, payload):
        qasm = str(payload.get("qasm", ""))
        backend = str(payload.get("backend", "spinq"))
        shots = max(1, min(8192, int(payload.get("shots", 2048))))
        if backend not in adapter.SUPPORTED_TARGETS:
            self._json({"error": "unknown backend"}, 400)
            return
        try:
            self._json({"result": adapter.run(qasm, backend, shots)})
        except Exception as exc:  # noqa: BLE001
            self._json({"error": _friendly_run_error(exc)})


def _friendly_run_error(exc: Exception) -> str:
    """把 traceback 翻译成零基础用户看得懂的话（友好报错，不甩栈）。"""
    msg = str(exc)
    low = msg.lower()
    if "'nonetype'" in low or "compile" in low or "parse" in low:
        return ("这段电路没能编译通过——通常是格式或语法问题。检查三点：\n"
                "① 开头有 OPENQASM 2.0; 和 include \"qelib1.inc\";\n"
                "② 声明了 qreg q[n]; 和 creg c[n];\n"
                "③ 门名拼写正确，且只用这 12 个：h, x, s, sdg, t, tdg, rz, ry, cx, cu1, swap, ccx。\n"
                "想要一份能跑的模板，点【跑电路】里的电路按钮。")
    if "qreg" in low or "creg" in low or "index" in low:
        return ("量子比特编号超出了声明范围。如果写了 qreg q[2];，"
                "就只能用 q[0] 和 q[1]。\n原始信息：" + msg)
    if "gate" in low or "unknown" in low:
        return ("用到了不支持的量子门。当前支持 12 个门："
                "h, x, s, sdg, t, tdg, rz, ry, cx, cu1, swap, ccx。\n原始信息：" + msg)
    return f"运行失败了：{msg}\n（如果是自己改的电路，先用【跑电路】里的模板对照一下格式。）"


def _friendly_llm_error(exc: Exception) -> str:
    msg = str(exc)
    if "LOOMQ_LLM" in msg or "环境变量" in msg or "模型调用失败" in msg:
        return ("🔑 模型服务未配置或调用失败（正式评测时由组委会自动注入，无需操作）。\n"
                "引导课 8 章、所有实验、真机回放都不需要它。\n"
                "想解锁「生成 / 纠错 / 选平台」：在 ⚙️ 配置里填一个 API Key，"
                "或启动前设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL。")
    return f"模型服务调用失败：{type(exc).__name__}: {msg}"


def _extract_qasm(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    fenced = re.search(r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2\.0;.*?)```",
                       text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    bare = re.search(r"(OPENQASM\s+2\.0;.*)", text, re.DOTALL)
    return bare.group(1).strip() if bare else None


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ Web 界面（零依赖，零基础友好）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if not (WEB / "index.html").is_file():
        print(f"错误：找不到前端资源目录 {WEB}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    data = tutor.curriculum()
    core = int(data["core_eta"])            # 核心 5 分钟（不含结课加餐）
    total = int(data["total_eta"])
    print("=" * 64)
    print("  LoomQ · 5 分钟从零基础到真机第一个量子实验")
    print(f"  打开浏览器访问：http://{args.host}:{args.port}")
    print(f"  引导课 {len(tutor.LESSONS)} 章：核心路线约 {core // 60} 分 {core % 60} 秒"
          f"（含结课加餐共约 {total // 60} 分 {total % 60} 秒）")
    print("  实验与真机回放无需任何配置；生成/纠错/选平台可在页面内 ⚙️ 配置。")
    print("  按 Ctrl+C 退出")
    print("=" * 64)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
