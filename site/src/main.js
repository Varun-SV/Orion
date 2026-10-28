import "./style.css";
import "./cinematic.css";
import { collections } from "./collections";
import { showcaseMarkup, mountShowcase } from "./showcase";
import { setupMotion } from "./motion";
import { sceneMarkup, mountScene } from "./scene";
import { storyMarkup, mountStory } from "./story";

const BASE = import.meta.env.BASE_URL;
const repository = "https://github.com/Varun-SV/Orion";
const stars = Array.from({ length: 54 }, (_, i) => {
  const x = (i * 173 + 97) % 1440,
    y = (i * 241 + 137) % 1100;
  return `<circle class="ambient-star" cx="${x}" cy="${y}" r="${i % 9 === 0 ? 1.6 : 0.7}" style="animation-delay:${-i % 7}s"/>`;
}).join("");
document.querySelector(".sky").innerHTML =
  `<svg class="constellation" viewBox="0 0 1440 1100" preserveAspectRatio="xMidYMin slice"><g>${stars}</g><path class="sky-path" d="m925 110 123 83 155-62 66 132-94 113m-127-183-63 178 98 113m-98-113-100-59M93 760l95 61 127-28 65 109m-192-81-67 132"/><g class="sky-cross"><path d="M1330 590v10m-5-5h10M113 250v8m-4-4h8M730 850v10m-5-5h10"/></g></svg>`;
const pages = {
  overview: {
    title: "Overview",
    description:
      "A local media workspace for movies, series, anime, web series, music and books.",
  },
  features: {
    title: "Features",
    description:
      "Review metadata, preview paths, organise seven collections and track recoverable jobs in Orion.",
  },
  install: {
    title: "Install",
    description:
      "Build and run Orion from source. No published installer is linked before a release exists.",
  },
  recovery: {
    title: "Recovery & privacy",
    description:
      "How local data, optional providers, durable jobs, backups and guarded undo work in Orion.",
  },
  demo: {
    title: "Demo",
    description:
      "Explore seven Orion collections using fictional sample data. No access to personal files or the local API.",
  },
};
const main = document.querySelector("main");
const themeSelect = document.querySelector("#theme");
let selected = 0;
let search = "";
let preview = false;
let completed = false;

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeSelect.value = theme;
  document.querySelector('meta[name="theme-color"]').content =
    theme === "night" ? "#070b10" : theme === "clay" ? "#f7f0e8" : "#f6f7f0";
  try {
    localStorage.setItem("orion-site-theme", theme);
  } catch {
    /* Browsing without storage keeps this session's theme. */
  }
}
let savedTheme;
try {
  savedTheme = localStorage.getItem("orion-site-theme");
} catch {
  /* Storage may be disabled. */
}
setTheme(
  ["ivory", "clay", "night"].includes(savedTheme) ? savedTheme : "night",
);
themeSelect.addEventListener("change", () => setTheme(themeSelect.value));
const motion = setupMotion();
let cleanupPage = () => {};

const eyebrow = (text) => '<p class="eyebrow"><span></span>' + text + "</p>";
const actions = () =>
  '<div class="actions"><a class="button primary" href="#install">Get started <span aria-hidden="true">↗</span></a><a class="button secondary" href="#demo">Explore the demo <span aria-hidden="true">→</span></a></div>';
const collectionList = () =>
  '<div class="collections">' +
  collections
    .map(
      (c) =>
        '<a class="collection-card" href="#demo" data-demo-select="' +
        collections.indexOf(c) +
        '"><span class="collection-number">' +
        c.glyph +
        "</span><h3>" +
        c.name +
        "</h3><p>" +
        c.kind +
        '</p><span class="collection-arrow" aria-hidden="true">↗</span></a>',
    )
    .join("") +
  "</div>";
const screenshot = (file, alt, caption) =>
  '<figure class="product-shot"><img src="' +
  BASE +
  "images/" +
  file +
  '" alt="' +
  alt +
  '" width="1440" height="1000"><figcaption>' +
  caption +
  "</figcaption></figure>";

