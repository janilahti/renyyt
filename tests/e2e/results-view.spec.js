const { test, expect } = require("@playwright/test");
const { expectLayout } = require("./layout");

async function prepare(page, count = 3, reminders = false) {
  await page.clock.setFixedTime(new Date("2026-11-07T10:00:00Z"));
  await page.route("**/api/v1/features", route => route.fulfill({ json: {
    feedback: false, pwa: true, reminders: { enabled: reminders, vapidPublicKey: "synthetic-test-key" }
  } }));
  await page.route("**/api/v1/renyyt", route => route.fulfill({ json: {
    services: Array.from({ length: count }, (_, index) => ({
      ASTAsnro: `SYNTHETIC-${index}`, ASTTyyppi: "1", ASTPos: "1",
      ASTNimi: `Synthetic bin ${index}`, ASTNextDate: "2026-11-14", ASTVali: "4"
    })), warnings: []
  } }));
  await page.goto("/");
  await page.locator("#username").fill("synthetic-account");
  await page.locator("#password").fill("synthetic-password");
}

async function fetchResults(page) {
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await expect(page.locator("#results-title")).toBeFocused();
}

for (const language of ["fi", "ar"]) {
  test(`manual fetch reveals a tall list without hiding its heading (${language})`, async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 650 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await prepare(page, 8);
    await page.locator("#languageSelect").selectOption(language);
    await fetchResults(page);
    await expect.poll(async () => (await page.locator("#results-title").boundingBox()).y).toBeCloseTo(12, 0);
  });
}

test("a short list fits while preserving context above it", async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 900 });
  await prepare(page, 1);
  // Hold the response so the test starts from a known scroll position, independent
  // of how a browser reveals the button before clicking it.
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route("**/api/v1/renyyt", async route => { await pending; await route.fallback(); });
  await page.locator("#loadBtn").click();
  await page.evaluate(() => window.scrollTo(0, 0));
  release();
  await expect(page.locator("#results-title")).toBeFocused();
  await expect.poll(async () => {
    const box = await page.locator("#resultsPanel").boundingBox();
    return box.y + box.height;
  }).toBeLessThanOrEqual(889);
  expect((await page.locator("#results-title").boundingBox()).y).toBeGreaterThan(80);
});

test("already visible results retain the page position", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1600 });
  await prepare(page, 1);
  await fetchResults(page);
  await page.evaluate(() => new Promise(resolve => window.requestAnimationFrame(resolve)));
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

test("closing a mobile keyboard can reveal more context, and later resizes do not move the page", async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 500 });
  await prepare(page, 1);
  await fetchResults(page);
  await expect.poll(async () => (await page.locator("#results-title").boundingBox()).y).toBeCloseTo(12, 0);
  // A larger visual viewport models the keyboard closing just after submission.
  await page.setViewportSize({ width: 430, height: 1000 });
  await expect.poll(async () => (await page.locator("#results-title").boundingBox()).y).toBeGreaterThan(80);
  await page.locator("#themeSelect").focus();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.setViewportSize({ width: 430, height: 650 });
  await page.evaluate(() => new Promise(resolve => window.requestAnimationFrame(() => window.requestAnimationFrame(resolve))));
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.locator("#themeSelect")).toBeFocused();
});

test("failed authentication keeps the login form and does not focus results", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/v1/renyyt", route => route.fulfill({ status: 401, json: { error: "Synthetic failure", code: "AUTH_FAILED" } }));
  await page.locator("#loadBtn").click();
  await expect(page.locator("#password")).toBeFocused();
  await expect(page.locator("#loginPanel")).not.toHaveClass(/compact/);
  await expect(page.locator("#resultsPanel")).toBeHidden();
});

for (const [width, reminders, columns] of [[390, false, 1], [430, false, 2], [600, true, 2], [801, true, 2], [960, false, 4], [1280, true, 5]]) {
  test(`results controls form balanced rows at ${width}px (reminders=${reminders})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await prepare(page, 3, reminders);
    await fetchResults(page);
    await expect(page.locator("#orderModeSelect")).toHaveAccessibleName("Järjestys");
    if (reminders) await expect(page.locator("#reminderBtn")).toBeVisible();
    for (const language of ["fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
      await page.locator("#languageSelect").selectOption(language);
      for (const mode of ["date", "manual"]) {
        await page.locator("#orderModeSelect").selectOption(mode);
        await expectLayout(page, "#resultsToolbar", width <= 700);
        const rows = await page.locator("#resultsToolbar").evaluate(root => {
          const rows = [];
          for (const control of root.children) {
            if (!control.checkVisibility()) continue;
            const box = control.getBoundingClientRect();
            let row = rows.find(row => Math.abs(row.top - box.top) < 1);
            if (!row) rows.push(row = { top: box.top, count: 0 });
            row.count++;
          }
          return rows.map(row => row.count);
        });
        const expected = columns === 1 ? [1, 1, 1, 1] : columns === 2 ? [2, 2] : [columns];
        if (reminders && columns !== 5) expected.push(1);
        expect(rows, `${language}/${mode}`).toEqual(expected);
      }
    }
  });
}
