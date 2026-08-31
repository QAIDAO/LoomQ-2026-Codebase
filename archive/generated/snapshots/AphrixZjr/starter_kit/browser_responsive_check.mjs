#!/usr/bin/env node

// Dependency-free responsive check for an already running Chromium-family CDP
// endpoint.  The script prints JSON only; callers decide where evidence belongs.

const cdpBase = process.argv[2] || "http://127.0.0.1:9333";
const appUrl = process.argv[3] || "http://127.0.0.1:8765/";

const viewports = [
  { label: "1366x768", width: 1366, height: 768, deviceScaleFactor: 1 },
  { label: "1280x720", width: 1280, height: 720, deviceScaleFactor: 1 },
  { label: "1024-css-pixels", width: 1024, height: 768, deviceScaleFactor: 1 },
  {
    label: "200-percent-zoom-equivalent",
    width: 640,
    height: 360,
    deviceScaleFactor: 2,
  },
];
const keyRegions = [
  ".global-header",
  ".goal-card",
  ".workspace",
  ".dialog-dock",
];

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
  let runtimeErrors = [];

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
  });

  function send(method, params = {}) {
    const id = nextId++;
    const result = new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
    });
    socket.send(JSON.stringify({ id, method, params }));
    return withTimeout(result, method);
  }

  async function waitForAppReady() {
    const deadline = Date.now() + 10000;
    const expectedUrl = new URL(appUrl).href;
    while (Date.now() < deadline) {
      try {
        const evaluated = await send("Runtime.evaluate", {
          expression: `({
            url: location.href,
            ready: document.readyState,
            regions: ${JSON.stringify(keyRegions)}.map(
              (selector) => Boolean(document.querySelector(selector))
            ),
          })`,
          returnByValue: true,
        });
        const value = evaluated.result?.value;
        if (
          value?.url === expectedUrl &&
          value.ready === "complete" &&
          value.regions?.every(Boolean)
        ) {
          return;
        }
      } catch {
        // A navigation can replace the execution context between two polls.
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`app did not become ready at ${expectedUrl}`);
  }

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Log.enable");

  const checks = [];
  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: viewport.deviceScaleFactor,
      mobile: false,
      screenWidth: viewport.width,
      screenHeight: viewport.height,
    });
    runtimeErrors = [];
    await send("Page.navigate", { url: appUrl });
    await waitForAppReady();
    await send("Runtime.evaluate", {
      expression: "new Promise(resolve => setTimeout(resolve, 500))",
      awaitPromise: true,
    });

    const expression = `(() => {
      const root = document.documentElement;
      const body = document.body;
      const width = Math.max(root?.scrollWidth || 0, body?.scrollWidth || 0);
      const height = Math.max(root?.scrollHeight || 0, body?.scrollHeight || 0);
      const selectors = ${JSON.stringify(keyRegions)};
      const regions = selectors.map((selector) => {
        const element = document.querySelector(selector);
        if (!element) return { selector, present: false };
        const rect = element.getBoundingClientRect();
        return {
          selector,
          present: true,
          left: Math.round(rect.left * 100) / 100,
          right: Math.round(rect.right * 100) / 100,
          width: Math.round(rect.width * 100) / 100,
          fits_horizontally: rect.left >= -1 && rect.right <= window.innerWidth + 1,
        };
      });
      return {
        title: document.title,
        blank: !body || !body.innerText.trim(),
        inner_width: window.innerWidth,
        inner_height: window.innerHeight,
        device_pixel_ratio: window.devicePixelRatio,
        document: { scroll_width: width, scroll_height: height },
        horizontal_overflow: width > window.innerWidth + 1,
        vertical_scrollable: height > window.innerHeight + 1,
        error_overlay: Boolean(document.querySelector('.diagnostic.error')),
        key_regions_fit_horizontally: regions.every(
          (region) => region.present && region.fits_horizontally
        ),
        regions,
      };
    })()`;
    const evaluated = await send("Runtime.evaluate", {
      expression,
      returnByValue: true,
    });
    const value = evaluated.result?.value;
    if (!value) throw new Error(`no page metrics returned for ${viewport.label}`);
    const check = {
      label: viewport.label,
      viewport: {
        width: viewport.width,
        height: viewport.height,
        device_scale_factor: viewport.deviceScaleFactor,
      },
      ...value,
      runtime_errors: [...runtimeErrors],
    };
    check.passed = Boolean(
      !check.blank &&
      !check.horizontal_overflow &&
      !check.error_overlay &&
      check.key_regions_fit_horizontally &&
      check.runtime_errors.length === 0 &&
      (viewport.width > 1024 || check.vertical_scrollable)
    );
    checks.push(check);
  }

  socket.close();
  const passed = checks.every((check) => check.passed);
  process.stdout.write(
    `${JSON.stringify({ app_url: appUrl, key_regions: keyRegions, passed, checks }, null, 2)}\n`,
  );
  if (!passed) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
