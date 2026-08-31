const registry = new Map();
const SVG_NS = "http://www.w3.org/2000/svg";
let tabGroupId = 0;

export function registerVisualizer(name, visualizer) {
  registry.set(name, visualizer);
}

export function renderVisualizations(context) {
  context.container.replaceChildren();
  let rendered = 0;
  for (const visualizer of registry.values()) {
    if (visualizer.supports(context)) {
      visualizer.render(context);
      rendered += 1;
    }
  }
  context.container.hidden = rendered === 0;
}

export function renderWelcomePreview(container) {
  container.replaceChildren();
  const card = buildPatternCard({
    shots: 1024,
    counts: { "00": 512, "11": 512 },
    fidelity: null,
  }, { preview: true });
  container.append(card);
  container.hidden = false;
}

registerVisualizer("woven-counts", {
  supports: ({ response }) => Boolean(response?.artifacts?.simulation?.counts),
  render: ({ response, container }) => {
    container.append(buildPatternCard(response.artifacts.simulation));
  },
});

registerVisualizer("circuit-diagram", {
  supports: ({ response }) => Boolean(response?.artifacts?.circuit),
  render: ({ response, container }) => {
    const circuit = response.artifacts.circuit;
    const card = artifactCard("柔性量子线路", `${circuit.qubit_count} qubits · depth ${circuit.depth}`, "artifact-wide");
    const scroll = document.createElement("div");
    scroll.className = "circuit-scroll";
    scroll.append(buildCircuitSvg(circuit, response.artifacts.qasm));
    card.append(scroll);
    const note = document.createElement("p");
    note.className = "artifact-footnote";
    note.textContent = "点击梭子或线结可定位到对应 QASM。交织纹样只标记由 H + CX 链明确形成的 Bell/GHZ 结构。";
    card.append(note);
    container.append(card);
  },
});

registerVisualizer("qasm-source", {
  supports: ({ response }) => Boolean(response?.artifacts?.qasm),
  render: ({ response, container }) => {
    const card = artifactCard("OpenQASM", "可复制、可定位、可复核", "artifact-source");
    const source = document.createElement("pre");
    source.className = "qasm-source";
    response.artifacts.qasm.split(/\r?\n/).forEach((text, index) => {
      const line = document.createElement("span");
      line.className = "source-line";
      line.dataset.sourceLine = String(index + 1);
      const number = document.createElement("b");
      number.textContent = String(index + 1).padStart(2, "0");
      const code = document.createElement("code");
      code.textContent = text || " ";
      line.append(number, code);
      source.append(line);
    });
    card.append(source);
    container.append(card);
  },
});

registerVisualizer("backend-selection", {
  supports: ({ response }) => Boolean(response?.artifacts?.backend_selection),
  render: ({ response, container }) => {
    const selection = response.artifacts.backend_selection;
    const card = artifactCard("后端适配", selection.constraints.join(" · ") || "官方能力表", "artifact-wide");
    const candidates = document.createElement("div");
    candidates.className = "backend-grid";
    const items = selection.candidates.length ? selection.candidates : selection.alternatives;
    items.forEach((backend) => {
      const item = document.createElement("article");
      item.className = "backend-card";
      const kind = document.createElement("span");
      kind.textContent = backend.kind === "qpu" ? "真实量子机" : "模拟器";
      const title = document.createElement("strong");
      title.textContent = backend.id;
      const detail = document.createElement("p");
      detail.textContent = `${backend.max_qubits} 比特 · ${costLabel(backend.cost)} · 排队 ${queueLabel(backend.queue)}`;
      item.append(kind, title, detail);
      candidates.append(item);
    });
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "artifact-footnote";
      empty.textContent = "没有平台同时满足全部条件。调整比特数、排队或费用要求后再试。";
      candidates.append(empty);
    }
    card.append(candidates);
    container.append(card);
  },
});

