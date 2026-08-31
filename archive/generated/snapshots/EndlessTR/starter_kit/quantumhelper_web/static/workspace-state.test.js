'use strict';

const assert = require('node:assert/strict');
const stateApi = require('./workspace-state.js');

function begin(state, requestId, prompt = 'prompt') {
  return stateApi.reducer(state, {
    type: 'BEGIN_REQUEST',
    payload: {requestId, taskId: 'task-1', prompt}
  });
}

function commit(state, requestId, patch = {}) {
  return stateApi.reducer(state, {
    type: 'APPLY_RESPONSE',
    payload: {
      requestId,
      taskId: 'task-1',
      baseRevision: state.pendingRequest.baseRevision,
      commitArtifact: true,
      patch
    }
  });
}

let state = stateApi.initialState();
state = begin(state, 'generate');
state = commit(state, 'generate', {currentQasm: 'qasm-v1'});
state = {...state, repairProposal: {proposedQasm: 'qasm-v2'}};
state = begin(state, 'pending-chat');
state = stateApi.reducer(state, {type: 'CANCEL_PENDING'});
state = stateApi.reducer(state, {type: 'REPAIR_APPLY_STARTED'});
assert.equal(state.repairApplying, true);
state = stateApi.reducer(state, {
  type: 'APPLY_REPAIR',
  payload: {baseRevision: 1, patch: {currentQasm: 'qasm-v2'}}
});
assert.equal(state.currentRevision, 2);
assert.equal(state.pendingRequest, null);
assert.equal(state.repairProposal, null);
const afterFirstApply = state;
state = stateApi.reducer(state, {
  type: 'APPLY_REPAIR',
  payload: {baseRevision: 2, patch: {currentQasm: 'double-applied'}}
});
assert.deepEqual(state, afterFirstApply, 'double repair apply must be ignored');

state = begin(state, 'new-request');
const staleResponse = stateApi.reducer(state, {
  type: 'APPLY_RESPONSE',
  payload: {requestId: 'old-request', taskId: 'task-1', baseRevision: 2, commitArtifact: true, patch: {currentQasm: 'stale'}}
});
assert.equal(staleResponse.currentQasm, 'qasm-v2');
assert.equal(staleResponse.pendingRequest.requestId, 'new-request');
const staleError = stateApi.reducer(state, {
  type: 'REQUEST_ERROR',
  payload: {requestId: 'old-request', taskId: 'task-1', baseRevision: 2, message: 'stale error'}
});
assert.equal(staleError.pendingRequest.requestId, 'new-request');

const memory = {
  value: JSON.stringify({
    ...stateApi.initialState(),
    taskId: 'task-1',
    currentRevision: 1,
    pendingRequest: {requestId: 'lost', taskId: 'task-1', baseRevision: 1, proposedRevision: 2},
    runStatus: {runId: 'run-1', taskId: 'task-1', revision: 1, target: 'spinq', stage: 'executing'}
  }),
  getItem() { return this.value; },
  setItem(_key, value) { this.value = value; },
  removeItem() { this.value = null; }
};
const restored = stateApi.createStore(memory).getState();
assert.equal(restored.pendingRequest, null);
assert.equal(restored.runStatus.stage, 'error');
assert.match(restored.lastError, /中断/);

state = stateApi.initialState();
state = begin(state, 'g');
state = commit(state, 'g', {currentQasm: 'qasm-v1'});
state = stateApi.reducer(state, {type: 'RUN_STARTED', payload: {runId: 'run-old', taskId: 'task-1', revision: 1, target: 'spinq', shots: 32}});
state = begin(state, 'modify');
state = commit(state, 'modify', {currentQasm: 'qasm-v2', runStatus: null});
assert.equal(state.currentRevision, 2);
const afterLateRun = stateApi.reducer(state, {type: 'RUN_SUCCESS', payload: {runId: 'run-old', result: {counts: {'0': 32}}}});
assert.equal(afterLateRun.result, null);
assert.equal(afterLateRun.currentQasm, 'qasm-v2');

state = stateApi.initialState();
state = begin(state, 'home-late');
state = stateApi.reducer(state, {type: 'GO_HOME'});
state = commit(state, 'home-late', {currentQasm: 'saved-while-home'});
assert.equal(state.view, 'home', 'late response must not force the workspace open');
assert.equal(state.currentQasm, 'saved-while-home');

