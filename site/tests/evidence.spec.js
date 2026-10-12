import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

test("all primary routes can be followed with the keyboard", async ({
  page,
}) => {
  await page.goto("./");
  const routes = [
    "Overview",
    "Features",
    "Install",
    "Recovery & privacy",
    "Demo",
  ];
  for (const route of routes) {
    const link = page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: route, exact: true });
    await link.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveTitle(new RegExp(route + ".*Orion"));
    await expect(link).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});

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

for (const width of [360, 390, 768, 1280, 1600]) {
  test(
    "sample actions and sticky fixture notice at " + width + "px",
    async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.emulateMedia({ reducedMotion: "reduce" });
      const requests = [],
        errors = [];
      page.on("request", (request) => requests.push(request.url()));
      page.on("pageerror", (error) => errors.push(error.message));
      for (const theme of ["ivory", "clay", "night"]) {
        await page.goto("./#demo");
        await page
          .getByRole("combobox", { name: "Colour theme" })
          .selectOption(theme);
        await page.getByRole("button", { name: "Books", exact: true }).click();
        await page.getByRole("button", { name: "Preview sample plan" }).click();
        await expect(page.getByTestId("sample-plan")).toContainText(
          "Books/Sample Author/",
        );
        await page
          .getByRole("button", { name: "Simulate organisation" })
          .click();
        await expect(page.getByRole("status")).toContainText(
          "No files were moved.",
        );
        await page.evaluate(() =>
          window.scrollTo(0, document.body.scrollHeight),
        );
        const banner = await page
          .getByRole("note", { name: "Fixture demo" })
          .boundingBox();
        expect(banner.y).toBeGreaterThanOrEqual(0);
        expect(banner.y + banner.height).toBeLessThanOrEqual(1000);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
      expect(
        requests.filter(
          (url) => !url.startsWith("http://127.0.0.1:4174/Orion/"),
        ),
      ).toEqual([]);
      expect(requests.filter((url) => /\/api\//.test(url))).toEqual([]);
      expect(errors).toEqual([]);
      if (process.env.SITE_CAPTURE_SCREENSHOTS === "1") {
        const directory = resolve(
          import.meta.dirname,
          "../../docs/validation/screenshots",
        );
        await mkdir(directory, { recursive: true });
        await page
          .getByRole("combobox", { name: "Colour theme" })
          .selectOption("ivory");
        await page.goto("./");
        await page.evaluate(() => document.fonts.ready);
        await page.evaluate(() => {
          document.activeElement?.blur();
          window.scrollTo(0, 0);
        });
        await page.screenshot({
          path: resolve(directory, "site-overview-" + width + ".png"),
          fullPage: true,
        });
        await page.goto("./#demo");
        await page.getByRole("button", { name: "Preview sample plan" }).click();
        await page.evaluate(() => {
          document.activeElement?.blur();
          window.scrollTo(0, 0);
        });
        await page.screenshot({
          path: resolve(directory, "site-demo-" + width + ".png"),
          fullPage: true,
        });
      }
    },
  );
}

test('reloading the skip-link fragment retains usable page content', async ({ page }) => {
  await page.goto('./');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page).toHaveTitle('Overview · Orion');
});
