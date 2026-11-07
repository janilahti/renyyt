const { test, expect } = require("@playwright/test");

const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;

function bins(dates) {
  return { services: dates.map((date, index) => ({
    ASTAsnro: `SYNTHETIC-${index}`, ASTTyyppi: "1", ASTPos: "1",
    ASTNimi: `Synthetic bin ${index}`, ASTNextDate: date, ASTVali: "4",
    tariff: { productgroup: "TEST" }
  })), warnings: [] };
}

async function openAt(page, time) {
  const start = new Date(time);
  await page.clock.install({ time: new Date(start.getTime() - MINUTE) });
  await page.addInitScript(() => {
    window.refreshRandomDraws = 0;
    Math.random = () => { window.refreshRandomDraws++; return 241.5 / 841; };
  });
  await page.goto("/");
  await page.clock.pauseAt(start);
}

async function fetchBins(page, remember = false) {
  await page.locator("#username").fill("synthetic-account");
  await page.locator("#password").fill("synthetic-password");
  await page.locator("#remember").setChecked(remember);
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
}

for (const dates of [[null], [null, null], [null, "2026-11-21"], []]) {
  test(`missing collection dates retry and recover: ${JSON.stringify(dates)}`, async ({ page }) => {
    let requests = 0;
    await page.route("**/api/v1/renyyt", route => {
      requests++;
      return route.fulfill({ json: bins(requests === 1 ? dates : ["2026-11-14", "2026-11-15"]) });
    });
    await openAt(page, "2026-11-07T10:00:00Z");
    await fetchBins(page);
    await expect(page.locator("#resultMeta")).toContainText("10.30");
    await expect(page.locator("#cards .card")).toHaveCount(dates.filter(Boolean).length);
    await page.clock.runFor(30 * MINUTE - 1);
    expect(requests).toBe(1);
    await page.clock.runFor(1);
    await expect(page.locator("#cards .card")).toHaveCount(2);
    expect(requests).toBe(2);
    await page.clock.runFor(30 * MINUTE);
    expect(requests, "recovered dates must replace the short retry schedule").toBe(2);
  });
}

test("overnight refresh keeps its random second across midnight and UI changes", async ({ page }) => {
  let requests = 0;
  let releaseRefresh;
  const refreshPending = new Promise(resolve => { releaseRefresh = resolve; });
  await page.route("**/api/v1/renyyt", async route => {
    requests++;
    if (requests === 2) await refreshPending;
    await route.fulfill({ json: bins([requests === 1 ? "2026-11-07" : "2026-11-14"]) });
  });
  await openAt(page, "2026-11-07T23:59:59Z");
  await fetchBins(page);
  await expect(page.locator("#resultMeta")).toContainText("00.05");
  await expect(page.locator("#resultMeta")).not.toContainText("00.05.01");
  await page.locator("#themeSelect").selectOption("dark");
  await page.locator("#compactViewBtn").click();
  await page.clock.runFor(1000 + 5 * MINUTE);
  expect(requests, "00:05:00 is still one second before the chosen fetch").toBe(1);
  expect(await page.evaluate(() => window.refreshRandomDraws)).toBe(1);
  await page.clock.runFor(1000);
  await expect.poll(() => requests).toBe(2);
  await page.evaluate(() => {
    window.document.dispatchEvent(new window.Event("visibilitychange"));
    window.document.dispatchEvent(new window.Event("visibilitychange"));
  });
  expect(requests, "resuming during a running request must not duplicate it").toBe(2);
  releaseRefresh();
  await expect(page.locator("#cards .date")).toContainText("14.11.2026");
  await expect.poll(() => page.evaluate(() => window.refreshRandomDraws)).toBe(2);
});

test("long intervals avoid timer overflow and catch up after sleep without redrawing", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/v1/renyyt", route => {
    requests++;
    return route.fulfill({ json: bins([requests === 1 ? "2026-12-12" : "2027-01-16"]) });
  });
  await openAt(page, "2026-11-07T10:00:00Z");
  await fetchBins(page);
  // Playwright itself limits a single fastForward number to signed 32 bits.
  await page.clock.fastForward(13 * DAY);
  await page.clock.fastForward(13 * DAY);
  expect(requests).toBe(1);
  expect(await page.evaluate(() => window.refreshRandomDraws)).toBe(1);
  const due = new Date("2026-12-13T00:05:01Z").getTime();
  const remaining = due - await page.evaluate(() => Date.now());
  await page.clock.fastForward(remaining - 1);
  expect(requests).toBe(1);
  await page.clock.runFor(1000);
  await expect.poll(() => requests).toBe(2);
  await expect(page.locator("#cards .date")).toContainText("16.1.2027");
});

test("cached fallback after a failed initial fetch retries without a reload", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/v1/renyyt", route => {
    requests++;
    return requests === 2
      ? route.fulfill({ status: 503, json: { error: "Synthetic offline failure" } })
      : route.fulfill({ json: bins(["2026-11-21"]) });
  });
  await openAt(page, "2026-11-07T10:00:00Z");
  await fetchBins(page, true);
  await page.reload();
  await fetchBins(page, true);
  await expect(page.locator("#resultMeta")).toContainText("10.30");
  await page.clock.runFor(30 * MINUTE);
  await expect.poll(() => requests).toBe(3);
  await expect(page.locator("#resultMeta")).toContainText("Seuraava päivitys 22.11. 00.05");
});

test("embed mode retries missing dates and restores the bins", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/v1/renyyt", route => {
    requests++;
    return route.fulfill({ json: bins(requests === 1 ? [null] : ["2026-11-21"]) });
  });
  await openAt(page, "2026-11-07T10:00:00Z");
  await fetchBins(page, true);
  // Exercise the supported in-page history transition with the current data.
  await page.evaluate(() => {
    window.history.pushState(null, "", "/embed");
    window.dispatchEvent(new window.PopStateEvent("popstate"));
  });
  await expect(page.locator("body")).toHaveClass(/embed-mode/);
  await expect(page.locator("#resultMeta")).toContainText("10.30");
  expect(requests).toBe(1);
  await page.clock.runFor(30 * MINUTE);
  await expect(page.locator("#cards .card")).toHaveCount(1);
  expect(requests).toBe(2);
});

test("failed automatic refresh retries and JSON import cancels live scheduling", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/v1/renyyt", route => {
    requests++;
    return requests === 2
      ? route.fulfill({ status: 503, json: { error: "Synthetic offline failure" } })
      : route.fulfill({ json: bins([null]) });
  });
  await openAt(page, "2026-11-07T10:00:00Z");
  await fetchBins(page);
  await page.clock.runFor(30 * MINUTE);
  await expect(page.locator("#resultMeta")).toContainText("11.00");
  await page.clock.runFor(30 * MINUTE);
  await expect.poll(() => requests).toBe(3);
  await expect(page.locator("#resultMeta")).toContainText("11.30");
  await page.locator("#compactHttpHelpBtn").click();
  await page.locator("#jsonImportFile").setInputFiles({
    name: "synthetic.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(bins(["2026-11-21"])))
  });
  await expect(page.locator("#httpDialog")).toBeHidden();
  await expect(page.locator("#resultMeta")).not.toContainText("11.30");
  await page.clock.runFor(DAY);
  expect(requests).toBe(3);
});
