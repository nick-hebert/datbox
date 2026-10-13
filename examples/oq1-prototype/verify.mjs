// Offline verification: load each file with ALL network routes aborted, record
// any request attempt, console errors, page errors; exercise filters; screenshot.
import { chromium } from "playwright";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

const dist = resolve(new URL(".", import.meta.url).pathname, "dist");
const files = ["oq1-echarts.html", "oq1-plotly.html", "oq1-vegalite.html"];
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });

for (const f of files) {
  const path = resolve(dist, f);
  const html = readFileSync(path, "utf8");
  // static scan: any absolute URL in src/href, any @import / url(http
  const external = [...html.matchAll(/(?:src|href)=["'](https?:)?\/\/[^"']+/g)].map((m) => m[0]);
  const imports = [...html.matchAll(/@import\s+url\(|url\(\s*["']?https?:/g)].length;

  const report = { file: f, size_mb: +(statSync(path).size / 1e6).toFixed(2), static_external_refs: external.length, static_css_remote: imports, requests_attempted: [], console_errors: [], page_errors: [] };
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 }, colorScheme: scheme, offline: true });
    const page = await ctx.newPage();
    await page.route("**/*", (route) => { const u = route.request().url(); if (!u.startsWith("file://")) { report.requests_attempted.push(u); return route.abort(); } route.continue(); });
    page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") report.console_errors.push(`${scheme}: ${m.text().slice(0, 200)}`); });
    page.on("pageerror", (e) => report.page_errors.push(`${scheme}: ${e.message.slice(0, 200)}`));
    await page.goto("file://" + path, { waitUntil: "load" });
    await page.waitForTimeout(1200);
    report[`kpi_${scheme}`] = await page.$$eval(".kpi .value", (els) => els.map((e) => e.textContent));
    await page.screenshot({ path: resolve(dist, f.replace(".html", `-${scheme}.png`)), fullPage: true });
    if (scheme === "light") {
      // cross-filter via dropdown, then via a click on the bar chart
      await page.selectOption(".filters select >> nth=1", "Software");
      await page.waitForTimeout(600);
      report.kpi_after_dropdown = await page.$$eval(".kpi .value", (els) => els.map((e) => e.textContent));
      const plot = await page.$("#plot-rev_by_region");
      const box = await plot.boundingBox();
      // click near the bottom of the first (tallest) bar
      await page.mouse.click(box.x + box.width * 0.19, box.y + box.height * 0.8);
      await page.waitForTimeout(600);
      report.filters_after_click = await page.evaluate(() => window.DAT.state.filters);
      report.kpi_after_click = await page.$$eval(".kpi .value", (els) => els.map((e) => e.textContent));
      await page.screenshot({ path: resolve(dist, f.replace(".html", "-filtered.png")), fullPage: true });
      // hover the line chart and grab whatever tooltip DOM appears
      const lp = await page.$("#plot-rev_by_month"); const lb = await lp.boundingBox();
      await page.mouse.move(lb.x + lb.width * 0.5, lb.y + lb.height * 0.45);
      await page.waitForTimeout(500);
      report.tooltip_text = await page.evaluate(() => {
        const cands = [...document.querySelectorAll("#vg-tooltip-element, .hoverlayer, div[style*='z-index: 9999999']")];
        return cands.map((c) => c.textContent.trim().replace(/\s+/g, " ").slice(0, 120)).filter(Boolean)[0] || null;
      });
    }
    await ctx.close();
  }
  console.log(JSON.stringify(report, null, 1));
}
await browser.close();
