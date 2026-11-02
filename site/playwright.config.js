import { defineConfig } from "@playwright/test";
// Software WebGL keeps the 3D scene deterministic on machines and CI runners without a GPU.
const args = [
  "--use-gl=angle",
  "--use-angle=swiftshader",
  "--enable-unsafe-swiftshader",
  "--ignore-gpu-blocklist",
];
export default defineConfig({
  testDir: "./tests",
  testIgnore: ["**/unit/**"],
  timeout: 60000,
  fullyParallel: true,
  workers: 2,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4174/Orion/",
    browserName: "chromium",
    launchOptions: {
      args,
      ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
        : {}),
    },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run build && npm run preview",
    url: "http://127.0.0.1:4174/Orion/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
