"use strict";

const state = { session: null, repair: null, agentProposal: null, request: 0 };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderMarkdown(value) {
  const lines = String(value).replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  let inCode = false;
  let list = null;
  const closeList = () => { if (list) { output.push(`</${list}>`); list = null; } };
  lines.forEach(line => {
    if (/^```/.test(line)) {
      closeList();
      output.push(inCode ? "</code></pre>" : "<pre><code>");
      inCode = !inCode;
      return;
    }
    if (inCode) { output.push(`${escapeHtml(line)}\n`); return; }
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (bullet || ordered) {
      const nextList = bullet ? "ul" : "ol";
      if (list !== nextList) { closeList(); output.push(`<${nextList}>`); list = nextList; }
      output.push(`<li>${renderInlineMarkdown((bullet || ordered)[1])}</li>`);
      return;
    }
    closeList();
    if (!line.trim()) return;
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) { const level = heading[1].length + 2; output.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`); return; }
    if (/^>\s?/.test(line)) { output.push(`<blockquote>${renderInlineMarkdown(line.replace(/^>\s?/, ""))}</blockquote>`); return; }
    output.push(`<p>${renderInlineMarkdown(line)}</p>`);
  });
  closeList();
  if (inCode) output.push("</code></pre>");
  return output.join("");
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    method: options.method || "POST",
    headers: { "Content-Type": "application/json" },
    body: options.body === undefined ? "{}" : JSON.stringify(options.body),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || value.recovery || "请求失败");
  return value;
}

function announce(text) {
  $("#live-region").textContent = "";
  window.setTimeout(() => { $("#live-region").textContent = text; }, 20);
}

function setAgentStatus(label, kind = "") {
  const status = $("#agent-status");
  status.textContent = label;
  status.className = `agent-status ${kind}`.trim();
}

function renderConversation(messages, understanding = "") {
  const container = $("#agent-conversation");
  container.replaceChildren();
  messages.forEach((message, index) => {
    const item = document.createElement("div");
    item.className = `agent-message ${message.role === "user" ? "user" : "assistant"}`;
    if (understanding && index === messages.length - 1 && message.role === "assistant") {
      const label = document.createElement("span");
      label.className = "agent-understanding";
      label.textContent = `理解：${understanding}`;
      item.appendChild(label);
    }
    if (message.role === "assistant") {
      const content = document.createElement("div");
      content.className = "markdown-body";
      content.innerHTML = renderMarkdown(message.content);
      item.appendChild(content);
    } else {
      item.append(document.createTextNode(message.content));
    }
    container.appendChild(item);
  });
  container.scrollTop = container.scrollHeight;
}

function renderAgentProposal(proposal) {
  state.agentProposal = proposal;
  $("#agent-surface").classList.toggle("has-proposal", Boolean(proposal));
  const panel = $("#agent-proposal");
  panel.hidden = !proposal;
  if (!proposal) return;
  const labels = { qasm: "电路", goal: "目标", backend: "后端" };
  $("#agent-proposal-kind").textContent = labels[proposal.kind] || proposal.kind;
  $("#agent-proposal-summary").textContent = proposal.summary;
  const safeToApply = proposal.safe_to_apply !== false;
  $("#agent-proposal-safety").textContent = safeToApply
    ? "本地结构验证通过，可在审阅差异后应用。"
    : "结构验证失败：该提案不能应用，请修改后重新生成。";
  $("#agent-proposal-safety").classList.toggle("error", !safeToApply);
  $("#agent-apply").disabled = !safeToApply;
  const diff = $("#agent-proposal-diff");
  diff.hidden = !proposal.diff;
  diff.innerHTML = (proposal.diff || "").split("\n").map(line => {
    const kind = line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@") ? "meta" : line.startsWith("+") ? "add" : line.startsWith("-") ? "delete" : "context";
    return `<span class="diff-line diff-${kind}">${escapeHtml(line) || " "}</span>`;
  }).join("");
}

function renderStages(session) {
  $("#stage-track").innerHTML = session.stage_labels.map((label, index) =>
    `<li class="${index < session.guide_stage || session.guide.complete ? "complete" : index === session.guide_stage ? "current" : ""}" ${index === session.guide_stage && !session.guide.complete ? 'aria-current="step"' : ""}>${index + 1}. ${escapeHtml(label)}</li>`
  ).join("");
}

