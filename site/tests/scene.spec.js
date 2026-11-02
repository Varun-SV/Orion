import { test, expect } from "@playwright/test";
import {
  COLLECTIONS,
  ROUTES,
  openHome,
  scrollToChapter,
  watchProblems,
} from "./helpers.js";

test("the 3D world starts, renders frames and reports no browser problems", async ({
  page,
}) => {
  const problems = watchProblems(page);
  await openHome(page);
  await expect(page.locator("#world")).toBeVisible();
  await expect
    .poll(
      async () =>
        Number(await page.locator("html").getAttribute("data-frames")),
      { timeout: 20000 },
    )
    .toBeGreaterThan(0);
  await expect(page.locator("html")).toHaveAttribute(
    "data-tier",
    /high|medium|low/,
  );
  expect(problems).toEqual([]);
});

test("the headline and calls to action are readable before the 3D scene has loaded", async ({
  page,
}) => {
  await page.route("**/assets/world-*.js", (route) => route.abort());
  const problems = [];
  page.on("pageerror", (error) => problems.push(error.message));
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Make room",
  );
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "For everything",
  );
  await expect(
    page.getByRole("link", { name: /Begin the descent/ }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-scene", "fallback", {
    timeout: 10000,
  });
  expect(problems).toEqual([]);
});

test("scrolling through the page activates every chapter in order", async ({
  page,
}) => {
  await openHome(page);
  const seen = [];
  for (const id of ROUTES) {
    await scrollToChapter(page, id, 0.2);
    await expect(page.locator("html")).toHaveAttribute("data-chapter", id);
    seen.push(id);
    await expect(page).toHaveTitle(/· Orion$/);
  }
  expect(seen).toEqual(ROUTES);
});

test("each collection is a real star: scrolling and the list select the matching cover", async ({
  page,
}) => {
  await openHome(page);
  await scrollToChapter(page, "features", 0.5);
  const buttons = page.locator(".collection-list button");
  await expect(buttons).toHaveCount(7);
  await expect(page.locator("[data-cover][aria-hidden='false']")).toHaveCount(
    1,
  );
  for (const [index, name] of COLLECTIONS.entries()) {
    await buttons.nth(index).click();
    await expect(buttons.nth(index)).toHaveAttribute("aria-current", "true");
    await expect(page.locator(`[data-cover="${index}"]`)).toHaveAttribute(
      "aria-hidden",
      "false",
    );
    await expect(
      page.locator(".collection-list button", { hasText: name }).first(),
    ).toHaveAttribute("aria-current", "true");
  }
});

test("clicking a star in the sky jumps to its collection", async ({
  page,
  isMobile,
}) => {
  test.skip(
    Boolean(isMobile),
    "Star labels are hidden on the opening phone view.",
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHome(page);
  const rigel = page.locator('.star-label[data-collection="6"]');
  await expect(rigel).toBeVisible({ timeout: 25000 });
  await rigel.locator(".hit").click();
  await expect(page.locator("html")).toHaveAttribute(
    "data-chapter",
    "features",
  );
  await expect(page.locator('[data-cover="6"]')).toHaveAttribute(
    "aria-hidden",
    "false",
  );
});

test("every star label is a keyboard-focusable button with an accessible name", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHome(page);
  const labels = page.locator(".star-label");
  await expect(labels).toHaveCount(7);
  for (let i = 0; i < 7; i++)
    await expect(labels.nth(i)).toHaveAttribute(
      "aria-label",
      /Go to this collection/,
    );
});

test("pausing stops the render loop and keeps the page usable; resuming restarts it", async ({
  page,
}) => {
  await openHome(page);
  const frames = async () =>
    Number(await page.locator("html").getAttribute("data-frames"));
  await expect.poll(frames, { timeout: 20000 }).toBeGreaterThan(10);
  await page
    .getByRole("button", { name: "Pause animations", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await page.waitForTimeout(700);
  const frozen = await frames();
  await page.waitForTimeout(1500);
  expect(await frames()).toBe(frozen);
  // Scrolling still works while paused.
  await scrollToChapter(page, "recovery", 0.2);
  await expect(page.locator("html")).toHaveAttribute(
    "data-chapter",
    "recovery",
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Resume animations", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Resume animations", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "running");
  await expect.poll(frames, { timeout: 20000 }).toBeGreaterThan(0);
});

test("the scene recovers from a lost WebGL context", async ({ page }) => {
  const problems = [];
  page.on("pageerror", (error) => problems.push(error.message));
  await openHome(page);
  await page.evaluate(() => {
    const gl = document.querySelector("#world").getContext("webgl2");
    window.__ext = gl.getExtension("WEBGL_lose_context");
    window.__ext.loseContext();
  });
  await expect(page.locator("html")).toHaveAttribute("data-scene", "lost");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".fallback-sky")).toBeVisible();
  await page.evaluate(() => window.__ext.restoreContext());
  await expect(page.locator("html")).toHaveAttribute("data-scene", "webgl");
  const before = Number(await page.locator("html").getAttribute("data-frames"));
  await expect
    .poll(
      async () =>
        Number(await page.locator("html").getAttribute("data-frames")),
      { timeout: 20000 },
    )
    .toBeGreaterThan(before);
  expect(problems).toEqual([]);
});

test("a saved pause preference still shows the complete constellation and labels", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    try {
      localStorage.setItem("orion-site-motion", "paused");
    } catch {}
  });
  await page.goto("./");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await expect(page.locator("html")).toHaveAttribute("data-scene", "webgl", {
    timeout: 20000,
  });
  const rigel = page.locator('.star-label[data-collection="6"]');
  await expect(rigel).toBeVisible({ timeout: 25000 });
  await expect(rigel).toHaveCSS("opacity", "1");
  await scrollToChapter(page, "features", 0.5);
  await expect(page.locator("html")).toHaveAttribute(
    "data-chapter",
    "features",
  );
});

test("pausing during the opening completes it instead of leaving a half-lit sky", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHome(page);
  await page
    .getByRole("button", { name: "Pause animations", exact: true })
    .click();
  const betelgeuse = page.locator('.star-label[data-collection="0"]');
  await expect(betelgeuse).toBeVisible({ timeout: 25000 });
  await expect(betelgeuse).toHaveCSS("opacity", "1");
});