function buildPatternCard(simulation, options = {}) {
  const entries = visibleCounts(simulation.counts);
  const total = Number(simulation.shots) || entries.reduce((sum, [, value]) => sum + value, 0) || 1;
  const meta = options.preview ? "Bell 态示意 · 非本次结果" : `本地理想推导 · 按 ${total.toLocaleString("zh-CN")} 次测量换算`;
  const card = artifactCard(options.preview ? "结果纹样示意" : "理想结果纹样", meta, "artifact-pattern");
  if (options.preview) card.querySelector("header span").classList.add("preview-badge");

  const intro = document.createElement("div");
  intro.className = "pattern-intro";
  const introText = document.createElement("p");
  introText.textContent = options.preview ? "这是 Bell 态理想分布的视觉示意。提交含线路的任务后，会换成该线路的推导结果。" : "每块代表线路在理想条件下可能得到的一种结果；颜色越深、纱线越密，代表所占概率越高。";
  const legend = document.createElement("span");
  legend.className = "pattern-legend";
  legend.innerHTML = "<i></i><i></i>低概率 → 高概率";
  intro.append(introText, legend);

  const group = ++tabGroupId;
  const tabs = document.createElement("div");
  tabs.className = "pattern-tabs";
  tabs.setAttribute("role", "tablist");
  const panels = [];
  [
    ["woven", "织物"],
    ["probability", "概率"],
    ["raw", "原始数据"],
  ].forEach(([name, label], index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pattern-tab";
    button.id = `pattern-tab-${group}-${name}`;
    button.dataset.panel = name;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(index === 0));
    button.setAttribute("aria-controls", `pattern-panel-${group}-${name}`);
    button.textContent = label;
    tabs.append(button);
  });

  const wovenPanel = panelElement(group, "woven", true);
  const woven = document.createElement("div");
  woven.className = "woven-grid";
  woven.style.setProperty("--swatch-count", String(Math.max(entries.length, 1)));
  entries.forEach(([state, count], index) => woven.append(buildSwatch(state, count, total, index)));
  const reading = document.createElement("p");
  reading.className = "pattern-reading";
  reading.append(document.createTextNode(patternExplanation(entries, total)));
  const caution = document.createElement("small");
  caution.textContent = options.preview ? "视觉示意，不是本次任务、云端或真机结果。" : "这是本地理想推导，不是云端或真机结果；精确判断请同时查看概率和原始数据。";
  reading.append(caution);
  wovenPanel.append(woven, reading);

  const probabilityPanel = panelElement(group, "probability", false);
  probabilityPanel.append(buildProbabilityChart(entries, total));

  const rawPanel = panelElement(group, "raw", false);
  const raw = document.createElement("pre");
  raw.className = "raw-counts";
  raw.textContent = JSON.stringify(simulation.counts, null, 2);
  rawPanel.append(raw);

  panels.push(wovenPanel, probabilityPanel, rawPanel);
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest(".pattern-tab");
    if (!button) return;
    tabs.querySelectorAll(".pattern-tab").forEach((item) => item.setAttribute("aria-selected", String(item === button)));
    panels.forEach((panel) => { panel.hidden = panel.dataset.panel !== button.dataset.panel; });
  });

  card.append(intro, tabs, ...panels);
  if (!options.preview && simulation.fidelity !== null && simulation.fidelity !== undefined) {
    const fidelity = document.createElement("p");
    fidelity.className = "artifact-footnote";
    fidelity.textContent = `目标分布保真度 ${(simulation.fidelity * 100).toFixed(2)}%。该数值来自本地理想态验证。`;
    card.append(fidelity);
  }
  return card;
}

function panelElement(group, name, selected) {
  const panel = document.createElement("div");
  panel.className = "pattern-panel";
  panel.id = `pattern-panel-${group}-${name}`;
  panel.dataset.panel = name;
  panel.setAttribute("role", "tabpanel");
  panel.setAttribute("aria-labelledby", `pattern-tab-${group}-${name}`);
  panel.hidden = !selected;
  return panel;
}

function visibleCounts(counts) {
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  if (entries.length <= 8) return entries;
  return [
    ...entries.slice(0, 7),
    ["其他", entries.slice(7).reduce((sum, [, value]) => sum + value, 0)],
  ];
}

