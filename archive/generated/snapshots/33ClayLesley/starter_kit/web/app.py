import sys
import os
import json
import tempfile
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from qiskit.visualization import (
    plot_histogram,
    plot_bloch_multivector,
    plot_state_city,
    plot_state_hinton,
    plot_state_qsphere,
)
from qiskit import QuantumCircuit
from qiskit_aer import Aer
from qiskit.qasm2 import loads
from starter_kit.adapter import agent_chat, run
import re

# ================== 页面配置 ==================
st.set_page_config(
    page_title="LoomQ · 量子游乐场",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================== 加载后端能力表 ==================
BACKENDS_PATH = Path(__file__).parent.parent / "backend_capabilities.json"
try:
    with open(BACKENDS_PATH, "r", encoding="utf-8") as f:
        BACKENDS = json.load(f)["backends"]
except Exception:
    BACKENDS = []


# ================== 工具函数 ==================
def parse_qasm_ops(qasm_code: str):
    """解析 QASM 为操作列表，供交互式电路渲染器使用。"""
    try:
        circuit = loads(qasm_code)
        ops = []
        for instr, qargs, cargs in circuit.data:
            op = {
                "gate": instr.name,
                "qubits": [circuit.find_bit(q).index for q in qargs],
                "cbits": [circuit.find_bit(c).index for c in cargs],
                "params": [str(p) for p in instr.params] if instr.params else [],
            }
            ops.append(op)
        return ops, circuit.num_qubits, circuit.num_clbits
    except Exception:
        return None, 0, 0


def assign_columns(ops, num_qubits):
    """贪心列分配，用于电路布局。"""
    last_col = [-1] * num_qubits
    for op in ops:
        col = max(last_col[q] for q in op["qubits"]) + 1
        op["col"] = col
        for q in op["qubits"]:
            last_col[q] = col
    return ops


def gates_to_qasm(gates, num_qubits):
    """把游乐场中的门列表转成 QASM。"""
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";',
             f'qreg q[{num_qubits}];', f'creg c[{num_qubits}];']
    for g in gates:
        t = g["type"]
        if t == "h":
            lines.append(f'h q[{g["q"]}];')
        elif t == "x":
            lines.append(f'x q[{g["q"]}];')
        elif t == "y":
            lines.append(f'y q[{g["q"]}];')
        elif t == "z":
            lines.append(f'z q[{g["q"]}];')
        elif t == "cx":
            lines.append(f'cx q[{g["c"]}],q[{g["t"]}];')
        elif t == "measure":
            lines.append(f'measure q[{g["q"]}] -> c[{g["q"]}];')
    return "\n".join(lines)


def recommend_backend(num_qubits, want_real=False):
    """根据比特数、类型、排队与成本推荐后端。"""
    if not BACKENDS:
        return None
    candidates = [b for b in BACKENDS if b["max_qubits"] >= num_qubits]
    if want_real:
        candidates = [b for b in candidates if b["kind"] == "qpu"]
    if not candidates:
        return None
    # 排序：模拟器优先（免费、无排队），再按 max_qubits 升序
    def sort_key(b):
        kind_rank = 0 if b["kind"] == "simulator" else 1
        queue_rank = 0 if b["queue"] == "none" else 1
        return (kind_rank, queue_rank, b["max_qubits"])
    candidates.sort(key=sort_key)
    return candidates[0]


def is_backend_recommendation(response: str) -> bool:
    """检测 agent_chat 返回是否为「智能推荐后端」模式（仅返回后端标识符）。"""
    text = response.strip()
    if not text or "```" in text or "OPENQASM" in text:
        return False
    # 匹配已知后端名称（如 braket_local_simulator）
    known_names = {b["name"] for b in BACKENDS}
    if text in known_names:
        return True
    # 兜底：匹配规范后端标识符模式（小写字母+下划线）
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", text)) and "_" in text


