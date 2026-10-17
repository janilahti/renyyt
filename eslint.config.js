const globals = require("globals");

module.exports = [
  { ignores: ["dist/**", "node_modules/**", "playwright-report/**", "test-results/**"] },
  {
    files: ["web/**/*.js"],
    languageOptions: { ecmaVersion: 2021, sourceType: "script", globals: { ...globals.browser, module: "readonly" } },
    rules: { "no-undef": "error", "no-unreachable": "error", "no-dupe-keys": "error", "no-redeclare": "error" }
  },
  {
    // helpers.js also runs in Node's dependency-free unit tests.
    files: ["web/helpers.js"],
    languageOptions: { globals: { Buffer: "readonly" } }
  },
  {
    files: ["tests/**/*.js", "playwright.config.js"],
    languageOptions: { ecmaVersion: 2021, sourceType: "commonjs", globals: { ...globals.node } },
    rules: { "no-undef": "error", "no-unreachable": "error", "no-dupe-keys": "error", "no-redeclare": "error" }
  },
  {
    // page.evaluate callbacks execute in the browser, while the test runner uses Node.
    files: ["tests/e2e/**/*.js"],
    languageOptions: { globals: { window: "readonly" } }
  }
];
