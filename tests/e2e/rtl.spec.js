const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");

for (const width of [320, 1280]) {
  test.describe(`Arabic ${width}px`, () => {
    test.use({ viewport: { width, height: 1200 } });

    test("mirrors layout, isolates technical text and preserves embed language", async ({ page }) => {
      await setTestDates(page);
      await page.goto("/");
      await page.locator("#languageSelect").selectOption("ar");
      await expect(page.locator("html")).toHaveAttribute("lang", "ar");
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await expect(page.locator("#login-title")).toHaveText("تسجيل الدخول");
      for (const id of ["username", "password", "suffixes"]) {
        await expect(page.locator(`#${id}`)).toHaveCSS("direction", "ltr");
      }
      const logo = await page.locator(".brand-logo").boundingBox();
      const heading = await page.locator(".header-copy-text").boundingBox();
      expect(logo.x).toBeGreaterThanOrEqual(heading.x + heading.width - 1);
      await expect(page.locator("#status")).toHaveCSS("text-align", "start");
      await login(page, true);
      await expect(page.locator(".card .type bdi").first()).toHaveText("Paperi");
      await expect(page.locator(".card .type bdi").first()).toHaveCSS("direction", "ltr");
      await page.locator(".card .raw-details summary").first().click();
      await expect(page.locator(".card .json-wrap").first()).toHaveCSS("direction", "ltr");
      await expect(page.locator(".card .raw-details pre").first()).toHaveCSS("direction", "ltr");
      await page.locator("#compactHttpHelpBtn").click();
      await expect(page.locator("#httpDialog")).toBeVisible();
      for (const id of ["httpExample", "curlExample", "embedUrlExample"]) {
        await expect(page.locator(`#${id}`)).toHaveCSS("direction", "ltr");
      }
      const title = await page.locator("#httpDialog .dialog-head h2").boundingBox();
      const close = await page.locator("#closeHttpDialog").boundingBox();
      expect(title.x).toBeGreaterThanOrEqual(close.x + close.width - 1);
      await page.locator("#closeHttpDialog").press("Enter");
      await expect(page.locator("#compactHttpHelpBtn")).toBeFocused();
      await page.locator("#readmeBtn").click();
      await expect(page.locator("#readmeContent")).toBeVisible();
      await expect(page.locator("#readmeContent")).toHaveAttribute("dir", "ltr");
      await expect(page.locator("#readmeContent")).toHaveAttribute("lang", "fi");
      await page.locator("#closeReadmeDialog").press("Enter");
      await page.locator("#compactEmbedBtn").click();
      await expect(page).toHaveURL(/lang=ar/);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await expect(page.locator("#cards .card")).toHaveCount(3);
      await page.reload();
      await expect(page.locator("#cards .card")).toHaveCount(3);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    });
  });
}

test("Arabic manual ordering keeps vertical arrows and supports dragging and switching back to LTR", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1200 });
  await setTestDates(page);
  await page.goto("/");
  await page.locator("#languageSelect").selectOption("ar");
  await login(page);
  await page.locator("#orderModeSelect").selectOption("manual");
  const cards = page.locator("#cards .card");
  const first = page.locator('#cards .card[data-service-key="A|1|1"]');
  const third = page.locator('#cards .card[data-service-key="C|1|1"]');
  await expect(first.locator(".move-up")).toHaveText("↑");
  await expect(first.locator(".move-down")).toHaveText("↓");
  await first.locator(".drag-handle").dragTo(third.locator(".type"));
  await expect(cards.nth(2)).toContainText("Paperi");
  await first.locator(".move-up").click();
  await expect(cards.nth(1)).toContainText("Paperi");
  await page.locator("#languageSelect").selectOption("fi");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(cards.nth(1)).toContainText("Paperi");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "fi");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
});