function prefillGuideInstruction(force = false) {
  if (!state.session || !$("#main").classList.contains("tutorial-active") || state.session.guide.complete) return;
  const input = $("#agent-input");
  if (force || !input.value.trim()) input.value = state.session.guide.preset_instruction;
}

function renderCircuit(session) {
  const ir = { gates: [], measurements: [], ...(session.circuit_ir || {}) };
  const qubitLabels = ir.qubit_labels || [];
  const classicalLabels = ir.classical_labels || [];
  const lastGate = ir.gates.length - 1;
  const referencedQubits = [...ir.gates.flatMap(gate => gate.qubits || []), ...ir.measurements.map(item => item.qubit)];
  const qubitCount = Math.max(Number(ir.qubits) || 0, referencedQubits.length ? Math.max(...referencedQubits) + 1 : 0, 1);
  const gates = Array.from({ length: qubitCount }, () => []);
  const measurementLeft = 115 + ir.gates.length * 95 + 25;
  ir.gates.forEach((gate, index) => {
    const left = 115 + index * 95;
    if (gate.name === "CX") {
      gates[gate.qubits[0]].push(`<span class="control ${index === lastGate ? "active" : ""}" style="left:${left + 14}px" aria-hidden="true"></span><span class="connector" style="left:${left + 20}px" aria-hidden="true"></span>`);
      gates[gate.qubits[1]].push(`<span class="target ${index === lastGate ? "active" : ""}" style="left:${left + 4}px" aria-hidden="true"></span>`);
    } else {
      gates[gate.qubits[0]].push(`<span class="gate ${index === lastGate ? "active" : ""}" style="left:${left}px" aria-hidden="true">${gate.name}</span>`);
    }
  });
  ir.measurements.forEach((item, index) => {
    const classicalLabel = item.classical_label || classicalLabels[item.classical] || `c[${item.classical}]`;
    gates[item.qubit].push(`<span class="measure" style="left:${measurementLeft}px" aria-hidden="true">M→${escapeHtml(classicalLabel)}</span>`);
  });
  $("#circuit-canvas").innerHTML = gates.map((items, index) => `<div class="wire"><span class="wire-label">${escapeHtml(qubitLabels[index] || `q[${index}]`)} |0⟩</span>${items.join("")}</div>`).join("");
  $("#circuit-description").textContent = session.circuit_description;
  $("#circuit-canvas").setAttribute("aria-label", session.circuit_description);
  const classicalCount = Math.max(Number(ir.classical_bits) || 0, 1);
  const bitLabels = classicalLabels.length
    ? [...classicalLabels].reverse()
    : Array.from({ length: classicalCount }, (_, index) => `c[${classicalCount - index - 1}]`);
  $("#bit-order").textContent = `经典位序 ${bitLabels.join("")}`;
}

function renderValidation(validation) {
  const items = ["syntax", "definitions", "gates", "measurements", "target"].map(key => validation && validation[key]).filter(Boolean);
  $("#validation-list").innerHTML = items.length ? items.map(item =>
    `<div class="validation-item ${item.status}"><span aria-hidden="true">${item.status === "pass" ? "✓" : item.status === "fail" ? "!" : "△"}</span><div><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.detail)}</p></div></div>`
  ).join("") : '<p class="empty-state">同步 QASM 后，将检查语法、寄存器、量子门和测量结构。</p>';
}

function renderResults(result) {
  const panel = $("#results-panel");
  panel.hidden = !result;
  $("#results-empty").hidden = Boolean(result);
  if (!result) return;
  const entries = Object.entries(result.counts).sort(([a], [b]) => a.localeCompare(b));
  $("#result-summary").textContent = `${result.backend} 完成 ${result.shots} shots，共观察到 ${entries.length} 种经典输出。${result.counting_method || "计数由当前本地执行器返回"}。`;
  $("#counts-chart").setAttribute("aria-label", entries.map(([bits, count]) => `${bits}：${count} 次，${(100 * count / result.shots).toFixed(1)}%`).join("；"));
  $("#counts-chart").innerHTML = entries.map(([bits, count]) => {
    const percent = 100 * count / result.shots;
    return `<div class="bar-row"><strong>${bits}</strong><div class="bar-track"><div class="bar" style="width:${percent}%"></div></div><span>${count} · ${percent.toFixed(1)}%</span></div>`;
  }).join("");
  $("#counts-table").innerHTML = entries.map(([bits, count]) => `<tr><th scope="row">${bits}</th><td>${count}</td><td>${(100 * count / result.shots).toFixed(1)}%</td><td>${(100 * (result.ideal[bits] || 0)).toFixed(1)}%</td></tr>`).join("");
  $("#result-boundary").textContent = result.boundary;
}

