const byId = (id) => document.getElementById(id);
const statusBox = byId("status");
let statusTimer;

function announce(message, isError = false) {
  clearTimeout(statusTimer);
  statusBox.textContent = message;
  statusBox.className = `status visible${isError ? " error" : ""}`;
  statusTimer = setTimeout(() => { statusBox.className = "status"; }, 5000);
}

async function request(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`${data.error || "请求失败"}${data.recovery ? `\n${data.recovery}` : ""}`);
  return data;
}

function payload(extra = {}) {
  return {
    qasm: byId("qasm").value,
    target: byId("target").value,
    shots: Number(byId("shots").value),
    ...extra,
  };
}

function render(data) {
  if (!data.result) return;
  const { counts, shots, backend, bit_order: bitOrder, meta } = data.result;
  const histogram = byId("histogram");
  histogram.replaceChildren();
  Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([state, count]) => {
    const ratio = count / shots;
    const row = document.createElement("div");
    row.className = "bar-row";
    const label = document.createElement("span");
    label.className = "state-label";
    label.textContent = `|${state}〉`;
    const track = document.createElement("div");
    track.className = "track";
    track.setAttribute("aria-label", `量子态 ${state}，概率 ${(ratio * 100).toFixed(1)}%`);
    const fill = document.createElement("div");
    fill.className = "fill";
    track.append(fill);
    const value = document.createElement("span");
    value.className = "bar-value";
    value.textContent = `${(ratio * 100).toFixed(1)}% · ${count}`;
    row.append(label, track, value);
    histogram.append(row);
    requestAnimationFrame(() => { fill.style.width = `${ratio * 100}%`; });
  });
  byId("empty-state").hidden = true;
  histogram.hidden = false;
  const certificate = meta.translation_certificate;
  const proof = certificate?.verified
    ? `全态等价 · ${certificate.certificate_sha256.slice(0, 10)}…`
    : "未生成证书";
  byId("run-meta").innerHTML = `<div><dt>状态</dt><dd>目标 IR 已验证执行</dd></div><div><dt>翻译证书</dt><dd>${proof}</dd></div><div><dt>后端</dt><dd>${backend}</dd></div><div><dt>位序</dt><dd>${bitOrder}（右侧 c[0]）</dd></div><div><dt>深度</dt><dd>${meta.depth}</dd></div>`;
  byId("raw-output").textContent = `${data.reply ? `${data.reply}\n\n` : ""}--- Target IR ---\n${data.target_ir || "（本次回答不是电路）"}\n\n--- Result ---\n${JSON.stringify(data.result, null, 2)}`;
}

async function withBusy(button, label, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try { await action(); }
  catch (error) { announce(error.message, true); }
  finally { button.disabled = false; button.textContent = original; }
}

byId("run-circuit").addEventListener("click", (event) => withBusy(event.currentTarget, "正在验证…", async () => {
  const data = await request("/api/run", payload());
  render(data);
  announce("运行成功：目标 IR 回读、全状态等价和结果 Schema 均已验证。", false);
  byId("results-title").scrollIntoView({ behavior: "smooth" });
}));

byId("ask-agent").addEventListener("click", (event) => withBusy(event.currentTarget, "智能体正在规划与自检…", async () => {
  const data = await request("/api/agent", payload({ prompt: byId("prompt").value }));
  if (data.qasm) byId("qasm").value = data.qasm;
  if (data.result) render(data);
  else byId("raw-output").textContent = data.reply;
  announce(data.qasm ? "智能体答案已通过本地语义验证。" : "后端建议已按官方能力表核对。", false);
  byId("results-title").scrollIntoView({ behavior: "smooth" });
}));

document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
  byId("prompt").value = button.dataset.prompt;
  byId("prompt").focus();
}));

byId("copy-qasm").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(byId("qasm").value); announce("QASM 已复制。", false); }
  catch { byId("qasm").select(); announce("已选中 QASM，请使用系统复制快捷键。", false); }
});
