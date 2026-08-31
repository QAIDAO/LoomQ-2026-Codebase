(() => {
  'use strict';

  const page = location.pathname.split('/').pop() || 'index.html';
  const BELL_QASM = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;`;
  const LOCAL_BACKENDS = {
    spinq: {target: 'spinq', name: 'SpinQ 本地模拟器', type: 'simulator'},
    originq: {target: 'originq', name: 'OriginQ 本地模拟器', type: 'simulator'},
    braket: {target: 'braket', name: 'Braket 本地模拟器', type: 'simulator'}
  };
  const ADAPTER_CODE_FORMATS = {
    spinq: 'OpenQASM 2.0',
    originq: 'OriginIR',
    braket: 'OpenQASM 3.0'
  };
  function targetForState(state) {
    const candidates = [
      state.selectedExecutionTarget,
      state.executionBackend?.target,
      state.recommendedBackend?.adapterTarget,
      state.backend?.adapterTarget,
      state.runStatus?.target,
      'spinq'
    ];
    return candidates.find(target => LOCAL_BACKENDS[target]) || 'spinq';
  }
  function circuitHasMeasurement(state) {
    const operations = Array.isArray(state?.circuit?.operations) ? state.circuit.operations : [];
    if (operations.some(operation => operation?.type === 'measurement' || operation?.name === 'measure')) return true;
    return typeof state?.currentQasm === 'string' && /\bmeasure\b/i.test(state.currentQasm);
  }

  // 美化方案 §8: 内部字段统一翻译成人话，技术原值只在 debug 层出现。
  const TASK_TYPE_LABELS = {
    generate_circuit: '生成线路',
    repair_circuit: '修复线路',
    modify_current_task: '调整线路',
    select_backend: '选择运行环境'
  };
  const MEASUREMENT_LABELS = {all: '全部测量', none: '不测量'};
  // 美化方案 §28: Current Task 变化后短暂高亮 + "已更新" 提示，约 2 秒后淡出。
  let lastRenderedTaskVersion = null;
  let taskUpdatedTimer = null;

  async function api(path, body, options = {}) {
    const response = await fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: body ? {'Content-Type': 'application/json'} : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: options.signal
    });
    let payload;
    try { payload = await response.json(); }
    catch (_) { throw new Error(`服务器返回了无法识别的内容（HTTP ${response.status}）`); }
    if (!response.ok || !payload.ok) {
      const error = new Error(payload.user_message || payload.error || `请求失败（HTTP ${response.status}）`);
      error.code = payload.code || 'REQUEST_ERROR';
      error.status = response.status;
      error.developerDetails = payload.developer_details || `${error.code}（HTTP ${response.status}）`;
      throw error;
    }
    return payload;
  }

  function notice(message, kind = 'error') {
    let box = document.getElementById('qh-notice');
    if (!box) {
      box = document.createElement('div');
      box.id = 'qh-notice';
      box.style.cssText = 'position:fixed;z-index:9999;right:20px;bottom:20px;max-width:min(440px,calc(100vw - 40px));padding:15px 18px;border-radius:13px;color:#fff;font:600 13px/1.6 system-ui;box-shadow:0 16px 40px rgba(0,0,0,.2)';
      document.body.appendChild(box);
    }
    box.style.background = kind === 'ok' ? '#557764' : '#9a4f56';
    box.textContent = message;
    clearTimeout(box._timer);
    box._timer = setTimeout(() => box.remove(), 7000);
  }

  function target() { return localStorage.getItem('qh_target') || 'spinq'; }
  function backendName() { return localStorage.getItem('qh_backend') || 'SpinQ 本地模拟器'; }
  function readPlan() {
    try { return JSON.parse(localStorage.getItem('qh_plan') || 'null'); }
    catch (_) { return null; }
  }
  function storePlan(plan) {
    localStorage.setItem('qh_plan', JSON.stringify(plan));
    localStorage.setItem('qh_task', plan.task);
    localStorage.setItem('qh_type', plan.type);
    localStorage.setItem('qh_goal', plan.goal);
    localStorage.setItem('qh_condition', plan.condition);
    localStorage.setItem('qh_output', plan.output);
    localStorage.setItem('qh_method', plan.method);
    localStorage.setItem('qh_custom_qasm', plan.qasm);
  }
  async function createPlan(prompt, typeHint) {
    const payload = await api('/api/plan', {prompt, type_hint: typeHint || null});
    storePlan(payload.plan);
    return payload.plan;
  }

  function clearAgentRunState() {
    [
      'qh_qasm', 'qh_last_check', 'qh_import_result', 'qh_custom_result',
      'qh_plan', 'qh_custom_qasm', 'qh_plan_error'
    ].forEach(key => localStorage.removeItem(key));
  }

  function summaryOperationCount(summary = {}) {
    if (summary.operation_count != null && Number.isFinite(Number(summary.operation_count))) {
      return Number(summary.operation_count);
    }
    return Number(summary.gate_count || 0) + Number(summary.measurement_count || 0);
  }

  function setupHomePhase2() {
    const form = document.getElementById('agentStartForm');
    const input = document.getElementById('agentInput');
    const button = document.getElementById('agentBtn');
    const errorBox = document.getElementById('agentInputError');
    if (!form || !input || !button || !errorBox) return;

    const resultBox = document.createElement('section');
    resultBox.id = 'agentStartResult';
    resultBox.className = 'status';
    resultBox.setAttribute('role', 'status');
    resultBox.setAttribute('aria-live', 'polite');
    resultBox.hidden = true;
    form.insertAdjacentElement('afterend', resultBox);

    const showError = message => {
      errorBox.textContent = message;
      errorBox.hidden = false;
    };
    const clearError = () => {
      errorBox.textContent = '';
      errorBox.hidden = true;
    };
    const focusComposer = () => {
      input.focus({preventScroll: true});
      form.scrollIntoView({behavior: 'smooth', block: 'center'});
    };
    const fillComposer = prompt => {
      input.value = prompt || '';
      clearError();
      focusComposer();
    };

    document.querySelectorAll('[data-prompt]').forEach(item => {
      item.addEventListener('click', () => fillComposer(item.dataset.prompt));
    });

    input.addEventListener('input', clearError);
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const prompt = input.value.trim();
      if (!prompt) {
        resultBox.hidden = true;
        showError('请先描述你希望完成的量子任务。');
        input.focus();
        return;
      }

      clearError();
      resultBox.hidden = false;
      resultBox.textContent = 'QuantumHelper 正在理解你的任务…';
      button.disabled = true;
      button.textContent = '正在分析…';
      try {
        const payload = await api('/api/chat', {prompt});
        if (payload.kind === 'qasm') {
          const count = summaryOperationCount(payload.summary);
          resultBox.textContent = `线路已生成并通过 adapter 校验：${payload.summary.qubits} 个量子比特 · ${count} 个操作。完整工作台将在下一阶段接入。`;
        } else if (payload.kind === 'backend') {
          resultBox.textContent = `已推荐 ${payload.backend.name}（${payload.answer}）。完整推荐说明将在下一阶段接入。`;
        } else {
          resultBox.textContent = payload.answer || 'Agent 已返回结果。';
        }
      } catch (error) {
        resultBox.hidden = true;
        showError(error.code === 'LLM_DISABLED'
          ? '模型服务尚未配置。可以点右上角「配置模型」填写，或直接导入 OpenQASM 线路。'
          : error.message);
      } finally {
        button.disabled = false;
        button.textContent = '发送 →';
      }
    });

    if (new URLSearchParams(location.search).get('start') === 'agent') {
      focusComposer();
    }
  }

  function renderWorkspace(state, dispatchAction, normalizeCounts) {
    const byId = id => document.getElementById(id);
    const replace = (node, children = []) => {
      if (!node) return;
      node.replaceChildren(...children);
    };
    const textNode = (tag, text, className) => {
      const node = document.createElement(tag);
      if (className) node.className = className;
      node.textContent = text == null ? '' : String(text);
      return node;
    };

    // 第二轮 §3：安全轻量 Markdown。先转义 HTML（防注入），再只渲染粗体/行内代码/简单列表。
    const escapeHtml = s => String(s).replace(/[&<>"']/g, c => (
      {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]
    ));
    const renderMarkdown = text => {
      const inline = escapeHtml(text == null ? '' : String(text))
        .replace(/`([^`\n]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
      const lines = inline.split('\n');
      let html = '';
      let inList = false;
      for (const raw of lines) {
        const line = raw.trim();
        if (!line) { if (inList) { html += '</ul>'; inList = false; } continue; }
        const item = line.match(/^[-•]\s+(.*)$/);
        if (item) {
          if (!inList) { html += '<ul>'; inList = true; }
          html += `<li>${item[1]}</li>`;
        } else {
          if (inList) { html += '</ul>'; inList = false; }
          html += `<p>${raw}</p>`;
        }
      }
      if (inList) html += '</ul>';
      return html;
    };

    const messages = byId('conversationMessages');
    replace(messages, state.messages.map(message => {
      const article = document.createElement('article');
      article.className = `message message--${message.role === 'user' ? 'user' : 'agent'}`;
      const body = document.createElement('div');
      body.className = 'message-body';
      if (message.role === 'user') {
        body.textContent = message.text;
      } else {
        // Agent 消息走安全 Markdown（转义后再渲染），避免 ** 原样显示。
        body.innerHTML = renderMarkdown(message.text);
      }
      article.append(textNode('strong', message.role === 'user' ? '你' : 'QuantumHelper'), body);
      return article;
    }));
    const revision = byId('currentRevisionLabel');
    if (revision) revision.textContent = state.taskId ? `任务版本 ${state.currentRevision}` : '';
    const conversationStatus = byId('conversationStatus');
    if (conversationStatus) {
      conversationStatus.hidden = !state.pendingRequest;
      conversationStatus.textContent = state.pendingRequest ? '正在理解、生成并检查线路…' : '';
    }
    const errorSummary = byId('errorSummary');
    if (errorSummary) { errorSummary.hidden = !state.lastError; errorSummary.textContent = state.lastError || ''; }
    const developerDetails = byId('developerDetails');
    const developerErrorCode = byId('developerErrorCode');
    if (developerDetails) developerDetails.hidden = !state.developerDetails;
    if (developerErrorCode) developerErrorCode.textContent = state.developerDetails || '';

    const taskFields = byId('taskFields');
    const task = state.task || null;
    if (taskFields) {
      // 美化方案 §8: Current Task 是一句摘要（目标 + 规模/测量方式），
      // 不再逐字段列出内部技术名——生成线路/修复线路等人话映射见 TASK_TYPE_LABELS。
      const rows = [];
      if (task) {
        const headline = task.goal || TASK_TYPE_LABELS[task.type] || '当前线路';
        rows.push(textNode('strong', headline, 'task-summary-title'));
        const detailParts = [];
        if (task.qubits != null && task.qubits !== '') detailParts.push(`${task.qubits} qubits`);
        if (task.measurement != null && task.measurement !== '') {
          if (typeof task.measurement === 'object') {
            const pairs = Array.isArray(task.measurement.pairs) ? task.measurement.pairs : [];
            detailParts.push(pairs.length
              ? `部分测量：${pairs.map(pair => `q${pair.qubit}→c${pair.classical_bit}`).join('、')}`
              : '部分测量');
          } else {
            detailParts.push(MEASUREMENT_LABELS[task.measurement] || task.measurement);
          }
        }
        if (detailParts.length) rows.push(textNode('span', detailParts.join(' · '), 'body-copy task-summary-detail'));
      }
      replace(taskFields, rows);
      taskFields.hidden = rows.length === 0;
    }
    const taskCard = byId('taskCard');
    const taskUpdatedFlag = byId('taskUpdatedFlag');
    if (state.taskVersion !== lastRenderedTaskVersion && lastRenderedTaskVersion !== null && state.taskVersion > 0) {
      if (taskUpdatedFlag) {
        taskUpdatedFlag.hidden = false;
        clearTimeout(taskUpdatedTimer);
        taskUpdatedTimer = setTimeout(() => { taskUpdatedFlag.hidden = true; }, 2000);
      }
      if (taskCard) {
        taskCard.classList.remove('is-updated');
        void taskCard.offsetWidth;
        taskCard.classList.add('is-updated');
      }
    }
    lastRenderedTaskVersion = state.taskVersion;
    const taskOriginalPrompt = byId('taskOriginalPrompt');
    if (taskOriginalPrompt) {
      const lastUserMessage = [...state.messages].reverse().find(message => message.role === 'user');
      taskOriginalPrompt.hidden = !(task && lastUserMessage);
      taskOriginalPrompt.textContent = (task && lastUserMessage) ? `你要求：${lastUserMessage.text}` : '';
    }

    // 第三轮 §14/§15：inspection 模式——展示正在检查的外部代码，而非当前任务线路。
    const inspectionSection = byId('inspectionSection');
    if (inspectionSection) {
      const inspecting = state.workspaceMode === 'inspection' && state.inspectedQasm;
      inspectionSection.hidden = !inspecting;
      if (inspecting) {
        const code = byId('inspectedCode');
        if (code) code.textContent = state.inspectedQasm;
        const diag = byId('inspectionDiagnostics');
        if (diag) {
          const items = Array.isArray(state.diagnostics) ? state.diagnostics : [];
          replace(diag, items.map(d => textNode('p',
            `${d.severity === 'error' ? '✗ ' : ''}${d.message}${d.line ? `（第 ${d.line} 行）` : ''}`,
            'status status--danger')));
        }
      }
    }

    const circuitCanvas = byId('circuitCanvas');
    const circuitEmpty = byId('circuitEmptyState');
    const circuit = state.circuit;
    const operations = circuit && Array.isArray(circuit.operations) ? circuit.operations : [];
    const qubits = circuit && Number.isInteger(circuit.qubits) ? circuit.qubits : 0;
    const activateOperations = operationIds => {
      const activeIds = new Set(operationIds.map(String));
      document.querySelectorAll('[data-operation-id]').forEach(node => {
        const active = activeIds.has(node.dataset.operationId);
        node.classList.toggle('is-active', active);
        if (node.matches('button')) node.setAttribute('aria-pressed', String(active));
      });
      document.querySelectorAll('[data-operation-ids]').forEach(node => {
        const active = (node.dataset.operationIds || '').split(' ').some(id => activeIds.has(id));
        node.classList.toggle('is-active', active);
      });
    };
    const activateOperation = operationId => activateOperations([operationId]);
    if (circuitCanvas) {
      const diagram = document.createElement('div');
      diagram.className = 'circuit-diagram';
      const legend = textNode('p', '● 表示控制位，⊕ 表示目标位；M→c 表示把量子测量结果写入经典位 c。只有出现 M 的线路会被读取。', 'circuit-scroll-hint');
      diagram.append(legend);
      for (let qubit = 0; qubit < qubits; qubit += 1) {
        const wire = document.createElement('div');
        wire.className = 'circuit-wire';
        wire.append(textNode('span', `q${qubit}`, 'wire-label'));
        const track = document.createElement('div');
        track.className = 'wire-track';
        operations.forEach(operation => {
          const slot = document.createElement('span');
          slot.className = 'gate-slot';
          const operationQubits = Array.isArray(operation.qubits) ? operation.qubits : [];
          if (operationQubits.includes(qubit)) {
            const gate = document.createElement('button');
            gate.type = 'button';
            gate.className = 'circuit-gate';
            if (operation.type === 'measurement') gate.classList.add('circuit-measurement');
            gate.dataset.operationId = String(operation.id);
            gate.setAttribute('aria-pressed', 'false');
            const params = Array.isArray(operation.params) && operation.params.length
              ? `(${operation.params.map(value => Number(value).toPrecision(4)).join(', ')})` : '';
            const name = String(operation.name || '?').toUpperCase();
            if (operation.type === 'measurement') {
              const clbit = Array.isArray(operation.clbits) ? operation.clbits[0] : '?';
              gate.textContent = `M→c${clbit}`;
              gate.setAttribute('aria-label', `测量 q${qubit} 到经典位 c${clbit}`);
            } else if (name === 'CX' && operationQubits.length >= 2) {
              const isControl = qubit === operationQubits[0];
              gate.textContent = isControl ? '●' : '⊕';
              gate.classList.add(isControl ? 'circuit-control' : 'circuit-target');
              gate.setAttribute('aria-label', `CX 门，控制位 q${operationQubits[0]}，目标位 q${operationQubits[1]}`);
              const upper = Math.min(...operationQubits);
              const lower = Math.max(...operationQubits);
              if (qubit === upper && lower > upper) {
                slot.classList.add('has-connector');
                const connector = document.createElement('span');
                connector.className = 'circuit-connector';
                connector.setAttribute('aria-hidden', 'true');
                connector.style.setProperty('--connector-height', `${(lower - upper) * 60}px`);
                slot.append(connector);
              }
            } else {
              gate.textContent = `${name}${params}`;
              if (params) { gate.classList.add('is-parameterized'); gate.dataset.parameterized = 'true'; }
              gate.setAttribute('aria-label', `${name}${params} 门，作用于 q${qubit}`);
            }
            gate.title = String(operation.label || gate.getAttribute('aria-label'));
            ['mouseenter', 'focus', 'click'].forEach(eventName =>
              gate.addEventListener(eventName, () => activateOperation(String(operation.id)))
            );
            if (operation.type === 'measurement') gate.classList.add('circuit-measurement-label');
            slot.append(gate);
          }
          track.append(slot);
        });
        wire.append(track);
        diagram.append(wire);
      }
      replace(circuitCanvas, operations.length && qubits ? [diagram] : []);
      circuitCanvas.hidden = !(operations.length && qubits);
    }
    if (circuitEmpty) {
      circuitEmpty.hidden = Boolean(operations.length && qubits);
      circuitEmpty.textContent = operations.length && qubits ? '' : '当前回复没有可绘制的线路操作。';
    }

    const explanationList = byId('explanationSteps');
    const explanationSteps = Array.isArray(state.explanationSteps) ? state.explanationSteps : [];
    if (explanationList) {
      replace(explanationList, explanationSteps.map((step, index) => {
        const item = document.createElement('li');
        const operationIds = Array.isArray(step.operation_ids) ? step.operation_ids.map(String) : [];
        item.dataset.operationIds = operationIds.join(' ');
        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'explanation-step';
        trigger.append(textNode('span', String(index + 1).padStart(2, '0'), 'step-index'));
        const copy = document.createElement('span');
        const gates = Array.isArray(step.gates) ? step.gates.join(' · ') : '';
        copy.append(
          textNode('strong', step.title || `第 ${index + 1} 步`),
          gates ? textNode('span', gates, 'small-copy') : document.createTextNode(''),
          textNode('span', step.explanation || '', 'body-copy')
        );
        trigger.append(copy);
        const activate = () => activateOperations(operationIds);
        ['mouseenter', 'focus', 'click'].forEach(eventName => trigger.addEventListener(eventName, activate));
        item.append(trigger);
        return item;
      }));
      explanationList.hidden = explanationSteps.length === 0;
    }
    const explanationError = byId('explanationError');
    if (explanationError) {
      explanationError.hidden = explanationSteps.length > 0 || !state.currentQasm;
      explanationError.textContent = explanationSteps.length ? '' : '暂时没有逐步解释。';
    }
    if (Array.isArray(state.relatedOperationIds) && state.relatedOperationIds.length) {
      activateOperations(state.relatedOperationIds);
    }

    const validationCard = byId('validationCard');
    const validationIssues = byId('validationIssues');
    const validation = state.validation;
    // 第二轮 §9：校验必须绑定当前 qasmVersion，旧校验不得继续显示绿色。
    const validationCurrent = validation && validation.qasmVersion === state.qasmVersion;
    const vStatus = validation && (validation.status || (validation.valid ? 'valid' : 'invalid'));
    if (validationCard) {
      validationCard.hidden = !validation;
      const vLabel = vStatus === 'stale' ? '! 已修改，待检查'
        : vStatus === 'checking' ? '○ 正在重新检查…'
        : vStatus === 'valid' ? '✓ 已检查'
        : vStatus === 'invalid' ? '× 发现问题，线路暂时不能运行'
        : '校验状态未知';
      // 美化方案 §10：正常状态只是一行 inline status，不再是大 Card；
      // 具体 UI 层级由 .workspace-section 的去卡片化统一处理。
      validationCard.className = vStatus === 'valid' ? 'status status--success'
        : vStatus === 'stale' || vStatus === 'checking' ? 'status status--info'
        : 'status status--danger';
      validationCard.textContent = validation ? vLabel : '';
    }
    if (validationIssues) {
      const errors = validationCurrent && validation && Array.isArray(validation.errors) ? validation.errors : [];
      // 美化方案 §10：只有 invalid 时才展开——用轻量文字列表而不是一串徽章。
      const children = errors.map(error => textNode('p', error, 'issue-line'));
      if (children.length && state.repairProposal) {
        const jump = document.createElement('a');
        jump.href = '#repairSection';
        jump.className = 'inline-link';
        jump.textContent = '查看修复建议 ›';
        children.push(jump);
      }
      replace(validationIssues, children);
      validationIssues.hidden = children.length === 0;
    }
    const validationActions = byId('validationActions');
    if (validationActions) { replace(validationActions); validationActions.hidden = true; }

    const repairSection = byId('repairSection');
    const repairIssues = byId('repairIssues');
    const repairBefore = byId('repairBeforeCode');
    const repairAfter = byId('repairAfterCode');
    const repairStatus = byId('repairStatus');
    const applyRepair = byId('applyRepairBtn');
    const keepOriginal = byId('keepOriginalBtn');
    const proposal = state.repairProposal;
    if (repairSection) repairSection.hidden = !proposal;
    if (repairIssues) {
      // 美化方案 §14：错误定位在前，用纯文字而不是一串警告徽章。
      const issues = proposal ? (proposal.issues || []).map(issue => textNode('p', issue.message || issue, 'issue-line')) : [];
      replace(repairIssues, issues);
      repairIssues.hidden = issues.length === 0;
    }
    if (repairBefore) repairBefore.textContent = proposal?.before || '未能提取完整原代码';
    if (repairAfter) repairAfter.textContent = proposal?.proposedQasm || '';
    if (repairStatus) {
      repairStatus.textContent = state.repairApplying ? '正在使用真实 validator 检查修复建议…' : '';
      repairStatus.hidden = !state.repairApplying;
    }
    if (applyRepair) applyRepair.disabled = !proposal || state.repairApplying || Boolean(state.pendingRequest);
    if (keepOriginal) keepOriginal.disabled = !proposal || state.repairApplying;

    const qasmMeta = byId('qasmMeta');
    const qasmDisclosure = byId('qasmDisclosure');
    const qasmCode = byId('qasmCode');
    const adapterCode = byId('adapterCode');
    const adapterCodeTitle = byId('adapterCodeTitle');
    const adapterCodeMeta = byId('adapterCodeMeta');
    const selectedCodeTarget = targetForState(state);
    const selectedAdapterCode = state.transpiledArtifacts?.[selectedCodeTarget] || '';
    const qasmIsValidated = state.validation?.valid === true && state.validation?.qasmVersion === state.qasmVersion;
    [qasmCode, adapterCode].filter(Boolean).forEach(codePanel => {
      // Both the HTML standard and common translation extensions honour these
      // markers. Backend syntax must remain byte-for-byte code, never prose.
      codePanel.setAttribute('translate', 'no');
      codePanel.classList.add('notranslate');
    });
    if (qasmMeta) {
      qasmMeta.hidden = !state.currentQasm;
      qasmMeta.textContent = state.currentQasm ? '标准源码与后端转译产物分开展示；切换执行目标即可核对对应语法。' : '';
    }
    if (qasmDisclosure) qasmDisclosure.hidden = !state.currentQasm;
    if (qasmCode) qasmCode.textContent = state.currentQasm || '';
    if (adapterCodeTitle) adapterCodeTitle.textContent = `${LOCAL_BACKENDS[selectedCodeTarget]?.name.replace(' 本地模拟器', '') || selectedCodeTarget} adapter 代码`;
    if (adapterCodeMeta) adapterCodeMeta.textContent = `${ADAPTER_CODE_FORMATS[selectedCodeTarget] || '目标语法'} · 由服务端 adapter 从标准代码转译；运行时会重新校验和转译。`;
    if (adapterCode) adapterCode.textContent = selectedAdapterCode || (qasmIsValidated
      ? '正在调用 adapter 生成后端代码…'
      : '等待线路通过 adapter 校验。');

    const requirements = byId('backendRequirements');
    if (requirements) {
      // 任务书 §11 硬约束模型：backend_requirements 现在是 {hard_constraints, preferences}。
      const source = (state.backendRequirements && state.backendRequirements.hard_constraints) || {};
      const rows = [];
      if (source.min_qubits != null) rows.push(textNode('span', `${source.min_qubits}+ qubits`, 'status status--info'));
      if (source.backend_type === 'hardware') rows.push(textNode('span', '真机', 'status status--info'));
      if (source.backend_type === 'simulator') rows.push(textNode('span', '模拟器', 'status status--info'));
      if (source.free === true) rows.push(textNode('span', '免费', 'status status--info'));
      if (source.zero_queue === true) rows.push(textNode('span', '零排队', 'status status--info'));
      if (source.account_required === false) rows.push(textNode('span', '无需账号', 'status status--info'));
      replace(requirements, rows);
      requirements.hidden = rows.length === 0;
    }
    const backend = byId('backendRecommendation');
    if (backend) {
      // 美化方案 §15: 推荐后端不再是"大 Card → 蓝 Card → 内部小 Card"，
      // 改成 标题 + 一行描述 + "为什么推荐"（纯文字 ✓ 列表）+ divider + 未满足项。
      const recommendation = state.recommendedBackend || state.backend;
      const rows = [];
      if (recommendation) {
        rows.push(textNode('strong', recommendation.name || recommendation.id, 'backend-name'));
        const kindLabel = recommendation.type === 'hardware' || recommendation.kind === 'hardware' || recommendation.kind === 'qpu' ? '真机' : '模拟器';
        const costLabel = recommendation.cost ? String(recommendation.cost) : null;
        const queueLabel = recommendation.queue === 'none' ? '零排队' : (recommendation.queue || null);
        rows.push(textNode('p', [kindLabel, costLabel, queueLabel].filter(Boolean).join(' · '), 'body-copy'));
        if ((recommendation.matchedReasons || []).length) {
          rows.push(textNode('p', '为什么推荐', 'section-label'));
          (recommendation.matchedReasons || []).forEach(reason => rows.push(textNode('p', `✓ ${reason}`, 'reason-line reason-line--good')));
        }
        rows.push(textNode('p', recommendation.runnableLocally
          ? '可通过本项目直接运行。'
          : '此后端不能通过当前本地 adapter 直接运行。', 'reason-line' + (recommendation.runnableLocally ? ' reason-line--good' : ' reason-line--warn')));
        if ((recommendation.unmetRequirements || []).length) {
          const divider = document.createElement('hr');
          divider.className = 'panel-divider';
          rows.push(divider);
          rows.push(textNode('p', state.matchStatus === 'no_exact_match' ? '没有环境能够全部满足你的要求。' : '', 'body-copy'));
          rows.push(textNode('p', '未满足', 'section-label'));
          (recommendation.unmetRequirements || []).forEach(reason => rows.push(textNode('p', `× ${reason}`, 'reason-line reason-line--warn')));
        }
      } else rows.push(textNode('p', '尚未选择运行后端。', 'small-copy'));
      replace(backend, rows);
      backend.hidden = false;
    }
    const recommendedCard = byId('recommendedBackendCard');
    if (recommendedCard) recommendedCard.hidden = !(state.recommendedBackend || state.backend);
    const recommended = state.recommendedBackend || state.backend;
    const backendTitle = byId('backendTitle');
    if (backendTitle) {
      backendTitle.textContent = recommended && ['qpu', 'hardware'].includes(recommended.kind || recommended.type)
        ? '推荐真实运行环境' : '推荐运行环境';
    }
    const cannotDirectRun = Boolean(recommended && recommended.runnableLocally !== true &&
      ['qpu', 'hardware'].includes(recommended.kind || recommended.type));
    const directWarning = byId('backendDirectRunWarning');
    const hardwareGuide = byId('hardwareGuide');
    if (directWarning) directWarning.hidden = !cannotDirectRun;
    if (hardwareGuide) hardwareGuide.hidden = !cannotDirectRun;
    const run = byId('runSettings');
    const canRun = Boolean(state.currentQasm && state.validation?.valid && state.validation?.qasmVersion === state.qasmVersion);
    const hasMeasurement = circuitHasMeasurement(state);
    const previewTarget = targetForState(state);
    if (run) {
      const controls = [];
      if (canRun) {
        const targetLabel = textNode('label', '执行目标', 'small-copy');
        const targetSelect = document.createElement('select');
        targetSelect.className = 'form-control';
        targetSelect.setAttribute('aria-label', '执行目标');
        [['spinq', 'SpinQ'], ['originq', 'OriginQ'], ['braket', 'Braket']].forEach(([value, label]) => {
          const option = document.createElement('option');
          option.value = value; option.textContent = label; option.selected = value === previewTarget;
          targetSelect.append(option);
        });
        targetSelect.addEventListener('change', () => {
          if (typeof dispatchAction === 'function') {
            dispatchAction({type: 'SELECT_EXECUTION_TARGET', target: targetSelect.value});
          }
        });
        const shotsLabel = textNode('label', 'Shots', 'small-copy');
        const shotsInput = document.createElement('input');
        shotsInput.className = 'form-control';
        shotsInput.type = 'number'; shotsInput.min = '1'; shotsInput.max = '10000'; shotsInput.step = '1';
        shotsInput.value = String(state.shots || 1024); shotsInput.setAttribute('aria-label', 'Shots');
        const runButtonLabel = !hasMeasurement
          ? '加入测量后可预览结果'
          : (state.runStatus?.stage === 'error' ? '重新进行本地预览' : '使用本地模拟器预览 →');
        const runButton = textNode('button', runButtonLabel, 'btn primary');
        runButton.type = 'button';
        const busy = ['checking', 'executing', 'reading'].includes(state.runStatus?.stage);
        runButton.disabled = busy || !hasMeasurement;
        runButton.addEventListener('click', () => document.dispatchEvent(new CustomEvent('workspace:run', {
          detail: {target: targetSelect.value, shots: Number(shotsInput.value)}
        })));
        controls.push(targetLabel, targetSelect, shotsLabel, shotsInput, runButton);
        if (!hasMeasurement) {
          controls.push(textNode('p', '当前电路检查通过，但没有测量操作，所以不会产生可视化结果。', 'small-copy run-measurement-hint'));
        }
      } else controls.push(textNode('p', '线路通过检查后才可运行。', 'small-copy'));
      replace(run, controls);
      run.hidden = false;
    }
    const execution = state.executionBackend || LOCAL_BACKENDS[previewTarget];
    const executionName = byId('executionBackendName');
    const executionSummary = byId('executionBackendSummary');
    const executionTense = executionSummary?.querySelector('.small-copy');
    if (executionName) executionName.textContent = execution?.name || '';
    if (executionTense) {
      executionTense.textContent = state.runStatus?.stage === 'complete'
        ? '本次预览实际使用' : ['checking', 'executing', 'reading'].includes(state.runStatus?.stage)
          ? '本次预览正在使用' : '本次预览将使用';
    }
    if (executionSummary) executionSummary.hidden = !canRun || !hasMeasurement;
    const progress = byId('runProgress');
    if (progress) {
      const stageText = {checking: '正在检查线路…', executing: '正在执行线路…', reading: '正在读取结果…', complete: '运行完成'};
      progress.textContent = stageText[state.runStatus?.stage] || '';
      progress.hidden = !stageText[state.runStatus?.stage];
    }
    const runError = byId('runError');
    if (runError) {
      runError.textContent = state.runStatus?.error || '';
      runError.hidden = !state.runStatus?.error;
    }

    const resultSection = byId('resultSection');
    const resultEmptyState = byId('resultEmptyState');
    const resultChart = byId('resultChart');
    const resultConclusion = byId('resultConclusion');
    const measured = state.result && !state.result.stale && state.result.artifactRevision === state.currentRevision;
    // 第二轮 §4：单一归一化结果，柱高/count/百分比全部从这里派生。
    const visibleEntries = (measured && typeof normalizeCounts === 'function'
      ? normalizeCounts(state.result.counts)
      : []).slice(0, 16);
    if (resultChart) {
      resultChart.setAttribute('role', 'list');
      const maximum = Math.max(1, ...visibleEntries.map(item => item.count));
      const bars = visibleEntries.map(item => {
        const {bitstring: label, count, probability} = item;
        const wrapper = document.createElement('div');
        wrapper.className = 'result-bar-item';
        wrapper.setAttribute('role', 'listitem');
        const fill = document.createElement('div');
        fill.className = 'result-bar-fill';
        // 用 count/max 保证最高柱恒为 100%、比值正确（§4 的 3:1 要求）。
        fill.style.height = `${Math.max(3, Math.round(count / maximum * 88))}%`;
        wrapper.append(
          fill,
          textNode('strong', label),
          textNode('span', `${count}（${Math.round(probability * 100)}%）`, 'small-copy')
        );
        return wrapper;
      });
      replace(resultChart, bars);
      resultChart.style.gridTemplateColumns = visibleEntries.length ? `repeat(${visibleEntries.length}, minmax(42px, 1fr))` : '';
      resultChart.hidden = visibleEntries.length === 0;
    }
    if (resultConclusion) {
      // 美化方案 §17: 结论优先——先给一句直接结论，再展示柱状图细节。
      const leader = visibleEntries[0];
      const runner = visibleEntries[1];
      let headline = '';
      if (leader) {
        const leaderPct = Math.round(leader.probability * 100);
        const closeToEven = runner && Math.abs(leader.probability - runner.probability) <= 0.05;
        headline = closeToEven
          ? `结果接近 ${leaderPct} / ${Math.round(runner.probability * 100)}`
          : `${leader.bitstring} 出现次数最高，占 ${leaderPct}%`;
      }
      resultConclusion.textContent = leader ? headline : '';
      resultConclusion.hidden = !leader;
    }
    const source = state.resultSource;
    const resultSourceName = byId('resultSourceName');
    const resultSourceDisclaimer = byId('resultSourceDisclaimer');
    const resultSourceBanner = byId('resultSourceBanner');
    if (resultSourceName) resultSourceName.textContent = source ? `ⓘ 本次结果来自 ${source.name}，是模拟结果，不是真机实验。` : '';
    if (resultSourceDisclaimer) resultSourceDisclaimer.textContent = source
      ? `本次共运行 ${state.result?.shots ?? ''} shots，可用于检查线路逻辑，但不能反映真实硬件噪声和误差。` : '';
    if (resultSourceBanner) resultSourceBanner.hidden = !(source && visibleEntries.length);
    const showMeasurementEmptyState = Boolean(state.currentQasm && canRun && !hasMeasurement);
    if (resultEmptyState) resultEmptyState.hidden = !showMeasurementEmptyState;
    if (resultSection) resultSection.hidden = visibleEntries.length === 0 && !showMeasurementEmptyState;
  }

  function setupHome() {
    const stateApi = window.QuantumWorkspaceState;
    if (!stateApi) { setupHomePhase2(); return; }
    const form = document.getElementById('agentStartForm');
    const input = document.getElementById('agentInput');
    const button = document.getElementById('agentBtn');
    const errorBox = document.getElementById('agentInputError');
    const followUpForm = document.getElementById('followUpForm');
    const followUpInput = document.getElementById('followUpInput');
    const followUpButton = document.getElementById('followUpBtn');
    const followUpError = document.getElementById('followUpError');
    const workspace = document.getElementById('agentWorkspace');
    if (!form || !input || !button || !errorBox || !workspace) return;

    const store = stateApi.createStore();
    // Errors are transient diagnostics, not task artifacts. Do not resurrect a
    // previous failed request/run after the user reloads the workspace.
    store.dispatch({type: 'CLEAR_ERRORS'});
    let controller = null;
    let runController = null;
    let repairController = null;
    let artifactController = null;
    let artifactRequestKey = null;
    let sessionId = sessionStorage.getItem('qh_session_id');
    if (!sessionId) {
      sessionId = stateApi.createId('session');
      sessionStorage.setItem('qh_session_id', sessionId);
    }
    const homeSections = [
      document.querySelector('.home-hero'),
      document.getElementById('inspirationTitle')?.closest('section'),
      document.querySelector('.beginner-banner'),
      document.querySelector('.direct')
    ].filter(Boolean);
    const workspaceNav = document.getElementById('workspaceNav');
    const topMeta = document.querySelector('.top-meta');
    const continueTaskBtn = document.getElementById('continueTaskBtn');
    const abortAll = () => {
      [controller, runController, repairController, artifactController].forEach(activeController => activeController?.abort());
      controller = null; runController = null; repairController = null; artifactController = null;
      artifactRequestKey = null;
    };
    const setHistoryView = (view, mode = 'push') => {
      history[mode === 'replace' ? 'replaceState' : 'pushState'](
        {qhView: view}, '', view === 'workspace' ? '#workspace' : location.pathname + location.search
      );
    };
    const setInlineError = (node, message) => {
      if (!node) return;
      node.textContent = message || '';
      node.hidden = !message;
    };
    const ensureTranspiledArtifacts = state => {
      const validationCurrent = state.validation?.valid === true && state.validation?.qasmVersion === state.qasmVersion;
      if (!state.currentQasm || !validationCurrent) return;
      const complete = Object.keys(LOCAL_BACKENDS).every(target =>
        typeof state.transpiledArtifacts?.[target] === 'string' && state.transpiledArtifacts[target].trim()
      );
      if (complete) {
        artifactRequestKey = null;
        return;
      }
      const requestKey = `${state.qasmVersion}:${state.currentQasm}`;
      if (artifactRequestKey === requestKey) return;
      artifactController?.abort();
      artifactController = new AbortController();
      artifactRequestKey = requestKey;
      const qasm = state.currentQasm;
      const qasmVersion = state.qasmVersion;
      api('/api/check', {qasm}, {signal: artifactController.signal})
        .then(checked => {
          store.dispatch({type: 'SET_TRANSPILED_ARTIFACTS', payload: {
            qasm,
            qasmVersion,
            artifacts: checked.transpiled || {}
          }});
        })
        .catch(error => {
          if (error.name === 'AbortError') return;
          artifactRequestKey = null;
          const codePanel = byId('adapterCode');
          if (codePanel && store.getState().currentQasm === qasm) {
            codePanel.textContent = `adapter 转译失败：${error.message}`;
          }
        });
    };
    const showState = state => {
      const active = state.view === 'workspace' && stateApi.hasTask(state);
      const shell = document.querySelector('.shell');
      if (shell) {
        shell.classList.toggle('workspace-shell', active);
        shell.classList.toggle('app-shell', !active);
      }
      homeSections.forEach(section => { section.hidden = active; });
      workspace.hidden = !active;
      if (workspaceNav) workspaceNav.hidden = !active;
      if (topMeta) topMeta.hidden = active;
      if (continueTaskBtn) continueTaskBtn.hidden = active || !stateApi.hasTask(state);
      if (active) {
        renderWorkspace(state, action => store.dispatch(action), stateApi.normalizeCounts);
        ensureTranspiledArtifacts(state);
      }
      button.disabled = Boolean(state.pendingRequest);
      button.textContent = state.pendingRequest ? '正在分析…' : '发送 →';
      if (followUpButton) {
        followUpButton.disabled = Boolean(state.pendingRequest);
        followUpButton.textContent = state.pendingRequest ? '正在分析…' : '发送 →';
      }
    };
    store.subscribe(showState);
    showState(store.getState());
    setHistoryView(store.getState().view, 'replace');
    const goHome = () => { store.dispatch({type: 'GO_HOME'}); setHistoryView('home'); };
    document.getElementById('homeLogo')?.addEventListener('click', event => { event.preventDefault(); goHome(); });
    document.getElementById('backHomeBtn')?.addEventListener('click', goHome);
    continueTaskBtn?.addEventListener('click', () => {
      store.dispatch({type: 'CONTINUE_TASK'});
      if (store.getState().view === 'workspace') setHistoryView('workspace');
    });
    document.getElementById('newTaskBtn')?.addEventListener('click', () => {
      abortAll();
      store.dispatch({type: 'NEW_TASK'});
      setHistoryView('home');
      input.value = '';
      input.focus({preventScroll: true});
    });
    addEventListener('popstate', event => {
      const view = stateApi.viewFromHistoryState(event.state, location.hash === '#workspace' ? 'workspace' : 'home');
      store.dispatch({type: 'SET_VIEW', view});
    });

    // 首页四张场景卡选中后，把 scenario_id 一并带给后端（任务书 §28/§29）。
    let pendingScenarioId = null;

    // 第二轮 §6：面板名 -> DOM id，用于响应 action 的高亮与滚动。
    const PANEL_IDS = {current_task: 'taskFields', circuit: 'circuitCanvas', validation: 'validationCard'};
    function highlightUpdatedPanels(action) {
      if (!action || !Array.isArray(action.updated_panels)) return;
      action.updated_panels.forEach(name => {
        const el = byId(PANEL_IDS[name]);
        if (!el) return;
        el.classList.remove('is-updated');
        void el.offsetWidth;  // 重新触发过渡，保证连续两次更新也能闪一下
        el.classList.add('is-updated');
        setTimeout(() => el.classList.remove('is-updated'), 900);
      });
      const primary = byId(PANEL_IDS[action.primary_panel]);
      if (primary) primary.scrollIntoView({behavior: 'smooth', block: 'center'});
    }

    const submitPrompt = async (prompt, errorNode) => {
      const value = String(prompt || '').trim();
      if (!value) { setInlineError(errorNode, '请先描述你希望完成的量子任务。'); return; }
      setInlineError(errorNode, '');
      if (controller) controller.abort();
      if (runController) {
        runController.abort();
        store.dispatch({type: 'CANCEL_RUN', message: '新的对话已取消本次本地预览，可以稍后重新运行。'});
      }
      controller = new AbortController();
      const before = store.getState();
      const requestId = stateApi.createId('request');
      const taskId = before.taskId || stateApi.createId('task');
      const taskContext = before.task ? {
        type: before.task.type || null,
        goal: before.task.goal || null,
        qubits: before.task.qubits ?? null,
        measurement: before.task.measurement || null
      } : null;
      const resultContext = before.result && !before.result.stale ? {
        counts: before.result.counts,
        shots: before.result.shots
      } : null;
      const wasHome = before.view !== 'workspace';
      store.dispatch({type: 'BEGIN_REQUEST', payload: {requestId, taskId, prompt: value}});
      if (wasHome) setHistoryView('workspace');
      const pending = store.getState().pendingRequest;
      try {
        const payload = await api('/api/chat', {
          prompt: value,
          schema_version: '1.0',
          request_id: requestId,
          session_id: sessionId,
          task_id: taskId,
          base_revision: pending.baseRevision,
          scenario_id: pendingScenarioId || undefined,
          context: {
            task: taskContext,
            current_qasm: before.currentQasm || null,
            result: resultContext
          }
        }, {signal: controller.signal});
        pendingScenarioId = null;
        const metadataPassed = payload.schema_version === '1.0' && payload.request_id === requestId &&
          payload.session_id === sessionId && payload.task_id === taskId &&
          payload.base_revision === pending.baseRevision;
        const circuitPassed = payload.kind !== 'qasm' || payload.validation?.valid === true;
        if (!metadataPassed || !circuitPassed) throw new Error('响应未通过任务版本或线路校验，已阻止覆盖当前任务。');
        const isRepair = payload.kind === 'qasm' && payload.intent === 'repair_circuit';
        const isGeneration = payload.kind === 'qasm' && !isRepair;
        const isBackend = payload.kind === 'backend';
        const isExplanation = payload.kind === 'explanation' && payload.intent === 'explain_circuit';
        // 任务书 §7/§27/§8: concept answers, clarifying questions and scenario
        // explanations all arrive as prose and leave the circuit untouched.
        const isAssistantText = payload.kind === 'qa' || payload.kind === 'clarify' || payload.kind === 'scenario';
        if (!isRepair && !isGeneration && !isBackend && !isExplanation && !isAssistantText) {
          throw new Error('Agent 返回了当前工作台无法处理的响应。');
        }
        const recommended = payload.backend_recommendation;
        const backendPatch = isBackend ? {
          id: payload.answer,
          ...payload.backend,
          matchedReasons: Array.isArray(payload.matched_reasons) ? payload.matched_reasons : [],
          unmetRequirements: Array.isArray(payload.unmet_requirements) ? payload.unmet_requirements : [],
          runnableLocally: payload.runnable_locally === true,
          adapterTarget: payload.adapter_target || null
        } : recommended ? {
          id: recommended.id,
          ...recommended.backend,
          matchedReasons: ['满足当前线路规模', '免费', '无需排队'],
          unmetRequirements: [],
          runnableLocally: recommended.runnable_locally === true,
          adapterTarget: recommended.runnable_locally ? recommended.backend?.platform : null
        } : null;
        const repairProposal = isRepair ? {
          before: payload.repair?.before || null,
          proposedQasm: payload.repair?.proposed_qasm || payload.qasm,
          issues: Array.isArray(payload.repair?.issues) ? payload.repair.issues : [],
          circuit: payload.circuit,
          validation: payload.validation,
          explanationSteps: Array.isArray(payload.explanation_steps) ? payload.explanation_steps : [],
          task: payload.task,
          backend: backendPatch
        } : null;
        // Problem 1 修复：goal 只从【本次请求】推断，绝不用 before.task.goal 兜底，
        // 否则 Bell→GHZ 时旧 goal 会残留。task 整体 replace，不做脏 merge。
        const inferredGoal = /\bghz\b/i.test(value)
          ? 'GHZ State'
          : (/贝尔|\bbell\b/i.test(value) ? 'Bell State' : null);
        const responseTask = payload.task ? {...payload.task, goal: payload.task.goal || inferredGoal} : null;
        store.dispatch({
          type: 'APPLY_RESPONSE',
          payload: {
            requestId,
            taskId,
            baseRevision: pending.baseRevision,
            commitArtifact: isGeneration,
            assistantText: isAssistantText
              ? (payload.assistant_message || payload.answer || '请参考上面的说明。')
              : isExplanation
              ? (payload.assistant_message || payload.answer || '这是当前线路中相关操作的说明。')
              : isRepair
              ? '我找到了可修复的问题。请确认建议，应用前不会覆盖原线路。'
              : isBackend
                ? `我已根据官方能力表推荐 ${payload.backend.name}。`
                : `我已生成 ${payload.summary.qubits} 比特线路，并通过 adapter 校验。${payload.assumptions?.length ? '\n\n我做了这些默认假设：' + payload.assumptions.map(a => `\n· ${a}`).join('') : ''}`,
            patch: isAssistantText ? {
              relatedOperationIds: [],
              repairProposal: null,
              // 第三轮 §14/§15：诊断/校验外部代码 → 进入 inspection 模式，展示被检查的代码。
              workspaceMode: payload.workspace_mode || 'task',
              inspectedQasm: payload.inspected_qasm || null,
              diagnostics: Array.isArray(payload.diagnosis?.issues) ? payload.diagnosis.issues : []
            } : isExplanation ? {
              relatedOperationIds: Array.isArray(payload.related_operation_ids) ? payload.related_operation_ids : []
            } : isRepair ? {
              intent: payload.intent,
              repairProposal
            } : isBackend ? {
              intent: 'select_backend',
              backendRequirements: payload.backend_requirements || null,
              backend: backendPatch,
              matchStatus: payload.match_status || 'unverified'
            } : {
              intent: payload.intent || null,
              task: responseTask || null,
              currentQasm: payload.qasm,
              transpiledArtifacts: payload.transpiled || {},
              circuit: payload.circuit || null,
              explanationSteps: Array.isArray(payload.explanation_steps) ? payload.explanation_steps : [],
              relatedOperationIds: [],
              validation: payload.validation || null,
              repairProposal: null,
              backendRequirements: null,
              backend: backendPatch,
              matchStatus: backendPatch ? 'full' : null,
              runStatus: null,
              result: null,
              workspaceMode: 'task',
              inspectedQasm: null,
              diagnostics: []
            }
          }
        });
        if (payload.action) highlightUpdatedPanels(payload.action);
        if (errorNode === followUpError && followUpInput) followUpInput.value = '';
        else input.value = '';
      } catch (error) {
        pendingScenarioId = null;
        if (error.name !== 'AbortError') {
          store.dispatch({type: 'REQUEST_ERROR', payload: {
            requestId, taskId, baseRevision: pending.baseRevision,
            message: error.code === 'LLM_DISABLED' ? '模型服务尚未配置。点右上角「配置模型」填写，或直接导入 OpenQASM 线路。' : error.message,
            developerDetails: error.developerDetails || null
          }});
        }
      }
    };

    document.querySelectorAll('[data-prompt]').forEach(item => {
      item.addEventListener('click', () => {
        input.value = item.dataset.prompt || '';
        pendingScenarioId = item.dataset.scenarioId || null;
        setInlineError(errorBox, '');
        input.focus({preventScroll: true});
        form.scrollIntoView({behavior: 'smooth', block: 'center'});
      });
    });
    const bindComposer = (composer, composerInput, composerError) => {
      if (!composer || !composerInput) return;
      composerInput.addEventListener('input', () => setInlineError(composerError, ''));
      composerInput.addEventListener('keydown', event => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          composer.requestSubmit();
        }
      });
      composer.addEventListener('submit', event => {
        event.preventDefault();
        submitPrompt(composerInput.value, composerError);
      });
    };
    bindComposer(form, input, errorBox);
    bindComposer(followUpForm, followUpInput, followUpError);

    const copyButton = document.getElementById('copyQasmBtn');
    if (copyButton) copyButton.addEventListener('click', async () => {
      const qasm = store.getState().currentQasm;
      if (!qasm) return;
      try {
        await navigator.clipboard.writeText(qasm);
        copyButton.textContent = '已复制';
        setTimeout(() => { copyButton.textContent = '复制标准代码'; }, 1600);
      } catch (_) { notice('复制失败，请手动选择代码。'); }
    });
    const copyAdapterButton = document.getElementById('copyAdapterCodeBtn');
    if (copyAdapterButton) copyAdapterButton.addEventListener('click', async () => {
      const state = store.getState();
      const target = targetForState(state);
      const code = state.transpiledArtifacts?.[target];
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code);
        copyAdapterButton.textContent = '已复制';
        setTimeout(() => { copyAdapterButton.textContent = '复制后端代码'; }, 1600);
      } catch (_) { notice('复制失败，请手动选择代码。'); }
    });
    document.addEventListener('workspace:discard-repair', () => {
      store.dispatch({type: 'DISCARD_REPAIR'});
    });
    document.getElementById('applyRepairBtn')?.addEventListener('click', () =>
      document.dispatchEvent(new CustomEvent('workspace:apply-repair'))
    );
    document.getElementById('keepOriginalBtn')?.addEventListener('click', () =>
      document.dispatchEvent(new CustomEvent('workspace:discard-repair'))
    );
    document.addEventListener('workspace:apply-repair', async () => {
      let before = store.getState();
      if (before.pendingRequest) {
        if (controller) controller.abort();
        store.dispatch({type: 'CANCEL_PENDING'});
        before = store.getState();
      }
      const proposal = before.repairProposal;
      if (!proposal || !proposal.proposedQasm || before.repairApplying) return;
      store.dispatch({type: 'REPAIR_APPLY_STARTED'});
      if (!store.getState().repairApplying) return;
      if (repairController) repairController.abort();
      repairController = new AbortController();
      const baseRevision = before.currentRevision;
      try {
        const checked = await api('/api/check', {qasm: proposal.proposedQasm}, {signal: repairController.signal});
        const latest = store.getState();
        if (latest.currentRevision !== baseRevision || latest.repairProposal !== proposal || !latest.repairApplying) {
          throw new Error('任务已经更新，这份修复建议不再适用。');
        }
        store.dispatch({type: 'APPLY_REPAIR', payload: {
          baseRevision,
          patch: {
            intent: 'repair_circuit',
            task: proposal.task || latest.task,
            currentQasm: proposal.proposedQasm,
            circuit: proposal.circuit || latest.circuit,
            explanationSteps: proposal.explanationSteps || [],
            relatedOperationIds: [],
            validation: {
              valid: true,
              errors: [],
              source: 'api/check',
              targets: Object.keys(checked.transpiled || {})
            },
            transpiledArtifacts: checked.transpiled || {},
            backend: proposal.backend || latest.backend,
            matchStatus: proposal.backend ? 'full' : latest.matchStatus,
            runStatus: null,
            result: null
          }
        }});
      } catch (error) {
        if (error.name !== 'AbortError') {
          store.dispatch({type: 'REPAIR_APPLY_FAILED', message: `修复未应用：${error.message}`});
        }
      }
    });
    document.addEventListener('workspace:run', async event => {
      const target = event.detail?.target;
      const shots = event.detail?.shots;
      if (!['spinq', 'originq', 'braket'].includes(target) || !Number.isInteger(shots) || shots < 1 || shots > 10000) {
        store.dispatch({type: 'SET_ERROR', message: '运行目标无效，或 shots 不是 1 到 10000 的整数。'});
        return;
      }
      const before = store.getState();
      if (!before.currentQasm || !before.validation?.valid || !before.taskId) return;
      if (!circuitHasMeasurement(before)) return;
      if (runController) runController.abort();
      runController = new AbortController();
      const runId = stateApi.createId('run');
      const taskId = before.taskId;
      const revision = before.currentRevision;
      const qasm = before.currentQasm;
      store.dispatch({type: 'RUN_STARTED', payload: {runId, taskId, revision, target, shots}});
      const isCurrentRun = () => {
        const current = store.getState();
        return current.taskId === taskId && current.currentRevision === revision && current.runStatus?.runId === runId;
      };
      try {
        await api('/api/check', {qasm}, {signal: runController.signal});
        if (!isCurrentRun()) return;
        store.dispatch({type: 'RUN_STAGE', payload: {runId, stage: 'executing'}});
        const payload = await api('/api/run', {qasm, target, shots}, {signal: runController.signal});
        if (!isCurrentRun()) return;
        store.dispatch({type: 'RUN_STAGE', payload: {runId, stage: 'reading'}});
        const result = payload.result && typeof payload.result === 'object' ? payload.result : {};
        store.dispatch({type: 'RUN_SUCCESS', payload: {
          runId,
          result: {...result, target: payload.target || target, shots: result.shots || shots}
        }});
      } catch (error) {
        if (error.name !== 'AbortError' && isCurrentRun()) {
          store.dispatch({type: 'RUN_ERROR', payload: {runId, message: error.message}});
        }
      }
    });
    if (new URLSearchParams(location.search).get('start') === 'agent' && !store.getState().taskId) {
      input.focus({preventScroll: true});
      form.scrollIntoView({behavior: 'smooth', block: 'center'});
    }
  }

  async function setupAgent() {
    const button = document.getElementById('agentBtn');
    const input = document.getElementById('agentInput');
    const output = document.getElementById('agentOutput');
    const result = document.getElementById('agentResult');
    const resultTitle = document.getElementById('agentResultTitle');
    const resultMeta = document.getElementById('agentResultMeta');
    const next = document.getElementById('agentNext');
    if (!button || !input || !output || !result || !next) return;
    document.querySelectorAll('[data-agent-example]').forEach(example => {
      example.onclick = () => { input.value = example.dataset.agentExample; input.focus(); };
    });
    button.onclick = async () => {
      const prompt = input.value.trim();
      if (!prompt) { notice('请先描述要生成、修复或选择后端的任务。'); return; }
      clearAgentRunState();
      localStorage.setItem('qh_agent_prompt', prompt);
      button.disabled = true;
      button.textContent = 'Agent 正在分析';
      result.classList.remove('show');
      next.hidden = true;
      try {
        const payload = await api('/api/chat', {prompt});
        output.textContent = payload.answer;
        if (payload.kind === 'qasm') {
          localStorage.setItem('qh_qasm', payload.qasm);
          localStorage.setItem('qh_last_check', JSON.stringify({ok: true, summary: payload.summary}));
          resultTitle.textContent = 'Agent 已生成并通过 adapter 校验';
          resultMeta.textContent = `${payload.summary.qubits} 个量子比特 · ${summaryOperationCount(payload.summary)} 个操作`;
          next.href = 'circuit-check.html';
          next.textContent = '检查并运行这条线路 →';
          next.hidden = false;
        } else if (payload.kind === 'backend') {
          const backend = payload.backend;
          resultTitle.textContent = backend.name;
          resultMeta.textContent = `${payload.answer} · ${backend.max_qubits} 比特 · ${backend.queue === 'none' ? '无需排队' : '可能排队'} · ${backend.cost}`;
          if (payload.adapter_target && backend.kind === 'simulator') {
            const localName = {spinq: 'SpinQ 本地模拟器', originq: 'OriginQ 本地模拟器', braket: 'Braket 本地模拟器'}[payload.adapter_target];
            localStorage.setItem('qh_target', payload.adapter_target);
            localStorage.setItem('qh_backend', localName);
          }
        } else {
          resultTitle.textContent = 'Agent 返回了说明';
          resultMeta.textContent = '请根据回复补充任务信息后重试。';
        }
        result.classList.add('show');
        result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      } catch (error) {
        output.textContent = '';
        if (error.code === 'LLM_DISABLED' && error.status === 503) {
          notice('Agent 尚未启用。请按 README 配置 LOOMQ_LLM_* 并设置 QUANTUMHELPER_ENABLE_LLM=1。');
        } else {
          notice(error.message);
        }
      } finally {
        button.disabled = false;
        button.textContent = '交给 Agent →';
      }
    };
  }
  function setProgress(percent, text) {
    const fill = document.getElementById('fill');
    const pct = document.getElementById('pct');
    const status = document.getElementById('status');
    if (fill) fill.style.width = `${percent}%`;
    if (pct) pct.textContent = `${percent}%`;
    if (status) status.textContent = text;
  }

  function finishSteps() {
    ['s1', 's2', 's3'].forEach(id => {
      const step = document.getElementById(id);
      if (step) { step.classList.remove('active'); step.classList.add('done'); }
    });
  }

  function bindRun(qasmProvider, storageKey, resultPage) {
    const button = document.getElementById('runBtn');
    const link = document.getElementById('resultLink');
    const backend = document.getElementById('backend');
    if (!button) return;
    if (backend) backend.textContent = backendName();
    let shotsInput = document.getElementById('qh-shots');
    const shotsLabel = [...document.querySelectorAll('.summary-item')].find(item => item.querySelector('.summary-name')?.textContent.trim() === 'shots');
    if (shotsLabel) {
      const value = shotsLabel.querySelector('.summary-value');
      if (value) {
        shotsInput = document.createElement('input');
        shotsInput.id = 'qh-shots'; shotsInput.type = 'number'; shotsInput.min = '1'; shotsInput.max = '10000'; shotsInput.step = '1';
        shotsInput.value = localStorage.getItem('qh_shots') || '1024';
        shotsInput.setAttribute('aria-label', 'shots');
        shotsInput.style.cssText = 'width:92px;padding:7px 9px;border:1px solid rgba(25,26,30,.12);border-radius:9px;background:#fff;text-align:right';
        value.replaceWith(shotsInput);
      }
    }
    button.onclick = async () => {
      const qasm = qasmProvider();
      if (!qasm) { notice('没有可运行的 QASM，请返回上一步生成或导入线路。'); return; }
      const shots = Number(shotsInput?.value || 1024);
      if (!Number.isInteger(shots) || shots < 1 || shots > 10000) { notice('shots 必须是 1 到 10000 的整数。'); return; }
      localStorage.setItem('qh_shots', String(shots));
      button.disabled = true;
      button.textContent = 'adapter 正在运行';
      setProgress(18, '正在校验线路');
      try {
        const checked = await api('/api/check', {qasm});
        localStorage.setItem('qh_last_check', JSON.stringify(checked));
        setProgress(62, `正在 ${backendName()} 执行`);
        const payload = await api('/api/run', {qasm, target: target(), shots});
        localStorage.setItem(storageKey, JSON.stringify(payload));
        finishSteps();
        setProgress(100, '真实运行完成');
        button.textContent = '运行完成';
        if (link) { link.classList.remove('disabled'); link.href = resultPage; }
        notice('adapter 已返回真实测量结果。', 'ok');
      } catch (error) {
        button.disabled = false;
        button.textContent = '重新运行';
        setProgress(0, '运行失败');
        notice(error.message);
      }
    };
  }

  function renderResult(storageKey) {
    const chart = document.querySelector('.chart');
    const clearResult = message => {
      if (chart) {
        chart.replaceChildren();
        chart.style.gridTemplateColumns = '1fr';
        const empty = document.createElement('p');
        empty.className = 'status status--warning';
        empty.textContent = message;
        chart.append(empty);
      }
      document.querySelectorAll('.reading').forEach(node => node.replaceChildren());
      ['meaning', 'resultTitle', 'typeText'].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.textContent = '';
      });
      document.querySelectorAll('.summary-item').forEach(item => {
        const name = item.querySelector('.summary-name');
        const value = item.querySelector('.summary-value');
        if (name && value && ['shots', '状态'].includes(name.textContent.trim())) value.textContent = '—';
      });
      notice(message);
    };
    const raw = localStorage.getItem(storageKey);
    if (!raw) { clearResult('还没有运行结果，请先返回运行页。'); return; }
    let payload;
    try { payload = JSON.parse(raw); } catch (_) { clearResult('本地结果已损坏，请重新运行。'); return; }
    const result = payload.result || {};
    const entries = Object.entries(result.counts || {})
      .filter(([label, count]) => typeof label === 'string' && Number.isFinite(Number(count)) && Number(count) >= 0)
      .sort((a, b) => a[0].localeCompare(b[0]));
    if (!chart || !entries.length) { clearResult('adapter 没有返回可展示的 counts。'); return; }
    const maximum = Math.max(...entries.map(([, count]) => Number(count)), 1);
    chart.style.gridTemplateColumns = `repeat(${entries.length},minmax(42px,1fr))`;
    chart.replaceChildren(...entries.map(([label, count]) => {
      const height = Math.max(3, Math.round(Number(count) / maximum * 88));
      const wrapper = document.createElement('div');
      wrapper.className = 'barwrap';
      wrapper.title = `${label}: ${count}`;
      const bar = document.createElement('div');
      bar.className = Number(count) >= maximum * .85 ? 'bar major' : 'bar';
      bar.style.height = `${height}%`;
      const caption = document.createElement('span');
      caption.className = 'lab';
      caption.append(document.createTextNode(label), document.createElement('br'), document.createTextNode(String(count)));
      wrapper.append(bar, caption);
      return wrapper;
    }));
    document.querySelectorAll('.section-title').forEach(title => {
      if (/次|结果|摘要/.test(title.textContent)) title.textContent = `${result.shots} 次运行后的真实结果`;
    });
    document.querySelectorAll('.summary-item').forEach(item => {
      const name = item.querySelector('.summary-name');
      const value = item.querySelector('.summary-value');
      if (name && value && name.textContent.trim() === 'shots') value.textContent = result.shots;
    });
    ['backend2', 'backend3'].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.textContent = backendName();
    });
    const reading = document.querySelector('.reading .main span, .reading div:first-child span');
    if (reading) {
      const leaders = entries.sort((a, b) => b[1] - a[1]).slice(0, 2).map(([key]) => key).join('、');
      reading.textContent = `adapter 返回的高频结果是 ${leaders}。柱高与实际 counts 对应，不是预置演示数据。`;
    }
  }

  async function setupImport() {
    const button = document.getElementById('checkBtn');
    const input = document.getElementById('qasm');
    if (!button || !input) return;
    button.onclick = async () => {
      button.disabled = true;
      button.textContent = '正在调用 adapter 检查';
      try {
        const payload = await api('/api/check', {qasm: input.value});
        localStorage.setItem('qh_qasm', input.value);
        localStorage.setItem('qh_last_check', JSON.stringify(payload));
        location.href = 'circuit-check.html';
      } catch (error) {
        notice(error.message);
        button.disabled = false;
        button.textContent = '检查线路 →';
      }
    };
  }

  function setupCheck() {
    let payload;
    try { payload = JSON.parse(localStorage.getItem('qh_last_check') || 'null'); } catch (_) {}
    if (!payload || !payload.summary) return;
    const summary = payload.summary;
    const values = {
      qcount: summary.qubits, sq: summary.qubits, two: summary.two_qubit_gates,
      sm: summary.measurement_count,
      measureStatus: summary.has_measurement ? '已包含' : '未发现',
      summary: [...summary.gates, summary.has_measurement ? 'MEASURE' : null].filter(Boolean).join(' · ')
    };
    Object.entries(values).forEach(([id, value]) => {
      const element = document.getElementById(id); if (element) element.textContent = value;
    });
    if (!summary.has_measurement) {
      const title = document.querySelector('.section-title');
      const hero = document.querySelector('.hero h1');
      const next = document.querySelector('a[href="backend.html?source=import"]');
      if (title) title.textContent = '线路能被识别，但暂时不能运行';
      if (hero) hero.innerHTML = '还缺少测量操作，<span class="hero-em">请先补全线路</span>';
      if (next) {
        next.classList.add('disabled');
        next.removeAttribute('href');
        next.textContent = '添加测量后才能继续';
        next.setAttribute('aria-disabled', 'true');
      }
    }
  }

  function setupBackends() {
    const container = document.querySelector('.backends');
    const continueButton = document.getElementById('continueBtn');
    if (!container || !continueButton) return;
    document.querySelector('.pref')?.remove();
    const heading = container.closest('.section-body')?.previousElementSibling?.querySelector('.section-title');
    if (heading) heading.textContent = '选择 adapter 的本地执行目标';
    const choices = [
      ['spinq', 'SpinQ 本地模拟器', 'adapter 的 SpinQ 执行目标，适合默认运行。'],
      ['originq', 'OriginQ 本地模拟器', '同一线路转到 adapter 的 OriginQ 执行目标。'],
      ['braket', 'Braket 本地模拟器', '同一线路转到 adapter 的 Braket 执行目标。']
    ];
    let selected = target();
    container.innerHTML = choices.map(([id, name, description], index) => `<div class="backend${id === selected ? ' selected' : ''}" data-id="${id}"><div class="backend-top"><div><div class="backend-name">${name}</div><p class="backend-desc">${description}</p></div>${index === 0 ? '<span class="tag">推荐</span>' : ''}</div><div class="metrics"><div class="metric"><span>位置</span><strong>服务器本地</strong></div><div class="metric"><span>排队</span><strong>无</strong></div><div class="metric"><span>费用</span><strong>免费</strong></div><div class="metric"><span>执行</span><strong>adapter.run</strong></div></div></div>`).join('');
    const cards = [...container.querySelectorAll('.backend')];
    cards.forEach(card => card.onclick = () => {
      cards.forEach(item => item.classList.remove('selected'));
      card.classList.add('selected'); selected = card.dataset.id;
    });
    continueButton.onclick = () => {
      const found = choices.find(([id]) => id === selected);
      localStorage.setItem('qh_target', selected);
      localStorage.setItem('qh_backend', found[1]);
      const source = new URLSearchParams(location.search).get('source') || 'custom';
      location.href = source === 'import' ? 'circuit-run.html' : 'custom-run.html';
    };
  }

  function setupScenario() {
    const button = document.getElementById('useExample');
    if (!button) return;
    const typeMap = {search: '查找', opt: '优化', measure: '测量', relation: '关联'};
    const promptMap = {
      search: '演示：在 8 个候选编号中读取预先指定的目标 6。',
      opt: '演示：用 4 位状态表示一个候选方案，并读取它的编码。',
      measure: '演示：重复运行两比特叠加线路并统计测量分布。',
      relation: '演示：运行 Bell 线路并观察两个量子比特的测量关联。'
    };
    const typeCode = new URLSearchParams(location.search).get('type') || 'search';
    button.onclick = async () => {
      const prompt = promptMap[typeCode] || promptMap.search;
      button.disabled = true; button.textContent = '正在生成可执行线路';
      try {
        await createPlan(prompt, typeMap[typeCode]);
        location.href = 'custom-plan.html';
      } catch (error) {
        notice(error.message); button.disabled = false; button.textContent = '用这个例子继续 →';
      }
    };
  }

  function setupCustomTask() {
    const button = document.getElementById('analyzeBtn');
    const input = document.getElementById('taskInput');
    if (!button || !input) return;
    button.onclick = async () => {
      const prompt = input.value.trim();
      if (!prompt) { notice('请先描述任务。'); return; }
      button.disabled = true; button.textContent = 'adapter 正在理解';
      try {
        const plan = await createPlan(prompt);
        const analysis = document.getElementById('analysis');
        if (analysis) analysis.classList.add('show');
        const values = {goal: plan.goal, type: plan.type, cond: plan.condition, out: plan.output};
        Object.entries(values).forEach(([id, value]) => { const element = document.getElementById(id); if (element) element.textContent = value; });
        analysis?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        notice('已匹配一个由 adapter 校验的演示方案。', 'ok');
      } catch (error) {
        localStorage.setItem('qh_plan_error', error.message);
        localStorage.setItem('qh_task_draft', prompt);
        if (error.code === 'NEED_MORE_INFO') location.href = 'task-adjust.html';
        else notice(error.message);
      }
      finally { button.disabled = false; button.textContent = '整理这个任务 →'; }
    };
  }

  function setupPlan() {
    const plan = readPlan();
    if (!plan) { notice('还没有生成方案，请先描述任务。'); return; }
    const values = {
      planTitle: `${plan.type}类型的可执行演示方案`, method: plan.method,
      methodDesc: plan.description, taskText: plan.task, taskType: plan.type, taskOutput: plan.output
    };
    plan.steps.forEach((step, index) => {
      values[`s${index + 1}t`] = step.title;
      values[`s${index + 1}d`] = step.description;
    });
    Object.entries(values).forEach(([id, value]) => { const element = document.getElementById(id); if (element) element.textContent = value; });
    const next = document.querySelector('a[href="custom-circuit.html"]');
    if (next) next.onclick = () => { localStorage.setItem('qh_custom_qasm', plan.qasm); };
  }

  function setupCustomCircuit() {
    const plan = readPlan();
    if (!plan) { notice('没有可展示的线路，请先生成方案。'); return; }
    const title = document.getElementById('circuitTitle'); if (title) title.textContent = `${plan.method} · adapter 已校验`;
    const method = document.getElementById('methodName'); if (method) method.textContent = plan.method;
    const qubits = document.getElementById('qubits'); if (qubits) qubits.textContent = plan.summary.qubits;
    const circuit = document.querySelector('.circuit');
    if (circuit) {
      circuit.innerHTML = '';
      const sequence = document.createElement('div');
      sequence.style.cssText = 'display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px';
      plan.operations.forEach((operation, index) => {
        const gate = document.createElement('button');
        gate.type = 'button'; gate.className = 'gate'; gate.style.cssText = 'position:static;transform:none;min-width:70px';
        gate.textContent = `${operation.name.toUpperCase()} q[${operation.qubits.join(',')}]`;
        gate.onclick = () => notice(`第 ${index + 1} 步：${gate.textContent}`, 'ok');
        sequence.appendChild(gate);
      });
      const measure = document.createElement('button');
      measure.type = 'button'; measure.className = 'gate'; measure.style.cssText = 'position:static;transform:none;min-width:90px'; measure.textContent = 'MEASURE ALL';
      measure.onclick = () => notice('末端测量所有量子比特。', 'ok'); sequence.appendChild(measure);
      const code = document.createElement('pre'); code.textContent = plan.qasm;
      code.style.cssText = 'margin:0;padding:16px;overflow:auto;border-radius:13px;background:#fff;font:12px/1.65 Consolas,monospace;white-space:pre-wrap';
      circuit.append(sequence, code);
    }
    const legends = [
      [plan.steps[0]?.title, plan.steps[0]?.description],
      [plan.steps[1]?.title, plan.steps[1]?.description],
      [plan.steps[2]?.title, plan.steps[2]?.description]
    ];
    legends.forEach((item, index) => {
      const titleElement = document.getElementById(`l${index + 1}t`);
      const descriptionElement = document.getElementById(`l${index + 1}d`);
      if (titleElement) titleElement.textContent = item[0] || '';
      if (descriptionElement) descriptionElement.textContent = item[1] || '';
    });
  }

  function setupTaskAdjust() {
    const article = document.querySelector('.panel .main');
    if (!article) return;
    const paragraph = article.querySelector('p');
    const message = localStorage.getItem('qh_plan_error');
    if (paragraph && message) paragraph.textContent = message;
    const input = document.createElement('textarea');
    input.id = 'qh-adjust-input'; input.value = localStorage.getItem('qh_task_draft') || '';
    input.placeholder = '补充：目标是什么、有哪些候选、怎样判断结果是否满足条件？';
    input.style.cssText = 'width:100%;min-height:120px;margin-top:20px;padding:15px;border:1px solid rgba(25,26,30,.12);border-radius:14px;resize:vertical;font:14px/1.65 system-ui';
    const button = document.createElement('button');
    button.className = 'btn primary'; button.textContent = '补充后重新分析 →'; button.style.marginTop = '12px';
    button.onclick = async () => {
      const prompt = input.value.trim(); if (!prompt) { notice('请先补充任务信息。'); return; }
      button.disabled = true; button.textContent = '正在重新分析';
      try { await createPlan(prompt); location.href = 'custom-plan.html'; }
      catch (error) { localStorage.setItem('qh_plan_error', error.message); if (paragraph) paragraph.textContent = error.message; notice(error.message); button.disabled = false; button.textContent = '补充后重新分析 →'; }
    };
    article.append(input, button);
  }

  const setup = {
    'index.html': setupHome,
    'agent.html': setupAgent,
    'scenario.html': setupScenario,
    'circuit-import.html': setupImport,
    'circuit-check.html': setupCheck,
    'backend.html': setupBackends,
    'circuit-run.html': () => bindRun(() => localStorage.getItem('qh_qasm'), 'qh_import_result', 'circuit-result.html'),
    'circuit-result.html': () => renderResult('qh_import_result'),
    'example-run.html': () => bindRun(() => BELL_QASM, 'qh_example_result', 'example-result.html'),
    'example-result.html': () => renderResult('qh_example_result'),
    'custom-task.html': setupCustomTask,
    'custom-plan.html': setupPlan,
    'custom-circuit.html': setupCustomCircuit,
    'custom-run.html': () => bindRun(() => localStorage.getItem('qh_custom_qasm'), 'qh_custom_result', 'custom-result.html'),
    'custom-result.html': () => renderResult('qh_custom_result'),
    'task-adjust.html': setupTaskAdjust
  };
  if (setup[page]) setup[page]();
})();