function renderBackendSummary(session) {
  const names = {
    loomq_reference_simulator: "LoomQ 内置状态向量参考模拟器",
    spinq_taurus_simulator: "量旋 SpinQit Taurus 本地模拟器",
    originq_local_simulator: "本源 pyQPanda 本地模拟器",
    braket_local_simulator: "AWS Braket LocalSimulator",
  };
  $("#backend-name").textContent = names[session.backend_selection] || session.backend_selection;
  $("#backend-id").textContent = `${session.backend_selection} · 当前执行器`;
}

function renderHardwareEvidence(value) {
  const missing = Array.isArray(value.missing) ? value.missing : [];
  const rejected = Array.isArray(value.rejected) ? value.rejected : [];
  const incomplete = missing.length || rejected.length;
  const issueText = incomplete
    ? ` 归档证据不完整：缺少 ${missing.join("、") || "无"}；拒绝 ${rejected.join("、") || "无"}。`
    : " 四项正式摘要均已通过身份与 Schema 校验。";
  $("#hardware-evidence-notice").textContent = `${value.notice}${issueText}`;
  $("#hardware-evidence-boundary").textContent = value.boundary;
  $("#hardware-evidence-circuits").innerHTML = (value.circuits || []).map(circuit => `
    <article class="hardware-evidence-card">
      <h3>${escapeHtml(circuit.label)} · ${(circuit.series || []).filter(series => series.kind === "archived_hardware").length === 2 ? "已归档真机结果" : "归档证据不完整"}</h3>
      ${(circuit.series || []).map(series => {
        const counts = Object.entries(series.counts || {}).sort(([left], [right]) => left.localeCompare(right));
        return `<section class="hardware-series ${series.kind}">
          <div><strong>${escapeHtml(series.provider)}</strong><small>${escapeHtml(series.backend)}${series.job_id ? ` · job ${escapeHtml(series.job_id)}` : ""}</small></div>
          <div class="hardware-counts" aria-label="${escapeHtml(counts.map(([bits, count]) => `${bits} ${count}`).join("；"))}">
            ${counts.map(([bits, count]) => `<span><b>${escapeHtml(bits)}</b> ${count} · ${(100 * count / series.shots).toFixed(1)}%</span>`).join("")}
          </div>
        </section>`;
      }).join("")}
      <table class="hardware-comparison">
        <caption>${escapeHtml(circuit.label)} 支撑与泄漏比较</caption>
        <thead><tr><th scope="col">数据</th><th scope="col">主峰</th><th scope="col">理想支撑</th><th scope="col">泄漏</th><th scope="col">时间</th></tr></thead>
        <tbody>${(circuit.series || []).map(series => `<tr>
          <th scope="row">${escapeHtml(series.provider)}</th>
          <td>${escapeHtml(series.dominant_states.join(" / "))}</td>
          <td>${(100 * series.support_probability).toFixed(1)}%</td>
          <td>${(100 * series.leakage_probability).toFixed(1)}%</td>
          <td>${escapeHtml(series.timestamp || "理论参考")}</td>
        </tr>`).join("")}</tbody>
      </table>
    </article>
  `).join("");
}

function render(session, options = {}) {
  state.session = session;
  window.sessionStorage.setItem("loomq-session-id", session.session_id);
  $("#goal-title").textContent = session.goal || "未设定";
  $("#guide-index").textContent = `${session.guide.index} / ${session.guide.total}`;
  $("#guide-title").textContent = session.guide.title;
  $("#primary-action").textContent = session.guide.complete ? "Bell 引导已完成" : "填入本阶段指令";
  $("#primary-action").disabled = session.guide.complete;
  $("#revision-label").textContent = `版本 ${session.circuit_revision}`;
  if (!options.keepEditor) $("#qasm-editor").value = session.qasm;
  $("#undo-button").disabled = !session.can_undo;
  $("#redo-button").disabled = !session.can_redo;
  $("#diagnostic").textContent = session.notice || "";
  $("#diagnostic").classList.toggle("error", session.state === "invalid");
  renderStages(session);
  renderCircuit(session);
  renderValidation(session.validation);
  $("#run-button").disabled = !(session.validation && session.validation.runnable);
  renderResults(session.result);
  renderBackendSummary(session);
  if (session.conversation && session.conversation.length) renderConversation(session.conversation);
  $("#operation-explanation").textContent = session.circuit_description || "当前 QASM 尚未形成可解析的电路描述。";
  $("#context-explanation").textContent = session.result
    ? `${session.result.counting_method || "本地执行器返回的计数"}；理想概率列来自确定性状态模拟。`
    : "当前尚未运行。运行位置视图会区分本地模拟器与需要账号、网络或排队的真机后端。";
}