function buildSwatch(state, count, total, swatchIndex) {
  const probability = count / total;
  const density = Math.sqrt(probability);
  const article = document.createElement("article");
  article.className = "pattern-swatch";
  article.setAttribute("aria-label", `${state}：${count} 次，${(probability * 100).toFixed(1)}%`);

  const patch = document.createElement("div");
  patch.className = "woven-patch";
  patch.style.setProperty("--density", density.toFixed(3));
  for (let index = 0; index < 144; index += 1) {
    const cell = document.createElement("i");
    const row = Math.floor(index / 12);
    const bit = state === "其他" ? String((row + index) % 2) : state[(row + index) % state.length];
    const filled = seededUnit(`${state}:${index}`) < Math.min(.96, .12 + probability * .88);
    cell.className = `weave-cell ${bit === "1" ? "bit-one" : "bit-zero"}${filled ? "" : " open"}`;
    cell.style.setProperty("--density", density.toFixed(3));
    cell.style.setProperty("--row", String(row));
    cell.style.setProperty("--swatch-index", String(swatchIndex));
    patch.append(cell);
  }

  const label = document.createElement("div");
  label.className = "swatch-label";
  const left = document.createElement("span");
  const code = document.createElement("code");
  code.textContent = state;
  const detail = document.createElement("span");
  detail.textContent = `${count.toLocaleString("zh-CN")} 次`;
  left.append(code, detail);
  const percent = document.createElement("strong");
  percent.textContent = `${(probability * 100).toFixed(1)}%`;
  label.append(left, percent);
  article.append(patch, label);
  return article;
}

function buildProbabilityChart(entries, total) {
  const chart = document.createElement("div");
  chart.className = "counts-chart";
  entries.forEach(([state, count]) => {
    const row = document.createElement("div");
    row.className = "count-row";
    const label = document.createElement("code");
    label.textContent = state;
    const track = document.createElement("div");
    track.className = "count-track";
    const bar = document.createElement("i");
    bar.style.setProperty("--bar-size", `${(count / total) * 100}%`);
    track.append(bar);
    const value = document.createElement("span");
    value.textContent = `${((count / total) * 100).toFixed(1)}%`;
    value.title = `${count} / ${total}`;
    row.append(label, track, value);
    chart.append(row);
  });
  return chart;
}

function patternExplanation(entries, total) {
  if (!entries.length) return "还没有收到可以绘制的测量结果。";
  const probabilities = entries.map(([state, count]) => ({ state, count, p: count / total }));
  const top = probabilities[0];
  const second = probabilities[1];
  if (probabilities.length === 2 && new Set(probabilities.map((item) => item.state)).size === 2 && probabilities.some((item) => item.state === "00") && probabilities.some((item) => item.state === "11")) {
    const a = probabilities.find((item) => item.state === "00");
    const b = probabilities.find((item) => item.state === "11");
    return `按 ${total.toLocaleString("zh-CN")} 次测量的规模换算，结果只包含 00 和 11：分别为 ${a.count.toLocaleString("zh-CN")} 和 ${b.count.toLocaleString("zh-CN")}。它与 Bell 态在当前测量方式下的理想分布一致。`;
  }
  if (top.p >= .7) return `结果主要落在 ${top.state}，约占 ${(top.p * 100).toFixed(1)}%。其他状态出现得较少。`;
  if (second && top.p + second.p >= .85 && Math.abs(top.p - second.p) <= .1) {
    return `结果主要集中在 ${top.state} 和 ${second.state}，两种结果出现得比较接近。`;
  }
  const spread = Math.max(...probabilities.map((item) => item.p)) - Math.min(...probabilities.map((item) => item.p));
  if (probabilities.length >= 3 && spread <= .08) return "这些结果出现得比较平均，目前没有明显占主导的状态。";
  return `出现最多的是 ${top.state}，约占 ${(top.p * 100).toFixed(1)}%。切换到“概率”或“原始数据”可以查看精确数值。`;
}

