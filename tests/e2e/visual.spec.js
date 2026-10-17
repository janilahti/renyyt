const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");

async function capture(page, filename, selector) {
  await page.evaluate(async () => {
    await window.document.fonts.ready;
    await Promise.all([...window.document.images].map(image => image.decode()));
    // Focus restoration is covered by responsive tests. Keep these images neutral.
    window.document.activeElement.blur();
    // Full-page captures must start at the top: otherwise offscreen fixed
    // elements (such as the skip link) can appear inside the document clip.
    window.scrollTo(0, 0);
  });
  await page.mouse.move(0, 0);
  await expect(page.locator(".skip-link")).not.toBeInViewport();
  if (selector) await expect(page.locator(selector)).toHaveScreenshot(filename);
  else await expect(page).toHaveScreenshot(filename, { fullPage: true });
}

for (const width of [320, 430, 768, 1280]) {
  for (const theme of ["light", "dark"]) {
    test.describe(`${width}px ${theme}`, () => {
      test.use({ viewport: { width, height: 844 }, colorScheme: theme, hasTouch: width < 1280 });

      test("login, results, dialogs and compact embed", async ({ page }) => {
        // Fixed reference week keeps dates, relative labels and refresh metadata
        // stable across runs without changing the server's real fixture path.
        await setTestDates(page, new Date("2024-01-01T10:00:00Z"));
        await page.route("**/api/v1/features", route => route.fulfill({ json: {
          feedback: true, pwa: true, reminders: { enabled: true, vapidPublicKey: "synthetic-public-key" }
        } }));
        const writes = [];
        const blockWrite = async route => {
          writes.push(route.request().url());
          await route.abort();
        };
        await page.route("**/api/v1/feedback", blockWrite);
        await page.route("**/api/v1/reminders/**", blockWrite);

        await page.goto("/");
        await expect(page.locator("#feedbackBtn")).toBeVisible();
        await page.locator("#themeSelect").selectOption(theme);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.evaluate(async () => { await window.navigator.serviceWorker.ready; });
        const suffix = `${width}-${theme}.png`;
        await capture(page, `login-${suffix}`);
        await login(page, true);
        await capture(page, `results-${suffix}`);

        for (const [name, open, dialog, close] of [
          ["bins", "#serviceFilterBtn", "#serviceFilterDialog", "#closeServiceFilterDialog"],
          ["feedback", "#feedbackBtn", "#feedbackDialog", "#closeFeedbackDialog"],
          ["reminders", "#reminderBtn", "#reminderDialog", "#closeReminderDialog"]
        ]) {
          await page.locator(open).click();
          await expect(page.locator(dialog)).toBeVisible();
          await capture(page, `${name}-${suffix}`, dialog);
          await page.locator(close).click();
          await expect(page.locator(dialog)).toBeHidden();
        }

        await page.locator("#compactViewBtn").click();
        await page.locator("#compactEmbedBtn").click();
        await expect(page.locator("body")).toHaveClass(/embed-mode/);
        await expect(page.locator("#resultsPanel")).toHaveClass(/compact-view/);
        await expect(page.locator("#cards .card")).toHaveCount(3);
        await capture(page, `embed-${suffix}`);
        expect(writes, "Visual tests must not send feedback or push state").toEqual([]);
      });
    });
  }
}