state = {...state, view: 'workspace'};
state = stateApi.reducer(state, {type: 'RUN_STARTED', payload: {
  runId: 'run-cancel', taskId: 'task-1', revision: state.currentRevision, target: 'spinq', shots: 64
}});
state = stateApi.reducer(state, {type: 'CANCEL_RUN'});
assert.equal(state.runStatus.stage, 'error');
assert.match(state.runStatus.error, /取消/);

state = stateApi.reducer(state, {type: 'GO_HOME'});
assert.equal(state.view, 'home');
state = stateApi.reducer(state, {type: 'CONTINUE_TASK'});
assert.equal(state.view, 'workspace');
assert.equal(stateApi.reducer(stateApi.initialState(), {type: 'SET_VIEW', view: 'workspace'}).view, 'home');
assert.equal(stateApi.viewFromHistoryState({qhView: 'workspace'}, 'home'), 'workspace');
assert.equal(stateApi.viewFromHistoryState({qhView: 'invalid'}, 'workspace'), 'workspace');

const taskWithRememberedError = {
  ...stateApi.initialState(),
  taskId: 'kept-task', currentQasm: 'kept-qasm', lastError: 'old error', developerDetails: 'old stack',
  repairApplying: true, runStatus: {stage: 'error', error: 'old run error'}
};
const clearedErrors = stateApi.reducer(taskWithRememberedError, {type: 'CLEAR_ERRORS'});
assert.equal(clearedErrors.taskId, 'kept-task');
assert.equal(clearedErrors.currentQasm, 'kept-qasm');
assert.equal(clearedErrors.lastError, null);
assert.equal(clearedErrors.developerDetails, null);
assert.equal(clearedErrors.repairApplying, false);
assert.equal(clearedErrors.runStatus, null);

const reset = stateApi.reducer({
  ...state,
  messages: [{role: 'user', text: 'old'}],
  intent: 'generate', task: {goal: 'old'}, currentQasm: 'old', circuit: {qubits: 2},
  explanationSteps: [{id: 'old'}], validation: {valid: true},
  recommendedBackend: {id: 'hardware'}, executionBackend: {target: 'originq'},
  resultSource: {target: 'originq'}, runStatus: {stage: 'complete'}, result: {counts: {'0': 1}}, shots: 77
}, {type: 'NEW_TASK'});
assert.deepEqual(reset, stateApi.initialState(), 'new task must clear every task field and restore defaults');
assert.equal(reset.shots, 1024);

const legacyMemory = {
  value: JSON.stringify({
    ...stateApi.initialState(), version: 1, taskId: 'legacy-task',
    messages: [{role: 'user', text: 'legacy'}], backend: {id: 'legacy-backend'},
    runStatus: {target: 'braket', stage: 'complete'}, result: {target: 'braket', counts: {'0': 1}}
  }),
  getItem() { return this.value; }, setItem(_key, value) { this.value = value; }, removeItem() { this.value = null; }
};
const migrated = stateApi.createStore(legacyMemory).getState();
assert.equal(migrated.recommendedBackend.id, 'legacy-backend');
assert.equal(migrated.executionBackend.target, 'braket');
assert.equal(migrated.resultSource.target, 'braket');

state = stateApi.initialState();
state = begin(state, 'source-generation');
state = commit(state, 'source-generation', {currentQasm: 'qasm', recommendedBackend: {id: 'hardware', type: 'hardware'}});
state = stateApi.reducer(state, {type: 'RUN_STARTED', payload: {
  runId: 'source-run', taskId: state.taskId, revision: state.currentRevision,
  target: 'originq', shots: 128, executionBackend: {target: 'originq', name: 'OriginQ 本地模拟器', type: 'simulator'}
}});
state = stateApi.reducer(state, {type: 'RUN_SUCCESS', payload: {
  runId: 'source-run', result: {counts: {'0': 128}},
  resultSource: {target: 'originq', name: 'OriginQ 本地模拟器', type: 'simulator'}
}});
assert.equal(state.recommendedBackend.id, 'hardware');
assert.equal(state.executionBackend.target, 'originq');
assert.equal(state.resultSource.target, 'originq');
assert.equal(state.runStatus.stage, 'complete');

// --- 第二轮 §16：状态版本化（taskVersion / qasmVersion / validation stale） ---