function seededUnit(text) {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function artifactCard(title, meta, className = "") {
  const card = document.createElement("section");
  card.className = `artifact-card ${className}`.trim();
  const heading = document.createElement("header");
  const label = document.createElement("h3");
  label.textContent = title;
  const detail = document.createElement("span");
  detail.textContent = meta;
  heading.append(label, detail);
  card.append(heading);
  return card;
}

function buildCircuitSvg(circuit, qasm) {
  const gateLines = sourceGateLines(qasm);
  const columnWidth = 72;
  const left = 62;
  const top = 42;
  const rowHeight = 54;
  const operationWidth = circuit.operations.length * columnWidth;
  const measureX = left + operationWidth + 48;
  const width = Math.max(460, measureX + 72);
  const height = Math.max(118, top * 2 + (circuit.qubit_count - 1) * rowHeight);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": "由柔性纱线和梭子组成的量子线路图" });

  for (let qubit = 0; qubit < circuit.qubit_count; qubit += 1) {
    const y = top + qubit * rowHeight;
    const path = yarnPath(left, measureX + 30, y, qubit);
    svg.append(svgElement("text", { x: 8, y: y + 4, class: "wire-label" }, `q${qubit}`));
    svg.append(svgElement("path", { d: path, class: "yarn-wire-under" }));
    svg.append(svgElement("path", { d: path, class: "yarn-wire" }));
  }

  circuit.operations.forEach((operation, index) => {
    const x = left + 28 + index * columnWidth;
    const qubits = operation.qubits;
    const line = gateLines[index];
    const group = svgElement("g", { class: "gate", tabindex: "0", role: "button", "aria-label": gateLabel(operation, line) });
    if (line) {
      group.dataset.line = String(line);
      const locate = () => window.dispatchEvent(new CustomEvent("loomq:source-line", { detail: { line } }));
      group.addEventListener("click", locate);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          locate();
        }
      });
    }

    if (qubits.length > 1) {
      const ys = qubits.map((qubit) => top + qubit * rowHeight);
      group.append(svgElement("path", { d: `M ${x} ${Math.min(...ys)} C ${x + 4} ${Math.min(...ys) + 18}, ${x - 4} ${Math.max(...ys) - 18}, ${x} ${Math.max(...ys)}`, class: "gate-weft" }));
      if (operation.name === "swap") {
        qubits.forEach((qubit) => drawShuttle(group, "S", x, top + qubit * rowHeight, true));
      } else {
        qubits.slice(0, -1).forEach((qubit) => group.append(svgElement("circle", { cx: x, cy: top + qubit * rowHeight, r: 7, class: "gate-knot" })));
        drawShuttle(group, operation.name === "cx" || operation.name === "ccx" ? "CX" : operation.name.toUpperCase(), x, top + qubits[qubits.length - 1] * rowHeight, true);
      }
    } else {
      drawShuttle(group, operation.name.toUpperCase(), x, top + qubits[0] * rowHeight, false);
    }
    if (operation.parameter !== null && operation.parameter !== undefined) {
      const y = top + Math.max(...qubits) * rowHeight + 28;
      group.append(svgElement("text", { x, y, class: "gate-parameter" }, operation.parameter.toFixed(2)));
    }
    svg.append(group);
  });

  drawEntanglementBraids(svg, circuit, left, top, rowHeight, columnWidth);

  circuit.measurements.forEach((measurement) => {
    const y = top + measurement.qubit * rowHeight;
    const group = svgElement("g", { class: "measure", role: "img", "aria-label": `测量 q${measurement.qubit}` });
    group.append(svgElement("rect", { x: measureX - 17, y: y - 14, width: 34, height: 28, rx: 10, class: "measure-spool" }));
    group.append(svgElement("path", { d: `M ${measureX - 10} ${y - 7} H ${measureX + 10} M ${measureX - 10} ${y + 7} H ${measureX + 10}`, class: "braid-b" }));
    group.append(svgElement("text", { x: measureX, y: y + 4 }, "M"));
    svg.append(group);
  });
  return svg;
}

