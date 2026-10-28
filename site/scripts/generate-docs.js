import { mkdir, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { marked, Renderer } from "marked";

const BASE = "/Orion/";
const DOCS_URL = `${BASE}docs/`;

const escapeHtml = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

function safeHref(rawHref, current, sourceToTarget) {
  if (!rawHref) return null;
  const decoded = (() => {
    try {
      return decodeURIComponent(rawHref);
    } catch {
      return rawHref;
    }
  })();
  if (/^(?:javascript|vbscript|data):/i.test(decoded.trim())) return null;
  if (
    /^(?:https?:|mailto:|tel:|\/\/)/i.test(rawHref) ||
    rawHref.startsWith("#")
  )
    return rawHref;
  const [pathPart, suffix = ""] = rawHref.split(/(?=[?#])/u, 2);
  if (pathPart === ".." || pathPart === "../") return `${BASE}`;
  const resolved = path.posix.normalize(
    path.posix.join(path.posix.dirname(current.source), pathPart),
  );
  const target =
    sourceToTarget.get(resolved) ??
    sourceToTarget.get(path.posix.basename(pathPart));
  if (target) return `${DOCS_URL}${target}${suffix}`;
  if (pathPart.endsWith(".md")) return null;
  if (!pathPart || pathPart.startsWith("/")) return rawHref;
  const repoPath = resolved.split("/").map(encodeURIComponent).join("/");
  return `https://github.com/Varun-SV/Orion/blob/main/${repoPath}${suffix}`;
}

function makeRenderer(current, sourceToTarget) {
  const renderer = new Renderer();
  const defaultLink = renderer.link.bind(renderer);
  const headingCounts = new Map();
  renderer.html = ({ text }) => escapeHtml(text);
  renderer.heading = ({ depth, text, tokens }) => {
    const base =
      String(text)
        .replace(/<[^>]*>/g, "")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(/[`*_~]/g, "")
        .toLocaleLowerCase()
        .normalize("NFKD")
        .replace(/\p{Diacritic}/gu, "")
        .replace(/[^\p{Letter}\p{Number}\s_-]/gu, "")
        .trim()
        .replace(/[\s_]+/g, "-")
        .replace(/-+/g, "-") || "section";
    const count = headingCounts.get(base) ?? 0;
    headingCounts.set(base, count + 1);
    const id = count ? `${base}-${count}` : base;
    return `<h${depth} id="${escapeHtml(id)}">${renderer.parser.parseInline(tokens)}</h${depth}>`;
  };
  renderer.link = (token) => {
    const href = safeHref(token.href, current, sourceToTarget);
    return href
      ? defaultLink({ ...token, href })
      : renderer.parser.parseInline(token.tokens ?? []);
  };
  const defaultImage = renderer.image.bind(renderer);
  renderer.image = (token) => {
    const href = safeHref(token.href, current, sourceToTarget);
    return href
      ? defaultImage({ ...token, href })
      : escapeHtml(token.text ?? "");
  };
  return renderer;
}

function tocFor(html) {
  return [...html.matchAll(/<h([23]) id="([^"]+)">([\s\S]*?)<\/h\1>/g)]
    .map(
      ([, level, id, text]) =>
        `<li class="toc-level-${level}"><a href="#${escapeHtml(id)}">${text.replace(/<[^>]*>/g, "")}</a></li>`,
    )
    .join("");
}

function pageShell(entry, content, toc, manifest) {
  const indexUrl = `${DOCS_URL}index.html`;
  const position = manifest.findIndex((item) => item.slug === entry.slug);
  const prev = manifest[position - 1];
  const next = manifest[position + 1];
  const navLinks = manifest
    .map(
      (item) =>
        `<a class="guide-link${item.slug === entry.slug ? " current" : ""}" href="${DOCS_URL}${item.slug}.html"${item.slug === entry.slug ? ' aria-current="page"' : ""}>${escapeHtml(item.title)}</a>`,
    )
    .join("");
  const prevNext = `<nav class="page-nav" aria-label="Guide navigation">${prev ? `<a rel="prev" href="${DOCS_URL}${prev.slug}.html"><span>Previous</span>${escapeHtml(prev.title)}</a>` : "<span></span>"}${next ? `<a rel="next" href="${DOCS_URL}${next.slug}.html"><span>Next</span>${escapeHtml(next.title)}</a>` : "<span></span>"}</nav>`;
  return `<!doctype html>
<html lang="en" data-theme="night">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="${escapeHtml(entry.description)}">
  <meta name="color-scheme" content="dark light"><title>${escapeHtml(entry.title)} · Orion docs</title>
  <link rel="icon" href="${BASE}favicon.svg"><link rel="stylesheet" href="${DOCS_URL}document.css"><link rel="stylesheet" href="${DOCS_URL}search.css">
  <script>try{const t=localStorage.getItem('orion-site-theme');if(t==='ivory'||t==='clay')document.documentElement.dataset.theme=t;const m=localStorage.getItem('orion-site-motion');if(m==='paused')document.documentElement.dataset.motion='paused'}catch{}</script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to guide</a>
  <header class="topbar"><a class="brand" href="${BASE}#overview" aria-label="Orion home"><svg class="brand-mark" viewBox="0 0 36 36" aria-hidden="true"><path d="M8 5 13 17 27 22 29 31M13 17 5 27M13 17 24 6"/><circle cx="8" cy="5" r="1.8"/><circle cx="13" cy="17" r="2.7"/><circle cx="27" cy="22" r="1.8"/><circle cx="29" cy="31" r="1.8"/><circle cx="5" cy="27" r="1.8"/><circle cx="24" cy="6" r="1.8"/></svg><span>ORION <small>FIELD GUIDE</small></span></a><div class="docs-controls"><a class="home-link" href="${BASE}#overview"><span>Back to </span>Orion ↗</a><button id="docs-motion-toggle" type="button" aria-label="Pause animations" aria-pressed="false"><span aria-hidden="true">Ⅱ</span></button><label class="visually-hidden" for="docs-theme">Colour theme</label><select id="docs-theme"><option value="night">Night</option><option value="ivory">Ivory</option><option value="clay">Clay</option></select></div></header>
  <div class="docs-layout">
    <aside class="sidebar" aria-label="Documentation navigation">
      <form class="search-form" role="search" action="${indexUrl}" method="get"><label for="doc-search">Search documentation</label><div class="search-row"><input id="doc-search" name="q" type="search" autocomplete="off" placeholder="Search guides…"><button type="submit" aria-label="Search">⌕</button></div></form>
      <details class="guides-menu" open><summary>Browse guides <span aria-hidden="true">⌄</span></summary><nav class="guide-nav" aria-label="Guides"><span class="nav-label">EXPLORE</span>${navLinks}</nav></details>
      <a class="repo-link" href="https://github.com/Varun-SV/Orion">Repository ↗</a>
    </aside>
    <main id="main" class="article-column">
      <div id="search-results" class="search-results" role="region" aria-label="Search results" aria-live="polite" hidden></div>
      <article class="article">${content}</article>
      ${prevNext}
    </main>
    <aside class="toc-panel" aria-label="On this page"><span class="nav-label">ON THIS PAGE</span><ol>${toc || '<li class="toc-empty">Guide overview</li>'}</ol></aside>
  </div>
  <footer class="docs-footer"><a href="${BASE}#overview">ORION</a><span>Local-first media organizing</span><a href="https://github.com/Varun-SV/Orion">Source ↗</a></footer>
  <script src="${DOCS_URL}docs.js" defer></script>
  <script src="${DOCS_URL}search.js" defer></script>
</body></html>`;
}

export async function generateDocs({
  sourceDir,
  outputDir,
  manifest,
  assets = [],
}) {
  if (!Array.isArray(manifest) || !manifest.length)
    throw new Error("Documentation manifest must contain guide entries");
  const sourceToTarget = new Map();
  for (const entry of manifest) {
    const source = path.posix.normalize(entry.source.replaceAll(path.sep, "/"));
    const target = `${entry.slug}.html`;
    sourceToTarget.set(source, target);
    sourceToTarget.set(target, target);
    sourceToTarget.set(path.posix.basename(target), target);
    if (source.endsWith(".md"))
      sourceToTarget.set(source.slice(0, -3) + ".html", target);
  }
  for (const asset of assets) {
    const source = path.posix.normalize(asset.source.replaceAll(path.sep, "/"));
    const target = asset.filename ?? path.posix.basename(source);
    sourceToTarget.set(source, target);
    sourceToTarget.set(path.posix.basename(source), target);
  }
  if (path.resolve(outputDir) === path.resolve(sourceDir))
    throw new Error("Documentation output must be separate from its sources");
  // This directory contains only reproducible build output. Removed manifest
  // entries must disappear on local rebuilds as well as clean CI checkouts.
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  const searchData = [];
  for (const entry of manifest) {
    let markdown = await readFile(
      path.resolve(sourceDir, entry.source),
      "utf8",
    );
    const supplemental = entry.supplemental ?? [];
    if (supplemental.length)
      markdown += `\n\n## ${entry.supplementalHeading ?? "Additional notices"}\n`;
    for (const extra of supplemental) {
      const text = await readFile(
        path.resolve(sourceDir, extra.source),
        "utf8",
      );
      markdown += `\n### ${extra.title}\n\nSee the locally served [${extra.label ?? extra.title} licence text](${extra.href}).\n\n${text}\n`;
    }
    let rendered = marked.parse(markdown, {
      gfm: true,
      breaks: false,
      mangle: false,
      renderer: makeRenderer(entry, sourceToTarget),
    });
    if (!/<h1(?:\s|>)/i.test(rendered))
      rendered = `<h1>${escapeHtml(entry.title)}</h1>\n${rendered}`;
    const html = pageShell(entry, rendered, tocFor(rendered), manifest);
    await writeFile(path.join(outputDir, `${entry.slug}.html`), html);
    const plainText = markdown
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/[#>*_\[\]()!]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    searchData.push({
      title: entry.title,
      description: entry.description,
      url: `${DOCS_URL}${entry.slug}.html`,
      text: plainText,
    });
  }
  for (const asset of assets) {
    const target =
      asset.filename ??
      path.posix.basename(asset.source.replaceAll(path.sep, "/"));
    await writeFile(
      path.join(outputDir, target),
      await readFile(path.resolve(sourceDir, asset.source)),
    );
  }
  await writeFile(
    path.join(outputDir, "search-index.json"),
    JSON.stringify(searchData),
  );
  return searchData.length;
}

export { safeHref };
