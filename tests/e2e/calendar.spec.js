const { test, expect } = require("@playwright/test");
const fs = require("fs");
const { login, setTestDates } = require("./support");
const { expectLayout } = require("./layout");

test.beforeEach(async ({ page }) => { await setTestDates(page); });

test("calendar choices, all-day Google links and standards-compliant download", async ({ page }) => {
  await page.goto("/");
  await login(page);
  await page.locator("#icsBtn").click();
  await expect(page.locator("#calendarDialog")).toBeVisible();
  const links = page.locator("#calendarEvents a");
  await expect(links).toHaveCount(3);
  const url = new URL(await links.first().getAttribute("href"));
  expect(url.origin).toBe("https://calendar.google.com");
  expect(url.searchParams.get("text")).toBe("Jäteastian tyhjennys: Paperi");
  expect(url.searchParams.get("dates")).toMatch(/^\d{8}\/\d{8}$/);
  expect(url.searchParams.has("username")).toBe(false);
  expect(url.searchParams.has("password")).toBe(false);
  await expect(links.first()).toHaveAttribute("rel", "noopener noreferrer");
  const downloading = page.waitForEvent("download");
  await page.locator("#downloadCalendarBtn").click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("renyyt-tyhjennykset.ics");
  const contents = fs.readFileSync(await download.path(), "utf8");
  expect((contents.match(/BEGIN:VEVENT/g) || []).length).toBe(3);
  expect(contents).toMatch(/DTSTAMP:\d{8}T\d{6}Z\r\n/);
  expect(contents).toMatch(/DTEND;VALUE=DATE:\d{8}\r\n/);
  expect(contents).not.toContain("secret");
  expect(contents).not.toContain("01-0000633-00");
  await expect(page.locator("#calendarStatus")).toContainText("Lataus käynnistetty");
  await page.locator("#closeCalendarDialog").click();
  await expect(page.locator("#icsBtn")).toBeFocused();
  // Export follows the user's bin selection.
  await page.locator("#serviceFilterBtn").click();
  await page.locator('#serviceFilterDialog input[type="checkbox"]').first().uncheck();
  await page.locator("#closeServiceFilterDialog").click();
  await page.locator("#icsBtn").click();
  await expect(links).toHaveCount(2);
  await expect(page.locator("#calendarEvents")).not.toContainText("Paperi");
  await page.locator("#closeCalendarDialog").click();
  await page.locator("#serviceFilterBtn").click();
  for (const checkbox of await page.locator('#serviceFilterDialog input[type="checkbox"]').all()) await checkbox.uncheck();
  await page.locator("#closeServiceFilterDialog").click();
  await page.locator("#icsBtn").click();
  await expect(links).toHaveCount(0);
  await expect(page.locator("#calendarStatus")).toContainText("Ei vietäviä tyhjennyspäiviä");
  await expect(page.locator("#downloadCalendarBtn")).toBeDisabled();
});

test("native file sharing handles success, cancellation, failures and missing support", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "canShare", { configurable: true, value: data => data.files.length === 1 });
    Object.defineProperty(navigator, "share", { value: async data => {
      if (window.shareFailure) throw new DOMException("Synthetic share result", window.shareFailure);
      window.sharedFile = { name: data.files[0].name, content: await data.files[0].text() };
    } });
  });
  await page.goto("/");
  await login(page);
  await page.locator("#icsBtn").click();
  await expect(page.locator("#shareCalendarBtn")).toBeVisible();
  await page.locator("#shareCalendarBtn").click();
  await expect.poll(() => page.evaluate(() => window.sharedFile?.content)).toContain("BEGIN:VCALENDAR");
  await page.evaluate(() => { window.shareFailure = "AbortError"; });
  await page.locator("#shareCalendarBtn").click();
  await expect(page.locator("#shareCalendarBtn")).toBeEnabled();
  await expect(page.locator("#calendarStatus")).toBeEmpty();
  await page.evaluate(() => { window.shareFailure = "NotAllowedError"; });
  await page.locator("#shareCalendarBtn").click();
  await expect(page.locator("#calendarStatus")).toContainText("Tiedostoa ei voitu jakaa");
  await page.locator("#closeCalendarDialog").click();
  await page.evaluate(() => Object.defineProperty(navigator, "canShare", { value: () => false }));
  await page.locator("#icsBtn").click();
  await expect(page.locator("#shareCalendarBtn")).toBeHidden();
  await expect(page.locator("#downloadCalendarBtn")).toBeEnabled();
});

test("calendar dialog fits mobile LTR and RTL languages", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 600 });
  await page.goto("/");
  await login(page);
  for (const language of ["fi", "en", "sv", "uk", "ar", "fa", "vi", "zh-Hans", "et"]) {
    await page.locator("#languageSelect").selectOption(language);
    await page.locator("#icsBtn").click();
    await expect(page.locator("#calendarDialog")).toBeVisible();
    await expectLayout(page, "#calendarDialog");
    await page.locator("#closeCalendarDialog").click();
    await expect(page.locator("#icsBtn")).toBeFocused();
  }
});
