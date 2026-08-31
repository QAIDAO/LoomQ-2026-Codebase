import {chromium} from "playwright";
import {tmpdir} from "node:os";
import {join} from "node:path";

const baseUrl = process.env.LOOMQ_BASE_URL || "http://127.0.0.1:8766";
const outputDir = tmpdir();
const browser = await chromium.launch();

async function inspectTextFit(page, scope = "body") {
  return page.locator(scope).evaluate((root) => {
    const selector = "h1,h2,h3,p,label,legend,summary,small,button,span,strong,dt,dd,li";
    const issues = [...root.querySelectorAll(selector)].flatMap((node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (
        node.closest('.sr-only, [aria-hidden="true"], [hidden]') ||
        style.display === "none" ||
        style.visibility === "hidden" ||
        rect.width <= 0 ||
        rect.height <= 0 ||
        rect.right <= 0 ||
        rect.left >= innerWidth
      ) return [];
      let hasHorizontalScroller = false;
      for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        if (
          ["auto", "scroll"].includes(getComputedStyle(parent).overflowX) &&
          parent.scrollWidth > parent.clientWidth + 2
        ) {
          hasHorizontalScroller = true;
          break;
        }
      }
      const ownOverflow = node.scrollWidth > node.clientWidth + 2 && !["auto", "scroll"].includes(style.overflowX);
      const viewportOverflow = !hasHorizontalScroller && (rect.left < -2 || rect.right > innerWidth + 2);
      if (!ownOverflow && !viewportOverflow) return [];
      return [{
        tag: node.tagName.toLowerCase(),
        text: node.textContent.trim().replace(/\s+/g, " ").slice(0, 80),
        ownOverflow,
        viewportOverflow,
      }];
    });
    if (document.documentElement.scrollWidth > innerWidth + 2) {
      issues.push({
        tag: "document",
        text: "页面宽度超过视口",
        scrollWidth: document.documentElement.scrollWidth,
        viewportWidth: innerWidth,
      });
    }
    const title = root.querySelector("#welcomeTitle");
    const titleRect = title?.getBoundingClientRect();
    if (title && !title.closest("[hidden]") && titleRect.width > 0 && titleRect.height > 0) {
      const walker = document.createTreeWalker(title, NodeFilter.SHOW_TEXT);
      const tops = [];
      while (walker.nextNode()) {
        const range = document.createRange();
        range.selectNodeContents(walker.currentNode);
        for (const rect of range.getClientRects()) if (rect.width > 0) tops.push(Math.round(rect.top));
      }
      const lineCount = new Set(tops).size;
      if (lineCount !== 2) issues.push({tag: "h1", text: title.textContent.trim(), lineCount, expectedLines: 2});
    }
    return issues;
  });
}

async function inspectLineBreaks(page, scope = "body") {
  return page.locator(scope).evaluate((root) => (
    [...root.querySelectorAll("h1,h2,h3,p,summary,button,label,small")]
      .flatMap((node) => {
        if (node.closest('.sr-only, [aria-hidden="true"], [hidden]')) return [];
        const style = getComputedStyle(node);
        const bounds = node.getBoundingClientRect();
        if (style.display === "none" || style.visibility === "hidden" || bounds.width <= 0 || bounds.height <= 0) return [];
        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
        const rows = new Map();
        while (walker.nextNode()) {
          if (!walker.currentNode.textContent.trim()) continue;
          const range = document.createRange();
          range.selectNodeContents(walker.currentNode);
          for (const rect of range.getClientRects()) {
            if (rect.width <= 0) continue;
            const roundedTop = Math.round(rect.top);
            const key = [...rows.keys()].find((top) => Math.abs(top - roundedTop) <= 3) ?? roundedTop;
            const row = rows.get(key) || {left: rect.left, right: rect.right};
            row.left = Math.min(row.left, rect.left);
            row.right = Math.max(row.right, rect.right);
            rows.set(key, row);
          }
        }
        const widths = [...rows.values()].map(({left, right}) => right - left);
        if (widths.length < 2) return [];
        const widest = Math.max(...widths);
        const last = widths.at(-1);
        const heading = /^H[1-3]$/.test(node.tagName);
        const minimumLastLine = heading ? widest * 0.42 : Number.parseFloat(style.fontSize) * 2.1;
        if (last >= minimumLastLine) return [];
        return [{
          tag: node.tagName.toLowerCase(),
          text: node.textContent.trim().replace(/\s+/g, " ").slice(0, 100),
          lineWidths: widths.map((width) => Math.round(width)),
          reason: heading ? "标题末行过短" : "末行出现孤字或短词",
        }];
      })
  ));
}

