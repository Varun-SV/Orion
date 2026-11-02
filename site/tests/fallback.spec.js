import { test, expect } from "@playwright/test";
import {
  COLLECTIONS,
  ROUTES,
  noOverflow,
  openHome,
  scrollToChapter,
} from "./helpers.js";

test.beforeEach(async ({ page }) => {
  // A browser with WebGL switched off or blocked.
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
      if (/webgl/i.test(String(type))) return null;
      return original.call(this, type, ...rest);
    };
  });
});

test("without WebGL the SVG constellation replaces the scene and nothing breaks", async ({
  page,
}) => {
  const problems = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on(
    "console",
    (message) => message.type() === "error" && problems.push(message.text()),
  );
  await openHome(page, "fallback");
  await expect(page.locator(".fallback-sky svg")).toBeVisible();
  await expect(page.locator("#world")).toBeHidden();
  expect(await page.locator(".fallback-sky circle").count()).toBe(8);
  expect(problems).toEqual([]);
});

test("without WebGL every chapter still works and shows its content", async ({
  page,
}) => {
  await openHome(page, "fallback");
  for (const id of ROUTES) {
    await scrollToChapter(page, id, 0.3);
    await expect(page.locator("html")).toHaveAttribute("data-chapter", id);
    await expect(page.locator(`#${id} h1, #${id} h2`).first()).toBeVisible();
  }
  await expect(page.locator(".collection-list button")).toHaveCount(7);
});

test("the sample works without WebGL: preview, simulate and reset for every collection", async ({
  page,
}) => {
  await openHome(page, "fallback");
  await page.goto("./#demo");
  for (const name of ["Movies", "Music", "Books"]) {
    await page.getByRole("button", { name: `Sample ${name}` }).click();
    await page.getByRole("button", { name: "Preview sample plan" }).click();
    await expect(page.getByTestId("hero-plan")).toContainText(
      name === "Music"
        ? "Music/Sample Artist/"
        : name === "Books"
          ? "Books/Sample Author/"
          : "Movies/The Lantern (2024)/",
    );
    await page.getByRole("button", { name: "Simulate organisation" }).click();
    await expect(page.getByRole("status")).toContainText(
      "No files were moved.",
    );
    await page.getByRole("button", { name: /Reset sample/ }).click();
    await expect(
      page.getByRole("button", { name: "Preview sample plan" }),
    ).toBeVisible();
  }
  expect(COLLECTIONS).toHaveLength(7);
});

test("the page has no horizontal overflow without WebGL", async ({ page }) => {
  await openHome(page, "fallback");
  expect(await noOverflow(page)).toBe(true);
});
