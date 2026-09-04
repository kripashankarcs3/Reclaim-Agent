import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1680, height: 1020 } });
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const m = await page.evaluate(() => {
  const metrics = document.querySelector(".metrics-panel");
  const cases = document.querySelector(".case-feed__list");
  const timeline = document.querySelector(".stage-stepper");
  const pack = (el) => ({ scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, overflow_px: el.scrollHeight - el.clientHeight });
  return { metrics: pack(metrics), caseFeedList: pack(cases), timelineStepper: pack(timeline) };
});
console.log(JSON.stringify(m, null, 2));
await browser.close();