function yarnPath(x1, x2, y, seed) {
  const amplitude = seed % 2 === 0 ? 1.3 : -1.3;
  const span = x2 - x1;
  return `M ${x1} ${y} C ${x1 + span * .18} ${y + amplitude}, ${x1 + span * .32} ${y - amplitude}, ${x1 + span * .5} ${y} S ${x1 + span * .82} ${y + amplitude}, ${x2} ${y}`;
}

function drawShuttle(group, label, x, y, compact) {
  const halfWidth = compact ? 21 : 22;
  const halfHeight = compact ? 13 : 14;
  const path = [
    `M ${x - halfWidth + 7} ${y - halfHeight}`,
    `H ${x + halfWidth - 7}`,
    `L ${x + halfWidth} ${y}`,
    `L ${x + halfWidth - 7} ${y + halfHeight}`,
    `H ${x - halfWidth + 7}`,
    `L ${x - halfWidth} ${y} Z`,
  ].join(" ");
  group.append(svgElement("path", { d: path, class: "gate-shuttle" }));
  group.append(svgElement("text", { x, y: y + 3, class: "gate-text" }, label));
}

function drawEntanglementBraids(svg, circuit, left, top, rowHeight, columnWidth) {
  const prepared = new Set();
  const pairs = [];
  circuit.operations.forEach((operation, index) => {
    if (operation.name === "h" && operation.qubits.length === 1) prepared.add(operation.qubits[0]);
    if (operation.name === "cx" && operation.qubits.length === 2 && prepared.has(operation.qubits[0])) {
      prepared.add(operation.qubits[1]);
      pairs.push({ from: operation.qubits[0], to: operation.qubits[1], index });
    }
  });
  pairs.forEach((pair, pairIndex) => {
    const x = left + 28 + pair.index * columnWidth + 31;
    const y1 = top + pair.from * rowHeight;
    const y2 = top + pair.to * rowHeight;
    const a = `M ${x - 24} ${y1} C ${x - 8} ${y1}, ${x + 8} ${y2}, ${x + 24} ${y2}`;
    const b = `M ${x - 24} ${y2} C ${x - 8} ${y2}, ${x + 8} ${y1}, ${x + 24} ${y1}`;
    svg.append(svgElement("path", { d: a, class: "braid-under" }));
    svg.append(svgElement("path", { d: b, class: "braid-under" }));
    svg.append(svgElement("path", { d: a, class: "braid-a" }));
    svg.append(svgElement("path", { d: b, class: "braid-b" }));
    if (pairIndex === 0) {
      svg.append(svgElement("text", { x: x - 23, y: Math.min(y1, y2) - 10, class: "braid-label" }, pairs.length > 1 ? "GHZ 交织" : "Bell 交织"));
    }
  });
}

function svgElement(name, attributes, text) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  if (text !== undefined) element.textContent = text;
  return element;
}

function sourceGateLines(qasm) {
  if (!qasm) return [];
  const gate = /^\s*(h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\b/i;
  return qasm.split(/\r?\n/).flatMap((line, index) => gate.test(line) ? [index + 1] : []);
}

function gateLabel(operation, line) {
  const qubits = operation.qubits.map((qubit) => `q${qubit}`).join("、");
  const plain = {
    h: "叠加",
    x: "翻转",
    cx: "联动",
    measure: "测量",
  }[operation.name] || operation.name.toUpperCase();
  return `${plain}（${operation.name.toUpperCase()}），作用于 ${qubits}${line ? `，源码第 ${line} 行` : ""}`;
}

function costLabel(cost) {
  return { free: "免费", free_quota: "含免费额度", paid: "可能计费" }[cost] || cost;
}

function queueLabel(queue) {
  return { none: "无", low: "较短", medium: "中等", high: "较长" }[queue] || queue;
}

window.addEventListener("loomq:source-line", (event) => {
  const line = document.querySelector(`[data-source-line="${event.detail.line}"]`);
  if (!line) return;
  document.querySelectorAll(".source-line.active").forEach((item) => item.classList.remove("active"));
  line.classList.add("active");
  line.scrollIntoView({ block: "nearest", behavior: "smooth" });
});
