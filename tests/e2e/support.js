const { expect } = require("@playwright/test");

async function login(page, remember = false) {
  await page.locator("#username").fill("01-0000633-00");
  await page.locator("#password").fill("secret");
  if (remember) await page.locator("#remember").check();
  await page.locator("#loadBtn").click();
  await expect(page.locator("#resultsPanel")).toBeVisible();
  await expect(page.locator("#cards .card")).toHaveCount(3);
}

async function setTestDates(page, referenceDate = new Date()) {
  // Use the reference week's Monday so today/tomorrow/this-week labels stay deterministic.
  const monday = new Date(referenceDate);
  monday.setUTCDate(monday.getUTCDate() - (monday.getUTCDay() + 6) % 7);
  monday.setUTCHours(10, 0, 0, 0);
  await page.clock.setFixedTime(monday);
  await page.route("**/api/v1/renyyt", async route => {
    // Exercise the real fixture server, then make only its sample dates relative.
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    const data = await response.json();
    data.services.forEach((service, index) => {
      const date = new Date(monday);
      date.setUTCDate(date.getUTCDate() + index);
      service.ASTNextDate = date.toISOString().slice(0, 10);
    });
    await route.fulfill({ response, json: data });
  });
}

module.exports = { login, setTestDates };
