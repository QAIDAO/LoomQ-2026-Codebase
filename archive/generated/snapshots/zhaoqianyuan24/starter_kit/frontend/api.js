export class ApiError extends Error {
  constructor(message, code = "request_failed", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function serviceUnavailableError() {
  return new ApiError(
    "LoomQ Product Service 未连接。请通过 http://127.0.0.1:4173/ 打开 Playground。",
    "product_service_unavailable",
  );
}

async function requestJson(path, options, fallbackMessage) {
  if (window.location.protocol === "file:") throw serviceUnavailableError();

  let response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...options });
  } catch {
    throw serviceUnavailableError();
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      payload.message || `${fallbackMessage} ${response.status}`,
      payload.error || "request_failed",
      response.status,
    );
  }
  return payload;
}

async function postJson(path, body, fallbackMessage) {
  return requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }, fallbackMessage);
}

export async function getLlmConfig() {
  return requestJson("/api/llm-config", { method: "GET" }, "配置服务返回");
}

export async function testLlmConfig(config) {
  return postJson("/api/llm-config/test", config, "连接测试返回");
}

export async function applyLlmConfig() {
  return postJson("/api/llm-config", {}, "配置服务返回");
}

export async function generateExperiment(prompt) {
  const payload = await postJson("/api/generate", { prompt }, "生成服务返回");
  if (payload.response_type === "backend_recommendation" && payload.backend_recommendation) {
    return payload;
  }
  if (!payload.experiment || (payload.response_type && payload.response_type !== "experiment")) {
    throw new Error("生成服务没有返回有效的实验或后端推荐。");
  }
  return { response_type: "experiment", experiment: payload.experiment };
}

export async function askQuestion(question, context = {}, history = []) {
  const payload = await postJson(
    "/api/ask",
    { question, context, history },
    "问答服务返回",
  );
  if (typeof payload.answer !== "string" || !payload.answer.trim()) {
    throw new Error("问答服务没有返回有效回答。");
  }
  return payload;
}

export async function runExperiment(qasm, shots, backendId) {
  const payload = await postJson(
    "/api/run",
    { qasm, shots, backend_id: backendId },
    "运行服务返回",
  );
  if (!payload.result || !payload.result.counts) {
    throw new Error("运行服务没有返回有效结果。");
  }
  return payload.result;
}