function overview() {
  return `<section class="hero">
    ${sceneMarkup()}
    <div class="hero-coordinates" aria-hidden="true"><span>ORION / THE PERSONAL MEDIA SYSTEM</span><span>YOUR UNIVERSE. A LITTLE MORE ORDERED.</span></div>
    <div class="hero-layout"><div class="hero-copy-block">
      ${eyebrow("LOCAL-FIRST. OPEN SOURCE. ENTIRELY YOURS.")}
      <h1>Every file.<br>In its<br><em>right orbit.</em></h1>
      <p class="hero-copy">A folder full of filenames. A universe of stories.<br>Orion turns the first into the second — with reviewed metadata, exact previews, and a record of every move.</p>
      <div class="actions"><a class="button primary" href="#install">Bring Orion home <span aria-hidden="true">↗</span></a><a class="button text-action" href="${BASE}docs/">Explore the docs <span aria-hidden="true">→</span></a></div>
      <p class="hero-note"><span class="small-dot"></span> YOUR FILES. YOUR COMPUTER. YOUR CALL.</p>
    </div><div class="hero-instrument"><div class="orbital-legend" aria-hidden="true"><span><i></i> YOUR LIBRARY, IN MOTION</span><span>07 COLLECTIONS / 01 HOME</span></div>${showcaseMarkup()}<div class="instrument-caption" aria-hidden="true"><span>01 — TRY A LITTLE ORDER</span><span>INTERACTIVE SAMPLE ↑</span></div></div></div>
    <div class="hero-floor"><span class="scroll-invitation"><span aria-hidden="true">↓</span> FOLLOW A FILE INTO ORBIT</span><span>BUILT FOR THE STORIES YOU KEEP <span aria-hidden="true">✦</span></span></div>
  </section>
  <section class="principles reveal" aria-label="Orion principles"><p><span>01</span> Local by design</p><p><span>02</span> Review before action</p><p><span>03</span> Never overwrite</p><p><span>04</span> Open source, always</p></section>
  ${storyMarkup()}
  <section class="section collection-section reveal"><div class="section-heading"><div>${eyebrow("SEVEN COLLECTIONS. ONE GRAVITY.")}<h2>There’s room for<br><em>your whole universe.</em></h2></div><a class="text-link" href="#demo">Explore every collection ↗</a></div>${collectionList()}</section>
  <section class="section product-section reveal"><div class="section-heading"><div>${eyebrow("MEET YOUR MISSION CONTROL")}<h2>Clarity at<br><em>every step.</em></h2></div><div class="product-description"><p>A real workspace, with real decisions.<br>Not another folder you’ll forget about.</p><a class="text-link" href="#features">Inside the workspace →</a></div></div>
    <div class="product-frame"><div class="product-frame-top"><span><i></i><i></i><i></i></span><span>ORION / YOUR LOCAL WORKSPACE</span><span>↗</span></div>${screenshot("production-night.png", "The real Orion application in its night theme, with seven media collections and local job status.", "ACTUAL PRODUCT · Captured with generated test media, never a personal library.")}</div>
    <div class="product-details"><article><span aria-hidden="true">⌘</span><h3>All the detail.<br>None of the guesswork.</h3><p>Exact paths, metadata evidence, saved naming presets and a preview you can actually approve.</p></article><article><span aria-hidden="true">↶</span><h3>A record.<br>And a way back.</h3><p>Follow a durable job. Retry an interruption. Preview guarded undo for unchanged recorded files.</p></article><article><span aria-hidden="true">◇</span><h3>Your media.<br>On your terms.</h3><p>Keep files on your computer or NAS. Connect metadata providers or Jellyfin and Emby when you choose.</p></article></div>
  </section>
  <section class="section docs-section reveal"><div>${eyebrow("YOUR FIELD GUIDE")}<h2>Find your<br><em>bearings.</em></h2><p>First launch or finer details.<br>Everything you need, right here.</p><a class="text-link" href="${BASE}docs/">Open the documentation ↗</a></div><div class="docs-preview"><span class="overline">THE ORION HANDBOOK</span><form class="docs-search-preview" action="${BASE}docs/" method="get"><span aria-hidden="true">⌕</span><label class="visually-hidden" for="home-docs-search">Search documentation</label><input id="home-docs-search" type="search" name="q" placeholder="What would you like to know?" required><button type="submit" aria-label="Search guides">↵</button></form><div class="guide-links"><a href="${BASE}docs/install.html"><span>01</span><div><strong>Your first launch</strong><small>Install, connect, and find your feet.</small></div><span>↗</span></a><a href="${BASE}docs/workflow.html"><span>02</span><div><strong>From scan to sorted</strong><small>A guided journey through your first library.</small></div><span>↗</span></a><a href="${BASE}docs/recovery.html"><span>03</span><div><strong>A safe way back</strong><small>Understand jobs, backups, recovery and undo.</small></div><span>↗</span></a></div></div></section>
  <section class="section closing reveal"><div class="closing-constellation constellation" aria-hidden="true">✦<span>✧</span><i></i></div>${eyebrow("KEEP YOUR COLLECTION CLOSE")}<h2>Every story<br>deserves <em>a home.</em></h2><p>Give yours a little order.<br>Keep a whole universe within reach.</p>${actions()}<span class="closing-note">LOCAL APP <span>·</span> SEVEN COLLECTIONS <span>·</span> OPEN SOURCE</span></section>`;
}
function features() {
  return (
    '<section class="page-intro">' +
    eyebrow("THE WORKSPACE") +
    "<h1>A little order.<br>A lot of possibility.</h1><p>One place to identify, review and organise your media, with a clear view of what happens next.</p></section>" +
    '<section class="section"><div class="feature-grid"><article><span class="step">01 / REVIEW</span><h2>Give every file a name.</h2><p>Search the review queue, compare metadata candidates, or correct a title manually. Optional providers help identify video, music and books; offline files can still be reviewed.</p></article><article><span class="step">02 / PREVIEW</span><h2>See the plan first.</h2><p>Inspect source and destination paths before approving. Naming profiles shape the output. Conflicts and unavailable sources need attention before a batch can proceed.</p></article><article><span class="step">03 / FOLLOW</span><h2>Know where things stand.</h2><p>Durable jobs record progress and outcomes. Inspect interruptions, retry eligible work and preview undo. Closing the browser leaves the installed backend running.</p></article></div></section>' +
    '<section class="wide-section">' +
    screenshot(
      "production-plan.png",
      "The real Orion plan preview showing source and destination paths before organisation.",
      "PREVIEW BEFORE APPROVAL · Production path preview with generated fixture files.",
    ) +
    "</section>" +
    '<section class="section">' +
    collectionList() +
    "</section>" +
    '<section class="section split"><div>' +
    eyebrow("OPTIONAL CONNECTIONS") +
    '<h2>Fits into your<br>media routine.</h2></div><div class="prose"><p>Connect Jellyfin or Emby for library lookups and refreshes. Enable NFO and artwork output per profile. Compare duplicates without automatic deletion, export batch reports, or watch a source for stable arrivals.</p><p>These connections need your own configuration. Provider or server failures appear separately from local file results. Live authenticated services are not represented by this public demo.</p><a class="text-link" href="#recovery">Read about data & recovery →</a></div></section>'
  );
}
function install() {
  return (
    '<section class="page-intro">' +
    eyebrow("BRING ORION HOME") +
    "<h1>Start on your<br>own computer.</h1><p>Build the local workspace from source. The public site is a guide and a sample demo; your installed app handles your library.</p></section>" +
    '<section class="section install-grid"><div><div class="notice"><span class="step">RELEASE STATUS</span><h2>Source available.</h2><p>No published installer is linked here.</p><p>Windows bundles are prepared by the release pipeline for maintainer review. Check the repository for published release availability and verification notes. Native macOS and Linux packages are not promised.</p><a class="text-link" href="' +
    repository +
    '" target="_blank" rel="noreferrer">View the source on GitHub ↗</a></div></div><div class="prose"><h2>Build from source</h2><p>Use Python 3.11 or 3.12, Node.js 24 and Git. From the repository root, create a virtual environment and install the web runtime dependencies. Node is needed for the build, not for running the compiled workspace.</p><pre><code>git clone https://github.com/Varun-SV/Orion.git\ncd Orion\npython -m venv .venv\n# Windows PowerShell\n.\\.venv\\Scripts\\Activate.ps1\n# macOS / Linux instead: source .venv/bin/activate\npython -m pip install --require-hashes -r requirements-web.lock\nnpm --prefix frontend ci\nnpm --prefix frontend run build\npython -m orion run --frontend-dir frontend/dist</code></pre><p>The launcher opens the loopback URL in your browser. Complete setup with a source folder and destination, review matches, then preview a plan before approving it.</p><p>Stop the backend with <code>python -m orion stop</code>. Keep the same <code>--data-dir</code> for run and stop when using an alternative data directory.</p><div class="document-links"><a data-document href="' +
    BASE +
    'docs/install.html">Full installation guide →</a><a data-document href="' +
    BASE +
    'docs/recovery.html">Backup & recovery guide →</a></div></div></section>' +
    '<section class="section closing"><h2>Take a look before you build.</h2><p>Explore a small fictional library. Nothing to install, and no files to connect.</p><a class="button primary" href="#demo">Open fixture demo →</a></section>'
  );
}
function recovery() {
  return (
    '<section class="page-intro">' +
    eyebrow("LOCAL BY DESIGN") +
    "<h1>Keep the decisions.<br>Keep the record.</h1><p>Good organisation includes knowing what changed, what did not, and what you can recover.</p></section>" +
    '<section class="section reading"><article><span class="step">01 / YOUR DATA</span><h2>The workspace lives with you.</h2><p>The installed UI and API share a loopback origin. Your sources, match decisions, plans and jobs live in a local SQLite database. Provider and media server credentials use the operating system keychain, or an explicitly selected session-only mode.</p><p>Optional metadata and server connections send the information needed for their requests. Configure them only if you want to use them. This static site uses local assets and saves your colour theme and motion preference in your browser.</p></article><article><span class="step">02 / FILE OPERATIONS</span><h2>Approve an exact plan.</h2><p>Plans record the proposed paths and identify collisions. Orion does not overwrite an existing destination. Cross-volume transfers use copy, verification and checkpoints before deleting the original. A durable journal records completed work and interruptions.</p><p>Recovery is a guided process. Source disappearance, interrupted copies or externally changed files may require review. A failed optional server refresh does not undo successful local organisation.</p></article><article><span class="step">03 / BACKUP & UNDO</span><h2>Recovery has boundaries.</h2><p>Database upgrades create a backup before migration. Keep an independent backup of your media and the app data directory. A plan record is not a media backup.</p><p>Undo previews a new job and checks the recorded file state. It refuses unsafe reversals when another application changed a file or a destination is occupied. It cannot promise to reverse arbitrary later edits.</p><a class="text-link" data-document href="' +
    BASE +
    'docs/recovery.html">Read the recovery guide →</a></article></section>' +
    '<section class="wide-section">' +
    screenshot(
      "production-jobs.png",
      "Production Orion Job centre displaying stored job results and actions.",
      "A DURABLE RECORD · Real production Job centre, using generated test media.",
    ) +
    "</section>"
  );
}
function demo() {
  const c = collections[selected];
  return (
    '<div class="demo-banner" role="note" aria-label="Fixture demo"><span class="small-dot"></span><strong>FIXTURE DEMO</strong><span>Fictional sample data. No access to your media. No files are moved.</span></div><section class="page-intro demo-intro">' +
    eyebrow("A SMALL LOOK AROUND") +
    "<h1>Meet your next<br>tidy library.</h1><p>Choose a collection, search a sample title and preview its organisation. Every action here is a browser-only simulation.</p></section>" +
    '<section class="demo-shell"><aside class="demo-sidebar"><p class="eyebrow">COLLECTIONS</p><div class="collection-buttons">' +
    collections
      .map(
        (item, index) =>
          '<button type="button" data-collection="' +
          index +
          '" aria-pressed="' +
          (selected === index) +
          '"><span aria-hidden="true">' +
          item.glyph +
          "</span>" +
          item.name +
          "</button>",
      )
      .join("") +
    '</div></aside><div class="demo-workspace"><div class="demo-heading"><div><p class="step">SAMPLE LIBRARY</p><h2>' +
    c.name +
    '</h2></div><button class="quiet-button" id="reset">Reset demo</button></div><label class="search-label"><span class="visually-hidden">Search sample collection</span><input type="search" id="search" placeholder="Search this sample collection" aria-label="Search sample collection"></label><div id="demo-result" data-testid="demo-result"></div><div id="plan-slot"></div><p class="demo-disclaimer">In the installed app, review selects real metadata and preview validates your configured paths. This sample omits that live validation.</p></div></section>' +
    '<section class="section demo-follow"><p>Want to work with your own library?</p><a class="text-link" href="#install">Set up the local app →</a></section>'
  );
}
function updateDemo() {
  const c = collections[selected];
  const matches = c.title.toLowerCase().includes(search.toLowerCase());
  const result = document.querySelector("#demo-result");
  if (!result) return;
  result.innerHTML = matches
    ? '<article class="sample-card"><div class="sample-art" aria-hidden="true"><span>' +
      c.glyph +
      '</span><div class="sample-orbit"></div></div><div class="sample-details"><span class="tag">FICTIONAL SAMPLE · ' +
      c.name +
      "</span><h3>" +
      c.title +
      "</h3><p>" +
      c.year +
      " · " +
      c.detail +
      '</p><p class="match-label">Sample match confirmed</p><button class="button primary" id="preview">Preview sample plan →</button></div></article>'
    : '<p class="empty">No sample titles match.</p>';
  document.querySelector("#preview")?.addEventListener("click", () => {
    preview = true;
    completed = false;
    updatePlan();
  });
  updatePlan();
}
function updatePlan() {
  const slot = document.querySelector("#plan-slot");
  if (!slot) return;
  const c = collections[selected];
  slot.innerHTML = preview
    ? '<section class="sample-plan" data-testid="sample-plan"><p class="step">SAMPLE PLAN · ONE FILE</p><h3>Every path, before the move.</h3><dl><dt>Sample source</dt><dd><code>' +
      c.source +
      "</code></dd><dt>Sample destination</dt><dd><code>" +
      c.destination +
      "</code></dd></dl><p>Illustrative paths only. No filesystem checks have run.</p>" +
      (completed
        ? '<p class="result" role="status" tabindex="-1">Sample complete. No files were moved.</p>'
        : '<button class="button primary" id="simulate">Simulate organisation</button>') +
      "</section>"
    : "";
  document.querySelector("#simulate")?.addEventListener("click", () => {
    completed = true;
    updatePlan();
    document.querySelector('[role="status"]').focus();
  });
}
const renderers = { overview, features, install, recovery, demo };
function render(focus = false) {
  const hash = location.hash.slice(1);
  if (hash === "content" && main.childElementCount) {
    main.focus();
    return;
  }
  const route = Object.hasOwn(pages, hash) ? hash : "overview";
  cleanupPage();
  main.innerHTML = renderers[route]();
  main.dataset.route = route;
  if (route === "overview") {
    const cleanups = [
      mountShowcase(main.querySelector(".showcase")),
      mountScene(main.querySelector(".hero")),
      mountStory(main.querySelector(".file-story")),
    ];
    cleanupPage = () => cleanups.forEach((cleanup) => cleanup());
  } else cleanupPage = () => {};
  main
    .querySelectorAll(".page-intro, .section, .wide-section, .demo-shell")
    .forEach((node) => node.classList.add("reveal"));
  document.title = pages[route].title + " · Orion";
  document.querySelector('meta[name="description"]').content =
    pages[route].description;
  document.querySelector('meta[property="og:title"]').content = document.title;
  document.querySelector('meta[property="og:description"]').content =
    pages[route].description;
  document.querySelectorAll("[data-route]").forEach((link) => {
    if (link.dataset.route === route) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  if (route === "demo") {
    search = "";
    preview = false;
    completed = false;
    updateDemo();
    document.querySelectorAll("[data-collection]").forEach((button) =>
      button.addEventListener("click", () => {
        selected = Number(button.dataset.collection);
        search = "";
        preview = false;
        completed = false;
        document.querySelector(".demo-heading h2").textContent =
          collections[selected].name;
        document.querySelector("#search").value = "";
        document
          .querySelectorAll("[data-collection]")
          .forEach((item) =>
            item.setAttribute(
              "aria-pressed",
              String(Number(item.dataset.collection) === selected),
            ),
          );
        updateDemo();
      }),
    );
    document.querySelector("#search").addEventListener("input", (event) => {
      search = event.target.value;
      updateDemo();
    });
    document.querySelector("#reset").addEventListener("click", () => {
      selected = 0;
      render();
      document.querySelector("#reset").focus();
    });
  }
  motion.refresh();
  if (focus) {
    main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
}
main.addEventListener("click", (event) => {
  const card = event.target.closest("[data-demo-select]");
  if (card) selected = Number(card.dataset.demoSelect);
});
window.addEventListener("hashchange", () =>
  motion.transition(() => render(true)),
);
render();
