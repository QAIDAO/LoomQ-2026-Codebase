(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.QuantumWorkspaceState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const VERSION = 3;
  const STORAGE_KEY = 'qh_session';
  const EXECUTION_TARGETS = new Set(['spinq', 'originq', 'braket']);

  function createId(prefix) {
    const random = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    return `${prefix || 'id'}-${random}`;
  }

  function initialState() {
    return {
      version: VERSION,
      view: 'home',
      taskId: null,
      currentRevision: 0,
      // 第二轮 §9/§11：任务与 QASM 的版本号，用于派生状态失效与响应核对。
      taskVersion: 0,
      qasmVersion: 0,
      conversationScope: null,
      // 第三轮 §14/§15：Active Artifact——正在检查的外部代码 ≠ 当前任务线路。
      workspaceMode: 'task',
      inspectedQasm: null,
      diagnostics: [],
      messages: [],
      intent: null,
      task: null,
      currentQasm: null,
      transpiledArtifacts: {},
      selectedExecutionTarget: null,
      circuit: null,
      explanationSteps: [],
      relatedOperationIds: [],
      validation: null,
      repairProposal: null,
      repairApplying: false,
      backendRequirements: null,
      recommendedBackend: null,
      executionBackend: null,
      resultSource: null,
      // `backend` is retained as a read-only migration alias for older sessions.
      backend: null,
      matchStatus: null,
      shots: 1024,
      runStatus: null,
      result: null,
      pendingRequest: null,
      lastError: null,
      developerDetails: null
    };
  }

  function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function safeTranspiledArtifacts(value) {
    if (!isRecord(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([target, code]) =>
      EXECUTION_TARGETS.has(target) && typeof code === 'string'
    ));
  }

  function safeState(value) {
    if (!isRecord(value) || ![1, 2, VERSION].includes(value.version)) return null;
    if (!Number.isInteger(value.currentRevision) || value.currentRevision < 0) return null;
    if (!Array.isArray(value.messages) || !Array.isArray(value.explanationSteps)) return null;
    const base = initialState();
    const interruptedChat = Boolean(value.pendingRequest);
    const interruptedRun = isRecord(value.runStatus) && ['checking', 'executing', 'reading'].includes(value.runStatus.stage);
    const restoredRun = interruptedRun
      ? {...value.runStatus, stage: 'error', error: '上次运行因页面刷新而中断，请重新运行。'}
      : value.runStatus;
    const recommendedBackend = value.recommendedBackend || value.backend || null;
    const executionBackend = value.executionBackend || (
      isRecord(value.runStatus) && value.runStatus.target
        ? {target: value.runStatus.target, name: localBackendName(value.runStatus.target), type: 'simulator'}
        : null
    );
    const resultSource = value.resultSource || (
      isRecord(value.result) && value.result.target
        ? {target: value.result.target, name: localBackendName(value.result.target), type: 'simulator'}
        : null
    );
    return {
      ...base,
      ...value,
      version: VERSION,
      view: value.view === 'workspace' && (value.taskId || value.messages.length) ? 'workspace' : 'home',
      currentRevision: value.currentRevision,
      messages: value.messages.filter(message =>
        isRecord(message) && ['user', 'assistant'].includes(message.role) && typeof message.text === 'string'
      ).slice(-100),
      explanationSteps: value.explanationSteps.filter(isRecord),
      relatedOperationIds: Array.isArray(value.relatedOperationIds) ? value.relatedOperationIds.map(String) : [],
      transpiledArtifacts: safeTranspiledArtifacts(value.transpiledArtifacts),
      selectedExecutionTarget: EXECUTION_TARGETS.has(value.selectedExecutionTarget)
        ? value.selectedExecutionTarget
        : (EXECUTION_TARGETS.has(executionBackend?.target) ? executionBackend.target : null),
      recommendedBackend,
      executionBackend,
      resultSource,
      backend: recommendedBackend,
      pendingRequest: null,
      repairApplying: false,
      runStatus: restoredRun || null,
      lastError: interruptedChat
        ? '上次 Agent 请求因页面刷新而中断，请再次发送。'
        : interruptedRun ? restoredRun.error : value.lastError || null,
      developerDetails: value.developerDetails || null
    };
  }

  function localBackendName(target) {
    return ({
      spinq: 'SpinQ 本地模拟器',
      originq: 'OriginQ 本地模拟器',
      braket: 'Braket 本地模拟器'
    })[target] || String(target || '本地模拟器');
  }

  // 第二轮 §4：唯一归一化结果来源。柱高、count 标签、百分比都从这一个数组派生，
  // 避免两套归一化导致「次数相同却柱高不同」。
  function normalizeCounts(counts) {
    if (!isRecord(counts)) return [];
    const entries = Object.entries(counts)
      .filter(([label, count]) => typeof label === 'string' && Number.isFinite(Number(count)) && Number(count) >= 0);
    const total = entries.reduce((sum, [, count]) => sum + Number(count), 0) || 1;
    return entries
      .map(([bitstring, count]) => ({bitstring, count: Number(count), probability: Number(count) / total}))
      .sort((a, b) => b.count - a.count);
  }

  function hasTask(state) {
    return Boolean(state && (state.taskId || state.currentQasm || (Array.isArray(state.messages) && state.messages.length)));
  }

  function viewFromHistoryState(historyState, fallback) {
    if (isRecord(historyState) && ['home', 'workspace'].includes(historyState.qhView)) {
      return historyState.qhView;
    }
    return fallback === 'workspace' ? 'workspace' : 'home';
  }

  function reducer(state, action) {
    const current = isRecord(state) && state.version === VERSION ? state : initialState();
    if (!isRecord(action) || typeof action.type !== 'string') return current;
    if (action.type === 'RESET' || action.type === 'NEW_TASK') return initialState();
    if (action.type === 'CLEAR_ERRORS') {
      const failedRun = isRecord(current.runStatus) && current.runStatus.stage === 'error';
      return {
        ...current,
        lastError: null,
        developerDetails: null,
        repairApplying: false,
        runStatus: failedRun ? null : current.runStatus
      };
    }
    if (action.type === 'GO_HOME') return {...current, view: 'home'};
    if (action.type === 'CONTINUE_TASK') {
      return hasTask(current) ? {...current, view: 'workspace'} : {...current, view: 'home'};
    }
    if (action.type === 'SET_VIEW') {
      const requested = action.view === 'workspace' ? 'workspace' : 'home';
      return {...current, view: requested === 'workspace' && !hasTask(current) ? 'home' : requested};
    }
    if (action.type === 'BEGIN_REQUEST') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const proposedRevision = current.currentRevision + 1;
      const taskId = typeof payload.taskId === 'string' && payload.taskId
        ? payload.taskId
        : current.taskId || createId('task');
      const requestId = typeof payload.requestId === 'string' && payload.requestId
        ? payload.requestId
        : createId('request');
      const prompt = typeof payload.prompt === 'string' ? payload.prompt : '';
      return {
        ...current,
        view: 'workspace',
        taskId,
        messages: [...current.messages, {id: createId('message'), role: 'user', text: prompt, revision: current.currentRevision}].slice(-100),
        pendingRequest: {requestId, taskId, baseRevision: current.currentRevision, proposedRevision},
        lastError: null,
        developerDetails: null
      };
    }
    if (action.type === 'APPLY_RESPONSE') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const pending = current.pendingRequest;
      if (!pending || payload.requestId !== pending.requestId ||
          payload.taskId !== pending.taskId || payload.baseRevision !== pending.baseRevision ||
          current.currentRevision !== pending.baseRevision) return current;
      const patch = isRecord(payload.patch) ? {...payload.patch} : {};
      if (patch.backend && !patch.recommendedBackend) patch.recommendedBackend = patch.backend;
      if (patch.recommendedBackend) patch.backend = patch.recommendedBackend;
      const assistantText = typeof payload.assistantText === 'string' ? payload.assistantText : '';
      const nextRevision = payload.commitArtifact === true ? pending.proposedRevision : current.currentRevision;
      const nextResult = payload.commitArtifact === true && current.result
        ? {...current.result, stale: true}
        : (Object.prototype.hasOwnProperty.call(patch, 'result') ? patch.result : current.result);

      // 第二轮 §9/§11：版本化 + 派生状态失效。
      const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
      const taskChanged = hasOwn(patch, 'task') && JSON.stringify(patch.task) !== JSON.stringify(current.task);
      const qasmChanged = hasOwn(patch, 'currentQasm') && patch.currentQasm !== current.currentQasm;
      const nextTaskVersion = taskChanged ? current.taskVersion + 1 : current.taskVersion;
      const nextQasmVersion = qasmChanged ? current.qasmVersion + 1 : current.qasmVersion;
      const nextTranspiledArtifacts = hasOwn(patch, 'transpiledArtifacts')
        ? safeTranspiledArtifacts(patch.transpiledArtifacts)
        : (qasmChanged ? {} : current.transpiledArtifacts);

      // validation 版本绑定：只有校验的是【当前这一版 QASM】才允许显示通过。
      let nextValidation = current.validation;
      if (hasOwn(patch, 'validation') && patch.validation) {
        nextValidation = {
          ...patch.validation,
          status: patch.validation.valid ? 'valid' : 'invalid',
          qasmVersion: nextQasmVersion
        };
      } else if (qasmChanged) {
        // QASM 变了但本事务没带新校验 → 立即 stale（§9 规则1），绝不继续显示绿色。
        nextValidation = {
          status: 'stale',
          qasmVersion: nextQasmVersion,
          valid: false,
          errors: ['当前线路已修改，等待重新检查'],
          source: null,
          targets: []
        };
      }

      return {
        ...current,
        ...patch,
        version: VERSION,
        view: current.view,
        taskId: pending.taskId,
        taskVersion: nextTaskVersion,
        qasmVersion: nextQasmVersion,
        conversationScope: hasOwn(patch, 'conversationScope') ? patch.conversationScope : current.conversationScope,
        validation: nextValidation,
        transpiledArtifacts: nextTranspiledArtifacts,
        currentRevision: nextRevision,
        messages: assistantText
          ? [...current.messages, {id: createId('message'), role: 'assistant', text: assistantText, revision: nextRevision}].slice(-100)
          : current.messages,
        result: nextResult,
        pendingRequest: null,
        lastError: null,
        developerDetails: null
      };
    }
    if (action.type === 'REQUEST_ERROR') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const pending = current.pendingRequest;
      if (!pending || payload.requestId !== pending.requestId ||
          payload.taskId !== pending.taskId || payload.baseRevision !== pending.baseRevision ||
          current.currentRevision !== pending.baseRevision) return current;
      return {
        ...current,
        pendingRequest: null,
        lastError: String(payload.message || '请求失败'),
        developerDetails: payload.developerDetails ? String(payload.developerDetails) : null
      };
    }
    if (action.type === 'DISCARD_REPAIR') {
      return {...current, repairProposal: null, repairApplying: false, lastError: null};
    }
    if (action.type === 'CANCEL_PENDING') {
      return {...current, pendingRequest: null, lastError: action.message ? String(action.message) : current.lastError};
    }
    if (action.type === 'REPAIR_APPLY_STARTED') {
      if (!current.repairProposal || current.repairApplying || current.pendingRequest) return current;
      return {...current, repairApplying: true, lastError: null};
    }
    if (action.type === 'APPLY_REPAIR') {
      const payload = isRecord(action.payload) ? action.payload : {};
      if (!current.repairProposal || !current.repairApplying || payload.baseRevision !== current.currentRevision || !isRecord(payload.patch)) {
        return current;
      }
      const patch = {...payload.patch};
      const qasmChanged = Object.prototype.hasOwnProperty.call(patch, 'currentQasm') && patch.currentQasm !== current.currentQasm;
      const nextQasmVersion = qasmChanged ? current.qasmVersion + 1 : current.qasmVersion;
      const nextTranspiledArtifacts = Object.prototype.hasOwnProperty.call(patch, 'transpiledArtifacts')
        ? safeTranspiledArtifacts(patch.transpiledArtifacts)
        : (qasmChanged ? {} : current.transpiledArtifacts);
      let nextValidation = current.validation;
      if (Object.prototype.hasOwnProperty.call(patch, 'validation') && patch.validation) {
        nextValidation = {...patch.validation, status: patch.validation.valid ? 'valid' : 'invalid', qasmVersion: nextQasmVersion};
      } else if (qasmChanged) {
        nextValidation = {status: 'stale', qasmVersion: nextQasmVersion, valid: false, errors: ['当前线路已修改，等待重新检查'], source: null, targets: []};
      }
      return {
        ...current,
        ...patch,
        qasmVersion: nextQasmVersion,
        validation: nextValidation,
        transpiledArtifacts: nextTranspiledArtifacts,
        currentRevision: current.currentRevision + 1,
        result: current.result ? {...current.result, stale: true} : null,
        repairProposal: null,
        repairApplying: false,
        lastError: null
      };
    }
    if (action.type === 'SET_ERROR') {
      return {
        ...current,
        lastError: String(action.message || '请求失败'),
        developerDetails: action.developerDetails ? String(action.developerDetails) : null
      };
    }
    if (action.type === 'SELECT_EXECUTION_TARGET') {
      return EXECUTION_TARGETS.has(action.target)
        ? {...current, selectedExecutionTarget: action.target}
        : current;
    }
    if (action.type === 'SET_TRANSPILED_ARTIFACTS') {
      const payload = isRecord(action.payload) ? action.payload : {};
      // /api/check may finish after the user has generated or repaired another
      // circuit. Bind the artifacts to both the source text and its version.
      if (payload.qasmVersion !== current.qasmVersion || payload.qasm !== current.currentQasm) return current;
      return {...current, transpiledArtifacts: safeTranspiledArtifacts(payload.artifacts)};
    }
    if (action.type === 'REPAIR_APPLY_FAILED') {
      return {...current, repairApplying: false, lastError: String(action.message || '修复未应用')};
    }
    if (action.type === 'RUN_STARTED') {
      const payload = isRecord(action.payload) ? action.payload : {};
      if (payload.taskId !== current.taskId || payload.revision !== current.currentRevision) return current;
      return {
        ...current,
        shots: payload.shots,
        selectedExecutionTarget: EXECUTION_TARGETS.has(payload.target) ? payload.target : current.selectedExecutionTarget,
        executionBackend: isRecord(payload.executionBackend)
          ? payload.executionBackend
          : {target: payload.target, name: localBackendName(payload.target), type: 'simulator'},
        resultSource: null,
        runStatus: {
          runId: payload.runId,
          taskId: payload.taskId,
          revision: payload.revision,
          target: payload.target,
          stage: 'checking',
          error: null
        },
        result: null,
        lastError: null
      };
    }
    if (action.type === 'RUN_STAGE') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const run = current.runStatus;
      if (!run || payload.runId !== run.runId || run.taskId !== current.taskId ||
          run.revision !== current.currentRevision) return current;
      return {...current, runStatus: {...run, stage: payload.stage}};
    }
    if (action.type === 'CANCEL_RUN') {
      const run = current.runStatus;
      if (!run || !['checking', 'executing', 'reading'].includes(run.stage)) return current;
      const message = String(action.message || '本地预览已取消，可以重新运行。');
      return {...current, runStatus: {...run, stage: 'error', error: message}, result: null};
    }
    if (action.type === 'RUN_SUCCESS') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const run = current.runStatus;
      if (!run || payload.runId !== run.runId || run.taskId !== current.taskId ||
          run.revision !== current.currentRevision || !isRecord(payload.result)) return current;
      return {
        ...current,
        runStatus: {...run, stage: 'complete', error: null},
        result: {...payload.result, taskId: current.taskId, artifactRevision: current.currentRevision, stale: false},
        resultSource: isRecord(payload.resultSource)
          ? payload.resultSource
          : current.executionBackend || {target: run.target, name: localBackendName(run.target), type: 'simulator'},
        lastError: null
      };
    }
    if (action.type === 'RUN_ERROR') {
      const payload = isRecord(action.payload) ? action.payload : {};
      const run = current.runStatus;
      if (!run || payload.runId !== run.runId || run.taskId !== current.taskId ||
          run.revision !== current.currentRevision) return current;
      const message = String(payload.message || '运行失败');
      return {...current, runStatus: {...run, stage: 'error', error: message}, result: null, lastError: message};
    }
    return current;
  }

  function createStore(storage) {
    const persistence = storage || (typeof sessionStorage !== 'undefined' ? sessionStorage : null);
    let state = initialState();
    const listeners = new Set();
    if (persistence) {
      try {
        const loaded = safeState(JSON.parse(persistence.getItem(STORAGE_KEY) || 'null'));
        if (loaded) state = loaded;
        else persistence.removeItem(STORAGE_KEY);
      } catch (_) {
        try { persistence.removeItem(STORAGE_KEY); } catch (_) {}
      }
    }
    function persist() {
      if (!persistence) return;
      try { persistence.setItem(STORAGE_KEY, JSON.stringify(state)); }
      catch (_) {}
    }
    return {
      getState: () => state,
      get currentRevision() { return state.currentRevision; },
      dispatch(action) {
        state = reducer(state, action);
        persist();
        listeners.forEach(listener => listener(state));
        return state;
      },
      subscribe(listener) {
        if (typeof listener !== 'function') return () => {};
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      reset() { return this.dispatch({type: 'RESET'}); }
    };
  }

  return {
    VERSION, STORAGE_KEY, createId, initialState, reducer, createStore,
    localBackendName, hasTask, viewFromHistoryState, normalizeCounts
  };
});
