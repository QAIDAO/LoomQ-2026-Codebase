import {chromium} from "playwright";

const provider = process.argv[2];
const confirmations = {
  spinq: "SPINQ_REAL_QPU",
  originq: "ORIGINQ_WUKONG_180_REAL_QPU",
};
if (process.argv[3] !== confirmations[provider]) {
  throw new Error("Explicit provider confirmation is required.");
}

const labels = {
  spinq: "系统配置 · SpinQ",
  originq: "系统配置 · 本源悟空",
};
const qasm = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];`;

const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8766", {waitUntil: "networkidle"});
  await page.locator('[data-studio-nav="create"]').click();
  await page.locator("#agentQasm").evaluate((node, value) => {
    node.textContent = value;
  }, qasm);
  await page.locator('input[name="executionKind"][value="qpu"]').check();
  const profile = page.locator(".hardware-profile").filter({hasText: labels[provider]});
  await profile.locator('input[name="hardwareProfile"]').check();
  await page.locator("#environmentRun").click();
  await page.locator("#hardwareConfirmSubmit").click();
  await page.waitForFunction(
    () => {
      const text = document.querySelector("#environmentStatus")?.textContent || "";
      return text.includes("已完成") || text.includes("失败") || text.includes("无法读取");
    },
    undefined,
    {timeout: 1_800_000, polling: 2_000},
  );
  const result = {
    status: await page.locator("#environmentStatus").textContent(),
    counts: await page.locator("#environmentCounts").getAttribute("aria-label"),
    provenance: await page.locator("#environmentProvenance").textContent(),
  };
  console.log(JSON.stringify(result, null, 2));
  if (!result.status.includes("已完成") || !result.counts) process.exitCode = 1;
} finally {
  await browser.close();
}
