const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");
const { expectLayout } = require("./layout");

async function expectActionRows(page, selector) {
  const rows = await page.locator(selector).evaluate(root => {
    const buttons = [...root.querySelectorAll("button")].filter(button => button.checkVisibility());
    const rows = [];
    for (const button of buttons) {
      const box = button.getBoundingClientRect();
      let row = rows.find(row => Math.abs(row.top - box.top) < 1);
      if (!row) rows.push(row = { top: box.top, buttons: [] });
      row.buttons.push(button.id);
    }
    return rows.map(row => row.buttons);
  });
  if (rows.flat().length === 3) {
    expect([[3], [1, 2], [1, 1, 1]]).toContainEqual(rows.map(row => row.length));
    return;
  }
  expect(rows.flat()).toHaveLength(4);
  // A single orphan belongs at the beginning, never at the trailing embed action.
  expect(rows.map(row => row.length)).not.toEqual([3, 1]);
  if (rows.length === 2) expect([[1, 3], [2, 2]]).toContainEqual(rows.map(row => row.length));
  if (rows.length > 2) expect(rows.map(row => row.length)).toEqual([1, 1, 1, 1]);
}

for (const width of [320, 430, 600, 700, 701, 960]) {
  test(`related controls stay grouped at ${width}px`, async ({ page }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width, height: 900 });
    await setTestDates(page);
    await page.route("**/api/v1/features", route => route.fulfill({ json: {
      feedback: true, pwa: true, reminders: { enabled: false }
    } }));
    await page.goto("/");
    await expect(page.locator("#feedbackBtn")).toBeVisible();
    await expectActionRows(page, ".login-fields .login-actions");
    await login(page, true);
    for (const language of ["fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
      await test.step(language, async () => {
        await page.locator("#languageSelect").selectOption(language);
        for (const theme of ["system", "light", "dark"]) {
          await page.locator("#themeSelect").selectOption(theme);
          await expectLayout(page, "main", width <= 700);
        }
        if (width > 360) {
          const languageBox = await page.locator("#languageSelect").boundingBox();
          const themeBox = await page.locator("#themeSelect").boundingBox();
          expect(Math.abs(languageBox.y - themeBox.y)).toBeLessThan(1);
        }
        await expectActionRows(page, ".compact-actions .login-actions");
        await page.locator("#expandLoginBtn").click();
        await expectActionRows(page, ".login-fields .login-actions");
        await expectLayout(page, "main", width <= 700);
        await page.locator("#loadBtn").focus();
        await page.keyboard.press("Tab");
        await expect(page.locator("#forgetBtn")).toBeFocused();
        await page.locator("#loadBtn").click();
        await expect(page.locator("#loginPanel")).toHaveClass(/compact/);
      });
    }
  });
}
