import { test, expect } from "@playwright/test";

test("four keyboard stage controls update the scene and explanation without taking focus", async ({
  page,
}) => {
  await page.goto("./");
  const group = page.getByRole("group", { name: "Story stages" });
  const controls = group.getByRole("button");
  const scene = page.locator(".file-story [data-story-scene]");

  await expect(controls).toHaveCount(4);
  const stages = ["scan", "review", "preview", "organise"];
  const labels = ["Scan", "Review", "Preview", "Organise"];
  for (const [index, stage] of stages.entries()) {
    const button = controls.nth(index);
    await button.focus();
    await page.keyboard.press(index % 2 ? "Space" : "Enter");
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(scene).toHaveAttribute("data-stage", stage);
    await expect(
      page.locator(".file-story [data-story-current]"),
    ).toContainText(labels[index]);
    await expect(
      page.locator(`.file-story [data-story-article="${stage}"]`),
    ).toHaveAttribute("data-active", "true");
    await expect(
      page.locator(".file-story [data-story-article][data-active='true']"),
    ).toHaveCount(1);
    await expect(button).toBeFocused();
  }
});

test("scrolling to a story article selects its stage", async ({ page }) => {
  await page.goto("./");
  const article = page.locator('.file-story [data-story-article="review"]');
  await article.scrollIntoViewIfNeeded();
  await page.waitForFunction(
    () =>
      document.querySelector(".file-story")?.dataset.activeStage === "review",
  );

  await expect(
    page
      .getByRole("group", { name: "Story stages" })
      .getByRole("button", { name: /02.*Review/i }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".file-story [data-story-scene]")).toHaveAttribute(
    "data-stage",
    "review",
  );
});

test("selecting a stage brings its chapter into view and keeps focus", async ({
  page,
}) => {
  await page.goto("./");
  const organize = page
    .getByRole("group", { name: "Story stages" })
    .getByRole("button", { name: /04.*Organise/i });
  const chapter = page.locator('.file-story [data-story-article="organise"]');
  await organize.focus();
  await page.keyboard.press("Enter");

  await expect(organize).toHaveAttribute("aria-pressed", "true");
  await expect(chapter).toBeInViewport();
  await expect(organize).toBeFocused();

  await page.mouse.wheel(0, -1100);
  await expect
    .poll(() => page.locator(".file-story").getAttribute("data-active-stage"))
    .not.toBe("organise");
  await expect(organize).toBeFocused();
});

test("reduced and paused motion keep story controls usable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  const group = page.getByRole("group", { name: "Story stages" });
  const controls = group.getByRole("button");
  await controls.nth(1).click();
  await expect(controls.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".file-story [data-story-scene]")).toHaveAttribute(
    "data-stage",
    "review",
  );

  await page.getByRole("button", { name: "Pause animations" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await controls.nth(2).click();
  await expect(controls.nth(2)).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".file-story [data-story-scene]")).toHaveAttribute(
    "data-stage",
    "preview",
  );
});

test("story stays within a 360px viewport and labels its sample as inert", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("./");
  await expect(page.locator(".file-story")).toContainText(
    "Fictional sample. No files are moved.",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
