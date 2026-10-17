const globals = require("globals");

module.exports = [
  { ignores: ["dist/**", "node_modules/**", "playwright-report/**", "test-results/**"] },
  {
    files: ["web/**/*.js"],
    languageOptions: { ecmaVersion: 2021, sourceType: "script", globals: { ...globals.browser, module: "readonly" } },
    rules: { "no-undef": "error", "no-unreachable": "error", "no-dupe-keys": "error", "no-redeclare": "error" }
  },
  {
    files: ["tests/**/*.js", "playwright.config.js"],
    languageOptions: { ecmaVersion: 2021, sourceType: "commonjs", globals: { ...globals.node } },
    rules: { "no-undef": "error", "no-unreachable": "error", "no-dupe-keys": "error", "no-redeclare": "error" }
  }
];
