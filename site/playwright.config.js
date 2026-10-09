import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  fullyParallel: true,
  workers: process.env.CI ? 2 : 3,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4174/Orion/",
    browserName: "chromium",
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {},
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run build && npm run preview",
    url: "http://127.0.0.1:4174/Orion/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
