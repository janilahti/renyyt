const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");
const { expectLayout } = require("./layout");
const i18n = require("../../web/i18n");

for (const dayOffset of [2, 6]) {
  test(`day after tomorrow is precise across all languages (${dayOffset === 6 ? "next week" : "same week"})`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await setTestDates(page);
    const today = new Date();
    today.setUTCDate(today.getUTCDate() - (today.getUTCDay() + 6) % 7 + dayOffset);
    today.setUTCHours(10, 0, 0, 0);
    await page.clock.setFixedTime(today);
    await page.route("**/api/v1/renyyt", async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.services.forEach((service, index) => {
        const date = new Date(today);
        date.setUTCDate(date.getUTCDate() + index + 2);
        service.ASTNextDate = date.toISOString().slice(0, 10);
      });
      await route.fulfill({ response, json: data });
    });
    await page.goto("/");
    await login(page);
    for (const language of i18n.supported) {
      await page.locator("#languageSelect").selectOption(language);
      await expect(page.locator("#cards .card").first().locator(".due-label"))
        .toHaveText(i18n.t(language, "due.dayAfterTomorrow"));
      await expect(page.locator("#nextSummary")).toHaveText(i18n.t(language, "results.nextDayAfterTomorrow"));
      await expectLayout(page, "main", false);
    }
    await page.locator("#languageSelect").selectOption("en");
    await expect(page.locator(".due-label").first()).toHaveText("COLLECTION IN 2 DAYS");
    // Later dates must still use the existing week/day-count wording.
    const later = page.locator("#cards .card").nth(1);
    await expect(later).not.toContainText("COLLECTION IN 2 DAYS");
    await expect(later).toContainText(dayOffset === 6 ? "in 3 days" : "COLLECTION THIS WEEK");
  });
}
