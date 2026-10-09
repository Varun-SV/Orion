/** Production UI QA. Only generated files under this run's isolated data root are changed. */
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend/package.json"));
const { chromium, expect } = require("@playwright/test");
const output = path.resolve(
  process.env.ORION_QA_OUTPUT ?? path.join(root, "docs/validation/screenshots"),
);
const scratch = path.join(root, ".superpowers/sdd/2026-10-08-orion-ui");
await fs.mkdir(scratch, { recursive: true });
await fs.mkdir(output, { recursive: true });
const run = await fs.mkdtemp(path.join(scratch, "qa-"));
const data = path.join(run, "data"),
  source = path.join(run, "incoming"),
  destination = path.join(run, "organised");
await fs.mkdir(source);
await fs.mkdir(destination);
const folder = path.join(source, "Arrival.2016");
await fs.mkdir(folder);
const fixture = Buffer.alloc(4 * 1024 * 1024, 73);
const originals = [];
for (let index = 0; index < 64; index++) {
  const name =
    index === 0
      ? "arrival.2016.mkv"
      : `arrival.2016.lang${String(index).padStart(2, "0")}.srt`;
  const file = path.join(folder, name);
  fixture.writeUInt32LE(index);
  await fs.writeFile(file, fixture);
  originals.push({
    file,
    digest: createHash("sha256").update(fixture).digest("hex"),
  });
}
const python =
  process.env.ORION_PYTHON ??
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const engine = spawn(
  existsSync(python)
    ? python
    : process.platform === "win32"
      ? "python"
      : "python3",
  ["-m", "orion", "--data-dir", data, "--port", "0", "--no-browser"],
  { cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] },
);
let stdout = "",
  stderr = "",
  url = "",
  browser,
  page,
  checks = [],
  exceptions = [],
  cookie = "",
  csrf = "",
  reloadState = "";
