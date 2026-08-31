#!/usr/bin/env node

// Dependency-free interaction check for an already running Chromium-family
// CDP endpoint. The target app must be running without LOOMQ_LLM_* values so
// the explicit preset fallback can be verified.

const cdpBase = process.argv[2] || "http://127.0.0.1:9333";
const appUrl = process.argv[3] || "http://127.0.0.1:8765/";

function withTimeout(promise, label, milliseconds = 15000) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out`)), milliseconds);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

async function main() {
  const targets = await withTimeout(
    fetch(`${cdpBase}/json/list`).then((response) => {
      if (!response.ok) throw new Error(`CDP target list returned ${response.status}`);
      return response.json();
    }),
    "CDP discovery",
  );
  const target = targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  if (!target) throw new Error("CDP did not expose a page target");

  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await withTimeout(
    new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    }),
    "CDP WebSocket connection",
  );

  let nextId = 1;
  const pending = new Map();
  const eventWaiters = new Map();
  const runtimeErrors = [];

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result || {});
      return;
    }
    if (message.method === "Runtime.exceptionThrown") {
      const details = message.params?.exceptionDetails || {};
      runtimeErrors.push(
        details.exception?.description || details.text || "uncaught runtime exception",
      );
    }
    if (message.method === "Log.entryAdded" && message.params?.entry?.level === "error") {
      runtimeErrors.push(message.params.entry.text || "browser error log entry");
    }
    const waiters = eventWaiters.get(message.method) || [];
    eventWaiters.delete(message.method);
    waiters.forEach((resolve) => resolve(message.params || {}));
  });

  function send(method, params = {}) {
    const id = nextId++;
    const result = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    socket.send(JSON.stringify({ id, method, params }));
    return withTimeout(result, method);
  }

  function waitForEvent(method) {
    const result = new Promise((resolve) => {
      const waiters = eventWaiters.get(method) || [];
      waiters.push(resolve);
      eventWaiters.set(method, waiters);
    });
    return withTimeout(result, method);
  }

  async function evaluate(expression, awaitPromise = false) {
    const result = await send("Runtime.evaluate", {
      expression,
      awaitPromise,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text || "browser evaluation failed");
    }
    return result.result?.value;
  }

  async function waitUntil(expression, label, milliseconds = 15000) {
    const deadline = Date.now() + milliseconds;
    while (Date.now() < deadline) {
      if (await evaluate(expression)) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`${label} timed out`);
  }

  async function sessionSnapshot() {
    return evaluate(`(async () => {
      const sessionId = sessionStorage.getItem("loomq-session-id");
      const response = await fetch("/api/experiments/" + sessionId);
      if (!response.ok) throw new Error("session fetch returned " + response.status);
      return response.json();
    })()`, true);
  }

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Log.enable");
  await evaluate(`(() => {
    if (location.origin === ${JSON.stringify(new URL(appUrl).origin)}) {
      sessionStorage.removeItem("loomq-session-id");
    }
  })()`);
  await send("Storage.clearDataForOrigin", {
    origin: new URL(appUrl).origin,
    storageTypes: "all",
  });

  const loaded = waitForEvent("Page.loadEventFired");
  await send("Page.navigate", { url: appUrl });
  await loaded;
  await waitUntil(
    'Boolean(sessionStorage.getItem("loomq-session-id")) && document.querySelector("#guide-index")?.textContent.trim() === "1 / 8"',
    "fresh Bell experiment",
  );
  await waitUntil(
    'document.querySelector("#hardware-evidence-notice")?.textContent.includes("四项正式摘要均已通过") === true',
    "archived hardware replay",
  );
  // Log.enable may replay entries from the target's previous navigation. Only
  // errors emitted by the fresh experiment and the interaction belong here.
  runtimeErrors.length = 0;

  const health = await evaluate('fetch("/api/health").then(response => response.json())', true);
  const hardwareReplay = await evaluate(`(() => ({
    cards: document.querySelectorAll("#hardware-evidence-circuits .hardware-evidence-card").length,
    text: document.querySelector("#hardware-evidence-circuits")?.innerText || "",
    notice: document.querySelector("#hardware-evidence-notice")?.textContent || "",
    boundary: document.querySelector("#hardware-evidence-boundary")?.textContent || ""
  }))()`);
  const before = await sessionSnapshot();
  const initial = await evaluate(`(() => ({
    button_label: document.querySelector("#primary-action")?.textContent.trim(),
    input_value: document.querySelector("#agent-input")?.value,
    tutorial_active: document.querySelector("#main")?.classList.contains("tutorial-active"),
    guide_index: document.querySelector("#guide-index")?.textContent.trim()
  }))()`);

  await evaluate('document.querySelector("#tutorial-toggle").click()');
  await waitUntil(
    'document.querySelector("#main")?.classList.contains("tutorial-active") === true',
    "Bell tutorial activation",
  );
  const afterTutorial = await evaluate(`(() => ({
    input_value: document.querySelector("#agent-input")?.value,
    guide_index: document.querySelector("#guide-index")?.textContent.trim()
  }))()`);

  await evaluate('document.querySelector("#primary-action").click()');
  const afterFillSession = await sessionSnapshot();
  const afterFill = await evaluate(`(() => ({
    input_value: document.querySelector("#agent-input")?.value,
    focused_element: document.activeElement?.id,
    guide_index: document.querySelector("#guide-index")?.textContent.trim(),
    revision_label: document.querySelector("#revision-label")?.textContent.trim()
  }))()`);

  await evaluate('document.querySelector("#agent-form").requestSubmit()');
  await waitUntil(
    'document.querySelector("#agent-send")?.disabled === false && document.querySelector("#guide-index")?.textContent.trim() === "2 / 8"',
    "Agent preset fallback response",
  );
  const afterSendSession = await sessionSnapshot();
  const afterSend = await evaluate(`(() => ({
    status_text: document.querySelector("#agent-status")?.textContent.trim(),
    status_class: document.querySelector("#agent-status")?.className,
    focused_element: document.activeElement?.id,
    guide_index: document.querySelector("#guide-index")?.textContent.trim(),
    error_overlay: Boolean(document.querySelector(".diagnostic.error")),
    understanding_label_present: Boolean(document.querySelector(".agent-understanding")),
    last_reply: [...document.querySelectorAll(".agent-message.assistant")].at(-1)?.innerText.trim()
  }))()`);

  // Complete the remaining seven stages through the same visible Agent-first
  // interaction.  This turns the check into a full product journey instead of
  // proving only the first transition.
  const journey = [afterSendSession];
  for (let sendIndex = 1; sendIndex < 8; sendIndex += 1) {
    const beforeStage = await sessionSnapshot();
    await evaluate('document.querySelector("#primary-action").click()');
    const filled = await evaluate('document.querySelector("#agent-input")?.value');
    if (filled !== beforeStage.guide.preset_instruction) {
      throw new Error(`stage ${sendIndex + 1} did not fill its exact preset`);
    }
    await evaluate('document.querySelector("#agent-form").requestSubmit()');
    const expectedIndex = Math.min(sendIndex + 2, 8);
    const completionClause = sendIndex === 7
      ? 'document.querySelector("#primary-action")?.disabled === true'
      : `document.querySelector("#guide-index")?.textContent.trim() === "${expectedIndex} / 8"`;
    await waitUntil(
      `document.querySelector("#agent-send")?.disabled === false && (${completionClause})`,
      `Bell stage ${sendIndex + 1}`,
    );
    journey.push(await sessionSnapshot());
  }

  const afterValidation = journey[5];
  const afterRun = journey[6];
  const afterExplore = journey[7];
  const completedDom = await evaluate(`(() => ({
    result_visible: document.querySelector("#results-panel")?.hidden === false,
    count_rows: document.querySelectorAll("#counts-table tr").length,
    boundary: document.querySelector("#result-boundary")?.textContent.trim(),
    guide_complete: document.querySelector("#primary-action")?.disabled === true,
    guide_index: document.querySelector("#guide-index")?.textContent.trim()
  }))()`);

  await evaluate('document.querySelector("#undo-button").click()');
  await waitUntil(
    'document.querySelector("#qasm-editor")?.value.includes("cx q[0],q[1]") === true',
    "undo CX deletion",
  );
  const afterUndo = await sessionSnapshot();

  const checks = [
    { name: "health_reports_agent_unconfigured", passed: health.agent_configured === false },
    {
      name: "formal_hardware_replay_is_complete_and_bounded",
      passed:
        hardwareReplay.cards === 2
        && hardwareReplay.text.includes("SpinQ")
        && hardwareReplay.text.includes("OriginQ")
        && hardwareReplay.notice.includes("四项正式摘要均已通过")
        && hardwareReplay.boundary.includes("不能单独认证纠缠"),
    },
    { name: "button_label_is_fill_instruction", passed: initial.button_label === "填入本阶段指令" },
    { name: "initial_agent_input_is_empty", passed: initial.input_value === "" },
    { name: "tutorial_does_not_prefill_agent_input", passed: afterTutorial.input_value === "" },
    {
      name: "button_fills_exact_current_preset",
      passed: afterFill.input_value === before.guide.preset_instruction,
    },
    { name: "button_focuses_agent_input", passed: afterFill.focused_element === "agent-input" },
    {
      name: "button_does_not_advance_stage",
      passed: afterFillSession.guide_stage === before.guide_stage,
    },
    {
      name: "button_does_not_change_circuit_revision",
      passed: afterFillSession.circuit_revision === before.circuit_revision,
    },
    { name: "button_does_not_change_qasm", passed: afterFillSession.qasm === before.qasm },
    {
      name: "send_advances_exactly_one_stage",
      passed: afterSendSession.guide_stage === before.guide_stage + 1,
    },
    {
      name: "fallback_status_is_explicit",
      passed:
        afterSend.status_text === "本地预置回退 · 未调用模型"
        && afterSend.status_class.split(/\s+/).includes("fallback"),
    },
    {
      name: "fallback_reply_is_explicit",
      passed: afterSend.last_reply?.includes("本地预置回复｜未调用模型") === true,
    },
    {
      name: "fallback_has_no_model_understanding_label",
      passed: afterSend.understanding_label_present === false,
    },
    { name: "send_refocuses_agent_input", passed: afterSend.focused_element === "agent-input" },
    { name: "no_error_overlay", passed: afterSend.error_overlay === false },
    {
      name: "all_eight_agent_sends_completed",
      passed:
        journey.length === 8
        && journey.map((session) => session.guide_stage).join(",") === "1,2,3,4,5,6,7,7"
        && afterExplore.guide_complete === true,
    },
    {
      name: "validation_precedes_run_and_is_structurally_safe",
      passed:
        afterValidation.result === null
        && afterValidation.validation?.runnable === true
        && afterValidation.validation?.measurements?.status === "pass"
        && afterValidation.validation?.target?.status === "pass",
    },
    {
      name: "run_produces_result_table_and_boundary",
      passed:
        afterRun.result?.status === "completed"
        && completedDom.result_visible
        && completedDom.count_rows > 0
        && completedDom.boundary?.includes("真机计数") === true,
    },
    {
      name: "explore_deletes_cx",
      passed:
        !afterExplore.qasm.includes("cx q[0],q[1]")
        && completedDom.guide_complete
        && completedDom.guide_index === "8 / 8",
    },
    {
      name: "undo_restores_deleted_cx",
      passed: afterUndo.qasm.includes("cx q[0],q[1]") && afterUndo.can_redo === true,
    },
    { name: "no_runtime_errors", passed: runtimeErrors.length === 0 },
  ];
  const passed = checks.every((item) => item.passed);
  const result = {
    app_url: appUrl,
    cdp_endpoint: cdpBase,
    expected_mode: "LLM environment absent; exact current Bell preset only",
    passed,
    checks,
    observations: {
      initial,
      hardware_replay: hardwareReplay,
      after_tutorial: afterTutorial,
      after_fill: afterFill,
      after_send: afterSend,
      guide_stage_before: before.guide_stage,
      guide_stage_after_fill: afterFillSession.guide_stage,
      guide_stage_after_send: afterSendSession.guide_stage,
      circuit_revision_before: before.circuit_revision,
      circuit_revision_after_fill: afterFillSession.circuit_revision,
      guide_stages_after_each_send: journey.map((session) => session.guide_stage),
      validation_after_stage_six: afterValidation.validation,
      run_id_after_stage_seven: afterRun.result?.run_id,
      qasm_after_explore: afterExplore.qasm,
      qasm_after_undo: afterUndo.qasm,
      completed_dom: completedDom,
    },
    runtime_errors: runtimeErrors,
  };

  socket.close();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!passed) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
