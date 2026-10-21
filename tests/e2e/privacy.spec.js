const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");
const { expectLayout } = require("./layout");
const i18n = require("../../web/i18n");

test("login identity and privacy information are available in every language", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await setTestDates(page);
  await page.goto("/");
  for (const language of i18n.supported) {
    await page.locator("#languageSelect").selectOption(language);
    const help = i18n.t(language, "login.credentialsHelp");
    expect(help).toContain("Oma jätehuolto");
    await expect(page.locator("#loginCredentialsHelp")).toHaveText(help);
    await expect(page.locator("#username")).toHaveAccessibleDescription(help);
    await expect(page.locator("#password")).toHaveAccessibleDescription(help);
    await expect(page.locator('[data-i18n="privacy.title"]')).toHaveText(i18n.t(language, "privacy.title"));
    await expect(page.locator('[data-i18n="privacy.text"]')).toHaveText(i18n.t(language, "privacy.text"));
    await expectLayout(page, "main", false);
  }
  await page.locator("#languageSelect").selectOption("fi");
  await login(page);
  await expect(page.locator("#loginCredentialsHelp")).toBeHidden();
  await expect(page.locator("#securityPanel")).toBeHidden();
  await page.locator("#expandLoginBtn").click();
  await expect(page.locator("#loginCredentialsHelp")).toBeVisible();
  await expect(page.locator("#securityPanel")).toBeVisible();
});