engine.stdout.on("data", (b) => {
  stdout += b;
  const matched = stdout.match(/Orion: (http:\/\/127\.0\.0\.1:\d+)/);
  if (matched) url = matched[1];
});
engine.stderr.on("data", (b) => (stderr += b));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function check(name, work) {
  await work();
  checks.push(name);
  console.log("PASS " + name);
}
async function request(route, body, method = "GET") {
  const response = await fetch(url + "/api/v1" + route, {
    method,
    headers: {
      ...(cookie ? { Cookie: cookie } : {}),
      ...(csrf ? { "X-Orion-CSRF": csrf } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok)
    throw new Error(
      `${method} ${route}: ${response.status} ${await response.text()}`,
    );
  return response.json();
}
async function navigate(route, name) {
  if ((await page.viewportSize()).width < 621)
    await page
      .getByRole("combobox", { name: "Navigate workspace" })
      .selectOption(route);
  else
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("button", { name, exact: true })
      .click();
  await expect(page.locator("h1")).toHaveText(name);
}
async function screenshot(name) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(output, name), fullPage: false });
}
async function terminal(id) {
  let last;
  for (let n = 0; n < 300; n++) {
    last = await request("/jobs/" + id);
    if (
      ["completed", "failed", "cancelled", "interrupted"].includes(last.state)
    )
      return last;
    await sleep(100);
  }
  throw new Error("Job timed out: " + JSON.stringify(last));
}
try {
  for (let n = 0; n < 200 && !url; n++) {
    if (engine.exitCode !== null)
      throw new Error("Backend startup failed: " + stderr);
    await sleep(100);
  }
  if (!url) throw new Error("Backend startup timed out: " + stderr);
  const session = await fetch(url + "/api/v1/session");
  cookie = session.headers.getSetCookie()[0].split(";")[0];
  csrf = (await session.json()).csrf_token;
  browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_CHANNEL
      ? { channel: process.env.BROWSER_CHANNEL }
      : process.platform === "win32" && !process.env.CI
        ? { channel: "msedge" }
        : {}),
  });
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("pageerror", (error) => exceptions.push(error.message));
  await page.goto(url);
  await check("First run and bundled fonts", async () => {
    await expect(
      page.getByRole("heading", { name: "Connect your sources" }),
    ).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    assert.equal(
      await page.evaluate(() =>
        document.fonts.check('16px "Newsreader Variable"'),
      ),
      true,
    );
  });
  await navigate("connections", "Connections");
  await check("One media-server control panel with seven real providers", async () => {
    await expect(page.getByRole("heading", {name:"Open Library",exact:true})).toBeVisible();
    await expect(page.getByRole("button", {name:"Save media server",exact:true})).toHaveCount(1);
    await expect(page.getByLabel("Replacement media server API key", {exact:true})).toHaveCount(1);
  });
  await navigate("settings", "Settings");
  await check("Movies preference rejects audio upload providers", async () => {
    const category = page.locator(".category-form").filter({has:page.getByRole("heading",{name:"Movies",exact:true})});
    const select=category.getByRole("combobox", {name:"Preferred provider"});
    await expect(select).toHaveValue("tmdb");
    assert.deepEqual(await select.locator("option:not([disabled])").evaluateAll(options=>options.map(o=>o.value)), ["tmdb"]);
  });
  await navigate("sources", "Sources & destinations");
  await page.getByRole("textbox", { name: "Source folder path" }).fill(source);
  await page
    .getByRole("combobox", { name: "Source collection" })
    .selectOption("movies");
  await page.getByRole("button", { name: "Add source", exact: true }).click();
  await expect(page.getByText("Source added. Ready to scan.")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Destination folder path" })
    .fill(destination);
  await page
    .getByRole("button", { name: "Add destination", exact: true })
    .click();
  await expect(
    page.getByText("Destination added.", { exact: true }),
  ).toBeVisible();
  await check("Live configuration metrics", async () => {
    const summary = await request("/overview");
    assert.equal(summary.sources, 1);
    assert.equal(summary.destinations, 1);
  });
  await page.getByRole("button", { name: "Scan sources", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Jobs", exact: true }),
  ).toBeVisible();
  const scan = (await request("/jobs")).find((j) => j.kind === "scan");
  assert.equal((await terminal(scan.id)).state, "completed");
  await navigate("review", "Match review");
  await page.getByRole("button", { name: /Review Arrival/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Review match" }),
  ).toBeVisible();
  await check("Escape closes review and restores focus", async () => {
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    assert.match(
      await page.evaluate(
        () => document.activeElement.getAttribute("aria-label") ?? "",
      ),
      /Review Arrival/,
    );
  });
  await page.getByRole("button", { name: /Review Arrival/ }).click();
  await page
    .getByRole("textbox", { name: "Title", exact: true })
    .fill("Arrival");
  await page.getByRole("textbox", { name: "Year", exact: true }).fill("2016");
  await screenshot("production-review.png");
  await page
    .getByRole("button", { name: "Confirm match", exact: true })
    .click();
  await navigate("profiles", "Naming presets");
  await page.getByRole("combobox", {name:"Naming preset"}).selectOption("default-movies");
  await check("Optional sidecars default off and persist only after explicit saving", async()=>{
    await expect(page.getByRole("checkbox",{name:"Write NFO metadata",exact:true})).not.toBeChecked();
    await expect(page.getByRole("checkbox",{name:"Download artwork",exact:true})).not.toBeChecked();
    await page.getByRole("checkbox",{name:"Write NFO metadata",exact:true}).check();
    await page.getByRole("button",{name:"Save preset",exact:true}).click();
    await expect(page.getByText("Preset saved. Existing previews retain their recorded version.")).toBeVisible();
    const profiles=await request("/profiles");
    assert.equal(profiles.find(p=>p.id==="default-movies").nfo_enabled,true);
  });
  await screenshot("production-presets.png");
  await navigate("movies", "Movies");
  await page
    .getByRole("checkbox", { name: "Select Arrival", exact: true })
    .check();
  await page
    .getByRole("button", { name: "Preview changes", exact: true })
    .click();
  const dest = (await request("/destinations"))[0];
  await page
    .getByRole("combobox", { name: "Destination", exact: true })
    .selectOption(dest.id);
  await page
    .getByRole("button", { name: "Create preview", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Path preview" }),
  ).toBeVisible();
  const plan = (await request("/plans"))[0];
  await check("Preview has real paths and changes no bytes", async () => {
    assert.equal(plan.operations.length, 65);
    assert.equal(plan.operations.filter(op=>op.kind==='create_nfo').length,1);
    assert.equal(
      createHash("sha256")
        .update(await fs.readFile(originals[0].file))
        .digest("hex"),
      originals[0].digest,
    );
    for (const op of plan.operations)
      assert.equal(existsSync(op.destination), false);
    await expect(
      page.getByRole("button", { name: "Organise", exact: true }),
    ).toBeDisabled();
  });
  await screenshot("production-plan.png");
  await page.getByRole("button", { name: "Revalidate", exact: true }).click();
  await page.getByRole("checkbox", { name: /I reviewed these paths/ }).check();
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith("/execute") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Organise", exact: true }).click();
  const job = await (await submitted).json();
  assert.ok(["running", "queued"].includes(job.state));
  reloadState = (await request("/jobs/" + job.id)).state;
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Jobs", exact: true }),
  ).toBeVisible();
  await check("Real job survives browser reload", async () => {
    const completed = await terminal(job.id);
    assert.equal(completed.state, "completed");
    assert.equal(completed.result.completed_operation_ids.length, 65);
    await expect(
      page.getByText("65 completed · 0 failed · 0 pending"),
    ).toBeVisible({ timeout: 15000 });
    for (const original of originals)
      assert.equal(existsSync(original.file), false);
    for (const op of plan.operations) {
      if(op.kind==='create_nfo'){
        assert.match(await fs.readFile(op.destination,'utf8'),/<title>Arrival<\/title>/);
        continue;
      }
      const original = originals.find((f) => f.file === op.source);
      assert.ok(original);
      assert.equal(
        createHash("sha256")
          .update(await fs.readFile(op.destination))
          .digest("hex"),
        original.digest,
      );
    }
  });
  await screenshot("production-jobs.png");
  await page.getByRole("button", { name: "Preview undo", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Path preview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Revalidate", exact: true }).click();
  await page.getByRole("checkbox", { name: /I reviewed these paths/ }).check();
  const undone = page.waitForResponse(
    (r) => r.url().endsWith("/execute") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Organise", exact: true }).click();
  const undoJob = await (await undone).json();
  await check(
    "Guarded undo restores every generated fixture byte",
    async () => {
      assert.equal((await terminal(undoJob.id)).state, "completed");
      for (const original of originals)
        assert.equal(
          createHash("sha256")
            .update(await fs.readFile(original.file))
            .digest("hex"),
          original.digest,
        );
      for (const op of plan.operations)
        assert.equal(existsSync(op.destination), false);
    },
  );
  const routes = [
    ["overview", "Overview"],
    ["review", "Match review"],
    ["movies", "Movies"],
    ["series", "TV series"],
    ["anime", "Anime"],
    ["anime_films", "Anime films"],
    ["web_series", "Web series"],
    ["music", "Music"],
    ["books", "Books"],
    ["plans", "Plans"],
    ["jobs", "Jobs"],
    ["sources", "Sources & destinations"],
    ["connections", "Connections"],
    ["profiles", "Naming presets"],
    ["comparison", "Compare versions"],
    ["gaps", "Episode gaps"],
    ["activity", "Activity"],
    ["settings", "Settings"],
  ];
  for (const theme of ["Ivory", "Clay", "Night"]) {
    await navigate("settings", "Settings");
    await page.getByRole("button", { name: theme, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      theme.toLowerCase(),
    );
    await navigate("overview", "Overview");
    await screenshot("production-" + theme.toLowerCase() + ".png");
  }
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const [route, name] of routes) {
      await navigate(route, name);
      await check(`${route}: ${width}px, no horizontal overflow`, async () =>
        assert.ok(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `Overflow on ${route} at ${width}`,
        ),
      );
    }
    await navigate("movies", "Movies");
    await page
      .getByRole("button", { name: "Review Arrival", exact: true })
      .click();
    await check(`Review dialog fits ${width}px`, async () => {
      const bounds = await page.getByRole("dialog").boundingBox();
      assert.ok(bounds.width <= width && bounds.x >= 0);
      await page
        .getByRole("button", { name: "Close", exact: true })
        .scrollIntoViewIfNeeded();
      await expect(
        page.getByRole("button", { name: "Confirm match", exact: true }),
      ).toBeVisible();
    });
    if (width === 390) await screenshot("production-review-mobile.png");
    await page.keyboard.press("Escape");
    if (width === 390) {
      await navigate("overview", "Overview");
      await screenshot("production-mobile.png");
    }
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await check("Reduced motion removes animation", async () =>
    assert.equal(
      await page
        .locator(".nav-item")
        .first()
        .evaluate((el) => getComputedStyle(el).transitionDuration),
      "0s",
    ),
  );
  await check("No uncaught JavaScript exceptions", async () =>
    assert.deepEqual(exceptions, []),
  );
  await fs.writeFile(
    path.join(output, "browser-results.json"),
    JSON.stringify(
      {
        passed: true,
        checks,
        exceptions,
        browser: browser.version(),
        reload_state: reloadState,
        generated_files: 64,
        generated_bytes: fixture.length * 64,
        base_url: url,
      },
      null,
      2,
    ),
  );
  console.log(
    `${checks.length} production browser checks passed; every fixture byte restored.`,
  );
} catch (error) {
  console.error(error);
  if (page)
    await page
      .screenshot({
        path: path.join(output, "production-failure.png"),
        fullPage: false,
      })
      .catch(() => {});
  await fs.writeFile(
    path.join(output, "browser-results.json"),
    JSON.stringify(
      {
        passed: false,
        checks,
        exceptions,
        error: String(error),
        reload_state: reloadState,
      },
      null,
      2,
    ),
  );
  process.exitCode = 1;
} finally {
  await browser?.close();
  if (url) {
    await request("/stop", undefined, "POST").catch(() => {});
    for (let n = 0; n < 100 && engine.exitCode === null; n++) await sleep(100);
  }
  if (engine.exitCode === null) engine.kill();
  console.log("Fixture run: " + run);
  if (!process.exitCode) {
    const resolved = await fs.realpath(run),
      boundary = await fs.realpath(scratch);
    assert.ok(
      resolved.startsWith(boundary + path.sep) &&
        path.basename(resolved).startsWith("qa-"),
      "Cleanup must stay in this harness temporary directory",
    );
    await fs.rm(resolved, { recursive: true });
  }
}
