// Lightweight OpenQASM 2.0 circuit parser and DOM renderer for the workspace.

const MAX_QUBITS = 32;
const MAX_OPERATIONS = 72;
const ROW_HEIGHT = 64;
const COLUMN_HEAD = 38;

export function parseQasmCircuit(qasm) {
  if (typeof qasm !== 'string' || !qasm.trim()) {
    throw new Error('缺少可绘制的 QASM');
  }

  const source = qasm
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/.*$/gm, '');
  const statements = source
    .split(';')
    .map((statement) => statement.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const quantumRegisters = new Map();
  const classicalRegisters = new Map();

  statements.forEach((statement) => {
    const quantum = statement.match(/^qreg\s+([A-Za-z_]\w*)\[(\d+)\]$/i);
    if (quantum) quantumRegisters.set(quantum[1], Number(quantum[2]));
    const classical = statement.match(/^creg\s+([A-Za-z_]\w*)\[(\d+)\]$/i);
    if (classical) classicalRegisters.set(classical[1], Number(classical[2]));
  });

  const qubits = [];
  quantumRegisters.forEach((size, name) => {
    for (let index = 0; index < size; index += 1) qubits.push(`${name}[${index}]`);
  });
  const operations = [];

  statements.forEach((statement) => {
    if (/^(OPENQASM|include|qreg|creg|gate|opaque)\b/i.test(statement)) return;

    const measurement = statement.match(/^measure\s+(.+?)\s*->\s*(.+)$/i);
    if (measurement) {
      const targets = resolveOperand(measurement[1], quantumRegisters);
      const classical = resolveOperand(measurement[2], classicalRegisters);
      if (targets.length) {
        operations.push({ gate: 'measure', targets, classical, source: statement });
      }
      return;
    }

    const barrier = statement.match(/^barrier\s+(.+)$/i);
    if (barrier) {
      const targets = resolveOperands(barrier[1], quantumRegisters);
      operations.push({ gate: 'barrier', targets: targets.length ? targets : qubits, source: statement });
      return;
    }

    const operation = statement.match(/^([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s+(.+)$/);
    if (!operation) return;
    const targets = resolveOperands(operation[3], quantumRegisters);
    if (!targets.length) return;
    operations.push({
      gate: operation[1].toLowerCase(),
      parameters: operation[2]?.trim() || '',
      targets,
      source: statement,
    });
  });

  const visibleQubits = qubits.slice(0, MAX_QUBITS);
  const visibleRows = new Set(visibleQubits);
  return {
    qubits: visibleQubits,
    operations: operations
      .filter((operation) => operation.targets.some((target) => visibleRows.has(target)))
      .slice(0, MAX_OPERATIONS),
    totalQubits: qubits.length,
    totalOperations: operations.length,
    truncated: qubits.length > MAX_QUBITS || operations.length > MAX_OPERATIONS,
  };
}

function resolveOperands(value, registers) {
  return value
    .split(',')
    .flatMap((operand) => resolveOperand(operand, registers));
}

function resolveOperand(value, registers) {
  const operand = value.trim();
  const indexed = operand.match(/^([A-Za-z_]\w*)\[(\d+)\]$/);
  if (indexed) {
    const size = registers.get(indexed[1]);
    const index = Number(indexed[2]);
    return Number.isInteger(size) && index >= 0 && index < size
      ? [`${indexed[1]}[${index}]`]
      : [];
  }
  const size = registers.get(operand);
  if (!Number.isInteger(size)) return [];
  return Array.from({ length: size }, (_, index) => `${operand}[${index}]`);
}

export class CircuitVisualizer {
  constructor(root) {
    this.root = root;
    this.empty = root.querySelector('#circuit-empty');
    this.view = root.querySelector('#circuit-view');
    this.scroll = root.querySelector('#circuit-scroll');
    this.summary = root.querySelector('#circuit-summary');
    this.name = root.querySelector('#circuit-name');
    this.version = root.querySelector('#circuit-version');
  }

  render(qasm, artifact = {}) {
    let circuit;
    try {
      circuit = parseQasmCircuit(qasm);
    } catch (_error) {
      this.showEmpty('暂无法绘制当前电路');
      return;
    }
    if (!circuit.qubits.length) {
      this.showEmpty('当前 QASM 没有量子寄存器');
      return;
    }

    this.empty.hidden = true;
    this.view.hidden = false;
    this.summary.hidden = false;
    this.name.textContent = compactGoal(artifact.goal) || inferCircuitName(circuit);
    this.version.textContent = artifact.version ? `v${artifact.version}` : '';
    this.summary.replaceChildren(
      createSummaryItem(`${circuit.totalQubits} 比特`),
      createSummaryItem(`${circuit.totalOperations} 个操作`),
    );
    this.scroll.replaceChildren(createCircuitDiagram(circuit));
    this.scroll.scrollLeft = 0;
    this.root.classList.remove('is-empty');
    this.root.classList.add('has-circuit');
    this.root.dispatchEvent(new CustomEvent('loomq:circuit-ready'));
  }

  clear() {
    this.scroll.replaceChildren();
    this.summary.replaceChildren();
    this.summary.hidden = true;
    this.view.hidden = true;
    this.version.textContent = '';
    this.empty.querySelector('strong').textContent = '等待当前电路';
    this.empty.hidden = false;
    this.root.classList.remove('has-circuit');
    this.root.classList.add('is-empty');
    this.root.dispatchEvent(new CustomEvent('loomq:circuit-clear'));
  }

  showEmpty(message) {
    this.clear();
    this.empty.querySelector('strong').textContent = message;
  }
}

function createCircuitDiagram(circuit) {
  const diagram = document.createElement('div');
  diagram.className = 'circuit-diagram';
  diagram.setAttribute('role', 'img');
  diagram.setAttribute(
    'aria-label',
    `${circuit.totalQubits} 个量子比特、${circuit.totalOperations} 个操作的量子电路`,
  );

  const labels = document.createElement('div');
  labels.className = 'circuit-labels';
  const labelHead = document.createElement('span');
  labelHead.className = 'circuit-label-head';
  labelHead.textContent = 'QUBIT';
  labels.append(labelHead);
  circuit.qubits.forEach((qubit) => {
    const label = document.createElement('div');
    label.className = 'circuit-qubit-label';
    const name = document.createElement('strong');
    name.textContent = qubit;
    const state = document.createElement('span');
    state.textContent = '|0⟩';
    label.append(name, state);
    labels.append(label);
  });

  const operations = document.createElement('div');
  operations.className = 'circuit-operations';
  circuit.operations.forEach((operation, index) => {
    operations.append(createOperationColumn(operation, index, circuit.qubits));
  });
  if (!circuit.operations.length) {
    const idle = document.createElement('div');
    idle.className = 'circuit-idle-column';
    idle.textContent = '尚无量子门';
    operations.append(idle);
  }

  diagram.append(labels, operations);
  if (circuit.truncated) {
    const notice = document.createElement('p');
    notice.className = 'circuit-truncated';
    notice.textContent = '电路较大，当前显示前 32 个比特和前 72 个操作。';
    diagram.append(notice);
  }
  return diagram;
}

function createOperationColumn(operation, index, qubits) {
  const rowByQubit = new Map(qubits.map((label, row) => [label, row]));
  const rows = operation.targets
    .map((target) => rowByQubit.get(target))
    .filter((row) => Number.isInteger(row));
  const column = document.createElement('div');
  column.className = `circuit-operation operation-${operation.gate}`;
  column.style.height = `${COLUMN_HEAD + qubits.length * ROW_HEIGHT}px`;
  column.title = operation.source;
  column.setAttribute('aria-label', operation.source);

  const number = document.createElement('span');
  number.className = 'operation-number';
  number.textContent = String(index + 1).padStart(2, '0');
  column.append(number);

  qubits.forEach((_qubit, row) => {
    const wire = document.createElement('i');
    wire.className = 'circuit-wire';
    wire.style.top = `${rowCenter(row)}px`;
    column.append(wire);
  });

  if (operation.gate === 'barrier') {
    if (rows.length) column.append(createConnector(Math.min(...rows), Math.max(...rows), true));
    return column;
  }

  if (operation.gate === 'measure') {
    rows.forEach((row, targetIndex) => {
      const classical = operation.classical?.[targetIndex] || '';
      column.append(createGateNode(row, 'M', 'measurement-gate', classical ? `→ ${classical}` : ''));
    });
    return column;
  }

  if (operation.gate === 'cx' || operation.gate === 'cnot') {
    appendControlledGate(column, rows, '⊕', 'target-gate');
    return column;
  }
  if (operation.gate === 'cz') {
    appendControlledGate(column, rows, 'Z', 'gate-box controlled-target');
    return column;
  }
  if (operation.gate === 'ccx') {
    appendMultiControlledGate(column, rows, '⊕');
    return column;
  }
  if (operation.gate === 'swap') {
    appendSwapGate(column, rows);
    return column;
  }
  if (operation.gate === 'cswap') {
    if (rows.length >= 3) {
      column.append(createConnector(Math.min(...rows), Math.max(...rows)));
      column.append(createGateNode(rows[0], '', 'control-gate'));
      column.append(createGateNode(rows[1], '×', 'swap-gate'));
      column.append(createGateNode(rows[2], '×', 'swap-gate'));
    }
    return column;
  }
  if (operation.gate.startsWith('c') && rows.length >= 2) {
    appendControlledGate(column, rows, gateLabel(operation.gate.slice(1)), 'gate-box controlled-target', operation.parameters);
    return column;
  }

  const label = gateLabel(operation.gate);
  rows.forEach((row) => column.append(createGateNode(row, label, 'gate-box', operation.parameters)));
  if (rows.length > 1 && !isRegisterWideSingleGate(operation.gate)) {
    column.append(createConnector(Math.min(...rows), Math.max(...rows)));
  }
  return column;
}

function appendControlledGate(column, rows, targetLabel, targetClass, detail = '') {
  if (rows.length < 2) return;
  column.append(createConnector(Math.min(rows[0], rows[1]), Math.max(rows[0], rows[1])));
  column.append(createGateNode(rows[0], '', 'control-gate'));
  column.append(createGateNode(rows[1], targetLabel, targetClass, detail));
}

function appendMultiControlledGate(column, rows, targetLabel) {
  if (rows.length < 3) return;
  column.append(createConnector(Math.min(...rows), Math.max(...rows)));
  rows.slice(0, -1).forEach((row) => column.append(createGateNode(row, '', 'control-gate')));
  column.append(createGateNode(rows.at(-1), targetLabel, 'target-gate'));
}

function appendSwapGate(column, rows) {
  if (rows.length < 2) return;
  column.append(createConnector(Math.min(rows[0], rows[1]), Math.max(rows[0], rows[1])));
  column.append(createGateNode(rows[0], '×', 'swap-gate'));
  column.append(createGateNode(rows[1], '×', 'swap-gate'));
}

function createConnector(firstRow, lastRow, barrier = false) {
  const connector = document.createElement('i');
  connector.className = barrier ? 'gate-connector barrier-connector' : 'gate-connector';
  connector.style.top = `${rowCenter(firstRow)}px`;
  connector.style.height = `${Math.max(1, (lastRow - firstRow) * ROW_HEIGHT)}px`;
  return connector;
}

function createGateNode(row, label, className, detail = '') {
  const node = document.createElement('span');
  node.className = `circuit-gate ${className}`;
  node.style.top = `${rowCenter(row)}px`;
  if (label) {
    const main = document.createElement('b');
    main.textContent = label;
    node.append(main);
  }
  if (detail) {
    const small = document.createElement('small');
    small.textContent = detail;
    node.append(small);
    node.title = detail;
  }
  return node;
}

function rowCenter(row) {
  return COLUMN_HEAD + row * ROW_HEIGHT + ROW_HEIGHT / 2;
}

function gateLabel(gate) {
  const labels = { id: 'I', u: 'U', u1: 'U1', u2: 'U2', u3: 'U3', rx: 'RX', ry: 'RY', rz: 'RZ', p: 'P', sx: '√X' };
  return labels[gate] || gate.toUpperCase();
}

function isRegisterWideSingleGate(gate) {
  return ['id', 'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 'rx', 'ry', 'rz', 'u', 'u1', 'u2', 'u3', 'p', 'sx'].includes(gate);
}

function compactGoal(goal) {
  if (typeof goal !== 'string') return '';
  const compact = goal.replace(/\s+/g, ' ').trim();
  return compact.length > 46 ? `${compact.slice(0, 46)}…` : compact;
}

function inferCircuitName(circuit) {
  const gates = circuit.operations.map((operation) => operation.gate);
  if (gates.includes('h') && gates.filter((gate) => gate === 'cx').length >= 2) return 'GHZ 电路';
  if (gates.includes('h') && gates.includes('cx')) return 'Bell 电路';
  return '量子电路';
}

function createSummaryItem(text) {
  const item = document.createElement('span');
  item.textContent = text;
  return item;
}