async function createExperiment(body = { mode: "bell" }) {
  try {
    const session = await api("/experiments", { body });
    render(session);
    announce("新实验已建立");
    return session;
  } catch (error) { showError(error); }
  return null;
}

function showError(error) {
  $("#diagnostic").textContent = `${error.message}。实验内容已保留，可编辑或撤销后重试。`;
  $("#diagnostic").classList.add("error");
  announce("操作失败，实验内容已保留");
}

$("#primary-action").addEventListener("click", () => {
  prefillGuideInstruction(true);
  $("#agent-input").focus();
  announce("本阶段指令已填入 Agent 对话框；发送后才会推进实验");
});

$("#apply-qasm").addEventListener("click", async () => {
  try {
    const session = await api(`/experiments/${state.session.session_id}/circuit`, { method: "PATCH", body: { qasm: $("#qasm-editor").value, circuit_revision: state.session.circuit_revision } });
    render(session);
    announce(session.state === "invalid" ? "QASM 有错误，最后有效电路已保留" : "QASM 已同步到图形电路");
  } catch (error) { showError(error); }
});

$("#preview-repair").addEventListener("click", async () => {
  try {
    state.repair = await api(`/experiments/${state.session.session_id}/repairs`, { body: { apply: false } });
    $("#repair-diff").hidden = !state.repair.safe;
    $("#repair-diff").textContent = state.repair.safe ? state.repair.diff : "";
    $("#apply-repair").hidden = !state.repair.safe;
    if (!state.repair.safe) {
      $("#diagnostic").textContent = "当前 QASM 没有可自动应用的安全语法修复。";
      $("#diagnostic").classList.remove("error");
    }
    announce(state.repair.safe ? "找到可安全应用的语法修复，请先审阅差异" : "没有可自动应用的安全修复");
  } catch (error) { showError(error); }
});

$("#apply-repair").addEventListener("click", async () => {
  try {
    const value = await api(`/experiments/${state.session.session_id}/repairs`, { body: { apply: true } });
    if (value.session) render(value.session);
    $("#repair-diff").hidden = true;
    $("#apply-repair").hidden = true;
    announce("安全修复已应用并重新验证，可撤销");
  } catch (error) { showError(error); }
});

async function historyAction(action) {
  try { render(await api(`/experiments/${state.session.session_id}/${action}`)); announce(action === "undo" ? "已撤销" : "已重做"); }
  catch (error) { showError(error); }
}
$("#undo-button").addEventListener("click", () => historyAction("undo"));
$("#redo-button").addEventListener("click", () => historyAction("redo"));

$("#recommend-button").addEventListener("click", async () => {
  try {
    const value = await api(`/experiments/${state.session.session_id}/backend-recommendations`);
    const container = $("#backend-list");
    container.hidden = false;
    container.innerHTML = value.items.map(item => `<div class="backend-item ${item.available ? "" : "unavailable"}"><span aria-hidden="true">${item.available ? "●" : "○"}</span><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.id)} · ${item.max_qubits} 比特 · ${escapeHtml(item.reason)}</small></div>${item.selectable ? `<button type="button" data-backend-id="${escapeHtml(item.id)}" ${item.id === value.selected ? "disabled" : ""}>${item.id === value.selected ? "已选择" : "选择"}</button>` : '<span class="badge">未连接</span>'}</div>`).join("");
    announce("后端比较已展开；本地模拟器保持可用");
  } catch (error) { showError(error); }
});

$("#backend-list").addEventListener("click", async event => {
  const button = event.target.closest("button[data-backend-id]");
  if (!button) return;
  try {
    const session = await api(`/experiments/${state.session.session_id}/backend`, { method: "PATCH", body: { backend_id: button.dataset.backendId } });
    render(session);
    $("#recommend-button").click();
    announce("运行后端已选择");
  } catch (error) { showError(error); }
});

