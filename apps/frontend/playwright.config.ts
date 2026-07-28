import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/accessibility",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npx next build && npx serve out -p 3000",
    port: 3000,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
});