"""Standard-library HTTP server for the local LoomQ interface."""

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict

try:
    from ..loomq_agent import respond_structured
except ImportError:
    from loomq_agent import respond_structured


WEB_ROOT = Path(__file__).with_name("web")
STATIC_FILES: Dict[str, str] = {
    "/": "index.html",
    "/index.html": "index.html",
    "/assets/styles.css": "assets/styles.css",
    "/assets/app.js": "assets/app.js",
    "/assets/visualizers.js": "assets/visualizers.js",
    "/assets/diagnostics.js": "assets/diagnostics.js",
    "/assets/session.js": "assets/session.js",
    "/assets/linen-weave.png": "assets/linen-weave.png",
    "/assets/yarn-ball-indigo.png": "assets/yarn-ball-indigo.png",
    "/assets/yarn-ball-green.png": "assets/yarn-ball-green.png",
    "/assets/yarn-ball-violet.png": "assets/yarn-ball-violet.png",
}


class LoomQHandler(BaseHTTPRequestHandler):
    server_version = "LoomQ/1.0"

    def log_message(self, format_string, *args):
        return

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {"status": "ok"})
            return
        relative = STATIC_FILES.get(self.path)
        if relative is None:
            self._json(404, {"error": "not_found"})
            return
        path = WEB_ROOT / relative
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/chat":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65_536:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            prompt = payload.get("prompt") if isinstance(payload, dict) else None
            history = payload.get("history") if isinstance(payload, dict) else None
            task = payload.get("task") if isinstance(payload, dict) else None
            response = respond_structured(prompt, history=history, task_hint=task)
            self._json(200, response.to_dict())
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, _error_payload(error, "invalid_request"))
        except RuntimeError as error:
            self._json(502, _error_payload(error, _runtime_error_code(str(error))))

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _error_payload(error: Exception, code: str) -> dict:
    message = str(error)
    guidance = {
        "configuration_missing": (
            "模型配置不完整",
            "运行位置：LOOMQ_LLM_* 环境变量",
            ["关闭当前服务并重新运行本地启动器", "确认 Base URL、API Key 和模型名称均已填写"],
        ),
        "authentication_failed": (
            "模型服务拒绝了凭证",
            "连接位置：LOOMQ_LLM_API_KEY",
            ["检查 API Key 是否完整、有效且仍有权限", "更新运行时变量后重启服务；不要把 Key 写入代码"],
        ),
        "rate_limited": (
            "模型服务暂时限制调用",
            "连接位置：模型服务配额",
            ["稍后重试", "检查账号余额、速率限制和模型可用性"],
        ),
        "service_unreachable": (
            "无法连接模型服务",
            "连接位置：LOOMQ_LLM_BASE_URL",
            ["检查 Base URL 和网络连接", "如果使用 VPN，确认容器或本地进程能够访问该地址"],
        ),
        "request_timeout": (
            "模型响应超过时间限制",
            "执行位置：LLM 请求",
            ["缩短任务描述后重试", "检查服务状态；正式评测单个 case 上限为 120 秒"],
        ),
        "qasm_validation_failed": (
            "生成线路未通过本地验证",
            "执行位置：OpenQASM 解析或理想态校验",
            ["在同一输入框补充原始目标和需要修复的代码", "根据错误详情检查寄存器、门参数、逗号和测量"],
        ),
        "invalid_request": (
            "任务输入无法处理",
            "输入位置：任务描述或会话上下文",
            ["检查输入是否为空或过长", "清空会话上下文后重试"],
        ),
        "upstream_error": (
            "本次任务没有完成",
            "执行位置：LoomQ Agent",
            ["保留当前输入并重试一次", "若持续失败，清空上下文并检查模型配置"],
        ),
    }[code]
    return {
        "error": message,
        "diagnostic": {
            "severity": "error",
            "code": code,
            "message": guidance[0],
            "location": guidance[1],
            "detail": message,
            "actions": guidance[2],
        },
    }


def _runtime_error_code(message: str) -> str:
    lowered = message.lower()
    if "missing required loomq l2 environment" in lowered:
        return "configuration_missing"
    if "http 401" in lowered or "http 403" in lowered:
        return "authentication_failed"
    if "http 429" in lowered:
        return "rate_limited"
    if "unreachable" in lowered:
        return "service_unreachable"
    if "timeout" in lowered:
        return "request_timeout"
    if "openqasm" in lowered or "circuit validation" in lowered:
        return "qasm_validation_failed"
    return "upstream_error"


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), LoomQHandler)
    print(f"LoomQ local interface: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the LoomQ web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    serve(arguments.host, arguments.port)
