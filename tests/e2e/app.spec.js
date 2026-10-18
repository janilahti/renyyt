const { test, expect } = require("@playwright/test");

const { login, setTestDates } = require("./support");
const { expectLayout } = require("./layout");

test.beforeEach(async ({ page }) => { await setTestDates(page); });

test("login, saved credentials, language and date labels", async ({ page }) => {
  await page.goto("/");
  await login(page, true);

  const cards = page.locator("#cards .card");
  await expect(cards.nth(0).locator(".due-label")).toHaveText("TYHJENNYS TÄNÄÄN");
  await expect(cards.nth(1).locator(".due-label")).toHaveText("TYHJENNYS HUOMENNA");
  await expect(cards.nth(2).locator(".due-label")).toHaveText("TYHJENNYS TÄLLÄ VIIKOLLA");

  await page.locator("#languageSelect").selectOption("uk");
  await expect(page.locator("#login-title")).not.toHaveText("Kirjautuminen");
  await expect(page.locator("#compactEmbedBtn")).toBeVisible();
  await expect(page.locator("#compactEmbedBtn")).not.toHaveText("Upotusnäkymä");

  await page.reload();
  await expect(page.locator("#username")).toHaveValue("01-0000633-00");
  await expect(page.locator("#password")).toHaveValue("secret");
});

test("automatic and manual order including drag and drop", async ({ page }) => {
  // Keep both drag endpoints visible; scrolling between them can move the source
  // underneath Playwright's pointer before the native drag starts.
  await page.setViewportSize({ width: 1280, height: 1200 });
  await page.goto("/");
  await login(page);

  const cards = page.locator("#cards .card");
  await expect(cards.nth(0)).toContainText("Paperi");
  await expect(cards.nth(2)).toContainText("Sekajäte");

  await page.locator("#orderModeSelect").selectOption("manual");
  const first = page.locator('#cards .card[data-service-key="A|1|1"]');
  const third = page.locator('#cards .card[data-service-key="C|1|1"]');
  await expect(first).toHaveAttribute("draggable", "true");
  // The card also contains interactive details; drag from its dedicated handle.
  await first.locator(".drag-handle").dragTo(third.locator(".type"));
  await expect(cards.nth(2)).toContainText("Paperi");

  await first.locator(".move-up").click();
  await expect(cards.nth(1)).toContainText("Paperi");
  await first.locator(".move-down").click();
  await expect(cards.nth(2)).toContainText("Paperi");

  await page.locator("#orderModeSelect").selectOption("date");
  await expect(cards.nth(0)).toContainText("Paperi");
});