async function inspectContrast(page, scope = "body") {
  return page.locator(scope).evaluate((root) => {
    const parseColor = (value) => {
      const match = value.match(/rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:[, /]+([\d.]+))?\)/);
      return match ? [Number(match[1]), Number(match[2]), Number(match[3]), match[4] === undefined ? 1 : Number(match[4])] : null;
    };
    const composite = (foreground, background) => {
      const alpha = foreground[3] + background[3] * (1 - foreground[3]);
      if (!alpha) return [255, 255, 255, 1];
      return [
        (foreground[0] * foreground[3] + background[0] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[1] * foreground[3] + background[1] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[2] * foreground[3] + background[2] * background[3] * (1 - foreground[3])) / alpha,
        alpha,
      ];
    };
    const luminance = (color) => {
      const channels = color.slice(0, 3).map((channel) => {
        const value = channel / 255;
        return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
      });
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const ratio = (a, b) => {
      const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (lighter + 0.05) / (darker + 0.05);
    };
    const effectiveBackground = (node) => {
      const chain = [];
      for (let element = node; element; element = element.parentElement) chain.push(element);
      let result = [255, 255, 255, 1];
      for (const element of chain.reverse()) {
        const color = parseColor(getComputedStyle(element).backgroundColor);
        if (color && color[3] > 0) result = composite(color, result);
      }
      return result;
    };
    return [...root.querySelectorAll("*")].flatMap((node) => {
      const text = [...node.childNodes]
        .filter((child) => child.nodeType === Node.TEXT_NODE)
        .map((child) => child.textContent)
        .join(" ")
        .trim()
        .replace(/\s+/g, " ");
      if (!text || node.matches("script,style,option") || node.closest('.sr-only, [aria-hidden="true"], [hidden]')) return [];
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      let opacity = 1;
      for (let element = node; element; element = element.parentElement) opacity *= Number.parseFloat(getComputedStyle(element).opacity);
      if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        opacity < 0.1 ||
        rect.width <= 0 ||
        rect.height <= 0 ||
        node.matches(":disabled")
      ) return [];
      const foreground = parseColor(style.color);
      const background = effectiveBackground(node);
      if (!foreground) return [];
      const renderedForeground = composite(foreground, background);
      const contrast = ratio(renderedForeground, background);
      const fontSize = Number.parseFloat(style.fontSize);
      const fontWeight = Number.parseInt(style.fontWeight, 10) || 400;
      const largeText = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700);
      const minimum = largeText ? 3 : 4.5;
      if (contrast + 0.01 >= minimum) return [];
      return [{
        tag: node.tagName.toLowerCase(),
        selector: node.id
          ? `#${node.id}`
          : `${node.tagName.toLowerCase()}${[...node.classList].map((name) => `.${name}`).join("")}`,
        text: text.slice(0, 90),
        contrast: Number(contrast.toFixed(2)),
        minimum,
        color: style.color,
        background: `rgb(${background.slice(0, 3).map(Math.round).join(", ")})`,
      }];
    });
  });
}