# ================== 主题 CSS ==================
st.markdown("""
<style>
    /* 全局暗色主题 */
    .stApp { background-color: #0d0d0d; }
    h1, h2, h3, h4, h5, h6 {
        color: #00aa55 !important;
        font-family: 'Courier New', monospace;
        text-shadow: 0 0 5px #00aa55;
    }
    p, li, .stMarkdown { color: #aaffaa !important; }
    .stTextArea textarea {
        background-color: #1a1a1a !important;
        color: #00aa55 !important;
        border: 1px solid #00aa55 !important;
        font-family: 'Courier New', monospace;
    }
    .stButton button {
        background-color: #0d0d0d !important;
        color: #00aa55 !important;
        border: 1px solid #00aa55 !important;
        font-family: 'Courier New', monospace;
        transition: all 0.3s;
    }
    .stButton button:hover {
        background-color: #00aa55 !important;
        color: #0d0d0d !important;
        box-shadow: 0 0 20px #00aa55;
    }
    .stSidebar { background-color: #0d0d0d !important; }
    .stCodeBlock { background-color: #1a1a1a !important; border-left: 3px solid #00aa55; }
    .stSuccess { background-color: #0a1a0a !important; color: #aaffaa !important; border-left: 3px solid #00aa55; }
    .stInfo { background-color: #0a1a0a !important; color: #aaffaa !important; border-left: 3px solid #00aa55; }
    .stWarning { background-color: #1a1a0a !important; color: #ffffaa !important; border-left: 3px solid #ffff00; }
    .stError { background-color: #1a0a0a !important; color: #ffaaaa !important; border-left: 3px solid #ff0000; }

    /* 英雄区动画标题 */
    .hero-title {
        font-size: 3.2rem; font-weight: bold; color: #00ff88;
        text-shadow: 0 0 20px #00aa55, 0 0 40px #00aa55;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { text-shadow: 0 0 20px #00aa55, 0 0 40px #00aa55; }
        50% { text-shadow: 0 0 30px #00ff88, 0 0 60px #00ff88; }
    }
    .hero-sub {
        color: #aaffaa; font-size: 1.2rem; opacity: 0.9;
    }

    /* 类比卡片 */
    .analogy-card {
        background: #0a1a0a; border: 1px solid #00aa55; border-radius: 10px;
        padding: 15px; margin: 8px 0; color: #aaffaa;
        transition: transform 0.3s, box-shadow 0.3s;
    }
    .analogy-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 0 20px #00aa55;
    }
    .analogy-card .emoji { font-size: 2rem; }
    .analogy-card .title { color: #00ff88; font-weight: bold; font-size: 1.1rem; }

    /* 徽章 */
    .badge {
        display: inline-block; background: #0a1a0a; border: 1px solid #00aa55;
        color: #00ff88; border-radius: 20px; padding: 4px 12px; margin: 4px;
        font-family: 'Courier New', monospace; font-size: 0.9rem;
    }
    .badge-earned { background: #00aa55; color: #0d0d0d; box-shadow: 0 0 10px #00aa55; }
    .badge-backend {
        display: inline-block; background: #00aa55; color: #0d0d0d;
        border: 1px solid #00ff88; border-radius: 25px; padding: 10px 24px;
        font-family: 'Courier New', monospace; font-size: 1.2rem;
        box-shadow: 0 0 15px #00aa55; margin: 20px 0;
    }

    /* 步骤指示器 */
    .step-indicator {
        display: flex; justify-content: center; gap: 10px; margin: 15px 0;
    }
    .step-dot {
        width: 14px; height: 14px; border-radius: 50%;
        background: #1a1a1a; border: 2px solid #00aa55;
    }
    .step-dot.active { background: #00ff88; box-shadow: 0 0 10px #00ff88; }
    .step-dot.done { background: #00aa55; }
</style>
""", unsafe_allow_html=True)