// Test 1：task 完整 replace（Bell → GHZ 不得残留），taskVersion 递增。
state = stateApi.initialState();
state = begin(state, 'bell');
state = commit(state, 'bell', {task: {goal: 'Bell State', qubits: 2}, currentQasm: 'bell-qasm', validation: {valid: true}});
assert.equal(state.task.goal, 'Bell State');
assert.equal(state.taskVersion, 1);
state = begin(state, 'ghz');
state = commit(state, 'ghz', {task: {goal: 'GHZ State', qubits: 3}, currentQasm: 'ghz-qasm', validation: {valid: true}});
assert.equal(state.task.goal, 'GHZ State', 'task 必须整体 replace，不得残留 Bell');
assert.equal(state.task.qubits, 3);
assert.equal(state.taskVersion, 2);

// Test 2：QASM 变化后 validation 立即 stale，不得继续 valid。
state = stateApi.initialState();
state = begin(state, 'a');
state = commit(state, 'a', {currentQasm: 'qasm-ok', validation: {valid: true}});
assert.equal(state.validation.status, 'valid');
assert.equal(state.validation.qasmVersion, state.qasmVersion);
state = begin(state, 'b');
state = commit(state, 'b', {currentQasm: 'qasm-broken'});  // 不带新校验
assert.equal(state.validation.status, 'stale', 'qasm 变了但没重新校验，必须 stale');
assert.equal(state.validation.valid, false);

// Test 3：旧 revision 的晚到响应被丢弃（不覆盖新 qasm/validation）。
state = stateApi.initialState();
state = begin(state, 'new');
const stale = stateApi.reducer(state, {
  type: 'APPLY_RESPONSE',
  payload: {requestId: 'old', taskId: 'task-1', baseRevision: 0, commitArtifact: true, patch: {currentQasm: 'old-qasm', validation: {valid: true}}}
});
assert.equal(stale.currentQasm, null, '旧响应不得写入');
assert.equal(stale.qasmVersion, 0);

// Adapter 产物与 QASM 同版本保存；选择后端只切换视图，新 QASM 不得残留旧产物。
state = stateApi.initialState();
state = begin(state, 'adapter-artifacts');
state = commit(state, 'adapter-artifacts', {
  currentQasm: 'qasm-v1',
  validation: {valid: true},
  transpiledArtifacts: {spinq: 'op2-v1', originq: 'originir-v1', braket: 'op3-v1', unsafe: 'ignored'}
});
assert.deepEqual(state.transpiledArtifacts, {spinq: 'op2-v1', originq: 'originir-v1', braket: 'op3-v1'});
state = stateApi.reducer(state, {type: 'SELECT_EXECUTION_TARGET', target: 'originq'});
assert.equal(state.selectedExecutionTarget, 'originq');
const selectedState = stateApi.reducer(state, {type: 'SELECT_EXECUTION_TARGET', target: 'unknown'});
assert.equal(selectedState.selectedExecutionTarget, 'originq', '未知 target 不得进入状态');
const artifactVersion = state.qasmVersion;
state = stateApi.reducer(state, {type: 'SET_TRANSPILED_ARTIFACTS', payload: {
  qasm: 'qasm-v1', qasmVersion: artifactVersion,
  artifacts: {spinq: 'fresh-op2', originq: 'fresh-originir', braket: 'fresh-op3'}
}});
assert.equal(state.transpiledArtifacts.braket, 'fresh-op3');
const beforeStaleArtifacts = state;
state = stateApi.reducer(state, {type: 'SET_TRANSPILED_ARTIFACTS', payload: {
  qasm: 'different-qasm', qasmVersion: artifactVersion,
  artifacts: {braket: 'stale-op3'}
}});
assert.deepEqual(state, beforeStaleArtifacts, '晚到的转译响应不得覆盖当前线路产物');
state = begin(state, 'adapter-artifacts-v2');
state = commit(state, 'adapter-artifacts-v2', {currentQasm: 'qasm-v2'});
assert.deepEqual(state.transpiledArtifacts, {}, 'QASM 改变且没有新转译结果时必须清空旧产物');

// Test 6：normalizeCounts —— 相等 counts 概率相等，3:1 counts 概率严格 3:1。
const equalCounts = stateApi.normalizeCounts({'0': 512, '1': 512});
assert.equal(equalCounts[0].probability, 0.5);
assert.equal(equalCounts[1].probability, 0.5);
assert.equal(equalCounts[0].count, equalCounts[1].count);
const threeToOne = stateApi.normalizeCounts({'00': 768, '11': 256});
assert.equal(threeToOne[0].probability, 0.75);
assert.equal(threeToOne[1].probability, 0.25);
assert.equal(threeToOne[0].count / threeToOne[1].count, 3);

console.log('workspace-state reducer tests passed');
