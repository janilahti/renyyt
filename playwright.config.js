const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests/e2e",
  testIgnore: "**/visual.spec.js",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:18514",
    timezoneId: "UTC",
    // Service-worker requests bypass Playwright routes used for synthetic fixtures.
    serviceWorkers: "block",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "python3 run.py",
    url: "http://127.0.0.1:18514/ready",
    // CI must never accidentally test an existing server with different settings.
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
    env: { ...process.env, RENYYT_LOG_LEVEL: "ERROR", RENYYT_FIXTURE_FILE: "tests/fixtures/e2e-services.json" }
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "firefox", use: { browserName: "firefox" } },
    { name: "webkit", use: { browserName: "webkit" } }
  ]
});
