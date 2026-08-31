#!/usr/bin/env python3
"""Minimal L2 web UI (stdlib only). Zero-physics users type Chinese, get QASM + counts."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

try:
    import adapter
    from loomq_agent import extract_qasm
except ImportError:
    from starter_kit import adapter
    from starter_kit.loomq_agent import extract_qasm


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LoomQ · 用人话指挥量子计算机</title>
<style>
body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;background:#111;color:#eee}
textarea{width:100%;min-height:90px;background:#1c1c1c;color:#eee;border:1px solid #444;padding:.6rem}
button{background:#e84a7f;color:#fff;border:0;padding:.5rem 1rem;margin:.4rem .2rem 0 0;cursor:pointer}
pre{background:#1a1a1a;padding:1rem;overflow:auto;white-space:pre-wrap}
.bar{display:flex;align-items:center;gap:.5rem;margin:.25rem 0}
.bar span{min-width:3rem}
.fill{height:12px;background:#e84a7f}
.hint{color:#aaa;font-size:.9rem}
</style>
</head>
<body>
<h1>LoomQ</h1>
<p class="hint">不会写 QASM 也可以。试一试下面三个现场任务。</p>
<p>
<button type="button" onclick="setP('生成一个 3 比特 GHZ 态并进行全测量')">任务1 GHZ</button>
<button type="button" onclick="setP('我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]')">任务2 纠错</button>
<button type="button" onclick="setP('我需要运行一个 15 比特电路，且零排队等待，选哪个平台？')">任务3 选后端</button>
</p>
<form method="post" action="/">
<textarea name="prompt" id="p" placeholder="用一句话说你想做什么"></textarea>
<p>
<label>后端
<select name="target">
<option>spinq</option><option>originq</option><option>braket</option>
</select>
</label>
<button type="submit">生成并运行</button>
</form>
<script>function setP(t){document.getElementById('p').value=t}</script>
__BODY__
</body></html>
"""


def bars(counts: dict) -> str:
    total = sum(counts.values()) or 1
    rows = []
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:8]:
        w = int(240 * v / total)
        rows.append(
            '<div class="bar"><span>%s</span><div class="fill" style="width:%dpx"></div> %d</div>'
            % (k, w, v)
        )
    return "".join(rows)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _html(self, extra: str = "") -> bytes:
        return PAGE.replace("__BODY__", extra).encode("utf-8")

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self._html())

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n).decode("utf-8", "replace")
        form = parse_qs(raw)
        prompt = (form.get("prompt") or [""])[0].strip()
        target = (form.get("target") or ["spinq"])[0]
        extra = ""
        if prompt:
            try:
                reply = adapter.agent_chat(prompt)
                extra += "<h2>智能体回复</h2><pre>%s</pre>" % (
                    reply.replace("&", "&amp;").replace("<", "&lt;")
                )
                qasm = extract_qasm(reply)
                if qasm:
                    result = adapter.run(qasm, target, 1024)
                    extra += "<h2>测量结果（柱状）</h2>" + bars(result.get("counts") or {})
                    extra += "<p class='hint'>主导态是出现最多的比特串。贝尔/GHZ 常见全 0 与全 1 大约各一半。</p>"
                    extra += "<pre>%s</pre>" % json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as exc:
                extra += "<p>出错了：%s。可以换种说法，或检查 LOOMQ_LLM_*。</p>" % exc
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self._html(extra))


def main() -> int:
    missing = [n for n in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL") if not os.environ.get(n)]
    if missing:
        print("缺少环境变量: " + ", ".join(missing), file=sys.stderr)
        return 2
    port = int(os.environ.get("LOOMQ_WEB_PORT", "8765"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("LoomQ web: http://127.0.0.1:%d" % port)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
