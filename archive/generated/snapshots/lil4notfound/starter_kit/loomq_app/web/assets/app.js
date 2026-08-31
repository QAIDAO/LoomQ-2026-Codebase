import { analyzeRepairInput, renderDiagnostics } from "/assets/diagnostics.js";
import { ConversationSession } from "/assets/session.js";
import { renderVisualizations, renderWelcomePreview } from "/assets/visualizers.js";

const EXAMPLES = [
  "生成一个 3 比特 GHZ 态并进行全测量",
  "目标是 Bell 态，请修复这段代码：\nH q[0];\nCX q[0] q[1]",
  "我需要运行 15 比特线路，希望免费、本地运行，而且不用排队",
];

const TASK_LABELS = {
  generate: "已识别 · 生成线路",
  repair: "已识别 · 修复代码",
  select_backend: "已识别 · 选择平台",
  explain: "已识别 · 概念解释",
};

const session = new ConversationSession(4);

const form = document.querySelector("#chat-form");
const prompt = document.querySelector("#prompt");
const answer = document.querySelector("#answer");
const thread = document.querySelector(".thread");
const copyButton = document.querySelector("#copy-answer");
const clearButton = document.querySelector("#clear-context");
const exampleButtons = [...document.querySelectorAll("[data-example-index]")];
const submitButton = document.querySelector("#submit-task");
const visualization = document.querySelector("#visualization");
const diagnostics = document.querySelector("#diagnostics");
const contextCount = document.querySelector("#context-count");
const contextSummary = document.querySelector("#context-summary");
const detectedTask = document.querySelector("#detected-task");
const resultWorkspace = document.querySelector(".result-workspace");

renderWelcomePreview(visualization);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = prompt.value.trim();
  if (!value) return;

  const preflight = analyzeRepairInput(value);
  setBusy(true);
  copyButton.disabled = true;
  answer.className = "answer loading";
  answer.textContent = "正在理解你的目标并进行本地核验…";
  detectedTask.textContent = "正在识别意图";
  detectedTask.classList.add("working");
  visualization.replaceChildren();
  visualization.hidden = true;
  renderDiagnostics({ container: diagnostics, preflight });

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: value,
        history: session.historyForRequest(),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new WeavingRequestError(payload);

    answer.className = "answer";
    answer.textContent = payload.answer;
    copyButton.disabled = false;
    session.record(value, payload.answer, payload.task);
    detectedTask.textContent = TASK_LABELS[payload.task] || "已识别 · 自然语言任务";
    detectedTask.classList.remove("working");
    updateContext();
    renderDiagnostics({ container: diagnostics, diagnostics: payload.diagnostics, preflight });
    renderVisualizations({ response: payload, container: visualization });
    showResult();
  } catch (error) {
    const problem = error instanceof WeavingRequestError ? error.payload.diagnostic : {
      severity: "error",
      code: "browser_request_failed",
      message: "页面无法完成本次请求",
      location: "连接位置：本地织络服务",
      detail: error.message,
      actions: ["确认本地服务仍在运行", "保留输入，刷新页面后重试"],
    };
    answer.className = "answer error";
    answer.textContent = problem?.message || "本次任务没有完成。";
    detectedTask.textContent = "识别未完成";
    detectedTask.classList.remove("working");
    renderDiagnostics({ container: diagnostics, diagnostics: [problem], preflight });
    showResult();
  } finally {
    setBusy(false);
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(answer.textContent);
  copyButton.textContent = "已复制";
  window.setTimeout(() => { copyButton.textContent = "复制回答"; }, 1200);
});

clearButton.addEventListener("click", () => {
  session.clear();
  detectedTask.textContent = "等待输入";
  updateContext();
  prompt.focus();
});

exampleButtons.forEach((button) => button.addEventListener("click", () => {
  prompt.value = EXAMPLES[Number(button.dataset.exampleIndex)] || EXAMPLES[0];
  prompt.focus();
  prompt.setSelectionRange(prompt.value.length, prompt.value.length);
}));

prompt.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") form.requestSubmit();
});

window.addEventListener("loomq:source-line", (event) => {
  if (document.querySelector(`[data-source-line="${event.detail.line}"]`)) return;
  const lines = prompt.value.split(/\r?\n/);
  const lineIndex = Math.max(0, Math.min(lines.length - 1, event.detail.line - 1));
  const start = lines.slice(0, lineIndex).reduce((total, line) => total + line.length + 1, 0);
  prompt.focus();
  prompt.setSelectionRange(start, start + lines[lineIndex].length);
});

function updateContext() {
  const turns = session.recentTurns();
  contextCount.textContent = `${turns.length} / 2 轮`;
  clearButton.disabled = turns.length === 0;
  if (!turns.length) {
    contextSummary.textContent = "还没有历史。";
    return;
  }
  const latest = turns[turns.length - 1];
  const label = latest.task === "repair" ? "修复" : latest.task === "select_backend" ? "后端" : "生成";
  const compact = latest.content.replace(/\s+/g, " ").slice(0, 70);
  contextSummary.textContent = `上一轮［${label}］${compact}${latest.content.length > 70 ? "…" : ""}`;
}

function setBusy(value) {
  thread.setAttribute("aria-busy", String(value));
  submitButton.disabled = value;
  exampleButtons.forEach((button) => { button.disabled = value; });
}

function showResult() {
  window.requestAnimationFrame(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    resultWorkspace.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  });
}

class WeavingRequestError extends Error {
  constructor(payload) {
    super(payload?.error || "织络请求失败");
    this.payload = payload;
  }
}
