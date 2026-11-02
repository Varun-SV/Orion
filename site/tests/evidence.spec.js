import { test, expect } from "@playwright/test";
import { calmScene } from "./helpers.js";

test.use({ storageState: calmScene });

test("standalone documentation and licences render with working local assets", async ({
  page,
  request,
}) => {
  const failures = [];
  page.on("response", (response) => {
    if (response.status() >= 400) failures.push(response.url());
  });
  page.on("pageerror", (error) => failures.push(error.message));
  for (const route of [
    "docs/install.html",
    "docs/recovery.html",
    "docs/licenses.html",
  ]) {
    await page.goto("./" + route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    for (const href of await page
      .locator('a[href^="/Orion/"]')
      .evaluateAll((links) => links.map((link) => link.href))) {
      const response = await request.get(href.split("#")[0]);
      expect(response.status()).toBe(200);
    }
  }
  expect(failures).toEqual([]);
});

test("reloading the skip-link fragment retains usable page content", async ({
  page,
}) => {
  await page.goto("./");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page).toHaveTitle("Overview · Orion");
});
