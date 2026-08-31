# -*- coding: utf-8 -*-
from flask import Flask, request, render_template_string, jsonify
import io
import base64
import re
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from starter_kit.adapter import agent_chat, run

load_dotenv()

app = Flask(__name__)

TEMPLATES = {
    "bell": {
        "name": "🔮 贝尔态",
        "description": "两个量子比特的纠缠态，量子计算的入门实验",
        "prompt": "生成一个2比特的贝尔态，并运行",
        "tags": ["纠缠", "入门"],
        "category": "基础实验"
    },
    "ghz": {
        "name": "🌀 GHZ 态",
        "description": "三个量子比特的最大纠缠态，验证多体量子纠缠",
        "prompt": "生成一个3比特的GHZ态，并运行",
        "tags": ["纠缠", "多比特"],
        "category": "基础实验"
    },
    "grover": {
        "name": "🔍 Grover 搜索",
        "description": "量子搜索算法，比经典算法平方加速",
        "prompt": "生成一个3比特的Grover搜索算法电路，搜索目标态为101",
        "tags": ["算法", "搜索"],
        "category": "量子算法"
    },
    "qft": {
        "name": "📐 QFT 变换",
        "description": "量子傅里叶变换，Shor算法的核心组件",
        "prompt": "生成一个4比特的量子傅里叶变换(QFT)电路",
        "tags": ["算法", "傅里叶"],
        "category": "量子算法"
    }
}