async function openCourse(viewport, filename, theme = "dark") {
  const page = await browser.newPage({viewport, colorScheme: "dark"});
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(baseUrl, {waitUntil: "networkidle"});
  if (theme === "light") await page.locator("#themeToggle").click();
  await page.locator('[data-studio-nav="learn"]').click();
  await page.locator("#courseResultStatus").getByText("L1 模拟完成").waitFor();
  await page.locator(".course-terms summary").click();
  await page.screenshot({path: join(outputDir, filename), fullPage: true});
  const textFit = [];
  const lineBreaks = [];
  const contrast = [];
  const lessonCount = await page.locator("#courseSidebarList button").count();
  for (let index = 0; index < lessonCount; index += 1) {
    if (index > 0) {
      await page.locator("#courseSidebarList button").nth(index).click();
      await page.locator("#courseResultStatus").getByText("L1 模拟完成").waitFor();
    }
    const lesson = await page.locator("#courseTitle").innerText();
    textFit.push(...(await inspectTextFit(page)).map((issue) => ({lesson, ...issue})));
    lineBreaks.push(...(await inspectLineBreaks(page)).map((issue) => ({lesson, ...issue})));
    contrast.push(...(await inspectContrast(page)).map((issue) => ({lesson, ...issue})));
  }
  const typography = await page.locator('[data-screen="course"] :is(h1,h2,h3,p,label,legend,summary,small,button,option)').evaluateAll((nodes) => (
    nodes
      .filter((node) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      })
      .map((node) => {
        const style = getComputedStyle(node);
        return {
          text: node.textContent.trim().replace(/\s+/g, " ").slice(0, 90),
          fontSize: Number.parseFloat(style.fontSize),
          color: style.color,
          background: style.backgroundColor,
          tag: node.tagName.toLowerCase(),
        };
      })
      .filter((item) => item.text)
  ));
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(250);
  const backToTopVisible = await page.locator("#courseBackToTop").evaluate((node) => (
    !node.hidden && node.classList.contains("is-visible") && getComputedStyle(node).pointerEvents !== "none"
  ));
  await page.screenshot({path: join(outputDir, filename.replace(".png", "-back-to-top.png"))});
  await page.locator("#courseBackToTop").click();
  await page.waitForFunction(() => scrollY < 5);
  await page.close();
  return {errors, typography, textFit, lineBreaks, contrast, backToTopVisible};
}

async function captureScreen(viewport, filename, theme, destination) {
  const page = await browser.newPage({viewport, colorScheme: "dark"});
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(baseUrl, {waitUntil: "networkidle"});
  if (theme === "light") await page.locator("#themeToggle").click();
  if (destination) await page.locator(`[data-studio-nav="${destination}"]`).click();
  await page.waitForTimeout(650);
  const textFit = await inspectTextFit(page);
  const lineBreaks = await inspectLineBreaks(page);
  const contrast = await inspectContrast(page);
  await page.screenshot({path: join(outputDir, filename), fullPage: destination === "create"});
  await page.close();
  return {errors, textFit, lineBreaks, contrast};
}

async function captureHandoff(filename, theme) {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: "dark"});
  await page.goto(baseUrl, {waitUntil: "networkidle"});
  if (theme === "light") await page.locator("#themeToggle").click();
  await page.locator(".story-next").scrollIntoViewIfNeeded();
  await page.waitForTimeout(650);
  await page.locator("#courseMap summary").click();
  const lineBreaks = await inspectLineBreaks(page, ".story-next");
  const contrast = await inspectContrast(page, ".story-next");
  const hoverContrast = [];
  const cards = page.locator("#courseList button");
  for (let index = 0; index < await cards.count(); index += 1) {
    await cards.nth(index).hover();
    hoverContrast.push(...(await inspectContrast(page, ".story-next")).map((issue) => ({card: index + 1, ...issue})));
  }
  const cueVisible = await page.locator(".story-scroll-cue").evaluate((node) => {
    const style = getComputedStyle(node);
    return style.visibility !== "hidden" && Number.parseFloat(style.opacity) > 0.01;
  });
  await page.screenshot({path: join(outputDir, filename)});
  await page.close();
  return {cueVisible, lineBreaks, contrast, hoverContrast};
}

async function captureStoryScenes(theme) {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, colorScheme: "dark"});
  await page.goto(baseUrl, {waitUntil: "networkidle"});
  if (theme === "light") await page.locator("#themeToggle").click();
  for (const index of [1, 3]) {
    await page.locator(".story-frame").nth(index).scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await page.screenshot({path: join(outputDir, `loomq-story-${index}-${theme}.png`)});
  }
  const lineBreaks = await inspectLineBreaks(page);
  const contrast = await inspectContrast(page);
  await page.close();
  return {lineBreaks, contrast};
}