function selectEvidence(name) {
  $$(".evidence-tab").forEach(tab => {
    const selected = tab.dataset.evidence === name;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  $$(".evidence-view").forEach(view => { view.hidden = view.id !== `evidence-${name}`; });
  $("#explain-button").setAttribute("aria-expanded", String(name === "explanation"));
}

$$('.evidence-tab').forEach(tab => tab.addEventListener("click", () => selectEvidence(tab.dataset.evidence)));

$("#explain-button").addEventListener("click", () => {
  selectEvidence("explanation");
  $("#explain-button").setAttribute("aria-expanded", "true");
});

$("#help-button").addEventListener("click", () => {
  const help = $("#shortcut-help");
  const willOpen = help.hidden;
  $("#agent-surface").hidden = willOpen;
  help.hidden = !willOpen;
  $("#close-secondary").hidden = !willOpen;
  $("#dialog-title").textContent = willOpen ? "键盘帮助" : "Agent";
  $("#help-button").setAttribute("aria-expanded", String(willOpen));
});

const systemPrefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function setReducedMotion(active, persist = true) {
  active = Boolean(active || systemPrefersReducedMotion);
  document.body.classList.toggle("reduce-motion", active);
  const button = $("#motion-button");
  button.setAttribute("aria-pressed", String(active));
  button.textContent = active ? "减少动态：已开启" : "减少动态：已关闭";
  button.setAttribute("aria-label", active ? "减少动态已开启；点击恢复动态效果" : "减少动态已关闭；点击减少动态效果");
  if (persist) window.localStorage.setItem("loomq-reduce-motion", String(active));
  return active;
}

$("#motion-button").addEventListener("click", () => {
  const active = !document.body.classList.contains("reduce-motion");
  const effective = setReducedMotion(active);
  announce(effective ? "减少动态已开启：顶部运行状态点已停止呼吸动画" : "减少动态已关闭：顶部运行状态点已恢复呼吸动画");
});

const savedMotionPreference = window.localStorage.getItem("loomq-reduce-motion");
setReducedMotion(savedMotionPreference === "true", false);

function setColorAccessible(active, persist = true) {
  document.body.classList.toggle("color-accessible", active);
  const button = $("#color-button");
  button.setAttribute("aria-pressed", String(active));
  button.textContent = active ? "色觉辅助：已开启" : "色觉辅助：已关闭";
  button.setAttribute("aria-label", active ? "色觉辅助配色已开启；点击恢复浅蓝浅粉配色" : "色觉辅助配色已关闭；点击切换到高区分配色");
  if (persist) window.localStorage.setItem("loomq-color-accessible", String(active));
}

$("#color-button").addEventListener("click", () => {
  const active = !document.body.classList.contains("color-accessible");
  setColorAccessible(active);
  announce(active ? "色觉辅助已开启：已切换为蓝橙高区分配色" : "色觉辅助已关闭：已恢复浅蓝浅粉配色");
});

setColorAccessible(window.localStorage.getItem("loomq-color-accessible") === "true", false);

$("#edit-goal").addEventListener("click", async () => {
  const goal = window.prompt("编辑实验目标", state.session.goal || "");
  if (!goal || goal === state.session.goal) return;
  try { render(await api(`/experiments/${state.session.session_id}/goal`, { method: "PATCH", body: { goal } })); announce("目标已更新，请重新验证"); }
  catch (error) { showError(error); }
});

function setTutorial(active) {
  $("#main").classList.toggle("tutorial-active", active);
  $("#stage-track").hidden = !active;
  $("#guide-card").hidden = !active;
  $("#tutorial-toggle").setAttribute("aria-pressed", String(active));
  $("#tutorial-toggle").textContent = active ? "退出 Bell 引导" : "开始 Bell 引导";
  announce(active ? "Bell 引导已开始，工作台功能保持开放" : "已退出 Bell 引导，当前实验保留");
}

$("#tutorial-toggle").addEventListener("click", async () => {
  const active = $("#main").classList.contains("tutorial-active");
  if (active) { setTutorial(false); return; }
  const ir = state.session.circuit_ir || {};
  const hasWork = (ir.gates || []).length || (ir.measurements || []).length || state.session.result;
  if (hasWork && !window.confirm("开始 Bell 引导会建立新的 Bell 实验。继续吗？")) return;
  if (hasWork) {
    try { render(await api("/experiments", { body: { mode: "bell" } })); }
    catch (error) { showError(error); return; }
  }
  setTutorial(true);
});
$("#exit-guide").addEventListener("click", () => setTutorial(false));

$("#validate-button").addEventListener("click", async () => {
  try {
    let session = await api(`/experiments/${state.session.session_id}/circuit`, { method: "PATCH", body: { qasm: $("#qasm-editor").value, circuit_revision: state.session.circuit_revision } });
    render(session);
    session = await api(`/experiments/${state.session.session_id}/validate`);
    render(session);
    selectEvidence("validation");
    announce(session.state === "runnable" ? "验证完成，可以运行" : "验证完成，请查看证据视图");
  } catch (error) { showError(error); }
});

$("#run-button").addEventListener("click", async () => {
  const shots = Number($("#shots-input").value);
  try {
    const session = await api(`/experiments/${state.session.session_id}/runs`, { body: { shots } });
    render(session);
    announce("本地运行完成，结果已显示");
  } catch (error) { showError(error); }
});

$("#close-secondary").addEventListener("click", () => {
  $("#shortcut-help").hidden = true;
  $("#agent-surface").hidden = false;
  $("#close-secondary").hidden = true;
  $("#dialog-title").textContent = "Agent";
  $("#help-button").setAttribute("aria-expanded", "false");
});

$("#agent-form").addEventListener("submit", async event => {
  event.preventDefault();
  const input = $("#agent-input");
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = "";
  const send = $("#agent-send");
  send.disabled = true;
  send.classList.add("loading");
  send.setAttribute("aria-label", "思考中");
  send.innerHTML = '<span class="progress-dots" aria-hidden="true"><i></i><i></i><i></i></span>';
  setAgentStatus("思考中");
  renderAgentProposal(null);
  try {
    const value = await api(`/experiments/${state.session.session_id}/agent`, { body: { prompt } });
    if (value.session) render(value.session);
    renderConversation(value.conversation, value.understanding);
    renderAgentProposal(value.proposal);
    setAgentStatus(
      value.status === "ready" ? `已连接 ${value.model}`
        : value.status === "fallback"
          ? (value.model_attempted
            ? "本地预置回退 · 回复非模型生成"
            : "本地预置回退 · 未调用模型")
          : value.status === "unavailable" ? "未配置" : "请求失败",
      value.status,
    );
    announce(
      value.proposal ? "Agent 已生成待确认提案"
        : value.status === "fallback" ? "已使用本地预置回复"
          : value.status === "error" ? "Agent 请求未完成" : "Agent 已回复",
    );
  } catch (error) {
    showError(error);
    setAgentStatus("请求失败", "error");
  } finally {
    send.disabled = false;
    send.classList.remove("loading");
    send.removeAttribute("aria-label");
    send.textContent = "发送";
    input.focus();
  }
});

$("#agent-apply").addEventListener("click", async () => {
  if (!state.agentProposal) return;
  try {
    const session = await api(`/experiments/${state.session.session_id}/apply-agent-proposal`, { body: { proposal_id: state.agentProposal.proposal_id } });
    renderAgentProposal(null);
    render(session);
    renderConversation(session.conversation);
    announce("Agent 提案已确认并应用");
  } catch (error) { showError(error); }
});

$("#agent-reject").addEventListener("click", () => {
  renderAgentProposal(null);
  announce("Agent 提案已取消，实验未改变");
});

async function restoreOrCreate() {
  const sharedSession = new URLSearchParams(window.location.search).get("session");
  const tutorialRequested = new URLSearchParams(window.location.search).get("tutorial") === "bell";
  const sessionId = sharedSession || window.sessionStorage.getItem("loomq-session-id");
  if (sessionId) {
    try {
      const response = await fetch(`/api/experiments/${sessionId}`);
      if (response.ok) { render(await response.json()); if (tutorialRequested) setTutorial(true); announce("已恢复当前实验"); return; }
    } catch (_) { /* The offline fallback below remains available. */ }
  }
  const session = await createExperiment();
  if (session && tutorialRequested) setTutorial(true);
}
fetch("/api/health").then(response => response.json()).then(value => {
  setAgentStatus(value.agent_configured ? "已配置" : "未配置", value.agent_configured ? "ready" : "unavailable");
}).catch(() => setAgentStatus("状态未知", "error"));
fetch("/api/hardware-evidence")
  .then(response => {
    if (!response.ok) throw new Error(`hardware evidence returned ${response.status}`);
    return response.json();
  })
  .then(renderHardwareEvidence)
  .catch(() => {
    $("#hardware-evidence-notice").textContent = "已归档真机摘要当前不可读取；本地实验功能不受影响。";
  });
restoreOrCreate();