# ================== 交互式电路渲染器（HTML 组件） ==================
GATE_INFO = {
    "h": ("H", "Hadamard gate - puts qubit into superposition", "#00ff88"),
    "x": ("X", "X gate - flips bit (0<->1)", "#ff8888"),
    "y": ("Y", "Y gate - rotation around Y axis", "#88ff88"),
    "z": ("Z", "Z gate - rotation around Z axis", "#8888ff"),
    "cx": ("\u2295", "CNOT gate - control qubit flips target", "#ffaa00"),
    "ccx": ("\u2295", "Toffoli gate - double-controlled NOT", "#ffaa00"),
    "measure": ("M", "Measure - collapse qubit to 0/1", "#ffffff"),
    "id": ("I", "Identity gate - wait", "#aaaaaa"),
    "u1": ("U1", "Phase gate", "#88ffff"),
    "u2": ("U2", "U2 gate", "#88ffff"),
    "u3": ("U3", "U3 gate", "#88ffff"),
    "p": ("P", "Phase gate", "#88ffff"),
    "s": ("S", "S gate - 90 degree phase", "#ff88ff"),
    "sdg": ("S\u2020", "S-dagger gate", "#ff88ff"),
    "t": ("T", "T gate - 45 degree phase", "#ff88ff"),
    "tdg": ("T\u2020", "T-dagger gate", "#ff88ff"),
    "rx": ("Rx", "Rotation around X", "#88ff88"),
    "ry": ("Ry", "Rotation around Y", "#88ff88"),
    "rz": ("Rz", "Rotation around Z", "#8888ff"),
    "swap": ("\u00d7", "SWAP gate - exchange two qubits", "#ffaa00"),
}


def interactive_circuit(ops, num_qubits, key="circ"):
    """渲染交互式电路图（SVG + 动画 + 悬停提示）。
    整个电路缩放适配到单一区域内，无需滚动即可完整查看。"""
    if not ops:
        return
    ops = assign_columns(ops, num_qubits)
    data = json.dumps({"ops": ops, "numQubits": num_qubits, "gateInfo": GATE_INFO})

    # 估算画布尺寸（逻辑坐标）
    WIRE = 60
    svg_w = 50 + (max(o["col"] for o in ops) + 1) * 60 + 40
    svg_h = 40 + num_qubits * WIRE + 20

    # iframe 展示区域：固定高度，SVG 内部等比缩放适配（meet）
    display_h = max(220, min(420, 40 + num_qubits * 48))

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    html, body {{
        margin: 0; padding: 0; background: #0d0d0d;
        font-family: 'Courier New', monospace; overflow: hidden;
    }}
    .wrap {{
        background: #0d0d0d; border: 1px solid #00aa55;
        border-radius: 10px; padding: 8px;
        display: flex; flex-direction: column;
        height: {display_h - 16}px; box-sizing: border-box;
    }}
    .hint {{
        color: #00ff88; font-size: 0.85rem; margin-bottom: 4px;
        flex: 0 0 auto;
    }}
    .svgbox {{
        flex: 1 1 auto; min-height: 0;
        display: flex; align-items: center; justify-content: center;
    }}
    svg {{
        max-width: 100%; max-height: 100%;
        width: auto; height: auto;
    }}
    @keyframes gateIn {{
        from {{ opacity: 0; transform: scale(0.5); }}
        to {{ opacity: 1; transform: scale(1); }}
    }}
    .gate-anim {{ transform-origin: center; }}
