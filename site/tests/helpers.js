import { expect } from "@playwright/test";

export const ROUTES = [
  "overview",
  "features",
  "scan",
  "preview",
  "recovery",
  "demo",
  "install",
];
export const COLLECTIONS = [
  "Movies",
  "Series",
  "Anime",
  "Anime films",
  "Web series",
  "Music",
  "Books",
];
export const WIDTHS = [360, 390, 768, 1280, 1600];

// Collects anything the browser would show a developer as a problem.
export function watchProblems(page) {
  const problems = [];
  page.on("pageerror", (error) => problems.push("pageerror: " + error.message));
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning")
      problems.push(message.type() + ": " + message.text());
  });
  page.on("requestfailed", (request) =>
    problems.push("requestfailed: " + request.url()),
  );
  page.on("response", (response) => {
    if (response.status() >= 400)
      problems.push(response.status() + " " + response.url());
  });
  return problems;
}

export async function openHome(page, scene = "webgl") {
  await page.goto("./");
  await expect(page.locator("html")).toHaveAttribute("data-scene", scene, {
    timeout: 20000,
  });
}

export async function scrollToChapter(page, id, fraction = 0) {
  await page.evaluate(
    ([id, fraction]) => {
      const section = document.getElementById(id);
      const probe = document.querySelector(".vh-probe").offsetHeight;
      const top = section.getBoundingClientRect().top + scrollY;
      window.scrollTo(
        0,
        top + fraction * Math.max(0, section.offsetHeight - probe),
      );
    },
    [id, fraction],
  );
}

export const noOverflow = (page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

// Tests that are not about the 3D scene start with animations paused, so a slow software-GL runner
// is not busy rendering while they exercise search, links or the sample.
export const calmScene = {
  cookies: [],
  origins: [
    {
      origin: "http://127.0.0.1:4174",
      localStorage: [{ name: "orion-site-motion", value: "paused" }],
    },
  ],
};