# ============================================================
# HTML 模板
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LoomQ · 量子接入平权计划</title>
    <style>
        /* ===== 全局重置 ===== */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: #f5f7fa;
            color: #1a1a2e;
            line-height: 1.6;
        }

        /* ===== Hero 区 ===== */
        .hero {
            background: linear-gradient(135deg, #0a0e1a 0%, #1a1a3e 40%, #0f3460 100%);
            color: white;
            padding: 60px 20px 50px;
            position: relative;
            overflow: hidden;
            min-height: 420px;
            display: flex;
            align-items: center;
        }
        .hero::before {
            content: '';
            position: absolute;
            inset: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400"><circle cx="100" cy="200" r="80" fill="rgba(0,212,255,0.06)"/><circle cx="700" cy="100" r="120" fill="rgba(74,144,217,0.05)"/><circle cx="400" cy="350" r="60" fill="rgba(0,212,255,0.04)"/><circle cx="200" cy="50" r="40" fill="rgba(74,144,217,0.04)"/></svg>') no-repeat center/cover;
            pointer-events: none;
        }
        .hero-content {
            max-width: 1100px;
            margin: 0 auto;
            width: 100%;
            position: relative;
            z-index: 1;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(0,212,255,0.15);
            border: 1px solid rgba(0,212,255,0.25);
            border-radius: 20px;
            padding: 4px 16px;
            font-size: 13px;
            color: #00d4ff;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
        }
        .hero h1 {
            font-size: 48px;
            font-weight: 800;
            letter-spacing: -0.5px;
            line-height: 1.15;
        }
        .hero h1 span { color: #00d4ff; }
        .hero p {
            font-size: 18px;
            opacity: 0.85;
            max-width: 560px;
            margin: 16px 0 24px;
        }
        .hero-stats {
            display: flex;
            gap: 40px;
            flex-wrap: wrap;
        }
        .hero-stats .stat {
            display: flex;
            flex-direction: column;
        }
        .hero-stats .stat .num {
            font-size: 28px;
            font-weight: 700;
            color: #00d4ff;
        }
        .hero-stats .stat .label {
            font-size: 13px;
            opacity: 0.7;
        }

        /* ===== 容器 ===== */
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px 20px 40px;
        }

        /* ===== 价值主张 ===== */
        .value-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin: -20px auto 32px;
            position: relative;
            z-index: 2;
        }
        .value-card {
            background: white;
            border-radius: 14px;
            padding: 22px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.07);
            text-align: center;
            border: 1px solid #eef2f7;
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }
        .value-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 32px rgba(0,0,0,0.10);
        }
        .value-card .icon { font-size: 32px; margin-bottom: 6px; }
        .value-card h3 { font-size: 16px; color: #1a1a2e; margin-bottom: 4px; }
        .value-card p { font-size: 13px; color: #666; }

        /* ===== 新手引导区 ===== */
        .guide-section {
            background: white;
            border-radius: 16px;
            padding: 28px 30px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.05);
            margin-bottom: 28px;
            border: 1px solid #eef2f7;
        }
        .guide-section h2 {
            font-size: 18px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .guide-section .sub {
            color: #666;
            font-size: 14px;
            margin-bottom: 14px;
        }
        .guide-buttons {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        .btn-guide {
            padding: 10px 24px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-guide.primary {
            background: linear-gradient(135deg, #4a90d9, #357abd);
            color: white;
        }
        .btn-guide.primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(74,144,217,0.35);
        }
        .btn-guide.secondary {
            background: #eef2f7;
            color: #333;
        }
        .btn-guide.secondary:hover {
            background: #d5dce8;
        }
        .guide-chat {
            margin-top: 16px;
            background: #f8faff;
            border-radius: 12px;
            padding: 16px 20px;
            border-left: 4px solid #4a90d9;
            font-size: 14px;
            color: #333;
            line-height: 1.7;
            display: none;
        }
        .guide-chat.show { display: block; }
        .guide-chat .step { font-weight: 600; color: #4a90d9; }
        .guide-chat .typing {
            color: #888;
            font-style: italic;
        }

        /* ===== 输入区 ===== */
        .input-area {
            background: white;
            border-radius: 16px;
            padding: 24px 28px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.05);
            border: 1px solid #eef2f7;
            margin-bottom: 24px;
        }
        .input-area textarea {
            width: 100%;
            padding: 14px 16px;
            font-size: 15px;
            border: 2px solid #e0e4ea;
            border-radius: 10px;
            resize: vertical;
            min-height: 72px;
            font-family: inherit;
            transition: border-color 0.2s;
        }
        .input-area textarea:focus {
            outline: none;
            border-color: #4a90d9;
            box-shadow: 0 0 0 3px rgba(74,144,217,0.12);
        }
        .input-row {
            display: flex;
            gap: 12px;
            margin-top: 14px;
            flex-wrap: wrap;
            align-items: center;
        }
        .btn {
            padding: 10px 32px;
            background: linear-gradient(135deg, #4a90d9, #357abd);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(74,144,217,0.35);
        }
        .btn-secondary {
            background: #e8ecf3;
            color: #333;
        }
        .btn-secondary:hover {
            background: #d5dce8;
            box-shadow: none;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .spinner {
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 3px solid #e0e4ea;
            border-top: 3px solid #4a90d9;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            vertical-align: middle;
            margin-right: 8px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* ===== 模板卡片 ===== */
        .template-section {
            margin-bottom: 24px;
        }
        .template-section h2 {
            font-size: 17px;
            color: #1a1a2e;
            margin-bottom: 12px;
        }
        .template-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
            gap: 12px;
        }
        .template-card {
            background: white;
            border-radius: 12px;
            padding: 14px 16px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border: 2px solid transparent;
            transition: all 0.2s;
            text-align: left;
        }
        .template-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            border-color: #4a90d9;
        }
        .template-card .name { font-weight: 600; font-size: 14px; }
        .template-card .desc { font-size: 12px; color: #666; margin: 2px 0 6px; }
        .template-card .tags { display: flex; gap: 4px; flex-wrap: wrap; }
        .template-card .tag {
            background: #eef2f7;
            border-radius: 10px;
            padding: 1px 10px;
            font-size: 10px;
            color: #555;
        }

        /* ===== 结果区 ===== */
        .result-area {
            background: white;
            border-radius: 16px;
            padding: 24px 28px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.05);
            margin-top: 24px;
            border: 1px solid #eef2f7;
            display: none;
        }
        .result-area.show { display: block; }
        .result-area h3 {
            font-size: 16px;
            color: #1a1a2e;
            margin: 16px 0 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .result-area h3:first-of-type { margin-top: 0; }
        .qasm-block {
            background: #1a1a2e;
            color: #cdd6f4;
            padding: 14px 18px;
            border-radius: 10px;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 13px;
            overflow-x: auto;
            white-space: pre-wrap;
            max-height: 350px;
            overflow-y: auto;
        }
        .counts-table {
            border-collapse: collapse;
            margin: 8px 0 12px;
        }
        .counts-table th, .counts-table td {
            border: 1px solid #ddd;
            padding: 6px 20px;
            text-align: center;
        }
        .counts-table th { background: #f0f4fa; }
        .chart-container img { max-width: 100%; border-radius: 10px; margin: 8px 0; }
        .explanation {
            background: #f0f7ff;
            border-left: 4px solid #4a90d9;
            padding: 14px 18px;
            border-radius: 6px;
            margin: 10px 0;
            font-size: 14px;
            line-height: 1.7;
        }
        .badge {
            display: inline-block;
            background: #eef2f7;
            border-radius: 10px;
            padding: 2px 12px;
            font-size: 12px;
            color: #555;
            margin-right: 6px;
        }
        .ref-list { padding-left: 20px; line-height: 1.9; }
        .ref-list li { font-size: 14px; }

        /* ===== Footer ===== */
        .footer {
            text-align: center;
            padding: 30px 20px 20px;
            color: #999;
            font-size: 13px;
            border-top: 1px solid #eef2f7;
            margin-top: 20px;
        }

        /* ===== 响应式 ===== */
        @media (max-width: 640px) {
            .hero { padding: 40px 16px 36px; min-height: 320px; }
            .hero h1 { font-size: 30px; }
            .hero p { font-size: 15px; }
            .hero-stats .stat .num { font-size: 20px; }
            .container { padding: 16px 12px; }
            .value-section { grid-template-columns: 1fr; margin-top: -10px; }
            .template-grid { grid-template-columns: 1fr 1fr; }
            .input-area { padding: 16px; }
            .input-row { flex-direction: column; align-items: stretch; }
        }
    </style>
</head>
<body>

<!-- ===== HERO ===== -->
<div class="hero">
    <div class="hero-content">
        <div class="hero-badge">🧪 量子接入平权计划 · 2026</div>
        <h1>让不懂"黑话"的人，<br>也能指挥<span>最前沿的算力</span></h1>
        <p>LoomQ 是一个智能量子中间层 —— 你只需用自然语言描述需求，我们生成电路、自动运行、并解释结果。</p>
        <div class="hero-stats">
            <div class="stat"><span class="num">3</span><span class="label">模拟器后端</span></div>
            <div class="stat"><span class="num">12</span><span class="label">门白名单</span></div>
            <div class="stat"><span class="num">0</span><span class="label">量子背景要求</span></div>
        </div>
    </div>
</div>

<div class="container">

    <!-- ===== 价值主张 ===== -->
    <div class="value-section">
        <div class="value-card">
            <div class="icon">🧠</div>
            <h3>零门槛 · 说人话</h3>
            <p>不需要懂 QASM，不需要学线性代数。用日常语言描述你的想法。</p>
        </div>
        <div class="value-card">
            <div class="icon">🔁</div>
            <h3>智能引导 · 需求诊断</h3>
            <p>不知道从哪开始？点击「我不知道怎么问」，LoomQ 会主动引导你。</p>
        </div>
        <div class="value-card">
            <div class="icon">📊</div>
            <h3>即学即用 · 自带解释</h3>
            <p>每个结果都附有物理意义解读和参考资料，边用边学。</p>
        </div>
        <div class="value-card">
            <div class="icon">🚀</div>
            <h3>一键模板 · 快速上手</h3>
            <p>内置贝尔态、GHZ 态、Grover 搜索等经典电路，点击即运行。</p>
        </div>
    </div>

    <!-- ===== 新手引导区 ===== -->
    <div class="guide-section">
        <h2>🤖 新手引导 · 需求诊断</h2>
        <div class="sub">不知道从哪开始？告诉我你想做什么，我来帮你梳理。</div>
        <div class="guide-buttons">
            <button class="btn-guide primary" onclick="startGuide()">💡 我不知道怎么问</button>
            <button class="btn-guide secondary" onclick="closeGuide()">✕ 收起</button>
        </div>
        <div class="guide-chat" id="guideChat">
            <div id="guideContent">
                <span class="step">🧐 LoomQ 智能体</span><br>
                <span id="guideText">你好！我是 LoomQ 智能体。为了更好地帮助你，我需要了解一些信息：<br><br>
                <strong>你遇到了什么问题？或者你想用量子计算做什么？</strong><br><br>
                （可以简短描述，例如：我想验证量子纠缠、我想理解 Grover 搜索、我想生成随机数……）
                </span>
                <div style="margin-top:12px; display:flex; gap:10px; flex-wrap:wrap;">
                    <input type="text" id="guideInput" placeholder="输入你的需求…" style="flex:1; min-width:160px; padding:8px 12px; border:1px solid #ddd; border-radius:6px;">
                    <button class="btn-guide primary" onclick="sendGuide()" style="padding:8px 20px;">发送</button>
                </div>
                <div id="guideResponse" style="margin-top:12px; color:#4a90d9; font-weight:500;"></div>
            </div>
        </div>
    </div>

    <!-- ===== 输入区 ===== -->
    <div class="input-area">
        <form method="POST" id="mainForm">
            <textarea name="user_input" id="userInput" placeholder="描述你想做什么… 例如：生成一个贝尔态并运行">{{ user_input or '' }}</textarea>
            <div class="input-row">
                <!-- 新增：后端选择下拉菜单 -->
                <select name="target_backend" style="padding:8px 12px; border-radius:6px; border:1px solid #ddd; background:white; font-size:14px;">
                    <option value="auto">🤖 自动选择</option>
                    <option value="spinq">量旋 (SpinQ)</option>
                    <option value="braket">AWS Braket</option>
                    <option value="originq">本源 (OriginQ)</option>
                </select>
                <button type="submit" class="btn" id="runBtn">🚀 运行</button>
                <button type="button" class="btn-secondary btn" onclick="clearInput()">🗑️ 清空</button>
                <span id="loadingHint" style="display:none; font-size:14px; color:#666; align-self:center;">
                    <span class="spinner"></span> 智能体思考中…
                </span>
            </div>
        </form>
    </div>

    <!-- ===== 预设模板 ===== -->
    <div class="template-section">
        <h2>📚 快速体验 · 点击即用</h2>
        <div class="template-grid">
            {% for key, tmpl in templates.items() %}
            <div class="template-card" onclick="fillTemplate('{{ tmpl.prompt }}')">
                <div class="name">{{ tmpl.name }}</div>
                <div class="desc">{{ tmpl.description }}</div>
                <div class="tags">
                    {% for tag in tmpl.tags[:2] %}
                    <span class="tag">{{ tag }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ===== 结果区 ===== -->
    {% if result or counts or explanation %}
    <div class="result-area show" id="resultArea">
        {% if result %}
        <h3>📄 生成结果</h3>
        <div class="qasm-block">{{ result }}</div>
        {% endif %}

        {% if counts %}
        <h3>📊 测量结果</h3>
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
            <span class="badge">shots: 1024</span>
            <span class="badge">后端: {{ backend or 'spinq_taurus' }}</span>
        </div>
        <table class="counts-table">
            <tr><th>状态</th><th>次数</th></tr>
            {% for k, v in counts.items() %}
            <tr><td>{{ k }}</td><td>{{ v }}</td></tr>
            {% endfor %}
        </table>
        {% if plot_url %}
        <div class="chart-container">
            <img src="data:image/png;base64,{{ plot_url }}" alt="Counts 柱状图">
        </div>
        {% endif %}
        {% endif %}

        {% if explanation %}
        <h3>🔬 物理意义</h3>
        <div class="explanation">{{ explanation }}</div>
        {% endif %}

        {% if refs %}
        <h3>📚 参考资料</h3>
        <ul class="ref-list">
            {% for ref in refs %}
            <li>{{ ref|safe }}</li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>
    {% endif %}
</div>

<div class="footer">
    LoomQ · 量子接入平权计划 &nbsp;|&nbsp; 让更多人用上量子计算 &nbsp;|&nbsp; Powered by DeepSeek
</div>

<!-- ===== JavaScript ===== -->
<script>
// 填充模板并立即运行（点击即运行）
function fillTemplate(text) {
    document.getElementById('userInput').value = text;
    document.getElementById('mainForm').submit();
}

function clearInput() {
    document.getElementById('userInput').value = '';
    // 同时清空已展示的结果
    const area = document.getElementById('resultArea');
    if (area) {
        area.classList.remove('show');
        area.style.display = 'none';
    }
    document.getElementById('userInput').focus();
}

// 引导对话（真实调用后端 LLM）
function startGuide() {
    const chat = document.getElementById('guideChat');
    chat.classList.add('show');
    document.getElementById('guideText').innerHTML =
        '你好！我是 LoomQ 智能体。为了更好地帮助你，我需要了解一些信息：<br><br>' +
        '<strong>你遇到了什么问题？或者你想用量子计算做什么？</strong><br><br>' +
        '（可以简短描述，例如：我想验证量子纠缠、我想理解 Grover 搜索、我想生成随机数……）';
    document.getElementById('guideResponse').innerHTML = '';
    document.getElementById('guideInput').value = '';
    document.getElementById('guideInput').focus();
}

function closeGuide() {
    document.getElementById('guideChat').classList.remove('show');
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}

function sendGuide() {
    const input = document.getElementById('guideInput');
    const response = document.getElementById('guideResponse');
    const msg = input.value.trim();
    if (!msg) { alert('请输入你的需求'); return; }

    response.innerHTML = '👤 你：' + escapeHtml(msg) + '<br><br>🤖 LoomQ：正在为你生成电路…';
    // 把需求填入主输入框并直接运行（真实调用后端）
    document.getElementById('userInput').value = msg;
    document.getElementById('mainForm').submit();
}

// 提交表单时显示 loading
document.getElementById('mainForm').addEventListener('submit', function() {
    document.getElementById('runBtn').disabled = true;
    document.getElementById('runBtn').textContent = '⏳ 运行中…';
    document.getElementById('loadingHint').style.display = 'inline-flex';
});

// 如果有结果，滚动到结果区
window.onload = function() {
    const area = document.getElementById('resultArea');
    if (area && area.classList.contains('show')) {
        setTimeout(() => area.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
    }
}
</script>

</body>
</html>
"""

# ============================================================
# Flask 路由
# ============================================================

def generate_explanation(raw_response: str, counts: dict) -> str:
    gates = re.findall(r'\b(h|x|cx|ccx|swap|rz|ry|cu1|s|sdg|t|tdg)\b', raw_response.lower())
    unique_gates = sorted(set(gates))
    h_count = gates.count('h')
    cx_count = gates.count('cx')

    # QFT：以受控相位门 cu1 为特征（傅里叶变换的核心相位门）
    if 'cu1' in gates:
        return """这个电路实现了 **量子傅里叶变换 (QFT)**。

- QFT 是 Shor 算法的核心组件，用于分解大整数
- 将量子态从位置基变换到相位基，提取周期信息

**应用场景**：整数分解、离散对数求解、相位估计等。"""
    # Grover：以 Toffoli 门 ccx 为特征（oracle / 扩散算子常用多控门）
    if 'ccx' in gates:
        return """这个电路实现了 **Grover 搜索算法**。

- 量子搜索算法可以在 O(√N) 步内完成搜索，比经典算法 O(N) 平方加速
- 核心操作：Oracle（标记目标态）+ 扩散算子（放大概率振幅）

**应用场景**：数据库搜索、密码破解、模式识别等。"""

    # 纠缠态按门组合判断（贝尔态 1 个 H + 1 个 CX；GHZ 1 个 H + 多个 CX）
    if h_count == 1 and cx_count == 1:
        return """这个电路制备了 **贝尔态 (Bell State)**，是量子纠缠最典型的例子。

- **H 门**（Hadamard）将量子比特置入叠加态
- **CNOT 门**（受控非门）将两个量子比特纠缠在一起

**测量结果解读**：两个量子比特的测量结果完全相关——要么都是 0，要么都是 1。这违反了经典物理的局域实在论，是量子力学核心特征的直接体现。"""
    if h_count == 1 and cx_count >= 2:
        return """这个电路制备了 **GHZ 态**，是多比特量子纠缠的经典案例。

- 通过多个 CNOT 门将多个量子比特纠缠在一起
- 所有量子比特的测量结果完全一致（全 0 或全 1）

**物理意义**：GHZ 态是多体量子纠缠的典型代表，在量子通信和量子计算中具有重要应用。"""

    return """量子电路执行成功。

电路包含 {} 种不同类型的量子门：{}。

**测量结果**反映了量子态的分布。如果你使用的是标准电路（如贝尔态、GHZ态），结果会呈现特定的相关性模式。""".format(len(unique_gates), ', '.join(unique_gates[:5]))

def generate_references(raw_response: str) -> list:
    refs = [
        '<a href="https://doc.spinq.cn/doc/spinqit/index.html" target="_blank">📖 量旋 SpinQit 文档</a>',
        '<a href="https://docs.aws.amazon.com/braket/" target="_blank">📖 AWS Braket 开发者文档</a>'
    ]
    if 'grover' in raw_response.lower():
        refs.append('<a href="https://en.wikipedia.org/wiki/Grover%27s_algorithm" target="_blank">📖 Grover 算法 (Wikipedia)</a>')
    if 'qft' in raw_response.lower() or 'fourier' in raw_response.lower():
        refs.append('<a href="https://en.wikipedia.org/wiki/Quantum_Fourier_transform" target="_blank">📖 量子傅里叶变换 (Wikipedia)</a>')
    if 'bell' in raw_response.lower() or 'ghz' in raw_response.lower():
        refs.append('<a href="https://en.wikipedia.org/wiki/Bell_state" target="_blank">📖 贝尔态 / GHZ 态 (Wikipedia)</a>')
    return refs

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_input = request.form.get('user_input', '')
        if not user_input.strip():
            return render_template_string(HTML_TEMPLATE, templates=TEMPLATES)

        # 读取用户选择的后端（如果有）
        target_backend = request.form.get('target_backend', 'auto')

        try:
            raw_response = agent_chat(user_input)
            is_qasm = "OPENQASM" in raw_response
            counts = None
            plot_url = None
            explanation = ""
            refs = []
            backend = None

            if is_qasm:
                # 根据用户选择决定尝试哪些后端
                if target_backend != 'auto':
                    # 用户指定了具体后端
                    backend_map = {
                        'spinq': 'spinq_taurus',
                        'braket': 'braket_local_simulator',
                        'originq': 'originq_local_simulator'
                    }
                    label = backend_map.get(target_backend, 'spinq_taurus')
                    backends_to_try = [(target_backend, label)]
                else:
                    # 自动尝试三个后端
                    backends_to_try = [
                        ("spinq", "spinq_taurus"),
                        ("braket", "braket_local_simulator"),
                        ("originq", "originq_local_simulator"),
                    ]

                counts = None
                backend = None
                for try_target, label in backends_to_try:
                    try:
                        result = run(raw_response, try_target, 1024)
                        counts = result.get("counts")
                        backend = result.get("backend", label)
                        break  # 成功则跳出循环
                    except Exception as e:
                        # 记录错误，继续尝试下一个后端
                        print(f"{try_target} 执行失败: {e}")
                        continue

                if counts:
                    # 绘制柱状图
                    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
                    plt.rcParams['axes.unicode_minus'] = False
                    fig, ax = plt.subplots(figsize=(6, 3.5))
                    ax.bar(counts.keys(), counts.values(), color='#4a90d9', edgecolor='white', linewidth=1.2)
                    ax.set_xlabel('状态')
                    ax.set_ylabel('次数')
                    ax.set_title('测量结果分布')
                    ax.grid(axis='y', linestyle='--', alpha=0.4)
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
                    buf.seek(0)
                    plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
                    plt.close()

                explanation = generate_explanation(raw_response, counts) if counts else "电路已生成，但所有尝试的后端均未能运行。请检查 QASM 语法或手动选择其他后端。"
                refs = generate_references(raw_response)

            result_display = raw_response if is_qasm else f"💡 后端建议：{raw_response}"

            return render_template_string(HTML_TEMPLATE,
                                          templates=TEMPLATES,
                                          user_input=user_input,
                                          result=result_display,
                                          counts=counts,
                                          plot_url=plot_url,
                                          explanation=explanation,
                                          refs=refs,
                                          backend=backend)
        except Exception as e:
            return render_template_string(HTML_TEMPLATE,
                                          templates=TEMPLATES,
                                          user_input=user_input,
                                          result=f"❌ 执行出错：{str(e)}")
    else:
        return render_template_string(HTML_TEMPLATE, templates=TEMPLATES)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)