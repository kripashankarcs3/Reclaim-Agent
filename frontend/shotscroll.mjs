import { chromium } from "playwright";
const [,, outPath, clickSel, scrollSel] = process.argv;
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1680, height: 1020 } });
page.on("pageerror", (err) => console.error("[pageerror]", err.message));
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
if (clickSel) {
  await page.click(clickSel);
  await page.waitForTimeout(700);
}
if (scrollSel) {
  await page.locator(scrollSel).last().scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
}
await page.screenshot({ path: outPath, fullPage: true });
await browser.close();
console.log("saved", outPath);
