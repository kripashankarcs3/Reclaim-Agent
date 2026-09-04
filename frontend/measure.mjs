import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1680, height: 1020 } });
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const m = await page.evaluate(() => {
  const shell = document.querySelector(".app-shell");
  const header = document.querySelector(".app-header");
  const grid = document.querySelector(".app-grid");
  const policy = document.querySelector(".policy-console");
  const timeline = document.querySelector(".timeline-panel");
  return {
    window_innerHeight: window.innerHeight,
    body_scrollHeight: document.body.scrollHeight,
    shell_clientHeight: shell.clientHeight,
    shell_scrollHeight: shell.scrollHeight,
    header_height: header.getBoundingClientRect().height,
    grid_height: grid.getBoundingClientRect().height,
    policy_height: policy.getBoundingClientRect().height,
    timeline_bottom: timeline.getBoundingClientRect().bottom,
    policy_top: policy.getBoundingClientRect().top,
    overlap: timeline.getBoundingClientRect().bottom - policy.getBoundingClientRect().top,
  };
});
console.log(JSON.stringify(m, null, 2));
await browser.close();
