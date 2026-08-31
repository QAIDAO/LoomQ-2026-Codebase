// DOM renderers for structured Agent responses.

import { renderMarkdown } from './markdown.js';

export function renderAgentResult(data, { onSuggestion } = {}) {
  const english = data.response_language === 'en';
  const article = createMessageShell('agent-message', 'LQ', 'LoomQ Agent');
  const body = article.querySelector('.message-body');
  const summary = document.createElement('div');
  summary.className = 'markdown-body message-summary';
  const summaryText = !data.ok && data.task_type === 'clarify'
    ? (english ? 'I need clearer information before I can continue.' : '我需要更明确的信息才能继续。')
    : !data.ok && data.task_type === 'recommend_backend'
    ? (english ? 'I could not find a platform matching every requirement.' : '没有找到满足全部条件的运行平台。')
    : !data.ok
    ? (english ? 'I could not complete this request.' : '暂时无法完成这个请求。')
    : data.backend_id
    ? (english ? 'I found a platform that matches your requirements.' : '我找到一个符合你要求的运行平台。')
    : data.display_text;
  renderMarkdown(summary, summaryText);
  body.append(summary);

  if (!data.ok) {
    body.append(createErrorCard(data, english));
  } else if (data.qasm) {
    body.append(createQasmCard(data, english));
  } else if (data.backend_id) {
    body.append(createBackendCard(data, english));
  }
  if (data.suggestions?.length) body.append(createSuggestions(data.suggestions, onSuggestion));
  return article;
}

export function renderUserMessage(text) {
  const article = createMessageShell('user-message', 'YOU', '你的需求');
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  article.querySelector('.message-body').append(paragraph);
  return article;
}

function createMessageShell(className, avatarText, metaText) {
  const article = document.createElement('article');
  article.className = `message ${className}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = avatarText;
  const body = document.createElement('div');
  body.className = 'message-body';
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.textContent = metaText;
  body.append(meta);
  article.append(avatar, body);
  return article;
}

function createErrorCard(data, english) {
  const error = document.createElement('div');
  error.className = 'error-card markdown-body';
  renderMarkdown(error, data.message || (english ? 'The task could not be completed.' : '暂时无法完成这个任务。'));
  return error;
}

function createQasmCard(data, english) {
  const card = document.createElement('div');
  card.className = 'result-card';
  const head = document.createElement('div');
  head.className = 'result-head';
  const badge = document.createElement('span');
  badge.className = 'validation-badge';
  badge.textContent = english ? 'Generated QASM' : '已生成 QASM';
  const copy = document.createElement('button');
  copy.className = 'copy-button';
  copy.type = 'button';
  copy.textContent = english ? 'Copy QASM' : '复制 QASM';
  copy.addEventListener('click', () => copyQasm(copy, data.qasm, english));
  head.append(badge, copy);
  card.append(head);

  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.textContent = data.qasm;
  pre.append(code);
  card.append(pre);
  return card;
}

async function copyQasm(button, qasm, english) {
  await navigator.clipboard.writeText(qasm);
  button.textContent = english ? 'Copied' : '已复制';
  window.setTimeout(() => {
    button.textContent = english ? 'Copy QASM' : '复制 QASM';
  }, 1400);
}

function createBackendCard(data, english) {
  const card = document.createElement('div');
  card.className = 'backend-card';
  const backend = data.backend || { id: data.backend_id, name: data.backend_id };
  const head = document.createElement('div');
  head.className = 'backend-head';
  const identity = document.createElement('div');
  identity.className = 'backend-identity';
  const kind = document.createElement('span');
  kind.textContent = backend.kind || (english ? 'Recommended platform' : '推荐平台');
  const name = document.createElement('strong');
  name.textContent = backend.name;
  const id = document.createElement('code');
  id.textContent = backend.id;
  identity.append(kind, name, id);
  const badge = document.createElement('span');
  badge.className = 'recommendation-badge';
  badge.textContent = english ? 'Best match' : '最符合条件';
  head.append(identity, badge);
  card.append(head);

  if (backend.max_qubits) {
    const facts = document.createElement('dl');
    facts.className = 'backend-facts';
    appendFact(facts, english ? 'Capacity' : '支持规模', english ? `Up to ${backend.max_qubits} qubits` : `最多 ${backend.max_qubits} 个量子比特`);
    appendFact(facts, english ? 'Queue' : '排队情况', backend.queue);
    appendFact(facts, english ? 'Cost' : '使用费用', backend.cost);
    appendFact(facts, english ? 'Account' : '账号要求', backend.account);
    card.append(facts);
  } else {
    const reason = document.createElement('p');
    reason.className = 'backend-note';
    reason.textContent = data.explanation || (english ? 'This platform matches your requirements.' : '该平台符合你的运行条件。');
    card.append(reason);
  }

  if (backend.notes) {
    const note = document.createElement('p');
    note.className = 'backend-note';
    note.textContent = `${english ? 'Note' : '补充说明'}：${backend.notes}`;
    card.append(note);
  }
  if (data.alternative_backends?.length) {
    const alternatives = document.createElement('p');
    alternatives.className = 'backend-alternatives';
    alternatives.textContent = `${english ? 'Other options' : '其他可选平台'}：${data.alternative_backends.map((item) => item.name).join('、')}`;
    card.append(alternatives);
  }
  return card;
}

function appendFact(container, labelText, valueText) {
  const item = document.createElement('div');
  const label = document.createElement('dt');
  label.textContent = labelText;
  const value = document.createElement('dd');
  value.textContent = valueText;
  item.append(label, value);
  container.append(item);
}

function createSuggestions(suggestions, onSuggestion) {
  const container = document.createElement('div');
  container.className = 'follow-up-suggestions';
  suggestions.forEach((text) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = text;
    button.addEventListener('click', () => onSuggestion?.(text));
    container.append(button);
  });
  return container;
}
