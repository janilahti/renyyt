const { test, expect } = require("@playwright/test");
const { login, setTestDates, openAction } = require("./support");
const { expectLayout } = require("./layout");

test.beforeEach(async ({ page }) => { await setTestDates(page); });

test("menu actions reflect available data, remain discoverable and restore focus", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#actionsBtn")).toHaveAccessibleName("Valikko");
  await expect(page.locator("#actionsBtn")).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#aboutBtn")).toBeHidden();
  await page.locator("#actionsBtn").press("Enter");
  await expect(page.locator("#actionsBtn")).toHaveAttribute("aria-expanded", "true");
  for (const id of ["icsBtn", "serviceFilterBtn", "installBtn"]) await expect(page.locator(`#${id}`)).toBeDisabled();
  for (const id of ["aboutBtn", "httpHelpBtn"]) await expect(page.locator(`#${id}`)).toBeEnabled();
  await expect(page.locator("#calendarMenuHelp")).toBeVisible();
  await page.locator("#closeActionsDialog").press("Tab");
  await expect(page.locator("#aboutBtn")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#httpHelpBtn")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#aboutBtn")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#actionsDialog")).toBeHidden();
  await expect(page.locator("#actionsBtn")).toBeFocused();
  await openAction(page, "#aboutBtn");
  await expect(page.locator("#actionsDialog")).toBeHidden();
  await expect(page.locator("#aboutDialog")).toBeVisible();
  await expect(page.locator("#closeAboutDialog")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#actionsBtn")).toBeFocused();
  await login(page);
  await page.locator("#actionsBtn").click();
  await expect(page.locator("#icsBtn")).toBeEnabled();
  await expect(page.locator("#serviceFilterBtn")).toBeEnabled();
  await expect(page.locator("#calendarMenuHelp")).toBeHidden();
  await page.locator("#serviceFilterBtn").click();
  await expect(page.locator("#serviceFilterDialog")).toBeVisible();
  await expect(page.locator("#actionsDialog")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator("#actionsBtn")).toBeFocused();
});

for (const width of [320, 430, 1280]) {
  test(`menu fits all languages and themes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 600 });
    await page.goto("/");
    for (const language of ["fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
      await page.locator("#languageSelect").selectOption(language);
      for (const theme of ["light", "dark"]) {
        await page.locator("#themeSelect").selectOption(theme);
        await page.locator("#actionsBtn").click();
        await expectLayout(page, "#actionsDialog", width < 1280);
        await page.locator("#httpHelpBtn").focus();
        await expect(page.locator("#httpHelpBtn")).toBeInViewport();
        await page.locator("#closeActionsDialog").click();
        await expect(page.locator("#actionsBtn")).toBeFocused();
      }
    }
  });
}

test("HTTP tools can import data before sign-in and enable data-dependent actions", async ({ page }) => {
  await page.goto("/");
  await openAction(page, "#httpHelpBtn");
  await expect(page.locator("#httpExample")).toContainText("POST");
  const date = await page.evaluate(() => {
    const next = new Date();
    next.setUTCDate(next.getUTCDate() + 7);
    return next.toISOString().slice(0, 10);
  });
  await page.locator("#jsonImportFile").setInputFiles({
    name: "synthetic.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ services: [{
      ASTAsnro: "SYNTHETIC", ASTTyyppi: "1", ASTPos: "1", ASTNimi: "Synthetic bin", ASTNextDate: date
    }] }))
  });
  await expect(page.locator("#httpDialog")).toBeHidden();
  await page.locator("#actionsBtn").click();
  await expect(page.locator("#icsBtn")).toBeEnabled();
  await expect(page.locator("#serviceFilterBtn")).toBeEnabled();
});

test("empty backend data disables collection tools and menu backdrop closes without scrolling the page", async ({ page }) => {
  await page.route("**/api/v1/renyyt", route => route.fulfill({ json: { services: [], warnings: [] } }));
  await page.goto("/");
  await page.locator("#username").fill("synthetic-account");
  await page.locator("#password").fill("synthetic-password");
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await page.locator("#actionsBtn").click();
  await expect(page.locator("#icsBtn")).toBeDisabled();
  await expect(page.locator("#serviceFilterBtn")).toBeDisabled();
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.click(2, 2);
  await expect(page.locator("#actionsDialog")).toBeHidden();
  await expect(page.locator("#actionsBtn")).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBe(before);
});

test("installation stays disabled when the server disables PWA support", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "platform", { value: "MacIntel" });
    Object.defineProperty(navigator, "maxTouchPoints", { value: 5 });
  });
  await page.route("**/api/v1/features", route => route.fulfill({ json: { pwa: false, feedback: false } }));
  await page.goto("/");
  await login(page, true);
  await page.locator("#actionsBtn").click();
  await expect(page.locator("#installBtn")).toBeDisabled();
  await expect(page.locator("#installMenuHelp")).toContainText("Asennus ei ole käytettävissä");
});

test("historical or undated data can be filtered but cannot be exported to the calendar", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-11-07T10:00:00Z"));
  await page.route("**/api/v1/renyyt", route => route.fulfill({ json: {
    services: ["2026-11-06", null, "invalid"].map((date, index) => ({
      ASTAsnro: `SYNTHETIC-${index}`, ASTTyyppi: "1", ASTPos: "1", ASTNimi: "Synthetic bin", ASTNextDate: date
    }))
  } }));
  await page.goto("/");
  await page.locator("#username").fill("synthetic-account");
  await page.locator("#password").fill("synthetic-password");
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await page.locator("#actionsBtn").click();
  await expect(page.locator("#icsBtn")).toBeDisabled();
  await expect(page.locator("#serviceFilterBtn")).toBeEnabled();
});

test("a failed account change disables menu actions on the hidden previous results", async ({ page }) => {
  await page.goto("/");
  await login(page);
  await page.locator("#expandLoginBtn").click();
  await page.locator("#username").fill("another-synthetic-account");
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route("**/api/v1/renyyt", async route => {
    await pending;
    await route.fulfill({ status: 401, json: { code: "AUTH_FAILED", error: "Synthetic failure" } });
  });
  await page.locator("#loadBtn").click();
  await page.locator("#actionsBtn").click();
  for (const id of ["icsBtn", "serviceFilterBtn"]) await expect(page.locator(`#${id}`)).toBeDisabled();
  await page.locator("#closeActionsDialog").click();
  release();
  await expect(page.locator("#password")).toBeFocused();
  await page.locator("#actionsBtn").click();
  for (const id of ["icsBtn", "serviceFilterBtn"]) await expect(page.locator(`#${id}`)).toBeDisabled();
});
