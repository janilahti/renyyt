const { defineConfig } = require("@playwright/test");
const base = require("./playwright.config");

module.exports = defineConfig({
  ...base,
  testIgnore: [],
  testMatch: "**/visual.spec.js",
  workers: 1,
  retries: 0,
  snapshotPathTemplate: "{testDir}/visual.spec.js-snapshots/{arg}{ext}",
  expect: {
    toHaveScreenshot: { animations: "disabled", caret: "hide", scale: "css", threshold: 0.1, maxDiffPixels: 0 }
  },
  use: {
    ...base.use,
    locale: "fi-FI",
    deviceScaleFactor: 1,
    reducedMotion: "reduce"
  },
  // Comparison images are reviewed in the pinned Linux/amd64 container only.
  projects: [{ name: "visual-chromium", use: { browserName: "chromium" } }]
});
