const { test, expect } = require("@playwright/test");

async function login(page, remember = false) {
  await page.locator("#username").fill("01-0000633-00");
  await page.locator("#password").fill("secret");
  if (remember) await page.locator("#remember").check();
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await expect(page.locator("#cards .card")).toHaveCount(3);
}

async function setTestDates(page) {
  // Use this week's Monday so today/tomorrow/this-week labels stay deterministic.
  const monday = new Date();
  monday.setUTCDate(monday.getUTCDate() - (monday.getUTCDay() + 6) % 7);
  monday.setUTCHours(10, 0, 0, 0);
  await page.clock.setFixedTime(monday);
  await page.route("**/api/v1/renyyt", async route => {
    // Exercise the real fixture server, then make only its sample dates relative.
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    const data = await response.json();
    data.services.forEach((service, index) => {
      const date = new Date(monday);
      date.setUTCDate(date.getUTCDate() + index);
      service.ASTNextDate = date.toISOString().slice(0, 10);
    });
    await route.fulfill({ response, json: data });
  });
}

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