</style>
</head>
<body>
    <div class="wrap">
        <div class="hint">\u26a1 Interactive Circuit - hover a gate for description</div>
        <div class="svgbox" id="{key}"></div>
    </div>
    <script>
    (function() {{
        const data = {data};
        const container = document.getElementById('{key}');
        if (!container) return;
        const svgNS = 'http://www.w3.org/2000/svg';
        const WIRE = 60, LEFT = 50, GATE = 40, TOP = 40;
        const maxCol = data.ops.reduce((m, o) => Math.max(m, o.col), 0);
        const width = LEFT + (maxCol + 1) * (GATE + 20) + 40;
        const height = TOP + data.numQubits * WIRE + 20;
        const svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.style.background = '#0d0d0d';
        svg.style.display = 'block';

        // 画线
        for (let q = 0; q < data.numQubits; q++) {{
            const y = TOP + q * WIRE;
            const line = document.createElementNS(svgNS, 'line');
            line.setAttribute('x1', LEFT - 20);
            line.setAttribute('y1', y);
            line.setAttribute('x2', width - 20);
            line.setAttribute('y2', y);
            line.setAttribute('stroke', '#00aa55');
            line.setAttribute('stroke-width', '1.5');
            line.setAttribute('opacity', '0.5');
            svg.appendChild(line);
            const label = document.createElementNS(svgNS, 'text');
            label.setAttribute('x', LEFT - 32);
            label.setAttribute('y', y + 5);
            label.setAttribute('fill', '#aaffaa');
            label.setAttribute('font-size', '12');
            label.setAttribute('font-family', 'Courier New');
            label.textContent = 'q' + q;
            svg.appendChild(label);
        }}

        // 画门
        data.ops.forEach((op, idx) => {{
            const info = data.gateInfo[op.gate] || [op.gate.toUpperCase(), op.gate, '#88ffff'];
            const x = LEFT + op.col * (GATE + 20);
            const y = TOP + op.qubits[0] * WIRE;
            const g = document.createElementNS(svgNS, 'g');
            g.setAttribute('class', 'gate-anim');
            g.style.animation = `gateIn 0.4s ease ${{idx * 0.05}}s both`;

            if (op.gate === 'cx' || op.gate === 'ccx') {{
                const line = document.createElementNS(svgNS, 'line');
                line.setAttribute('x1', x + GATE/2);
                line.setAttribute('y1', y);
                line.setAttribute('x2', x + GATE/2);
                line.setAttribute('y2', TOP + op.qubits[op.qubits.length-1] * WIRE);
                line.setAttribute('stroke', '#ffaa00');
                line.setAttribute('stroke-width', '2');
                g.appendChild(line);
                op.qubits.slice(0, -1).forEach(q => {{
                    const dot = document.createElementNS(svgNS, 'circle');
                    dot.setAttribute('cx', x + GATE/2);
                    dot.setAttribute('cy', TOP + q * WIRE);
                    dot.setAttribute('r', '5');
                    dot.setAttribute('fill', '#ffaa00');
                    g.appendChild(dot);
                }});
                const target = document.createElementNS(svgNS, 'circle');
                target.setAttribute('cx', x + GATE/2);
                target.setAttribute('cy', TOP + op.qubits[op.qubits.length-1] * WIRE);
                target.setAttribute('r', '12');
                target.setAttribute('fill', 'none');
                target.setAttribute('stroke', '#ffaa00');
                target.setAttribute('stroke-width', '2');
                g.appendChild(target);
                const plus = document.createElementNS(svgNS, 'text');
                plus.setAttribute('x', x + GATE/2);
                plus.setAttribute('y', TOP + op.qubits[op.qubits.length-1] * WIRE + 5);
                plus.setAttribute('text-anchor', 'middle');
                plus.setAttribute('fill', '#ffaa00');
                plus.setAttribute('font-size', '14');
                plus.textContent = '\u2295';
                g.appendChild(plus);
            }} else if (op.gate === 'measure') {{
                const rect = document.createElementNS(svgNS, 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y - GATE/2);
                rect.setAttribute('width', GATE);
                rect.setAttribute('height', GATE);
                rect.setAttribute('fill', '#1a1a1a');
                rect.setAttribute('stroke', '#ffffff');
                rect.setAttribute('stroke-width', '1.5');
                rect.setAttribute('rx', '4');
                g.appendChild(rect);
                const text = document.createElementNS(svgNS, 'text');
                text.setAttribute('x', x + GATE/2);
                text.setAttribute('y', y + 6);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('fill', '#ffffff');
                text.setAttribute('font-size', '16');
                text.textContent = 'M';
                g.appendChild(text);
            }} else {{
                const rect = document.createElementNS(svgNS, 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y - GATE/2);
                rect.setAttribute('width', GATE);
                rect.setAttribute('height', GATE);
                rect.setAttribute('fill', '#1a1a1a');
                rect.setAttribute('stroke', info[2]);
                rect.setAttribute('stroke-width', '2');
                rect.setAttribute('rx', '4');
                g.appendChild(rect);
                const text = document.createElementNS(svgNS, 'text');
                text.setAttribute('x', x + GATE/2);
                text.setAttribute('y', y + 6);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('fill', info[2]);
                text.setAttribute('font-size', '14');
                text.setAttribute('font-family', 'Courier New');
                text.textContent = info[0];
                g.appendChild(text);
            }}

            const tip = document.createElementNS(svgNS, 'title');
            tip.textContent = info[1];
            g.appendChild(tip);
            svg.appendChild(g);
        }});

        container.appendChild(svg);
    }})();
    </script>
