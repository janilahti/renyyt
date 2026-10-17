const { test, expect } = require("@playwright/test");

async function login(page, remember = false) {
  await page.locator("#username").fill("01-0000633-00");
  await page.locator("#password").fill("secret");
  if (remember) await page.locator("#remember").check();
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await expect(page.locator("#cards .card")).toHaveCount(3);
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-10-07T10:00:00+03:00"));
});

test("login, saved credentials, language and date labels", async ({ page }) => {
  await page.goto("/");
  await login(page, true);

  const cards = page.locator("#cards .card");
  await expect(cards.nth(0)).toContainText("Tänään");
  await expect(cards.nth(1)).toContainText("Huomenna");
  await expect(cards.nth(2)).toContainText("Tällä viikolla");

  await page.locator("#languageSelect").selectOption("uk");
  await expect(page.locator("#login-title")).not.toHaveText("Kirjautuminen");
  await expect(page.locator("#embedBtn")).not.toHaveText("Upotusnäkymä");

  await page.reload();
  await expect(page.locator("#username")).toHaveValue("01-0000633-00");
  await expect(page.locator("#password")).toHaveValue("secret");
});

test("automatic and manual order including drag and drop", async ({ page }) => {
  await page.goto("/");
  await login(page);

  const cards = page.locator("#cards .card");
  await expect(cards.nth(0)).toContainText("Paperi");
  await expect(cards.nth(2)).toContainText("Sekajäte");

  await page.locator("#orderModeSelect").selectOption("manual");
  const first = page.locator('#cards .card[data-service-key="A|1|1"]');
  const third = page.locator('#cards .card[data-service-key="C|1|1"]');
  await expect(first).toHaveAttribute("draggable", "true");
  await first.dragTo(third);
  await expect(cards.nth(2)).toContainText("Paperi");

  await page.locator("#orderModeSelect").selectOption("date");
  await expect(cards.nth(0)).toContainText("Paperi");
});

test("embed, documentation dialogs, install prompt and responsive header", async ({ page }) => {
  await page.goto("/");
  await login(page, true);
  await page.locator("#embedBtn").click();
  await expect(page).toHaveURL(/\/embed#.*theme=/);
  expect(page.url()).toContain("credentials=v1.");
  expect(page.url()).not.toContain("username=");
  expect(page.url()).not.toContain("password=");
  expect(page.url()).not.toContain("embed=1");
  await expect(page.locator("body")).toHaveClass(/embed-mode/);
  await expect(page.locator("header")).toBeHidden();
  await expect(page.locator("#cards .card")).toHaveCount(3);

  await page.goto("/");
  await page.locator("#readmeBtn").click();
  await expect(page.locator("#readmeDialog")).toBeVisible();
  await expect(page.locator("#readmeContent")).toContainText("Renyyt");

  const apiLink = page.locator('#readmeContent a[data-doc-path="API.md"]').first();
  if (await apiLink.count()) {
    await apiLink.click();
    await expect(page.locator("#readmeDialogTitle")).toHaveText("API.md");
  }
  const technicalLink = page.locator('#readmeContent a[data-doc-path="TECHNICAL.md"]').first();
  if (await technicalLink.count()) {
    await technicalLink.click();
    await expect(page.locator("#readmeDialogTitle")).toHaveText("TECHNICAL.md");
  }
  await page.locator("#closeReadmeDialog").click();

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
  await page.goto("/");
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await context.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page).toHaveTitle(/Renyyt/);
  await expect(page.locator("#loginPanel")).toBeVisible();
  await context.setOffline(false);
});
