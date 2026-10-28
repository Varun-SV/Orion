import { test, expect } from "@playwright/test";
import { docsManifest } from "../docs/manifest.mjs";

test("the observatory starts with a working organising sample in the first viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("./");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  const sample = page.getByRole("region", {
    name: "Interactive organising sample",
  });
  await expect(sample).toBeVisible();
  const box = await sample.boundingBox();
  expect(box.y).toBeLessThan(500);
  await expect(sample.getByText(/fictional sample/i)).toBeVisible();
  await sample.getByRole("button", { name: "Preview sample plan" }).click();
  await expect(sample.getByTestId("hero-plan")).toContainText(
    "Movies/The Lantern (2024)",
  );
  await sample.getByRole("button", { name: "Simulate organisation" }).click();
  await expect(sample.getByRole("status")).toContainText(
    "No files were moved.",
  );
  await sample.getByRole("button", { name: "Reset sample" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    sample.getByRole("button", { name: "Preview sample plan" }),
  ).toBeFocused();
  await sample
    .getByRole("button", { name: "Sample Music", exact: true })
    .click();
  await sample.getByRole("button", { name: "Preview sample plan" }).click();
  await expect(sample.getByTestId("hero-plan")).toContainText(
    "Music/Sample Artist/",
  );
});

test("motion can be paused persistently without disabling navigation or the sample", async ({
  page,
}) => {
  await page.goto("./");
  await page
    .getByRole("button", { name: "Pause animations", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Resume animations", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("link", { name: "Features", exact: true })
    .click();
  await expect(page).toHaveTitle("Features · Orion");
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("link", { name: "Overview", exact: true })
    .click();
  await page
    .getByRole("region", { name: "Interactive organising sample" })
    .getByRole("button", { name: "Preview sample plan" })
    .click();
  await expect(page.getByTestId("hero-plan")).toBeVisible();
});

test("reduced motion removes decorative activity while keeping the content usable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(
    await page
      .locator("html")
      .evaluate((el) => getComputedStyle(el).scrollBehavior),
  ).toBe("auto");
  const animated = await page
    .locator(".orbit-decoration, .constellation, .ambient-star")
    .evaluateAll((nodes) =>
      nodes.some(
        (node) =>
          getComputedStyle(node).animationName !== "none" &&
          getComputedStyle(node).animationDuration !== "0s",
      ),
    );
  expect(animated).toBe(false);
});

test("every public guide has static text and local documentation navigation", async ({
  browser,
  request,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  try {
    for (const slug of [
      "index",
      "install",
      "workflow",
      "collections",
      "naming",
      "providers",
      "recovery",
      "troubleshooting",
      "runtime",
      "integrations",
      "github-delivery",
      "licenses",
    ]) {
      const path = "/Orion/docs/" + (slug === "index" ? "" : slug + ".html");
      const response = await request.get(path);
      expect(response.status(), path).toBe(200);
      await page.goto("http://127.0.0.1:4174" + path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const docs = await page
        .locator("a[href]")
        .evaluateAll((links) =>
          links
            .map((link) => link.getAttribute("href"))
            .filter((href) => /\/docs\//.test(href)),
        );
      expect(docs.length).toBeGreaterThan(5);
      expect(docs.every((href) => href.startsWith("/Orion/docs/"))).toBe(true);
      expect(await page.locator("main").innerText()).not.toMatch(
        /404|Cannot GET/,
      );
    }
  } finally {
    await context.close();
  }
});

test("homepage documentation search returns local guides and code can be copied", async ({
  page,
  context,
}) => {
  await page.goto("./");
  await page
    .getByRole("searchbox", { name: "Search documentation" })
    .fill("keychain");
  await page.getByRole("button", { name: "Search guides" }).click();
  await expect(page).toHaveURL(/\/Orion\/docs\/\?q=keychain/);
  const results = page.getByRole("region", { name: "Search results" });
  await expect(results.getByRole("link").first()).toBeVisible();
  const hrefs = await results
    .getByRole("link")
    .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
  expect(hrefs.every((href) => href.startsWith("/Orion/docs/"))).toBe(true);
  await page.goto("./docs/install.html");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const button = page
    .getByRole("button", { name: "Copy code", exact: true })
    .first();
  const expected = await page.locator("pre code").first().innerText();
  await button.click();
  await expect(
    page.getByText("Code copied to clipboard.", { exact: true }).first(),
  ).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    expected,
  );
});

test("documentation search empty results and clipboard failure remain actionable", async ({
  page,
}) => {
  await page.goto("./docs/?q=zzzxxyy-nothing");
  await expect(
    page.getByRole("region", { name: "Search results" }),
  ).toContainText("No guides matched.");
  await page.goto("./docs/install.html");
  await page.evaluate(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error("Unavailable");
        },
      },
    }),
  );
  await page
    .getByRole("button", { name: "Copy code", exact: true })
    .first()
    .click();
  await expect(
    page
      .getByText(
        "Could not copy code. Select the code block and copy it manually.",
        { exact: true },
      )
      .first(),
  ).toBeVisible();
});

