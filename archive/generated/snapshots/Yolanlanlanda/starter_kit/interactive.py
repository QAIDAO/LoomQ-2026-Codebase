#!/usr/bin/env python3
"""LoomQ L2 交互入口 —— 零依赖网页版「量语」。

浏览器 ⇄ 内置小服务器 ⇄ adapter.agent_chat()

启动：python starter_kit/interactive.py   （需先设好 LOOMQ_LLM_* 环境变量）
访问：http://localhost:8000

设计说明：
  - 只用标准库 http.server / json，不装任何第三方包。
  - GET /        返回聊天页（内嵌单文件 HTML/CSS/JS）。
  - POST /chat   收 {message, history}；把上文拼进本轮 prompt 后调 agent_chat()，
                 返回 {reply}。多轮上下文靠服务器端拼历史实现（agent_chat 本身是单轮入口）。
  - 缺 API key / 模型报错时返回中文可读错误，前端展示，不崩。
"""

import json
import http.server
import socketserver
from urllib.parse import urlparse

import os
import sys

# ---------------------------------------------------------------------------
# 让脚本在仓库根 或 starter_kit/ 下都能直接 import adapter
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# 兼容从顶层包导入（starter_kit.adapter）与直连（adapter）两种路径
try:
    from starter_kit.adapter import agent_chat  # 当以包形式运行
except ImportError:
    try:
        from adapter import agent_chat          # 当直接跑 starter_kit/interactive.py
    except ImportError:
        from starter_kit.starter_kit.adapter import agent_chat  # 兜底

PORT = int(os.environ.get("LOOMQ_PORT", "8000"))

# 拼历史的窗口大小：只保留最近若干条，避免超长
MAX_HISTORY = 6


def _build_messages(history, message):
    """把上文拼进本轮，构造一次 agent_chat 的完整 prompt。"""
    if not history:
        return message
    parts = []
    for item in history[-MAX_HISTORY:]:
        if item.get("role") == "user":
            parts.append("用户问：" + (item.get("content") or ""))
        else:
            parts.append("助手答：" + (item.get("content") or ""))
    parts.append("用户现在问：" + message)
    return "以下是我们的对话上文：\n" + "\n".join(parts)


