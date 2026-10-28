import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { generateDocs } from "../../scripts/generate-docs.js";

test("removes stale guides and evidence from subsequent generated builds", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-rebuild-"));
  const sourceDir = path.join(root, "sources");
  const outputDir = path.join(root, "out");
  await mkdir(sourceDir);
  await writeFile(
    path.join(sourceDir, "guide.md"),
    "# A guide\n\nKeep this current.\n",
  );
  await writeFile(path.join(sourceDir, "old.json"), "{}");
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "old",
        title: "Old guide",
        source: "guide.md",
        description: "Old",
      },
    ],
    assets: [{ source: "old.json" }],
  });
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "index",
        title: "Current guide",
        source: "guide.md",
        description: "Current",
      },
    ],
  });
  await assert.rejects(readFile(path.join(outputDir, "old.html")), {
    code: "ENOENT",
  });
  await assert.rejects(readFile(path.join(outputDir, "old.json")), {
    code: "ENOENT",
  });
  assert.match(
    await readFile(path.join(outputDir, "index.html"), "utf8"),
    /Keep this current/,
  );
  await rm(root, { recursive: true, force: true });
});

test("generates static, readable guide pages with safe local links and search data", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-"));
  const sourceDir = path.join(root, "sources");
  const outputDir = path.join(root, "out");
  await mkdir(sourceDir);
  await writeFile(
    path.join(sourceDir, "start.md"),
    "# Getting started\n\nRead [recovery](recovery.md), [its old HTML path](recovery.html), or [the project](https://example.com).\n\n```sh\npython -m orion run\n```\n",
  );
  await writeFile(
    path.join(sourceDir, "recovery.md"),
    "# Recovery\n\nKeep your original files safe.\n",
  );

  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "index",
        title: "Documentation",
        source: "start.md",
        description: "Start here",
      },
      {
        slug: "recovery",
        title: "Recovery",
        source: "recovery.md",
        description: "Restore safely",
      },
    ],
  });

  const index = await readFile(path.join(outputDir, "index.html"), "utf8");
  const recovery = await readFile(
    path.join(outputDir, "recovery.html"),
    "utf8",
  );
  const search = JSON.parse(
    await readFile(path.join(outputDir, "search-index.json"), "utf8"),
  );
  assert.match(index, /<h1[^>]*>Getting started<\/h1>/);
  assert.match(index, /href="\/Orion\/docs\/recovery\.html"/);
  assert.doesNotMatch(index, /href="recovery\.html"/);
  assert.match(index, /href="https:\/\/example\.com"/);
  assert.match(index, /python -m orion run/);
  assert.match(index, /Search documentation/);
  assert.match(recovery, /Keep your original files safe/);
  assert.ok(
    search.some(
      (entry) =>
        entry.url === "/Orion/docs/recovery.html" &&
        entry.text.includes("Recovery"),
    ),
  );
  await rm(root, { recursive: true, force: true });
});

test("escapes raw HTML and blocks javascript links from trusted Markdown sources", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-safe-"));
  const sourceDir = path.join(root, "sources");
  const outputDir = path.join(root, "out");
  await mkdir(sourceDir);
  await writeFile(
    path.join(sourceDir, "x.md"),
    "# Safe\n\n<script>alert(1)</script> [bad](javascript:alert%281%29)\n",
  );
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      { slug: "index", title: "Docs", source: "x.md", description: "Safe" },
    ],
  });
  const html = await readFile(path.join(outputDir, "index.html"), "utf8");
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /href="javascript:/i);
  await rm(root, { recursive: true, force: true });
});

test("gives plain-text licence sources a heading and includes local font notices", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-licence-"));
  const sourceDir = path.join(root, "sources");
  const outputDir = path.join(root, "out");
  await mkdir(sourceDir);
  await writeFile(
    path.join(sourceDir, "LICENSE"),
    "MIT License\n\nPermission is hereby granted.\n",
  );
  await writeFile(
    path.join(sourceDir, "font-license.txt"),
    "Font terms for local use.\n",
  );
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "licenses",
        title: "Licences",
        source: "LICENSE",
        description: "Licence terms",
        supplemental: [
          {
            title: "Font licences",
            source: "font-license.txt",
            href: "/Orion/fonts/font-license.txt",
          },
        ],
      },
    ],
  });
  const html = await readFile(path.join(outputDir, "licenses.html"), "utf8");
  assert.match(html, /<h1[^>]*>Licences<\/h1>/);
  assert.match(html, /MIT License/);
  assert.match(html, /Font terms for local use/);
  assert.match(html, /href="\/Orion\/fonts\/font-license\.txt"/);
  await rm(root, { recursive: true, force: true });
});

