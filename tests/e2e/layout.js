const { expect } = require("@playwright/test");

async function expectLayout(page, selector = "main", mobile = true) {
  const problems = await page.locator(selector).evaluate((root, mobile) => {
    const issues = [];
    const bounds = root.getBoundingClientRect();
    const name = el => el.id || el.className || el.tagName;
    const visible = el => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && el.checkVisibility({ visibilityProperty: true });
    };
    const hitTarget = el => el.type === "checkbox" ? el.labels[0] : el;
    const controls = [...root.querySelectorAll("button, input, select, textarea, summary")].filter(visible);
    if (root.scrollWidth > root.clientWidth + 1) issues.push("container scrolls horizontally");
    if (window.document.documentElement.scrollWidth > window.innerWidth + 1) issues.push("page scrolls horizontally");
    for (const el of controls) {
      // Native checkboxes use their associated label as the larger touch target.
      const target = hitTarget(el);
      const box = target.getBoundingClientRect();
      if (mobile && (box.width < 43.5 || box.height < 43.5)) issues.push(`${name(el)} target ${box.width.toFixed(1)}x${box.height.toFixed(1)}`);
      if (box.left < bounds.left - 1 || box.right > bounds.right + 1 || box.left < -1 || box.right > window.innerWidth + 1) {
        issues.push(`${name(el)} extends outside its container`);
      }
      if (el.tagName === "SELECT") {
        const style = window.getComputedStyle(el);
        const canvas = window.document.createElement("canvas").getContext("2d");
        canvas.font = style.font;
        const textWidth = canvas.measureText(el.selectedOptions[0].textContent).width;
        // Reserve room for padding and the native dropdown arrow as well as text.
        const requiredWidth = textWidth + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 20;
        if (box.width < requiredWidth) issues.push(`${name(el)} truncates its selected option (${box.width.toFixed(1)}px available, ${requiredWidth.toFixed(1)}px required)`);
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
    if (mobile && rememberHelp && visible(rememberHelp)) {
      const label = root.querySelector(".remember-label").getBoundingClientRect();
      const help = rememberHelp.getBoundingClientRect();
      if (help.top < label.bottom - 1 || help.width < rememberHelp.parentElement.clientWidth - 1) {
        issues.push("saved-credential explanation must occupy its own full-width row");
      }
    }
    return issues;
  }, mobile);
  expect(problems, `Layout at ${page.viewportSize().width}px in ${selector}`).toEqual([]);
}

module.exports = { expectLayout };
