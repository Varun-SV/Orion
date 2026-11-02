import { test, expect } from "@playwright/test";
import { calmScene } from "./helpers.js";

test.use({ storageState: calmScene });

test("the install chapter keeps its truthful claims and no release download is linked", async ({
  page,
  request,
}) => {
  await page.goto("./#install");
  await expect(
    page.getByText("No published installer is linked here."),
  ).toBeVisible();
  await expect(page.getByText("Plex is not implemented.")).toBeVisible();
  const hrefs = await page
    .locator("a[href]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href")));
  expect(hrefs.some((href) => /releases\/download|\.exe$/.test(href))).toBe(
    false,
  );
  for (const href of hrefs.filter((h) => h.startsWith("/Orion/docs/"))) {
    expect((await request.get(href.split("#")[0])).status(), href).toBe(200);
  }
});

test("the sample never contacts the local app or any other origin", async ({
  page,
}) => {
  const requests = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("./#demo");
  await page.getByRole("button", { name: "Preview sample plan" }).click();
  await page.getByRole("button", { name: "Simulate organisation" }).click();
  expect(
    requests.filter((url) => !url.startsWith("http://127.0.0.1:4174/Orion/")),
  ).toEqual([]);
  expect(
    requests.filter((url) =>
      /\/api\/|localhost:8765|127\.0\.0\.1:8765/.test(url),
    ),
  ).toEqual([]);
});
