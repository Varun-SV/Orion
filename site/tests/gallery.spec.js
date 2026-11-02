import { test, expect } from "@playwright/test";

const collections = [
  ["Movies", "The Lantern", "Movies/The Lantern (2024)/The Lantern (2024).mkv"],
  [
    "Series",
    "Northbound",
    "Series/Northbound (2023)/Season 01/Northbound - S01E02.mkv",
  ],
  [
    "Anime",
    "Cloud Atlas Academy",
    "Anime/Cloud Atlas Academy (2022)/Season 01/Cloud Atlas Academy - S01E01.mkv",
  ],
  [
    "Anime films",
    "Paper Moon Garden",
    "Anime Films/Paper Moon Garden (2021)/Paper Moon Garden (2021).mkv",
  ],
  [
    "Web series",
    "Small Hours",
    "Web Series/Small Hours (2025)/Season 01/Small Hours - S01E03.mp4",
  ],
  [
    "Music",
    "Quiet Lines",
    "Music/Sample Artist/Quiet Lines (2020)/01 - First Light.flac",
  ],
  [
    "Books",
    "The Field Notebook",
    "Books/Sample Author/The Field Notebook (2019)/The Field Notebook.epub",
  ],
];

test("collection selectors work by keyboard and update the featured path", async ({
  page,
}) => {
  await page.goto("./");
  const group = page.getByRole("group", { name: "Explore collections" });
  const buttons = group.getByRole("button");
  const feature = page.locator(".collection-gallery [data-gallery-feature]");

  await expect(buttons).toHaveCount(7);
  for (const [index, [name, title, destination]] of collections.entries()) {
    const button = group.getByRole("button", { name, exact: true });
    await button.focus();
    await page.keyboard.press(index % 2 ? "Space" : "Enter");
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(feature.locator("[data-gallery-title]")).toHaveText(title);
    await expect(feature.locator("[data-gallery-destination]")).toHaveText(
      destination,
    );
    await expect(button).toBeFocused();
  }
});

test("featured collection link opens the matching fixture demo collection", async ({
  page,
}) => {
  await page.goto("./");
  const group = page.getByRole("group", { name: "Explore collections" });
  await group.getByRole("button", { name: "Books", exact: true }).click();

  const link = page.locator(".collection-gallery .gallery-open-link");
  await expect(link).toHaveAttribute("href", "#demo");
  await expect(link).toHaveAttribute("data-demo-select", "6");
  await link.click();

  await expect(page).toHaveURL(/#demo$/);
  await expect(page.getByTestId("demo-result")).toContainText(
    "The Field Notebook",
  );
  await expect(page.locator("[data-collection='6']")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