</body>
</html>
    """
    # 写入临时文件，用 st.iframe 加载
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
    tmp.write(html)
    tmp.close()
    st.iframe(Path(tmp.name), height=display_h)


# ================== 会话状态初始化 ==================
if "playground_gates" not in st.session_state:
    st.session_state.playground_gates = []
if "playground_qubits" not in st.session_state:
    st.session_state.playground_qubits = 2
if "badges" not in st.session_state:
    st.session_state.badges = set()
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "user_input" not in st.session_state:
    st.session_state.user_input = "生成一个3比特的GHZ纠缠态，并测量所有比特。"
if "badge_message" not in st.session_state:
    st.session_state.badge_message = None


def earn_badge(name):
    if name not in st.session_state.badges:
        st.session_state.badges.add(name)
        st.session_state.badge_message = f"🎉 恭喜获得徽章：{name}！"
        return True
    return False


# ================== 侧边栏 ==================
with st.sidebar:
    st.markdown("## 🎯 你的量子徽章")
    all_badges = ["🎮 游乐场新手", "💬 语言大师", "🔧 修复专家", "🧠 量子思考者", "🚀 真机梦想家"]
    for b in all_badges:
        earned = b in st.session_state.badges
        cls = "badge badge-earned" if earned else "badge"
        st.markdown(f'<span class="{cls}">{b}</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("## 🚀 快速示例")
    examples = [
        "生成一个贝尔态（Bell State），并测量两个比特。",
        "生成一个3比特的GHZ纠缠态，并测量所有比特。",
        "生成一个4比特的量子随机数生成器。",
        "生成一个2比特的量子叠加态，并测量。",
        "什么是量子门？请用生活类比解释。",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.user_input = ex
            st.rerun()
    st.markdown("---")
    st.markdown("💡 **提示**：右侧选择自然语言实验室可自由输入任何问题。")


# ================== 英雄区 ==================
st.markdown('<div class="hero-title">💚 LoomQ · 量子游乐场</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">像玩游戏一样玩量子计算！</div>', unsafe_allow_html=True)

# 类比卡片
st.markdown("### 🎲 先记住两个「生活类比」")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("""
    <div class="analogy-card">
        <div class="emoji">🪙</div>
        <div class="title">叠加态 = 旋转的硬币</div>
        落下前既是正面也是反面，量子比特就是这样「既是 0 又是 1」。
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown("""
    <div class="analogy-card">
        <div class="emoji">🎲</div>
        <div class="title">纠缠 = 心灵感应骰子</div>
        一对骰子无论相隔多远，掷出的点数永远一致。
    </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown("""
    <div class="analogy-card">
        <div class="emoji">🎮</div>
        <div class="title">量子门 = 游戏技能</div>
        每个门就像游戏里的技能按键，按一下比特就「变身」一次。
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ================== 主功能区（Tabs） ==================
tab_academy, tab_play, tab_lab = st.tabs(["📚 新手学院", "🎮 量子游乐场", "💬 自然语言实验室"])

# ========== Tab 1: 新手学院 ==========
with tab_academy:
    st.markdown("## 📚 新手学院")
    st.markdown("**3 步学会量子计算**，就像学玩游戏一样简单！")

    st.markdown("### 第 1 步：认识量子比特（Qubit）")
    st.markdown("""
    - 普通比特只有 **0** 或 **1** 两种状态（像开关：开/关）
    - 量子比特可以 **同时是 0 和 1**（像旋转的硬币）
    - 用 **H 门** 可以把比特「转起来」进入叠加态
    """)

    st.markdown("### 第 2 步：让比特「心灵感应」")
    st.markdown("""
    - 用 **CNOT 门** 让两个比特纠缠
    - 纠缠后，测量一个，另一个会瞬间确定（无论多远！）
    - 这就是量子计算最神奇的地方
    """)

    st.markdown("### 第 3 步：测量并看结果")
    st.markdown("""
    - 测量 = 让硬币落下，看到确定的结果
    - 多次运行会得到**概率分布**（直方图）
    - 试试在「游乐场」搭一个贝尔态电路！
    """)

    if st.button("🎮 去游乐场试试贝尔态！"):
        st.session_state.playground_gates = [
            {"type": "h", "q": 0},
            {"type": "cx", "c": 0, "t": 1},
            {"type": "measure", "q": 0},
            {"type": "measure", "q": 1},
        ]
        st.session_state.playground_qubits = 2
        st.rerun()

# ========== Tab 2: 量子游乐场 ==========
with tab_play:
    st.markdown("## 🎮 量子游乐场")
    st.markdown("**像搭积木一样搭电路！** 选择比特数，点击按钮添加量子门，然后运行看看结果。")

    col_set, col_ops = st.columns([1, 3])
    with col_set:
        nq = st.slider("量子比特数", 1, 5, st.session_state.playground_qubits, key="pg_nq")
        st.session_state.playground_qubits = nq
        if st.button("🗑️ 清空电路"):
            st.session_state.playground_gates = []
            st.rerun()

    with col_ops:
        st.markdown("**添加量子门**（点击对应比特）")
        gcol1, gcol2, gcol3, gcol4 = st.columns(4)
        with gcol1:
            if st.button("H 门", key="pg_h"):
                st.session_state.playground_gates.append({"type": "h", "q": 0})
                st.rerun()
            if st.button("X 门", key="pg_x"):
                st.session_state.playground_gates.append({"type": "x", "q": 0})
                st.rerun()
        with gcol2:
            if st.button("Y 门", key="pg_y"):
                st.session_state.playground_gates.append({"type": "y", "q": 0})
                st.rerun()
            if st.button("Z 门", key="pg_z"):
                st.session_state.playground_gates.append({"type": "z", "q": 0})
                st.rerun()
        with gcol3:
            if st.button("CNOT 0→1", key="pg_cx"):
                st.session_state.playground_gates.append({"type": "cx", "c": 0, "t": 1})
                st.rerun()
            if st.button("测量 q0", key="pg_m0"):
                st.session_state.playground_gates.append({"type": "measure", "q": 0})
                st.rerun()
        with gcol4:
            if st.button("CNOT 1→0", key="pg_cx2"):
                st.session_state.playground_gates.append({"type": "cx", "c": 1, "t": 0})
                st.rerun()
            if st.button("测量 q1", key="pg_m1"):
                st.session_state.playground_gates.append({"type": "measure", "q": 1})
                st.rerun()

    # 当前所选门列表（文字展示，不再重复渲染电路图）
    if st.session_state.playground_gates:
        st.markdown("**当前电路：** " + " → ".join(
            g["type"].upper() + (f"({g['c']}->{g['t']})" if g["type"] == "cx" else f"({g['q']})")
            for g in st.session_state.playground_gates
        ))
    else:
        st.info("电路还是空的，点击上面的按钮添加门吧！")

    if st.button("🚀 运行游乐场电路", type="primary"):
        if not st.session_state.playground_gates:
            st.warning("请先添加至少一个量子门！")
        else:
            qasm_code = gates_to_qasm(st.session_state.playground_gates, st.session_state.playground_qubits)
            st.session_state.last_result = {"qasm": qasm_code, "source": "playground"}
            earn_badge("🎮 游乐场新手")
            st.rerun()

# ========== Tab 3: 自然语言实验室 ==========
with tab_lab:
    st.markdown("## 💬 自然语言实验室")
    st.markdown("**用大白话描述你的量子实验**，Agent 会帮你写代码、验证、修复并讲解原理。")

    user_input = st.text_area("💬 输入你的量子实验想法", value=st.session_state.user_input, height=80)
    col_run, col_hint = st.columns([1, 4])
    with col_run:
        run_clicked = st.button("🚀 运行实验", type="primary")
    with col_hint:
        st.caption("例如：「生成一个贝尔态」或「什么是量子纠缠？」")

    if run_clicked:
        with st.spinner("🧠 Agent 正在思考并验证代码..."):
            full_response = agent_chat(user_input)

            # ===== 智能推荐后端模式：agent 仅返回后端标识符（如 braket_local_simulator） =====
            if is_backend_recommendation(full_response):
                st.session_state.last_result = {
                    "backend_recommendation": full_response.strip(),
                    "source": "backend_recommendation",
                }
            else:
                match = re.search(r"```(?:qasm)?\s*\n(.*?)\n```", full_response, re.DOTALL)
                if match:
                    qasm_code = match.group(1)
                else:
                    qasm_code = full_response

                # 执行电路
                try:
                    result = run(qasm_code, target="spinq", shots=1024)
                    counts = result["counts"]
                    run_success = True
                except Exception as e:
                    st.error(f"❌ 运行失败: {e}")
                    counts = None
                    run_success = False

                st.session_state.last_result = {
                    "qasm": qasm_code,
                    "counts": counts,
                    "run_success": run_success,
                    "explanation": full_response,
                    "source": "lab",
                }
                if run_success:
                    earn_badge("💬 语言大师")


# ================== 徽章消息提示 ==================
if st.session_state.badge_message:
    st.success(st.session_state.badge_message)
    st.session_state.badge_message = None

# ================== 结果展示区 ==================
if st.session_state.last_result:
    st.markdown("---")
    st.markdown("## 📊 实验结果")

    lr = st.session_state.last_result

    # ===== 智能推荐后端模式：显示绿色徽章 =====
    if lr.get("source") == "backend_recommendation":
        st.markdown(
            '<div style="text-align:center;">'
            '<span class="badge badge-backend">⚡ 当前运行于：本地模拟器（无需排队，即刻返回）</span>'
            '</div>',
            unsafe_allow_html=True
        )
        st.stop()

    qasm_code = lr["qasm"]

    # 解析电路用于交互式渲染
    ops, num_qubits, num_clbits = parse_qasm_ops(qasm_code)

    # 智能后端文本推荐
    if num_qubits > 0:
        rec = recommend_backend(num_qubits, want_real=False)
        if rec:
            kind_label = "模拟器" if rec["kind"] == "simulator" else "真机"
            st.caption(f"💡 已自动选择最适合的{kind_label}「{rec['name']}」运行（最大 {rec['max_qubits']} 比特）")

    # 交互式电路图（唯一一张，缩放适配完整展示）
    st.subheader("🔌 量子电路图")
    if ops:
        interactive_circuit(ops, num_qubits, key="result_circ")
    else:
        st.warning("无法解析电路图。")

    # QASM 代码
    st.subheader("📄 生成的 QASM 代码")
    st.code(qasm_code, language="qasm")

    # 原理讲解
    if lr.get("explanation"):
        st.subheader("🧠 原理讲解")
        full_response = lr["explanation"]
        if "🧠 原理讲解：" in full_response:
            explanation = full_response.split("🧠 原理讲解：")[1].strip()
        else:
            explanation = full_response
        st.success(explanation)

    # 运行结果
    if lr.get("run_success") and lr.get("counts"):
        counts = lr["counts"]
        col_viz1, col_viz2 = st.columns(2)

        with col_viz1:
            st.subheader("📊 测量结果分布")
            fig_hist, ax_hist = plt.subplots(figsize=(5, 3))
            plot_histogram(counts, ax=ax_hist, color='#00aa55', title='')
            ax_hist.set_facecolor('#0d0d0d')
            fig_hist.patch.set_facecolor('#0d0d0d')
            ax_hist.spines['bottom'].set_color('#00aa55')
            ax_hist.spines['left'].set_color('#00aa55')
            ax_hist.tick_params(colors='#aaffaa')
            ax_hist.xaxis.label.set_color('#aaffaa')
            ax_hist.yaxis.label.set_color('#aaffaa')
            st.pyplot(fig_hist)

        with col_viz2:
            st.subheader("🌀 量子态可视化")
            statevector = None
            try:
                circuit_no_meas = loads(qasm_code)
                qc = QuantumCircuit(circuit_no_meas.num_qubits, circuit_no_meas.num_clbits)
                for instr, qargs, cargs in circuit_no_meas.data:
                    if instr.name != 'measure':
                        qc.append(instr, qargs, cargs)
                backend_state = Aer.get_backend('statevector_simulator')
                job_state = backend_state.run(qc)
                statevector = job_state.result().get_statevector()
            except Exception as e:
                st.warning("Statevector computation failed.")

            if statevector is not None:
                n_qubits_sv = circuit_no_meas.num_qubits

                # 提供多种可视化形式供用户选择
                view_options = []
                if n_qubits_sv == 1:
                    view_options = [
                        "🎈 布洛赫球 (Bloch Sphere)",
                        "📊 概率幅柱状图",
                    ]
                else:
                    view_options = [
                        "🌀 Q-Sphere",
                        "🏙️ 态城市图 (State City)",
                        "🔲 概率幅矩阵 (Hinton)",
                        "📊 概率幅柱状图",
                    ]

                viz_choice = st.radio("选择呈现形式：", view_options, key="viz_choice", horizontal=True)
                viz_rendered = False

                # 按选择渲染对应视图，失败时自动回退到概率幅柱状图
                try:
                    if "布洛赫球" in viz_choice:
                        fig_v = plot_bloch_multivector(statevector)
                        fig_v.patch.set_facecolor('#0d0d0d')
                        for ax in fig_v.axes:
                            ax.set_facecolor('#0d0d0d')
                            ax.tick_params(colors='#aaffaa')
                        st.pyplot(fig_v)
                        viz_rendered = True
                    elif "Q-Sphere" in viz_choice:
                        fig_v = plot_state_qsphere(statevector)
                        fig_v.patch.set_facecolor('#0d0d0d')
                        st.pyplot(fig_v)
                        viz_rendered = True
                    elif "态城市图" in viz_choice:
                        fig_v = plot_state_city(statevector, title='')
                        fig_v.patch.set_facecolor('#0d0d0d')
                        st.pyplot(fig_v)
                        viz_rendered = True
                    elif "概率幅矩阵" in viz_choice:
                        fig_v = plot_state_hinton(statevector, title='')
                        fig_v.patch.set_facecolor('#0d0d0d')
                        st.pyplot(fig_v)
                        viz_rendered = True
                except Exception as e:
                    viz_rendered = False

                # 概率幅柱状图（始终可用，且作为回退）
                if not viz_rendered:
                    st.caption("Showing probability amplitudes (positive part).")
                    probs = np.abs(statevector) ** 2
                    n = len(probs)
                    labels = [f"|{i:0{max(1, (n-1).bit_length())}b}>" for i in range(n)]
                    fig_prob, ax_prob = plt.subplots(figsize=(5, 2.5))
                    ax_prob.bar(range(n), probs, color='#00aa55')
                    ax_prob.set_xticks(range(n))
                    ax_prob.set_xticklabels(labels, color='#aaffaa', fontsize=9)
                    ax_prob.set_facecolor('#0d0d0d')
                    fig_prob.patch.set_facecolor('#0d0d0d')
                    ax_prob.tick_params(colors='#aaffaa')
                    ax_prob.set_xlabel("Basis state", color='#aaffaa')
                    ax_prob.set_ylabel("Probability", color='#aaffaa')
                    ax_prob.spines['bottom'].set_color('#00aa55')
                    ax_prob.spines['left'].set_color('#00aa55')
                    st.pyplot(fig_prob)
            else:
                st.info("无法获取态矢量信息。")

    elif lr.get("run_success"):
        st.info("电路运行成功，但没有测量结果。")

# ================== 页脚 ==================
st.markdown("---")
st.caption("💚 LoomQ · 量子接入平权计划 — 让不懂「黑话」的人，也能指挥最前沿的算力。")