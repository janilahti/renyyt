const { test, expect } = require("@playwright/test");
const { setTestDates } = require("./support");
const { expectLayout } = require("./layout");
const i18n = require("../../web/i18n");

for (const width of [600, 601]) {
  test(`collection labels fit across the ${width}px card breakpoint`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const monday = new Date();
    monday.setUTCDate(monday.getUTCDate() - (monday.getUTCDay() + 6) % 7);
    monday.setUTCHours(10, 0, 0, 0);
    await setTestDates(page, monday);
    await page.route("**/api/v1/renyyt", async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.services.push({ ...data.services[2], ASTAsnro: "D" });
      data.services.push({ ...data.services[2], ASTAsnro: "E" });
      data.services.forEach((service, index) => {
        const date = new Date(monday);
        date.setUTCDate(date.getUTCDate() + [0, 1, 2, 3, 7][index]);
        Object.assign(service, {
          ASTNextDate: date.toISOString().slice(0, 10),
          ASTNimi: "Synthetic collection bin 140 L", KIRPros: 50,
          tariff: { productgroup: "BIO" },
          kimppa: { KIMNimi1: "Synthetic shared bin", KIMMaara: 2 }
        });
      });
      await route.fulfill({ response, json: data });
    });
    await page.goto("/");
    await page.locator("#username").fill("01-0000633-00");
    await page.locator("#password").fill("secret");
    await page.locator("#remember").check();
    await page.locator("#loadBtn").click();
    await expect(page.locator("#cards .card")).toHaveCount(5);

    for (const mode of ["normal", "compact", "embed"]) {
      if (mode === "compact") await page.locator("#compactViewBtn").click();
      if (mode === "embed") await page.locator("#compactEmbedBtn").click();
      for (const language of i18n.supported) {
        if (mode === "embed") {
          // Embedded links expose language through their public URL parameter.
          await page.evaluate(language => {
            const params = new URLSearchParams(window.location.hash.slice(1));
            params.set("lang", language);
            window.location.hash = params.toString();
          }, language);
        } else {
          await page.locator("#languageSelect").selectOption(language);
        }
        await expect(page.locator("html")).toHaveAttribute("lang", language);
        await test.step(`${mode}/${language}`, () => checkLabels(page, width, `${mode}/${language}`));
        if (width === 601 && mode === "normal" && language === "en") {
          await test.step("English at 150% text size still centres wrapped lines", async () => {
            await page.evaluate(() => { window.document.documentElement.style.fontSize = "150%"; });
            try {
              expect(await checkLabels(page, width, "en/150% text"), "Exercise actual multiline pill text").toBeTruthy();
            } finally {
              await page.evaluate(() => { window.document.documentElement.style.removeProperty("font-size"); });
            }
          });
        }
      }
    }
  });
}

async function checkLabels(page, width, context) {
  await page.evaluate(() => window.document.fonts.ready);
  const labels = await page.locator(".card-date-block").evaluateAll(blocks => blocks.map(block => {
    const label = block.querySelector(".due-label, .help");
    const date = block.querySelector(".date");
    const main = block.parentElement.querySelector(".card-main");
    const bounds = label.getBoundingClientRect();
    const range = window.document.createRange();
    range.selectNodeContents(label);
    const lines = new Map();
    for (const rect of range.getClientRects()) {
      const key = Math.round(rect.top);
      const line = lines.get(key) || { left: rect.left, right: rect.right };
      line.left = Math.min(line.left, rect.left);
      line.right = Math.max(line.right, rect.right);
      lines.set(key, line);
    }
    return {
      text: label.textContent,
      wrappedPill: label.matches(".due-label") && lines.size > 1,
      centered: !label.matches(".due-label") || [...lines.values()].every(line => Math.abs((line.left + line.right - bounds.left - bounds.right) / 2) < 2),
      fits: label.scrollWidth <= label.clientWidth + 1 && bounds.width <= block.clientWidth + 1,
      gap: bounds.top - date.getBoundingClientRect().bottom,
      below: block.getBoundingClientRect().top >= main.getBoundingClientRect().bottom - 1
    };
  }));
  expect(labels).toHaveLength(5);
  for (const label of labels) {
    const message = `${context}: ${JSON.stringify(label)}`;
    expect(label.centered, message).toBeTruthy();
    expect(label.fits, message).toBeTruthy();
    expect(label.gap, message).toBeGreaterThanOrEqual(3);
    expect(label.gap, message).toBeLessThanOrEqual(5);
    expect(label.below, message).toBe(width <= 600);
  }
  await expectLayout(page, "main", false);
  return labels.some(label => label.wrappedPill);
}
