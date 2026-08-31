#!/usr/bin/env python3
"""假的模型服务：一个说 OpenAI 协议的桩（仅供测试，不在提交路径上）

**为什么需要它。**

L2 的代码要处理很多"模型没配合"的情况：答案是错的、格式是垃圾、
服务连不上、连续两轮都改不对……这些情况用真模型**没法稳定复现**，
温度调到 0 也只是让它每次答得一样，不是让它按你要的方式答错。

所以这里起一个本地小服务，让它**按剧本回答**。于是每一种失败路径
都变成一条可重复、可回归的测试。

顺带还有一个好处：整套 L2 逻辑可以在完全没有 API Key、
甚至完全断网的情况下开发和验证。

用法：

    with FakeLLM(["第一次的回复", "第二次的回复"]):
        reply = agent.agent_chat("生成一个 3 比特 GHZ 态")

进入上下文时会自动设置 LOOMQ_LLM_* 三个环境变量指向本地端口，
退出时恢复原样。
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ENV_KEYS = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")


class FakeLLM:
    """按剧本回答的本地模型服务。

    script : list[str] | callable
        - 传列表：第 n 次调用返回第 n 个字符串作为模型回复内容；用完后重复最后一个。
        - 传函数：每次调用时以请求体为参数调用它，返回字符串作为回复内容。
        - 列表元素若是 int，则表示"这次直接返回该 HTTP 错误码"，用来测服务异常。
    """

    def __init__(self, script, model="fake-model"):
        self.script = script
        self.model = model
        self.calls = []
        self._server = None
        self._thread = None
        self._saved_env = {}

    # ---- 上下文管理 ----

    def __enter__(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.calls.append(body)

                content = outer._next_response(body)
                if isinstance(content, int):
                    self.send_response(content)
                    self.end_headers()
                    self.wfile.write(b'{"error": "fake failure"}')
                    return

                payload = {
                    "id": "fake-%d" % len(outer.calls),
                    "object": "chat.completion",
                    "model": outer.model,
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}
                    ],
                }
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # 别把请求日志刷进测试输出
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        port = self._server.server_address[1]
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}
        os.environ["LOOMQ_LLM_BASE_URL"] = "http://127.0.0.1:%d/v1" % port
        os.environ["LOOMQ_LLM_API_KEY"] = "fake-key"
        os.environ["LOOMQ_LLM_MODEL"] = self.model
        return self

    def __exit__(self, *exc_info):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False

    # ---- 剧本 ----

    def _next_response(self, body):
        if callable(self.script):
            return self.script(body)
        index = min(len(self.calls) - 1, len(self.script) - 1)
        return self.script[index]


class NoServer:
    """把环境变量指向一个没人监听的端口，用来测"模型服务连不上"。"""

    def __enter__(self):
        self._saved = {key: os.environ.get(key) for key in ENV_KEYS}
        os.environ["LOOMQ_LLM_BASE_URL"] = "http://127.0.0.1:9/v1"  # 端口 9 是 discard，必定连不上
        os.environ["LOOMQ_LLM_API_KEY"] = "fake-key"
        os.environ["LOOMQ_LLM_MODEL"] = "fake-model"
        return self

    def __exit__(self, *exc_info):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False


class NoConfig:
    """模拟一台**什么都没配**的机器：环境变量清空，且找不到任何 .env 文件。

    光清环境变量已经不够了：llm_client 在变量缺失时会去几个约定位置找 .env
    补上（为的是不用每条命令前面手写一串 export）。开发机上那个文件是存在的，
    于是"没配置"这个场景根本模拟不出来——这一节测试因此假通过过一次。

    所以这里连"去哪儿找文件"一起接管掉。**接管放在测试脚手架里，
    不在产品代码里加一个只为测试服务的开关**。
    """

    def __enter__(self):
        self._saved = {key: os.environ.pop(key, None) for key in ENV_KEYS}
        try:
            from starter_kit.loomq import envfile
        except ImportError:
            from loomq import envfile  # type: ignore[no-redef]
        self._envfile = envfile
        self._saved_search = envfile.search_paths
        envfile.search_paths = lambda: ()
        return self

    def __exit__(self, *exc_info):
        self._envfile.search_paths = self._saved_search
        for key, value in self._saved.items():
            if value is not None:
                os.environ[key] = value
        return False