test("creates unique heading IDs, TOC entries and resolvable fragment links", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-toc-"));
  const sourceDir = path.join(root, "sources");
  const outputDir = path.join(root, "out");
  await mkdir(sourceDir);
  await writeFile(
    path.join(sourceDir, "guide.md"),
    "# Guide\n\n## Draft release guard\n\n## Draft release guard\n\n### Check results\n\n[Jump to guard](#draft-release-guard) and [release guide](release.md#draft-release-guard).\n",
  );
  await writeFile(
    path.join(sourceDir, "release.md"),
    "# Delivery\n\n## Draft release guard\n\nA verified release starts with the approved tag.\n",
  );
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "index",
        title: "Docs",
        source: "guide.md",
        description: "Guide",
      },
      {
        slug: "github-delivery",
        title: "Developer delivery",
        source: "release.md",
        description: "Release guide",
      },
    ],
  });
  const html = await readFile(path.join(outputDir, "index.html"), "utf8");
  const delivery = await readFile(
    path.join(outputDir, "github-delivery.html"),
    "utf8",
  );
  assert.match(html, /<h2 id="draft-release-guard">Draft release guard<\/h2>/);
  assert.match(
    html,
    /<h2 id="draft-release-guard-1">Draft release guard<\/h2>/,
  );
  assert.match(html, /<h3 id="check-results">Check results<\/h3>/);
  assert.match(html, /href="#draft-release-guard"/);
  assert.match(html, /href="#draft-release-guard-1"/);
  assert.match(
    html,
    /href="\/Orion\/docs\/github-delivery\.html#draft-release-guard"/,
  );
  assert.match(
    delivery,
    /<h2 id="draft-release-guard">Draft release guard<\/h2>/,
  );
  await rm(root, { recursive: true, force: true });
});

test("publishes first-party JSON evidence locally and rewrites guide links to it", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "orion-docs-repo-link-"));
  const sourceDir = path.join(root, "repo");
  const outputDir = path.join(root, "out");
  await mkdir(path.join(sourceDir, "docs", "validation"), { recursive: true });
  await writeFile(
    path.join(sourceDir, "docs", "github-delivery.md"),
    "# Delivery\n\nSee [settings evidence](validation/github-settings.json) and [package evidence](validation/package-smoke.json).\n",
  );
  await writeFile(
    path.join(sourceDir, "docs", "validation", "github-settings.json"),
    '{"pages":"workflow"}\n',
  );
  await writeFile(
    path.join(sourceDir, "docs", "validation", "package-smoke.json"),
    '{"verified":true}\n',
  );
  await generateDocs({
    sourceDir,
    outputDir,
    manifest: [
      {
        slug: "github-delivery",
        title: "Delivery",
        source: "docs/github-delivery.md",
        description: "Delivery guide",
      },
    ],
    assets: [
      {
        source: "docs/validation/github-settings.json",
        filename: "github-settings.json",
      },
      {
        source: "docs/validation/package-smoke.json",
        filename: "package-smoke.json",
      },
    ],
  });
  const html = await readFile(
    path.join(outputDir, "github-delivery.html"),
    "utf8",
  );
  assert.match(html, /href="\/Orion\/docs\/github-settings\.json"/);
  assert.match(html, /href="\/Orion\/docs\/package-smoke\.json"/);
  assert.equal(
    await readFile(path.join(outputDir, "github-settings.json"), "utf8"),
    '{"pages":"workflow"}\n',
  );
  assert.equal(
    await readFile(path.join(outputDir, "package-smoke.json"), "utf8"),
    '{"verified":true}\n',
  );
  await rm(root, { recursive: true, force: true });
});
