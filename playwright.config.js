const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8787",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "python3 run.py",
    url: "http://127.0.0.1:8787/ready",
    reuseExistingServer: true,
    timeout: 15_000,
    env: { ...process.env, RENYYT_LOG_LEVEL: "ERROR", RENYYT_FIXTURE_FILE: "tests/fixtures/e2e-services.json" }
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }]
});
