const QASM_TOKEN = /\b(openqasm|include|qreg|creg|measure|h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\b/i;
const QASM_CODE_SIGNAL = /(?:\bOPENQASM\s+\d+(?:\.\d+)?|\binclude\s+["']|\b(?:qreg|creg)\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\]|\bmeasure\s+[A-Za-z_]\w*(?:\s*\[\s*\d+\s*\])?\s*->|\b(?:h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\s*(?:\([^\r\n)]*\)\s*)?[A-Za-z_]\w*\s*\[\s*\d+\s*\])/i;
const UPPERCASE_GATE = /\b(H|X|S|SDG|T|TDG|RZ|RY|CX|CU1|SWAP|CCX)\b/g;
const STATEMENT_START = /^\s*(openqasm|include|qreg|creg|measure|h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\b/i;

export function analyzeRepairInput(source) {
  if (!QASM_CODE_SIGNAL.test(source)) return [];
  const diagnostics = [];
  const lines = source.split(/\r?\n/);
  let sawHeader = false;

  lines.forEach((raw, index) => {
    const lineNumber = index + 1;
    const line = raw.replace(/\/\/.*$/, "").trim();
    if (!line || line.startsWith("```") || !QASM_TOKEN.test(line)) return;
    if (/OPENQASM\s+2\.0/i.test(line)) sawHeader = true;

    const uppercase = [...line.matchAll(UPPERCASE_GATE)].map((match) => match[0]);
    if (uppercase.length) {
      diagnostics.push({
        severity: "warning",
        code: "uppercase_gate",
        line: lineNumber,
        message: `第 ${lineNumber} 行包含大写门名：${[...new Set(uppercase)].join("、")}`,
        suggestion: "OpenQASM 2.0 门名区分大小写，请改为小写。",
      });
    }

    const statement = line.replace(/^.*?(?=(?:openqasm|include|qreg|creg|measure|h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx)\b)/i, "");
    if (STATEMENT_START.test(statement) && !/[;{}]\s*$/.test(statement)) {
      diagnostics.push({
        severity: "warning",
        code: "missing_semicolon",
        line: lineNumber,
        message: `第 ${lineNumber} 行可能缺少分号`,
        suggestion: "每条 OpenQASM 语句都应以分号结束。",
      });
    }

    const gate = statement.match(/^\s*(cx|cu1|swap|ccx)\b(?:\s*\([^)]*\))?\s+(.+?);?\s*$/i);
    if (gate) {
      const expectedCommas = gate[1].toLowerCase() === "ccx" ? 2 : 1;
      const commaCount = (gate[2].match(/,/g) || []).length;
      if (commaCount < expectedCommas) {
        diagnostics.push({
          severity: "warning",
          code: "missing_operand_comma",
          line: lineNumber,
          message: `第 ${lineNumber} 行的 ${gate[1].toLowerCase()} 操作数分隔不完整`,
          suggestion: `该门需要 ${expectedCommas + 1} 个操作数，并使用逗号分隔。`,
        });
      }
    }
  });

  if (!sawHeader) {
    diagnostics.unshift({
      severity: "warning",
      code: "missing_header",
      line: 1,
      message: "没有检测到 OPENQASM 2.0 头部",
      suggestion: "修复结果应包含版本头、qelib1.inc、qreg、creg 和测量。",
    });
  }
  return diagnostics.slice(0, 8);
}

export function renderDiagnostics({ container, diagnostics = [], preflight = [] }) {
  const items = [...preflight, ...diagnostics.map(normalizeDiagnostic)];
  container.replaceChildren();
  container.hidden = items.length === 0;
  if (!items.length) return;

  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const needsReview = items.some((item) => item.severity === "warning" || item.severity === "error");
  heading.innerHTML = `<span>${needsReview ? "人工复核 · 松线" : "已自动检查"}</span><strong>${items.length} 条</strong>`;
  const list = document.createElement("div");
  list.className = "diagnostic-list";
  items.forEach((item) => list.append(createDiagnostic(item)));
  container.append(heading, list);
}

function normalizeDiagnostic(item) {
  const suggestions = {
    local_validation_passed: "线路已经通过解析与理想态检查，可以查看线路图和测量分布。",
    local_validation_retried: "初版未通过检查，当前展示的是自动修复并重新验证后的版本。",
    deterministic_backend_filter: "候选项来自赛事能力表，不依赖模型猜测。",
  };
  return {
    severity: item.severity || "info",
    code: item.code || "agent_diagnostic",
    message: item.message || "Agent 返回了一条诊断信息。",
    line: item.line,
    location: item.location,
    suggestion: item.suggestion || suggestions[item.code],
    detail: item.detail,
    actions: item.actions || [],
  };
}

function createDiagnostic(item) {
  const article = document.createElement("article");
  article.className = `diagnostic diagnostic-${item.severity || "info"}`;

  const marker = document.createElement("span");
  marker.className = "diagnostic-marker";
  marker.textContent = item.severity === "error" ? "!" : item.severity === "warning" ? "△" : "✓";

  const body = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = item.message;
  body.append(title);

  if (item.location) appendText(body, item.location, "diagnostic-location");
  if (item.detail && item.detail !== item.message) appendText(body, item.detail, "diagnostic-detail");
  if (item.suggestion) appendText(body, item.suggestion, "diagnostic-suggestion");
  if (item.actions?.length) {
    const actions = document.createElement("ol");
    item.actions.forEach((text) => {
      const action = document.createElement("li");
      action.textContent = text;
      actions.append(action);
    });
    body.append(actions);
  }

  if (item.line) {
    const locate = document.createElement("button");
    locate.type = "button";
    locate.className = "line-link";
    locate.textContent = `查看这根线 · 定位第 ${item.line} 行`;
    locate.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("loomq:source-line", { detail: { line: item.line } }));
    });
    body.append(locate);
  }
  article.append(marker, body);
  return article;
}

function appendText(parent, text, className) {
  const paragraph = document.createElement("p");
  paragraph.className = className;
  paragraph.textContent = text;
  parent.append(paragraph);
}
