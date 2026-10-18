const { test, expect } = require("@playwright/test");
const { login, setTestDates } = require("./support");

const widths = [320, 390, 430];

async function expectLayout(page, selector = "main") {
  const problems = await page.locator(selector).evaluate(root => {
    const issues = [];
    const bounds = root.getBoundingClientRect();
    const name = el => el.id || el.className || el.tagName;
    const visible = el => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && el.checkVisibility({ visibilityProperty: true });
    };
    const hitTarget = el => el.type === "checkbox" ? el.labels[0] : el;
    const controls = [...root.querySelectorAll("button, input, select, textarea, summary")].filter(visible);
    if (root.scrollWidth > root.clientWidth + 1) issues.push(`${selector} scrolls horizontally`);
    if (window.document.documentElement.scrollWidth > window.innerWidth + 1) issues.push("page scrolls horizontally");
    for (const el of controls) {
      // Native checkboxes use their associated label as the larger touch target.
      const target = hitTarget(el);
      const box = target.getBoundingClientRect();
      if (box.width < 43.5 || box.height < 43.5) issues.push(`${name(el)} target ${box.width.toFixed(1)}x${box.height.toFixed(1)}`);
      if (box.left < bounds.left - 1 || box.right > bounds.right + 1 || box.left < -1 || box.right > window.innerWidth + 1) {
        issues.push(`${name(el)} extends outside ${selector}`);
      }
      if (el.tagName === "SELECT") {
        const style = window.getComputedStyle(el);
        const canvas = window.document.createElement("canvas").getContext("2d");
        canvas.font = style.font;
        const textWidth = canvas.measureText(el.selectedOptions[0].textContent).width;
        // Reserve room for padding and the native dropdown arrow as well as text.
        const requiredWidth = textWidth + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 20;
        if (box.width < requiredWidth) issues.push(`${name(el)} truncates its selected option`);
      }
    }
    const overlaps = (a, b) => {
      const x = a.getBoundingClientRect(), y = b.getBoundingClientRect();
      return Math.min(x.right, y.right) - Math.max(x.left, y.left) > 1 && Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top) > 1;
    };
    for (let i = 0; i < controls.length; i++) {
      for (const other of controls.slice(i + 1)) {
        // The password visibility button deliberately sits inside the padded input.
        if ([controls[i].id, other.id].includes("togglePasswordBtn") && [controls[i].id, other.id].includes("password")) continue;
        if (overlaps(hitTarget(controls[i]), hitTarget(other))) issues.push(`${name(controls[i])} overlaps ${name(other)}`);
      }
    }
    for (const parent of root.querySelectorAll(".header-copy, .header-row, .card-top, .dialog-head")) {
      const children = [...parent.children].filter(visible);
      for (let i = 0; i < children.length; i++) {
        const child = children[i];
        if (child.scrollWidth > child.clientWidth + 1) issues.push(`${name(child)} clips its content`);
        for (const other of children.slice(i + 1)) {
          if (overlaps(child, other)) issues.push(`${name(child)} overlaps ${name(other)}`);
        }
      }
    }
    const rememberHelp = root.querySelector("#rememberHelp");
    if (rememberHelp && visible(rememberHelp)) {
      const label = root.querySelector(".remember-label").getBoundingClientRect();
      const help = rememberHelp.getBoundingClientRect();
      if (help.top < label.bottom - 1 || help.width < rememberHelp.parentElement.clientWidth - 1) {
        issues.push("saved-credential explanation must occupy its own full-width row");
      }
    }
    return issues;
  });
  expect(problems, `Layout at ${page.viewportSize().width}px in ${selector}`).toEqual([]);
}

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
      for (const language of ["fi", "en", "sv", "uk", "ar"]) {
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
      for (const language of ["fi", "uk", "ar"]) {
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
            if (dialog === "#feedbackDialog" && language === "ar") {
              await page.locator("#feedbackMessage").fill("رسالة تجريبية");
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