class Handler(http.server.BaseHTTPRequestHandler):
    # 关闭默认的 Server 头 + 允许跨域（本地调试友好）
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path == "/":
            self._send(200, PAGE, ctype="text/html; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urlparse(self.path).path != "/chat":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            message = (payload.get("message") or "").strip()
            history = payload.get("history") or []
        except (ValueError, json.JSONDecodeError):
            self._send(400, json.dumps({"error": "请求格式错误"}))
            return

        if not message:
            self._send(400, json.dumps({"error": "消息不能为空"}))
            return

        prompt = _build_messages(history, message)
        try:
            reply = agent_chat(prompt)
            self._send(200, json.dumps({"reply": reply}, ensure_ascii=False))
        except RuntimeError as exc:
            # 最常见的：缺环境变量 / 模型不可达。给中文可读提示。
            msg = str(exc)
            if "environment variable" in msg:
                hint = (
                    "还没有配置模型。请在启动前设置环境变量：\n"
                    "  LOOMQ_LLM_BASE_URL（例如 https://api.deepseek.com）\n"
                    "  LOOMQ_LLM_API_KEY（你的 key）\n"
                    "  LOOMQ_LLM_MODEL（例如 deepseek-v4-flash）"
                )
            else:
                hint = "调用模型出错：" + msg
            self._send(200, json.dumps({"reply": hint}, ensure_ascii=False))
        except Exception as exc:
            self._send(200, json.dumps(
                {"reply": "出错了：%s: %s" % (type(exc).__name__, exc)},
                ensure_ascii=False,
            ))

    def log_message(self, fmt, *args):
        # 安静模式，不刷屏
        pass


# ---------------------------------------------------------------------------
# 前端页面（单文件，内嵌 HTML/CSS/JS）
# ---------------------------------------------------------------------------
PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>量语 · 用自然语言使用量子计算机</title>
<style>
  :root {
    --sky-top: #dcedf9;
    --sky-mid: #eaf4fb;
    --sky-low: #f8fbff;
    --cloud: #ffffff;
    --ink: #2b3a4a;
    --ink-soft: #6f7f8b;
    --ink-faint: #93a1ac;
    --accent: #4a86e0;
    --accent-deep: #3a74cf;
    --card: rgba(255, 255, 255, 0.88);
    --line: #e2ecf5;
    --shadow: 0 18px 50px rgba(88, 132, 178, 0.16);
    --shadow-soft: 0 8px 28px rgba(88, 132, 178, 0.10);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }

  body {
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, -apple-system, sans-serif;
    color: var(--ink);
    background: linear-gradient(180deg, var(--sky-top) 0%, var(--sky-mid) 34%, var(--sky-low) 68%, #ffffff 100%);
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
    position: relative;
    min-height: 100vh;
  }

  /* ---------- 科技感动态线条 ---------- */
  #waves {
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    pointer-events: none;
  }

  /* ---------- 主体 ---------- */
  .wrap {
    position: relative;
    z-index: 2;
    max-width: 760px;
    margin: 0 auto;
    padding: clamp(48px, 10vh, 120px) 24px 80px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .hero { text-align: center; margin-bottom: 44px; }
  .eyebrow { font-size: 13px; letter-spacing: 0.22em; color: var(--accent); font-weight: 600; margin-bottom: 18px; }
  .hero h1 {
    font-size: clamp(30px, 5.4vw, 46px);
    line-height: 1.22;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--ink);
  }
  .hero p {
    margin: 18px auto 0;
    font-size: clamp(15px, 2.2vw, 17px);
    line-height: 1.7;
    color: var(--ink-soft);
    max-width: 560px;
  }

  /* ---------- 输入框 ---------- */
  .composer {
    width: 100%;
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 20px;
    box-shadow: var(--shadow);
    padding: 10px 12px 10px 18px;
    display: flex;
    align-items: flex-end;
    gap: 12px;
    transition: box-shadow .25s ease, border-color .25s ease, transform .25s ease;
  }
  .composer:focus-within {
    border-color: #bcd6f2;
    box-shadow: 0 22px 58px rgba(80, 126, 172, 0.22);
    transform: translateY(-2px);
  }
  .composer textarea {
    flex: 1;
    border: none;
    outline: none;
    resize: none;
    font-family: inherit;
    font-size: 17px;
    line-height: 1.6;
    color: var(--ink);
    background: transparent;
    max-height: 160px;
    padding: 10px 0 8px;
  }
  .composer textarea::placeholder { color: var(--ink-faint); }
  .composer textarea::-webkit-scrollbar { width: 6px; }
  .composer textarea::-webkit-scrollbar-thumb { background: #d4e2ee; border-radius: 3px; }

  .send {
    flex: 0 0 auto;
    width: 46px;
    height: 46px;
    border-radius: 14px;
    border: none;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    display: grid;
    place-items: center;
    transition: background .2s ease, transform .15s ease, opacity .2s ease;
    box-shadow: 0 8px 20px rgba(74, 134, 224, 0.32);
  }
  .send:hover { background: var(--accent-deep); transform: translateY(-1px); }
  .send:active { transform: translateY(0); }
  .send.off { opacity: .45; cursor: default; box-shadow: none; }
  .send svg { width: 20px; height: 20px; }

  /* ---------- 示例卡片 ---------- */
  .templates { width: 100%; margin-top: 44px; }
  .templates-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .templates-head span { font-size: 14px; color: var(--ink-soft); }
  .templates-head a { font-size: 14px; color: var(--accent); text-decoration: none; font-weight: 500; cursor: pointer; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 18px 18px 20px;
    cursor: pointer;
    text-align: left;
    backdrop-filter: blur(6px);
    box-shadow: var(--shadow-soft);
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
  }
  .card:hover { transform: translateY(-4px); box-shadow: var(--shadow); border-color: #c6dbf0; }
  .card .icon { font-size: 20px; margin-bottom: 12px; display: block; }
  .card h3 { font-size: 15px; font-weight: 600; color: var(--ink); margin-bottom: 6px; }
  .card p { font-size: 13px; line-height: 1.55; color: var(--ink-soft); }

  /* ---------- 对话视图 ---------- */
  .chat { width: 100%; display: none; flex-direction: column; gap: 16px; }
  .back {
    align-self: flex-start;
    border: none;
    background: transparent;
    color: var(--ink-soft);
    font-size: 14px;
    cursor: pointer;
    padding: 6px 0;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .back:hover { color: var(--accent); }
  .bubble { max-width: 92%; line-height: 1.65; font-size: 15px; }
  .bubble.user {
    align-self: flex-end;
    background: var(--accent);
    color: #fff;
    padding: 12px 18px;
    border-radius: 18px 18px 4px 18px;
    box-shadow: 0 8px 22px rgba(74, 134, 224, 0.26);
  }
  .bubble.bot {
    align-self: flex-start;
    background: #ffffff;
    border: 1px solid var(--line);
    color: var(--ink);
    padding: 14px 18px;
    border-radius: 18px 18px 18px 4px;
    box-shadow: var(--shadow-soft);
  }
  .bubble.bot.muted { color: var(--ink-soft); font-size: 14px; }
  .typing { display: inline-flex; gap: 5px; align-items: center; height: 20px; }
  .typing i { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); opacity: .4; animation: blink 1.2s infinite; }
  .typing i:nth-child(2) { animation-delay: .2s; }
  .typing i:nth-child(3) { animation-delay: .4s; }
  @keyframes blink { 0%,60%,100% { opacity:.35; transform: translateY(0);} 30% { opacity:1; transform: translateY(-3px);} }

  /* qasm 代码块 */
  pre.qasm {
    background: #f4f8fc;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 12px 14px;
    overflow-x: auto;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 13px;
    line-height: 1.6;
    color: #254a7a;
    white-space: pre;
    margin: 8px 0 0;
  }

  @media (max-width: 640px) {
    .cards { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
  <canvas id="waves"></canvas>

  <div class="wrap">
    <!-- 入口视图 -->
    <section id="view-enter">
      <div class="hero">
        <div class="eyebrow">量语 · QUANTALK</div>
        <h1>用自然语言，<br>使用量子计算机</h1>
        <p>不用懂量子黑话。把你想实现的结果告诉我，我来帮你把电路写好、选对机器、跑起来。</p>
      </div>

      <div class="composer">
        <textarea id="input" rows="1" placeholder="比如：帮我做一个 3 个比特的 GHZ 态，选哪个后端跑？"></textarea>
        <button class="send off" id="send" aria-label="发送">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 19V6M12 6l-6 6M12 6l6 6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>

      <div class="templates">
        <div class="templates-head">
          <span>不会说？从这几件事开始</span>
          <a onclick="return false">我可以做什么 ›</a>
        </div>
        <div class="cards">
          <div class="card" onclick="ask('帮我做一个 2 个比特的贝尔态电路')">
            <span class="icon">🔧</span>
            <h3>生成电路</h3>
            <p>「帮我做一个 2 个比特的贝尔态电路」</p>
          </div>
          <div class="card" onclick="ask('这个电路该用哪个后端跑最好？')">
            <span class="icon">🖥️</span>
            <h3>选后端</h3>
            <p>「这个电路该用哪个后端跑最好？」</p>
          </div>
          <div class="card" onclick="ask('帮我看看这段 QASM 哪里错了：H q[0]; CNOT q[0],q[1]')">
            <span class="icon">🧩</span>
            <h3>纠错修复</h3>
            <p>「这段 QASM 哪里错了，帮我修修」</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 对话视图 -->
    <section id="view-chat" class="chat">
      <button class="back" onclick="reset()">← 返回问题</button>
      <div id="bubbles" style="display:flex; flex-direction:column; gap:16px;"></div>
      <div class="composer">
        <textarea id="chat-input" rows="1" placeholder="继续问我…（Enter 发送，Shift+Enter 换行）"></textarea>
        <button class="send off" id="chat-send" aria-label="发送">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 19V6M12 6l-6 6M12 6l6 6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </section>
  </div>

<script>
  const enterInput = document.getElementById('input');
  const enterSend = document.getElementById('send');
  const chatInput = document.getElementById('chat-input');
  const chatSend = document.getElementById('chat-send');
  const viewEnter = document.getElementById('view-enter');
  const viewChat = document.getElementById('view-chat');
  const history = []; // 上文问答，随对话增长

  function setupComposer(inputEl, sendEl) {
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
      sendEl.classList.toggle('off', inputEl.value.trim() === '');
    });
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFrom(inputEl, sendEl); }
    });
    inputEl.addEventListener('blur', () => { if (!inputEl.value) inputEl.style.height = ''; });
    sendEl.addEventListener('click', () => sendFrom(inputEl, sendEl));
  }
  setupComposer(enterInput, enterSend);
  setupComposer(chatInput, chatSend);

  function sendFrom(inputEl, sendEl) {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    inputEl.style.height = '';
    sendEl.classList.add('off');
    goChat(text);
  }

  function ask(promptText) {
    goChat(promptText);
  }

  function goChat(text) {
    viewEnter.style.display = 'none';
    viewChat.style.display = 'flex';
    const bubbles = document.getElementById('bubbles');

    const ub = document.createElement('div');
    ub.className = 'bubble user';
    ub.textContent = text;
    bubbles.appendChild(ub);

    const bot = document.createElement('div');
    bot.className = 'bubble bot';
    bot.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
    bubbles.appendChild(bot);
    bubbles.scrollIntoView({ behavior: 'smooth', block: 'end' });

    fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: history.slice() }),
    })
      .then(r => r.json())
      .then(data => {
        const reply = data.reply || data.error || '（没有返回内容）';
        bot.classList.remove('muted');
        bot.innerHTML = renderReply(reply);
        history.push({ role: 'user', content: text });
        history.push({ role: 'assistant', content: data.reply || '' });
        bubbles.scrollIntoView({ behavior: 'smooth', block: 'end' });
      })
      .catch(err => {
        bot.classList.add('muted');
        bot.textContent = '连接服务器失败：' + err.message;
      });
  }

  // 把模型的回复渲染成气泡：qasm 代码块样式化，其余按纯文本
  function renderReply(text) {
    const txt = text || '';
    // 提取 ```qasm ... ``` 代码块
    const parts = [];
    const re = /```qasm\n([\s\S]*?)```/g;
    let last = 0, m;
    const frags = [];
    while ((m = re.exec(txt)) !== null) {
      if (m.index > last) frags.push({ type: 'text', content: txt.slice(last, m.index) });
      frags.push({ type: 'qasm', content: m[1].trim() });
      last = re.lastIndex;
    }
    if (last < txt.length) frags.push({ type: 'text', content: txt.slice(last) });

    for (const f of frags) {
      if (f.type === 'qasm') {
        const pre = document.createElement('pre');
        pre.className = 'qasm';
        pre.textContent = f.content;
        parts.push(pre);
      } else {
        const div = document.createElement('div');
        div.style.whiteSpace = 'pre-wrap';
        div.textContent = f.content.trim();
        parts.push(div);
      }
    }
    const wrap = document.createElement('div');
    parts.forEach(p => wrap.appendChild(p));
    return wrap.innerHTML;
  }

  function reset() {
    viewChat.style.display = 'none';
    viewEnter.style.display = 'block';
    history.length = 0;
    enterInput.value = '';
    enterInput.style.height = '';
    chatInput.value = '';
    chatInput.style.height = '';
    enterSend.classList.add('off');
    chatSend.classList.add('off');
    enterInput.focus();
  }

  // ============ 科技感动态正弦波线条 ============
  const wv = document.getElementById('waves');
  const wctx = wv.getContext('2d');
  let wdpr = Math.min(window.devicePixelRatio || 1, 2);
  let ww, wh;

  function resizeWave() {
    wdpr = Math.min(window.devicePixelRatio || 1, 2);
    ww = window.innerWidth;
    wh = window.innerHeight;
    wv.width = ww * wdpr;
    wv.height = wh * wdpr;
    wv.style.width = ww + 'px';
    wv.style.height = wh + 'px';
    wctx.setTransform(wdpr, 0, 0, wdpr, 0, 0);
  }
  resizeWave();
  window.addEventListener('resize', resizeWave);

  const WAVES = [
    { amp: 26,  freq: 0.008, speed: 0.010, y0: 0.30, alpha: 0.20, width: 1.4, phase: 0 },
    { amp: 40,  freq: 0.006, speed: 0.008, y0: 0.44, alpha: 0.16, width: 1.6, phase: 1.3 },
    { amp: 30,  freq: 0.010, speed: 0.013, y0: 0.56, alpha: 0.14, width: 1.2, phase: 2.6 },
    { amp: 22,  freq: 0.009, speed: 0.011, y0: 0.68, alpha: 0.12, width: 1.3, phase: 4.0 },
    { amp: 34,  freq: 0.005, speed: 0.007, y0: 0.82, alpha: 0.10, width: 1.5, phase: 5.1 },
  ];
  const WAVE_COLOR = '130, 170, 225';

  function drawWave(t) {
    wctx.clearRect(0, 0, ww, wh);
    for (const w of WAVES) {
      wctx.beginPath();
      wctx.strokeStyle = `rgba(${WAVE_COLOR}, ${w.alpha})`;
      wctx.lineWidth = w.width;
      const baseY = wh * w.y0;
      for (let x = 0; x <= ww; x += 6) {
        const y = baseY
          + Math.sin(x * w.freq + t * w.speed + w.phase) * w.amp
          + Math.sin(x * w.freq * 0.5 - t * w.speed * 0.6 + w.phase * 2) * w.amp * 0.35;
        if (x === 0) wctx.moveTo(x, y);
        else wctx.lineTo(x, y);
      }
      wctx.stroke();
    }
  }

  let wt = 0;
  (function flow() {
    wt += 1;
    drawWave(wt);
    requestAnimationFrame(flow);
  })();
</script>
</body>
</html>
"""


def main():
    server = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    print("量语 · 交互入口已启动：http://localhost:%d" % PORT)
    print("如需停止，按 Ctrl+C。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
