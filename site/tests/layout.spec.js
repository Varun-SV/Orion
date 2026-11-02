import { test, expect } from "@playwright/test";
import {
  ROUTES,
  WIDTHS,
  noOverflow,
  openHome,
  scrollToChapter,
  watchProblems,
} from "./helpers.js";

for (const width of WIDTHS) {
  test(`no overflow, clipped text or errors in any chapter at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width < 700 ? 800 : 900 });
    const problems = watchProblems(page);
    await openHome(page);
    for (const id of ROUTES) {
      for (const fraction of [0.05, 0.5, 0.95]) {
        await scrollToChapter(page, id, fraction);
        await page.waitForTimeout(60);
        expect(await noOverflow(page), `${id} @${fraction}`).toBe(true);
      }
      // The active chapter's heading must sit inside the viewport when its text is fully shown.
      await scrollToChapter(page, id, id === "features" ? 0.05 : 0.4);
      const heading = page.locator(`#${id} h1, #${id} h2`).first();
      await expect(heading).toBeVisible();
      const box = await heading.boundingBox();
      expect(box.x, `${id} heading left edge`).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width, `${id} heading right edge`).toBeLessThanOrEqual(
        width + 1,
      );
    }
    expect(problems).toEqual([]);
  });
}

test("the mobile menu opens, lists every route, navigates and closes with Escape", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openHome(page);
  const toggle = page.getByRole("button", { name: "Open navigation" });
  await toggle.click();
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const label of [
    "Overview",
    "Features",
    "Docs",
    "Install",
    "Recovery & privacy",
    "Demo",
  ])
    await expect(nav.getByRole("link", { name: label })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeFocused();
  await expect(nav).toBeHidden();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await nav.getByRole("link", { name: "Install" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-chapter", "install");
  await expect(nav).toBeHidden();
});

test("hash routes load the matching chapter, with the right title, after a reload", async ({
  page,
}) => {
  await openHome(page);
  const titles = {
    overview: "Overview",
    features: "Features",
    recovery: "Recovery & privacy",
    demo: "Demo",
    install: "Install",
  };
  for (const [id, title] of Object.entries(titles)) {
    await page.goto("./#" + id);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-chapter", id, {
      timeout: 15000,
    });
    await expect(page).toHaveTitle(
      new RegExp(`^${title.replace("&", "\\&")} · Orion$`),
    );
    expect(new URL(page.url()).pathname).toBe("/Orion/");
  }
});

test("every chapter's text is visible and readable when reached by an anchor link", async ({
  page,
}) => {
  await openHome(page);
  for (const id of ["features", "scan", "preview", "recovery"]) {
    await page.goto("./#" + id);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-chapter", id, {
      timeout: 15000,
    });
    const panel = page.locator(`#${id} .panel`).first();
    await expect(panel).toHaveCSS("opacity", "1");
    await expect(page.locator(`#${id} h2`)).toBeVisible();
  }
  // And through the page's own links.
  await page.goto("./");
  await page.getByRole("link", { name: /Begin the descent/ }).click();
  await expect(page.locator("#features .panel").first()).toHaveCSS(
    "opacity",
    "1",
  );
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("link", { name: "Recovery & privacy" })
    .click();
  await expect(page.locator("#recovery .panel").first()).toHaveCSS(
    "opacity",
    "1",
  );
});

for (const [width, height] of [
  [844, 390],
  [667, 375],
  [740, 360],
]) {
  test(`pinned chapters keep every control inside a short ${width}x${height} viewport`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height });
    await openHome(page);
    for (const id of ["overview", "features", "scan", "preview", "recovery"]) {
      await scrollToChapter(page, id, 0.4);
      await page.waitForTimeout(80);
      const outside = await page.evaluate((id) => {
        const bad = [];
        for (const el of document.querySelectorAll(
          `#${id} .pin a, #${id} .pin button, #${id} .pin h1, #${id} .pin h2`,
        )) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          if (r.top < 40 || r.bottom > innerHeight + 1)
            bad.push(
              `${el.tagName} ${el.textContent.trim().slice(0, 24)} ${Math.round(r.top)}-${Math.round(r.bottom)}`,
            );
        }
        return bad;
      }, id);
      expect(outside, `${id} at ${width}x${height}`).toEqual([]);
    }
  });
}
