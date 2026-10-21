const { test, expect } = require("@playwright/test");
const { login, setTestDates, stubUnsubscribedPush } = require("./support");
const { expectLayout } = require("./layout");
const { locale, direction, supported } = require("../../web/i18n");

for (const language of ["vi", "zh-Hans", "et"]) {
  for (const width of [768, 1280]) {
    test.describe(`${language} ${width}px`, () => {
      test.use({ viewport: { width, height: 1000 } });

      test("localized layouts and dates fit and the language persists in embed", async ({ page }) => {
        await setTestDates(page);
        await stubUnsubscribedPush(page);
        const writes = [];
        await page.route("**/api/v1/features", route => route.fulfill({ json: {
          feedback: true, pwa: true, reminders: { enabled: true, vapidPublicKey: "synthetic-public-key" }
        } }));
        for (const pattern of ["**/api/v1/feedback", "**/api/v1/reminders/**"]) {
          await page.route(pattern, route => { writes.push(route.request().url()); return route.abort(); });
        }
        await page.goto("/");
        await expect(page.locator("#feedbackBtn")).toBeVisible();
        await page.locator("#languageSelect").selectOption(language);
        await expect(page.locator("html")).toHaveAttribute("lang", language);
        await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
        await expectLayout(page, "main", false);
        await login(page, true);
        await expectLayout(page, "main", false);
        const expectedDate = await page.evaluate(locale => new Intl.DateTimeFormat(locale, {
          weekday: "short", day: "numeric", month: "numeric", year: "numeric"
        }).format(new Date()), locale(language));
        await expect(page.locator(".card .date").first()).toHaveText(expectedDate);
        for (const [open, dialog, close] of [
          ["#serviceFilterBtn", "#serviceFilterDialog", "#closeServiceFilterDialog"],
          ["#feedbackBtn", "#feedbackDialog", "#closeFeedbackDialog"],
          ["#reminderBtn", "#reminderDialog", "#closeReminderDialog"]
        ]) {
          await page.locator(open).click();
          await expect(page.locator(dialog)).toBeVisible();
          await expectLayout(page, dialog, false);
          if (dialog === "#feedbackDialog") {
            const text = language === "et" ? "Eesti: õ ä ö ü — prügikasti tühjendus" : language === "vi" ? "Tiếng Việt: Ắ ễ ộ ự — kiểm tra" : "简体中文：垃圾清运时间，测试。";
            await page.locator("#feedbackMessage").pressSequentially(text);
            await expect(page.locator("#feedbackMessage")).toHaveValue(text);
          }
          await page.locator(close).press("Enter");
          await expect(page.locator(open)).toBeFocused();
        }
        await page.reload();
        await expect(page.locator("html")).toHaveAttribute("lang", language);
        await login(page, true);
        await page.locator("#compactEmbedBtn").click();
        await expect(page).toHaveURL(new RegExp(`lang=${language}`));
        await expect(page.locator("html")).toHaveAttribute("lang", language);
        await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
        await expect(page.locator("#cards .card")).toHaveCount(3);
        await expectLayout(page, "main", false);
        expect(writes).toEqual([]);
      });
    });
  }
}

test("IME candidate confirmation must not submit a partial password", async ({ page }) => {
  await setTestDates(page);
  await page.goto("/");
  await page.locator("#languageSelect").selectOption("zh-Hans");
  await page.locator("#username").fill("01-0000633-00");
  await page.locator("#password").fill("synthetic-密码");
  for (const event of [{ key: "Enter", isComposing: true }, { key: "Enter", keyCode: 229 }]) {
    // Inspect synchronous application state before any network response can finish.
    const submitted = await page.locator("#password").evaluate((input, event) => {
      input.dispatchEvent(new window.KeyboardEvent("keydown", { ...event, bubbles: true }));
      return window.document.querySelector("#loadBtn").disabled;
    }, event);
    expect(submitted, "committing an IME candidate must not start sign-in").toBe(false);
  }
  await page.locator("#password").press("Enter");
  await expect(page.locator("#cards .card")).toHaveCount(3);
});

test("README button opens the short guide in every interface language", async ({ page }) => {
  await page.goto("/");
  for (const language of supported) {
    await page.locator("#languageSelect").selectOption(language);
    await page.locator("#readmeBtn").click();
    await expect(page.locator("#readmeDialogTitle")).toHaveText(`README.${language}.md`);
    const content = page.locator("#readmeContent");
    await expect(content).toBeVisible();
    await expect(content).toHaveAttribute("lang", language);
    await expect(content).toHaveAttribute("dir", direction(language));
    await expect(content).toContainText("python3 run.py");
    await expect(content.locator('a[data-doc-path="TECHNICAL.md"]')).toBeVisible();
    await page.locator("#closeReadmeDialog").click();
  }
});
