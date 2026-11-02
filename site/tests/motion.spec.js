import { test, expect } from "@playwright/test";
import { openHome, scrollToChapter } from "./helpers.js";

test("reduced motion shows the headline at once and runs no decorative loop", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("html")).toHaveAttribute("data-scene", "webgl", {
    timeout: 20000,
  });
  const opacities = await page
    .locator(".hero .w")
    .evaluateAll((nodes) => nodes.map((n) => getComputedStyle(n).opacity));
  expect(opacities.length).toBeGreaterThan(2);
  expect(opacities.every((o) => o === "1")).toBe(true);
  await page.waitForTimeout(800);
  const a = Number(
    (await page.locator("html").getAttribute("data-frames")) || 0,
  );
  await page.waitForTimeout(1200);
  const b = Number(
    (await page.locator("html").getAttribute("data-frames")) || 0,
  );
  expect(b).toBe(a);
  await expect(
    page.getByRole("button", { name: "Pause animations" }),
  ).toHaveAttribute("title", /device preference/);
});

test("reduced motion still moves between chapters (still frames) and the page keeps working", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openHome(page);
  await scrollToChapter(page, "preview", 0.4);
  await expect(page.locator("html")).toHaveAttribute("data-chapter", "preview");
  await expect(
    page.getByRole("heading", { name: /See every path/ }),
  ).toBeVisible();
});