for (const width of [320, 1280]) {
  for (const language of ["fi", "ar"]) {
    test(`compact manual ordering stays usable and persists at ${width}px in ${language}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1200 });
      await page.goto("/");
      await page.locator("#languageSelect").selectOption(language);
      await login(page);
      await page.locator("#compactViewBtn").click();
      await page.locator("#orderModeSelect").selectOption("manual");

      const cards = page.locator("#cards .card");
      const first = page.locator('#cards .card[data-service-key="A|1|1"]');
      await expect(first.locator(".drag-handle")).toBeVisible();
      await expect(first.locator(".move-up")).toBeVisible();
      await expect(first.locator(".move-down")).toBeVisible();
      await expect(first.locator(".essential-details")).toBeHidden();
      await expect(first.locator(".raw-details")).toBeHidden();
      await expectLayout(page, "#resultsPanel", width < 700);
      await first.locator(".move-down").click();
      await expect(cards.nth(1)).toHaveAttribute("data-service-key", "A|1|1");
      await first.locator(".move-up").click();
      await expect(cards.first()).toHaveAttribute("data-service-key", "A|1|1");
      await first.locator(".move-down").click();

      await page.reload();
      await login(page);
      await expect(page.locator("#resultsPanel")).toHaveClass(/compact-view/);
      await expect(page.locator("#orderModeSelect")).toHaveValue("manual");
      await expect(cards.first()).toHaveAttribute("data-service-key", "B|1|1");
      await expect(first.locator(".move-up")).toBeVisible();
      await page.locator("#orderModeSelect").selectOption("date");
      await expect(cards.first()).toHaveAttribute("data-service-key", "A|1|1");
      await expect(page.locator(".reorder-controls")).toHaveCount(0);
    });
  }
}

test("saved-credential embed button works after the login form collapses", async ({ page }) => {
  await page.goto("/");
  await login(page, true);
  await expect(page.locator("#embedBtn")).toBeHidden();
  await page.locator("#compactEmbedBtn").click();
  await expect(page).toHaveURL(/\/embed#.*theme=/);
  // This button intentionally uses credentials already saved in this browser.
  expect(page.url()).not.toContain("credentials=");
  expect(page.url()).toContain("view=v1.");
  expect(page.url()).not.toContain("username=");
  expect(page.url()).not.toContain("password=");
  expect(page.url()).not.toContain("embed=1");
  await expect(page.locator("body")).toHaveClass(/embed-mode/);
  await expect(page.locator("header")).toBeHidden();
  await expect(page.locator("#cards .card")).toHaveCount(3);
});

test("HTTP example produces an embed URL usable in a fresh browser context", async ({ page, browser }) => {
  await page.goto("/");
  await login(page);
  await page.locator("#orderModeSelect").selectOption("manual");
  await page.locator('#cards [data-service-key="A|1|1"] .move-down').click();
  await page.locator("#compactViewBtn").click();
  await page.locator("#compactHttpHelpBtn").click();
  await expect(page.locator("#embedUrlExample")).toContainText("credentials=v1.");
  const url = await page.locator("#embedUrlExample").textContent();
  expect(url).toContain("view=v1.");
  expect(url).not.toContain("password=");

  const freshContext = await browser.newContext({ timezoneId: "UTC" });
  try {
    const freshPage = await freshContext.newPage();
    await setTestDates(freshPage);
    await freshPage.goto(url);
    await expect(freshPage.locator("body")).toHaveClass(/embed-mode/);
    await expect(freshPage.locator("#cards .card")).toHaveCount(3);
    await expect(freshPage.locator("#cards .card").first()).toHaveAttribute("data-service-key", "B|1|1");
    await expect(freshPage.locator("#resultsPanel")).toHaveClass(/compact-view/);
    await expect(freshPage.locator("#resultsToolbar")).toBeHidden();
    await expect(freshPage.locator(".reorder-controls")).toHaveCount(0);
    await expect(freshPage.locator("#cards .card").first()).toHaveAttribute("draggable", "false");
    expect(await freshPage.evaluate(() => window.localStorage.getItem("renyyt.credentials"))).toBeNull();
  } finally {
    await freshContext.close();
  }
});

test("documentation dialog follows README links", async ({ page }) => {
  await page.goto("/");
  for (const document of ["API.md", "TECHNICAL.md"]) {
    await page.locator("#readmeBtn").click();
    await expect(page.locator("#readmeDialog")).toBeVisible();
    await expect(page.locator("#readmeContent")).toContainText("Renyyt");
    await page.locator(`#readmeContent a[data-doc-path="${document}"]`).first().click();
    await expect(page.locator("#readmeDialogTitle")).toHaveText(document);
    await expect(page.locator("#readmeContent")).toBeVisible();
    await page.locator("#closeReadmeDialog").click();
  }
});

test("install prompt and responsive header", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => {
    const event = new Event("beforeinstallprompt");
    event.preventDefault = () => {};
    event.prompt = async () => {};
    event.userChoice = Promise.resolve({ outcome: "dismissed", platform: "web" });
    window.dispatchEvent(event);
  });
  await expect(page.locator("#installBtn")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  const headerBox = await page.locator(".header-row").boundingBox();
  expect(headerBox.width).toBeLessThanOrEqual(390);
});

test("service worker shell works offline after activation", async ({ page, context }) => {
  // Date rewriting is unnecessary here. Routing disables Firefox's cache and
  // turns reload into a cache-bypassing load that bypasses the service worker.
  await page.unroute("**/api/v1/renyyt");
  await page.goto("/");
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await context.setOffline(true);
  try {
    const response = await page.reload({ waitUntil: "domcontentloaded" });
    expect(response.fromServiceWorker()).toBe(true);
    expect(await page.evaluate(() => navigator.onLine)).toBe(false);
    await expect(page).toHaveTitle(/Renyyt/);
    await expect(page.locator("#loginPanel")).toBeVisible();
  } finally {
    await context.setOffline(false);
  }
});
