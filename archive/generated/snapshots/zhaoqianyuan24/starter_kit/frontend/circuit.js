const GATE_LABELS = {
  h: "H",
  x: "X",
  s: "S",
  sdg: "S†",
  t: "T",
  tdg: "T†",
  ry: "RY",
  rz: "RZ",
};

export function renderCircuit(experiment, { svg, stateOrder }) {
  const { circuit } = experiment;
  const qubitGap = 70;
  const qubitYs = Array.from({ length: circuit.num_qubits }, (_, index) => 55 + index * qubitGap);
  const classicalY = 55 + circuit.num_qubits * qubitGap;
  const wireStart = 118;
  const width = Math.max(800, 260 + circuit.operations.length * 90);
  const height = classicalY + 42;
  const wires = [
    ...qubitYs.map((y) => `<path d="M${wireStart} ${y}H${width - 40}" />`),
    `<path d="M${wireStart} ${classicalY}H${width - 40}" />`,
  ].join("");
  const labels = [
    ...qubitYs.map((y, index) => `<text class="qubit-label" x="14" y="${y + 6}">q${index}</text><text class="ket-label" x="66" y="${y + 6}">|0⟩</text>`),
    `<text class="classical-register" x="76" y="${classicalY + 6}">c</text>`,
  ].join("");
  const operations = circuit.operations.map((operation, index) => {
    const markup = renderOperation(operation, 175 + index * 90, qubitYs, classicalY);
    return `<g class="operation" data-operation-index="${operation.index}" role="button" tabindex="0" aria-pressed="false" aria-label="查看 ${escapeMarkup(operation.technical || operation.title)} 的解释">${markup}</g>`;
  }).join("");

  const stateOrderLabel = Array.from({ length: circuit.num_qubits }, (_, index) => `q${index}`).join(", ");
  stateOrder.textContent = `状态顺序：${stateOrderLabel}`;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.style.minWidth = width > 800 ? `${width}px` : "";
  svg.innerHTML = `
    <title id="circuit-title">${escapeMarkup(experiment.title)}量子电路</title>
    <desc id="circuit-desc">该电路由真实 L2 生成，并通过 LoomQ L1 parser/IR 校验。</desc>
    <g class="wires">${wires}</g>
    <g class="labels">${labels}</g>
    ${operations}
  `;
}

function renderOperation(operation, x, qubitYs, classicalY) {
  if (operation.type === "measure") {
    const y = qubitYs[operation.qubit];
    return `<g class="measure"><rect x="${x - 22}" y="${y - 22}" width="44" height="44" rx="6" /><path class="meter-arc" d="M${x - 11} ${y + 7}a12 12 0 0 1 22 0" /><path class="meter-hand" d="M${x} ${y + 5}l8-9" /><path class="measure-link" d="M${x} ${y + 22}V${classicalY}" /><path class="measure-link" d="m${x - 6} ${classicalY - 10} 6 10 6-10" /></g>`;
  }

  const gate = operation.gate;
  const qubits = operation.qubits;
  if (Object.hasOwn(GATE_LABELS, gate)) {
    const label = operation.parameter ? `${GATE_LABELS[gate]}(${operation.parameter})` : GATE_LABELS[gate];
    return renderSingleGate(x, qubitYs[qubits[0]], label);
  }
  if (gate === "cx") return renderControlledGate(x, qubitYs[qubits[0]], qubitYs[qubits[1]], "+");
  if (gate === "cu1") return renderControlledGate(x, qubitYs[qubits[0]], qubitYs[qubits[1]], "P");
  if (gate === "swap") return renderSwapGate(x, qubitYs[qubits[0]], qubitYs[qubits[1]]);
  if (gate === "ccx") return renderCcxGate(x, qubits.map((qubit) => qubitYs[qubit]));
  return "";
}

function renderSingleGate(x, y, label) {
  const safeLabel = escapeMarkup(label);
  const fontSize = safeLabel.length > 5 ? 11 : 16;
  return `<g class="single-gate"><rect x="${x - 25}" y="${y - 22}" width="50" height="44" rx="8" /><text x="${x}" y="${y + 6}" style="font-size:${fontSize}px">${safeLabel}</text></g>`;
}

function renderControlledGate(x, controlY, targetY, targetLabel) {
  if (targetLabel === "+") {
    return `<g class="controlled-gate"><circle class="control" cx="${x}" cy="${controlY}" r="7" /><path d="M${x} ${controlY}V${targetY}" /><circle cx="${x}" cy="${targetY}" r="17" /><path d="M${x - 12} ${targetY}h24M${x} ${targetY - 12}v24" /></g>`;
  }
  return `<g class="controlled-gate"><circle class="control" cx="${x}" cy="${controlY}" r="7" /><path d="M${x} ${controlY}V${targetY}" /><rect x="${x - 22}" y="${targetY - 22}" width="44" height="44" rx="8" /><text x="${x}" y="${targetY + 6}">${targetLabel}</text></g>`;
}

function renderSwapGate(x, firstY, secondY) {
  return `<g class="swap-gate"><path d="M${x} ${firstY}V${secondY}M${x - 10} ${firstY - 10}l20 20M${x + 10} ${firstY - 10}l-20 20M${x - 10} ${secondY - 10}l20 20M${x + 10} ${secondY - 10}l-20 20" /></g>`;
}

function renderCcxGate(x, qubitYs) {
  return `<g class="ccx-gate"><path d="M${x} ${Math.min(...qubitYs)}V${Math.max(...qubitYs)}" /><circle class="control" cx="${x}" cy="${qubitYs[0]}" r="7" /><circle class="control" cx="${x}" cy="${qubitYs[1]}" r="7" /><circle cx="${x}" cy="${qubitYs[2]}" r="17" /><path d="M${x - 12} ${qubitYs[2]}h24M${x} ${qubitYs[2] - 12}v24" /></g>`;
}

export function escapeMarkup(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}