test("documentation offers persistent theme and motion controls across guide navigation", async ({
  page,
}) => {
  await page.goto("./docs/install.html");
  await page
    .getByRole("combobox", { name: "Colour theme" })
    .selectOption("clay");
  await page
    .getByRole("button", { name: "Pause animations", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await page
    .getByRole("navigation", { name: "Guide navigation" })
    .getByRole("link", { name: /Next.*First workflow/ })
    .click();
  await expect(page).toHaveURL(/\/Orion\/docs\/workflow.html/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "clay");
  await expect(
    page.getByRole("button", { name: "Resume animations", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("combobox", { name: "Colour theme" }),
  ).toHaveValue("clay");
});

test("mobile guides start with readable content and an expandable guide menu", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./docs/install.html");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(
    (await page.getByRole("heading", { level: 1 }).boundingBox()).y,
  ).toBeLessThan(400);
  await expect(
    page.getByRole("navigation", { name: "Guides", exact: true }),
  ).toBeHidden();
  // A native summary's accessibility role differs between browser engines.
  // Exercise its actual keyboard behavior rather than requiring a button role.
  await page.locator("summary").filter({ hasText: "Browse guides" }).focus();
  await page.keyboard.press("Enter");
  await page
    .getByRole("navigation", { name: "Guides", exact: true })
    .getByRole("link", { name: "Naming and output" })
    .click();
  await expect(page).toHaveURL(/\/Orion\/docs\/naming.html/);
});

for (const width of [360, 390, 768, 1280, 1600]) {
  test(`documentation remains readable without overflow at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const slug of [
      "index",
      "install",
      "naming",
      "integrations",
      "github-delivery",
      "licenses",
    ]) {
      await page.goto("./docs/" + slug + ".html");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  });
}

test("all local guide links and section anchors resolve in the built site", async ({
  page,
  request,
}) => {
  await page.goto("./docs/");
  const pages = new Map();
  async function content(path) {
    if (!pages.has(path)) {
      const response = await request.get(path);
      expect(response.status(), path).toBe(200);
      pages.set(path, {
        html: await response.text(),
        type: response.headers()["content-type"] ?? "",
      });
    }
    return pages.get(path);
  }
  for (const { slug } of docsManifest) {
    const path = "/Orion/docs/" + slug + ".html";
    const source = await content(path);
    const links = await page.evaluate(
      (html) =>
        Array.from(
          new DOMParser()
            .parseFromString(html, "text/html")
            .querySelectorAll("a[href]"),
          (a) => a.getAttribute("href"),
        ),
      source.html,
    );
    expect(
      links.filter((href) => href.includes("github.com/Varun-SV/Orion/blob/")),
    ).toEqual([]);
    for (const href of links) {
      const target = new URL(href, "http://127.0.0.1:4174" + path);
      if (
        target.origin !== "http://127.0.0.1:4174" ||
        !target.pathname.startsWith("/Orion/")
      )
        continue;
      const destination = await content(target.pathname);
      // The public shell uses hash routes, while guides use heading anchors.
      if (
        target.pathname === "/Orion/" &&
        ["#overview", "#features", "#install", "#recovery", "#demo"].includes(
          target.hash,
        )
      )
        continue;
      if (target.hash && destination.type.includes("text/html")) {
        const exists = await page.evaluate(
          ({ html, id }) =>
            !!new DOMParser()
              .parseFromString(html, "text/html")
              .getElementById(id),
          {
            html: destination.html,
            id: decodeURIComponent(target.hash.slice(1)),
          },
        );
        expect(exists, `${path} links to missing ${href}`).toBe(true);
      }
    }
  }
});
