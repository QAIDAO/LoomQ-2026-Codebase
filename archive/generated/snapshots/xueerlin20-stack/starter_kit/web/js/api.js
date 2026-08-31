// Local HTTP API client for browser modules.

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch (_error) {
    throw new Error('LoomQ 服务返回了无法识别的响应');
  }
  if (!response.ok) {
    if (response.status === 404 && path === '/api/config') {
      throw new Error('后台版本过旧，请重启 LoomQ 网页服务');
    }
    throw new Error(data.error || '请求失败');
  }
  return data;
}

export const api = {
  getConfiguration() {
    return requestJson('/api/config');
  },

  saveConfiguration(configuration) {
    return requestJson('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configuration),
    });
  },

  sendChat(payload) {
    return requestJson('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  runCurrentCircuit(payload) {
    return requestJson('/api/circuit/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  resetConversation(conversationId) {
    return requestJson('/api/conversation/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    });
  },
};
