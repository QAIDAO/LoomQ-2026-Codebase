"""
LoomQ Agent 网页交互入口

启动方式:
    python3 app.py
然后浏览器打开 http://127.0.0.1:5000

依赖: flask (见 requirements.txt)
"""

import os
import traceback
from flask import Flask, request, jsonify, send_from_directory

from l2 import agent_chat 

app = Flask(__name__, static_folder=None)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return send_from_directory(_THIS_DIR, "index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "消息不能为空"}), 400

    try:
        reply = agent_chat(prompt)
        return jsonify({"reply": reply})
    except Exception as e:
        # return error to server backend for debug
        # return message only to frontend without exposing internal details
        traceback.print_exc()
        return jsonify({"error": f"调用失败: {type(e).__name__}: {e}"}), 500


@app.route("/api/health")
def health():
    """
    Fast self-checker: check whether variables are defined without calling LLM
    """
    required = ["LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"]
    missing = [k for k in required if not os.environ.get(k)]
    return jsonify({
        "ok": len(missing) == 0,
        "missing_env_vars": missing,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("LoomQ Agent 网页入口启动中...")
    print("浏览器打开: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False)