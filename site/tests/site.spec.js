import { test, expect } from "@playwright/test";
const routes = [
  "Overview",
  "Features",
  "Install",
  "Recovery & privacy",
  "Demo",
];
const collections = [
  "Movies",
  "Series",
  "Anime",
  "Anime films",
  "Web series",
  "Music",
  "Books",
];

test("repository-prefix routes reload with correct titles and local documentation", async ({
  page,
  request,
}) => {
  await page.goto("./");
  for (const route of routes) {
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: route, exact: true })
      .click();
    await expect(page).toHaveTitle(new RegExp(route + ".*Orion"));
    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(new URL(page.url()).pathname).toBe("/Orion/");
  }
  await page.goto("./#install");
  await expect(
    page.getByText("No published installer is linked here."),
  ).toBeVisible();
  await expect(
    page.getByText("python -m orion run --frontend-dir frontend/dist", {
      exact: false,
    }),
  ).toBeVisible();
  const documents = await page.locator("a[data-document]").all();
  expect(documents.length).toBeGreaterThanOrEqual(2);
  for (const link of documents) {
    const href = await link.getAttribute("href");
    expect(href).toMatch(/^\/Orion\/docs\//);
    const response = await request.get(href);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toMatch(/text\/html/);
    expect(await response.text()).toContain("<h1>");
  }
  const links = await page
    .locator("a[href]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href")));
  expect(links.some((href) => /releases\/download|\.exe$/.test(href))).toBe(
    false,
  );
});

test("seven fixture collections support search, preview, simulated organisation and reset", async ({
  page,
}) => {
  await page.goto("./#demo");
  await expect(page.getByRole("note", { name: "Fixture demo" })).toBeVisible();
  for (const collection of collections) {
    await page.getByRole("button", { name: collection, exact: true }).click();
    await expect(page.getByTestId("demo-result")).toContainText(collection);
  }
  await page.getByRole("button", { name: "Movies", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "Search sample collection" })
    .fill("no such fixture");
  await expect(page.getByText("No sample titles match.")).toBeVisible();
  await page
    .getByRole("searchbox", { name: "Search sample collection" })
    .fill("");
  await page.getByRole("button", { name: "Preview sample plan" }).click();
  await expect(page.getByTestId("sample-plan")).toContainText(
    "Movies/The Lantern (2024)",
  );
  await page.getByRole("button", { name: "Simulate organisation" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Sample complete. No files were moved.",
  );
  await expect(page.getByRole("note", { name: "Fixture demo" })).toBeVisible();
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.getByTestId("sample-plan")).toHaveCount(0);
});

test("theme persists, keyboard navigation works and reduced motion is respected", async ({
  page,
}) => {
  await page.goto("./");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await page
    .getByRole("combobox", { name: "Colour theme" })
    .selectOption("night");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await page
    .getByRole("combobox", { name: "Colour theme" })
    .selectOption("clay");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "clay");
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page
      .locator("html")
      .evaluate((el) => getComputedStyle(el).scrollBehavior),
  ).toBe("auto");
  await page.goto("./#demo");
  await page.getByRole("button", { name: "Movies", exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Series", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("demo-result")).toContainText("Series");
});

for (const width of [360, 390, 768, 1280, 1600]) {
  test(
    "all routes fit at " +
      width +
      "px without private API calls or missing assets",
    async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      const failures = [],
        requests = [];
      page.on("response", (response) => {
        if (response.status() >= 400)
          failures.push(response.status() + " " + response.url());
      });
      page.on("requestfailed", (request) => failures.push(request.url()));
      page.on("pageerror", (error) => failures.push(error.message));
      page.on("request", (request) => requests.push(request.url()));
      for (const route of ["", "#features", "#install", "#recovery", "#demo"]) {
        await page.goto("./" + route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        ).toBe(true);
        const broken = await page
          .locator("img")
          .evaluateAll((images) =>
            images
              .filter((image) => !image.complete || image.naturalWidth === 0)
              .map((image) => image.src),
          );
        expect(broken).toEqual([]);
      }
      expect(failures).toEqual([]);
      expect(
        requests.filter(
          (url) => !url.startsWith("http://127.0.0.1:4174/Orion/"),
        ),
      ).toEqual([]);
      expect(
        requests.filter((url) =>
          /\/api\/|localhost:8765|127\.0\.0\.1:8765/.test(url),
        ),
      ).toEqual([]);
    },
  );
}

