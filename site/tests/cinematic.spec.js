import { test, expect } from "@playwright/test";

test("the orbital scene renders locally and stays still when animations are paused", async ({
  page,
}) => {
  await page.goto("./");
  const canvas = page.locator("canvas.orbital-canvas");
  await expect(canvas).toBeVisible();
  await expect
    .poll(() =>
      canvas.evaluate((el) =>
        Array.from(
          el.getContext("2d").getImageData(0, 0, el.width, el.height).data,
        ).some((value) => value > 0),
      ),
    )
    .toBe(true);
  await page
    .getByRole("button", { name: "Pause animations", exact: true })
    .click();
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const still = await canvas.evaluate((el) => el.toDataURL());
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        let count = 0;
        const tick = () =>
          ++count === 8 ? resolve() : requestAnimationFrame(tick);
        requestAnimationFrame(tick);
      }),
  );
  expect(await canvas.evaluate((el) => el.toDataURL())).toBe(still);
  await page
    .getByRole("combobox", { name: "Colour theme" })
    .selectOption("clay");
  await expect
    .poll(() => canvas.evaluate((el) => el.toDataURL()))
    .not.toBe(still);
});

test("a browser without Canvas still has the visual fallback and working sample", async ({
  page,
}) => {
  await page.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = () => null;
  });
  await page.goto("./");
  await expect(page.locator(".orbital-fallback")).toBeVisible();
  const sample = page.getByRole("region", {
    name: "Interactive organising sample",
  });
  await sample.getByRole("button", { name: "Preview sample plan" }).click();
  await sample.getByRole("button", { name: "Simulate organisation" }).click();
  await expect(sample.getByRole("status")).toContainText(
    "No files were moved.",
  );
});
