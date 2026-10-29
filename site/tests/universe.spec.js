import { test, expect } from "@playwright/test";

test("the mobile navigation exposes every route and closes accessibly", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav).toBeHidden();
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(
    nav.getByRole("link", { name: "Demo", exact: true }),
  ).toBeInViewport();
  await expect(
    nav.getByRole("link", { name: "Overview", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(nav).toBeHidden();
  await expect(
    page.getByRole("button", { name: "Open navigation", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await nav.getByRole("link", { name: "Features", exact: true }).click();
  await expect(page).toHaveTitle("Features · Orion");
  await expect(nav).toBeHidden();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(nav).toBeVisible();
});

for (const width of [390, 768, 1440]) {
  test(`the visual opening keeps artwork clear of text at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 960 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("./");
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: testInfo.outputPath(`opening-${width}.png`),
    });
    const heading = await page.getByRole("heading", { level: 1 }).boundingBox();
    const cover = await page.locator(".universe-cover--0").boundingBox();
    if (width > 930)
      expect(heading.x + heading.width).toBeLessThan(cover.x + 20);
    else expect(cover.y).toBeGreaterThan(heading.y + heading.height);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);

    await page.locator(".collection-gallery").scrollIntoViewIfNeeded();
    await page
      .locator(".collection-gallery")
      .screenshot({ path: testInfo.outputPath(`gallery-${width}.png`) });
    await page
      .getByRole("button", { name: "Explore Orion", exact: true })
      .click();
    const sample = page.getByRole("region", {
      name: "Interactive organising sample",
    });
    await expect(
      sample.getByRole("button", { name: "Preview sample plan" }),
    ).toBeInViewport();
    await expect(
      sample.getByRole("button", { name: "Sample Movies", exact: true }),
    ).toBeFocused();
  });
}
