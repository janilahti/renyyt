const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");

const { expectLayout } = require("./layout");

const widths = [320, 390, 430];

for (const width of widths) {
  test.describe(`${width}px`, () => {
    test.use({ viewport: { width, height: 844 }, hasTouch: true });

    test.beforeEach(async ({ page }) => {
      await setTestDates(page);
      // Enable optional UI without configuring SMTP or a push sender on the server.
      await page.route("**/api/v1/features", route => route.fulfill({ json: {
        feedback: true, pwa: true, reminders: { enabled: true, vapidPublicKey: "synthetic-public-key" }
      } }));
    });

    test("header and login fit in every supported language", async ({ page }) => {
      await page.goto("/");
      await expect(page.locator("#feedbackBtn")).toBeVisible();
      for (const language of ["fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
        await test.step(language, async () => {
          await page.locator("#languageSelect").selectOption(language);
          await expect(page.locator("html")).toHaveAttribute("lang", language);
          await page.locator("#password").fill("synthetic-password");
          await page.locator("#togglePasswordBtn").tap();
          await expect(page.locator("#password")).toHaveAttribute("type", "text");
          await page.locator("#togglePasswordBtn").tap();
          await expect(page.locator("#password")).toHaveAttribute("type", "password");
          await expectLayout(page);
        });
      }
    });

    test("results, dialogs and embed stay usable on a narrow screen", async ({ page }) => {
      const sideEffects = [];
      const blockSend = async route => {
        sideEffects.push(route.request().url());
        await route.abort();
      };
      await page.route("**/api/v1/feedback", blockSend);
      await page.route("**/api/v1/reminders/**", blockSend);
      await page.goto("/");
      await login(page, true);
      for (const language of ["fi", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
        await test.step(language, async () => {
          await page.locator("#languageSelect").selectOption(language);
          await expectLayout(page);
          await page.locator("#orderModeSelect").selectOption("manual");
          await expectLayout(page);
          for (const [open, dialog, close] of [
            ["#serviceFilterBtn", "#serviceFilterDialog", "#closeServiceFilterDialog"],
            ["#feedbackBtn", "#feedbackDialog", "#closeFeedbackDialog"],
            ["#reminderBtn", "#reminderDialog", "#closeReminderDialog"]
          ]) {
            await page.locator(open).tap();
            await expect(page.locator(dialog)).toBeVisible();
            await expectLayout(page, dialog);
            if (dialog === "#feedbackDialog" && ["ar", "fa"].includes(language)) {
              await page.locator("#feedbackMessage").fill(language === "ar" ? "رسالة تجريبية" : "پیام آزمایشی");
              await expect(page.locator("#feedbackMessage")).toHaveCSS("direction", "rtl");
              await page.locator("#feedbackMessage").fill("Synthetic feedback");
              await expect(page.locator("#feedbackMessage")).toHaveCSS("direction", "ltr");
              await page.locator("#feedbackMessage").fill("");
              await expect(page.locator("#feedbackEmail")).toHaveCSS("direction", "ltr");
            }
            if (dialog === "#serviceFilterDialog") {
              const firstBin = page.locator(`${dialog} input[type=checkbox]`).first();
              await firstBin.uncheck();
              await expect(page.locator("#cards .card")).toHaveCount(2);
              await firstBin.check();
              await expect(page.locator("#cards .card")).toHaveCount(3);
            }
            await page.locator(close).tap();
            await expect(page.locator(dialog)).not.toBeVisible();
            await expect(page.locator(open)).toBeFocused();
          }
        });
      }
      await page.locator("#compactViewBtn").click();
      await page.locator("#compactEmbedBtn").click();
      await expect(page.locator("body")).toHaveClass(/embed-mode/);
      await expect(page.locator("header")).toBeHidden();
      await expect(page.locator("#cards .card")).toHaveCount(3);
      await expectLayout(page);
      expect(sideEffects, "Opening dialogs must not send feedback or push state").toEqual([]);
    });
  });
}

test.describe("long document dialogs", () => {
  test.use({ viewport: { width: 390, height: 600 }, hasTouch: true });

  test("modal scrolling never moves the background page", async ({ page }) => {
    await setTestDates(page);
    await page.goto("/");
    await login(page);
    await page.locator("#readmeBtn").tap();
    const dialog = page.locator("#readmeDialog");
    await expect(page.locator("#readmeContent")).toBeVisible();
    const backgroundY = await page.evaluate(() => window.scrollY);
    await dialog.hover();
    await page.mouse.wheel(0, 10000);
    await expect.poll(() => dialog.evaluate(el => el.scrollTop + el.clientHeight >= el.scrollHeight - 1)).toBe(true);
    await page.mouse.wheel(0, 600);
    // A gesture over the backdrop must not scroll the underlying document either.
    await page.mouse.move(2, 300);
    await page.mouse.wheel(0, 600);
    await page.waitForTimeout(250);
    expect(await page.evaluate(() => window.scrollY)).toBe(backgroundY);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    const closedY = await page.evaluate(() => window.scrollY);
    expect(closedY).toBe(backgroundY);
    await page.mouse.move(200, 300);
    await page.mouse.wheel(0, 600);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(closedY);
  });

  test("header and complete content stay reachable after viewport changes", async ({ page }) => {
    await page.goto("/");
    const dialog = page.locator("#readmeDialog");
    const close = page.locator("#closeReadmeDialog");
    const expectInsideViewport = async () => {
      const geometry = await dialog.evaluate(el => {
        const rect = el.getBoundingClientRect();
        const viewport = window.visualViewport;
        const top = viewport?.offsetTop || 0;
        return { top: rect.top, bottom: rect.bottom, viewportTop: top,
          viewportBottom: top + (viewport?.height || window.innerHeight),
          scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight };
      });
      expect(geometry.top).toBeGreaterThanOrEqual(geometry.viewportTop);
      expect(geometry.bottom).toBeLessThanOrEqual(geometry.viewportBottom + 1);
      expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight);
      expect(geometry.scrollTop).toBe(0);
      await expect(close).toBeInViewport();
      await expect(page.locator("#readmeDialogTitle")).toBeInViewport();
    };
    for (const language of ["fi", "ar"]) {
      await page.locator("#languageSelect").selectOption(language);
      await page.locator("#readmeBtn").scrollIntoViewIfNeeded();
      await page.locator("#readmeBtn").tap();
      await expect(page.locator("#readmeContent")).toBeVisible();
      await expectInsideViewport();
      await page.setViewportSize({ width: 390, height: 400 });
      await expectInsideViewport();
      await dialog.evaluate(el => { el.scrollTop = el.scrollHeight; });
      const technicalLink = page.locator('#readmeContent a[data-doc-path="TECHNICAL.md"]');
      await expect(technicalLink).toBeInViewport();
      await technicalLink.tap();
      await expect(page.locator("#readmeDialogTitle")).toHaveText("TECHNICAL.md");
      await expect(page.locator("#readmeContent")).toBeVisible();
      await expectInsideViewport();
      await dialog.evaluate(el => { el.scrollTop = el.scrollHeight; });
      await expect(page.locator("#readmeContent > :last-child")).toBeInViewport();
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await expect(page.locator("#readmeBtn")).toBeFocused();
      await page.setViewportSize({ width: 390, height: 600 });
    }
  });
});