async function captureHardwareControls(theme) {
  const page = await browser.newPage({viewport: {width: 1024, height: 900}, colorScheme: "dark"});
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(baseUrl, {waitUntil: "networkidle"});
  if (theme === "light") await page.locator("#themeToggle").click();
  await page.locator('[data-studio-nav="create"]').click();
  const environmentHiddenBeforeQasm =
    await page.locator("#environmentChooser").getAttribute("hidden") !== null;
  await page.evaluate(() => {
    document.querySelector("#agentQasm").textContent = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q[0] -> c[0];`;
    document.querySelector("#environmentChooser").hidden = false;
  });
  const prematureLocalValidationCount = await page.locator(".local-validation").count();
  await page.locator("#environmentRun:not([disabled])").waitFor();
  await page.locator("#environmentRun").click();
  await page.waitForTimeout(1000);
  if (await page.locator("#environmentResult").getAttribute("hidden") !== null) {
    throw new Error(`local environment audit failed: ${await page.locator("#environmentStatus").textContent()}`);
  }
  const localResultVisible = await page.locator("#environmentCounts").getAttribute("aria-label");
  await page.locator("#environmentStatus").evaluate((node) => { node.textContent = "上个任务已完成"; });
  await page.locator('input[name="executionKind"][value="qpu"]').check();
  const qpuFeedback = await page.locator("#environmentStatus").textContent();
  await page.locator('input[name="executionKind"][value="custom"]').check();
  const formTextFit = await inspectTextFit(page, "#hardwareConfig");
  const formContrast = await inspectContrast(page, "#hardwareConfig");
  const profilesTextFit = await inspectTextFit(page, "#hardwareProfiles");
  const profilesContrast = await inspectContrast(page, "#hardwareProfiles");
  await page.locator('[data-studio-nav="history"]').click();
  await page.locator(".hardware-history-item").first().waitFor();
  const historyCount = await page.locator(".hardware-history-item").count();
  await page.locator(".hardware-history-item details").first().click();
  await page.locator(".hardware-history-detail pre").first().waitFor();
  const historyTextFit = await inspectTextFit(page, "#hardwareHistory");
  const historyContrast = await inspectContrast(page, "#hardwareHistory");
  await page.screenshot({path: join(outputDir, `loomq-hardware-history-${theme}.png`)});
  await page.locator('[data-studio-nav="create"]').click();
  await page.evaluate(() => {
    renderActiveHardwareJob({
      task_id: "1234567890abcdef1234567890abcdef",
      status: "running",
      stage_message: "本源平台正在排队、映射物理 qubit 或执行电路。",
      provider_job_id: "PROVIDER-JOB-123",
      created_at: new Date(Date.now() - 125000).toISOString(),
    });
  });
  const currentTextFit = await inspectTextFit(page, "#hardwareCurrent");
  const currentContrast = await inspectContrast(page, "#hardwareCurrent");
  const currentStage = await page.locator("#hardwareCurrentStage").textContent();
  await page.evaluate(() => {
    document.querySelector("#hardwareConfirmPlatform").textContent = "本源悟空 180";
    document.querySelector("#hardwareConfirm").showModal();
  });
  const dialogTextFit = await inspectTextFit(page, "#hardwareConfirm");
  const dialogContrast = await inspectContrast(page, "#hardwareConfirm");
  await page.screenshot({path: join(outputDir, `loomq-hardware-controls-${theme}.png`)});
  await page.close();
  return {
    errors,
    environmentHiddenBeforeQasm,
    localResultVisible,
    prematureLocalValidationCount,
    qpuFeedback,
    historyCount,
    currentStage,
    textFit: [...formTextFit, ...profilesTextFit, ...historyTextFit, ...currentTextFit, ...dialogTextFit],
    contrast: [...formContrast, ...profilesContrast, ...historyContrast, ...currentContrast, ...dialogContrast],
  };
}

const desktop = await openCourse({width: 1440, height: 1000}, "loomq-course-dark-desktop.png");
const tablet = await openCourse({width: 1024, height: 900}, "loomq-course-dark-tablet.png");
const mobile = await openCourse({width: 390, height: 844}, "loomq-course-dark-mobile.png");
const lightDesktop = await openCourse({width: 1440, height: 1000}, "loomq-course-light-desktop.png", "light");
const lightTablet = await openCourse({width: 1024, height: 900}, "loomq-course-light-tablet.png", "light");
const lightMobile = await openCourse({width: 390, height: 844}, "loomq-course-light-mobile.png", "light");
const screenErrors = {
  homeDark: await captureScreen({width: 1440, height: 1000}, "loomq-home-dark.png", "dark"),
  homeLight: await captureScreen({width: 1440, height: 1000}, "loomq-home-light.png", "light"),
  homeMobileDark: await captureScreen({width: 390, height: 844}, "loomq-home-dark-mobile.png", "dark"),
  homeMobileLight: await captureScreen({width: 390, height: 844}, "loomq-home-light-mobile.png", "light"),
  playgroundDark: await captureScreen({width: 1440, height: 1000}, "loomq-playground-dark.png", "dark", "create"),
  playgroundLight: await captureScreen({width: 1440, height: 1000}, "loomq-playground-light.png", "light", "create"),
};
const handoffs = {
  dark: await captureHandoff("loomq-handoff-dark.png", "dark"),
  light: await captureHandoff("loomq-handoff-light.png", "light"),
};
const storyScenes = {
  dark: await captureStoryScenes("dark"),
  light: await captureStoryScenes("light"),
};
const hardwareControls = {
  dark: await captureHardwareControls("dark"),
  light: await captureHardwareControls("light"),
};
const courseAudits = [desktop, tablet, mobile, lightDesktop, lightTablet, lightMobile];
console.log(JSON.stringify({desktop, tablet, mobile, lightDesktop, lightTablet, lightMobile, screenErrors, handoffs, storyScenes, hardwareControls}, null, 2));
const browserErrors = [
  ...courseAudits.flatMap((result) => result.errors),
  ...Object.values(screenErrors).flatMap((result) => result.errors),
  ...Object.values(hardwareControls).flatMap((result) => result.errors),
];
const textFitIssues = [
  ...courseAudits.flatMap((result) => result.textFit),
  ...Object.values(screenErrors).flatMap((result) => result.textFit),
  ...Object.values(hardwareControls).flatMap((result) => result.textFit),
];
const contrastIssues = [
  ...courseAudits.flatMap((result) => result.contrast),
  ...Object.values(screenErrors).flatMap((result) => result.contrast),
  ...Object.values(handoffs).flatMap((result) => [...result.contrast, ...result.hoverContrast]),
  ...Object.values(storyScenes).flatMap((result) => result.contrast),
  ...Object.values(hardwareControls).flatMap((result) => result.contrast),
];
const lineBreakIssues = [
  ...courseAudits.flatMap((result) => result.lineBreaks),
  ...Object.values(screenErrors).flatMap((result) => result.lineBreaks),
  ...Object.values(handoffs).flatMap((result) => result.lineBreaks),
  ...Object.values(storyScenes).flatMap((result) => result.lineBreaks),
];
if (
  browserErrors.length ||
  textFitIssues.length ||
  lineBreakIssues.length ||
  contrastIssues.length ||
  !courseAudits.every(({backToTopVisible}) => backToTopVisible) ||
  Object.values(hardwareControls).some(({localResultVisible}) => !localResultVisible?.includes("1 为 1024 次")) ||
  Object.values(hardwareControls).some(({prematureLocalValidationCount}) => prematureLocalValidationCount !== 0) ||
  Object.values(hardwareControls).some(({qpuFeedback}) => qpuFeedback !== "") ||
  Object.values(hardwareControls).some(({historyCount}) => historyCount < 1) ||
  Object.values(hardwareControls).some(({currentStage}) => !currentStage?.includes("映射物理 qubit")) ||
  Object.values(handoffs).some(({cueVisible}) => cueVisible)
) {
  process.exitCode = 1;
}
await browser.close();
