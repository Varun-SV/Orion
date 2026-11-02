import "./style.css";
import { collections } from "./collections.js";
import { mountShowcase } from "./showcase.js";
import { chapterIds, contentMarkup, pageMeta } from "./content.js";
import { activeCollection, locate } from "./director.js";
import { STARS, starPositions } from "./stars-data.js";

const html = document.documentElement;
const main = document.querySelector("#content");
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const reducedQuery = matchMedia("(prefers-reduced-motion: reduce)");

/* ---------- content ---------- */
main.innerHTML = contentMarkup();
mountShowcase(main.querySelector(".showcase"));
const sections = [...main.querySelectorAll(".chapter")];
const covers = [...main.querySelectorAll("[data-cover]")];
const listButtons = [...main.querySelectorAll(".collection-list button")];
const capStar = main.querySelector("[data-cap-star]");
const capTitle = main.querySelector("[data-cap-title]");
const capDetail = main.querySelector("[data-cap-detail]");
const probe = document.querySelector(".vh-probe");
probe.style.cssText =
  "position:fixed;left:0;top:0;width:1px;height:100vh;height:100svh;visibility:hidden;pointer-events:none";

/* ---------- fallback constellation (also shown if WebGL is unavailable) ---------- */
{
  const stars = starPositions();
  const edges = [
    [7, 0],
    [7, 1],
    [0, 4],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [2, 6],
    [6, 5],
  ];
  const lines = edges
    .map(
      ([a, b]) =>
        `<path class="fl" d="M${stars[a].x.toFixed(1)} ${(-stars[a].y).toFixed(1)}L${stars[b].x.toFixed(1)} ${(-stars[b].y).toFixed(1)}"/>`,
    )
    .join("");
  const dots = stars
    .map(
      (s, i) =>
        `<circle class="fs twinkle${s.name === "Betelgeuse" ? " fs--warm" : ""}" style="animation-delay:${-i * 0.7}s" cx="${s.x.toFixed(1)}" cy="${(-s.y).toFixed(1)}" r="${(1.2 + (3.6 - s.mag) * 0.5).toFixed(2)}"/>`,
    )
    .join("");
  document.querySelector(".fallback-sky").innerHTML =
    `<svg viewBox="-34 -34 68 68" role="presentation">${lines}${dots}</svg>`;
}

/* ---------- header, navigation, motion ---------- */
const siteHeader = document.querySelector(".site-header");
const navToggle = document.querySelector(".nav-toggle");
const primaryNav = document.querySelector("#primary-navigation");
const narrowNav = matchMedia("(max-width: 860px)");
function setNavigation(open) {
  siteHeader.classList.toggle("navigation-open", open);
  navToggle.setAttribute("aria-expanded", String(open));
  navToggle.setAttribute(
    "aria-label",
    open ? "Close navigation" : "Open navigation",
  );
  navToggle.firstElementChild.textContent = open ? "×" : "☰";
}
navToggle.addEventListener("click", () => {
  const open = navToggle.getAttribute("aria-expanded") !== "true";
  setNavigation(open);
  if (open) primaryNav.querySelector("a").focus();
});
siteHeader.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    navToggle.getAttribute("aria-expanded") === "true"
  ) {
    setNavigation(false);
    navToggle.focus();
  }
});
primaryNav.addEventListener(
  "click",
  (event) => event.target.closest("a") && setNavigation(false),
);
narrowNav.addEventListener("change", () => setNavigation(false));

const motionButton = document.querySelector("#motion-toggle");
let paused = false;
try {
  paused = localStorage.getItem("orion-site-motion") === "paused";
} catch {
  /* Storage may be disabled; the choice then lasts for this visit. */
}
let world = null;
function syncMotion() {
  const mode = paused ? "paused" : reducedQuery.matches ? "reduced" : "running";
  html.dataset.motion = mode;
  motionButton.setAttribute(
    "aria-label",
    paused ? "Resume animations" : "Pause animations",
  );
  motionButton.setAttribute("aria-pressed", String(paused));
  motionButton.querySelector("[data-motion-icon]").textContent = paused
    ? "▷"
    : "Ⅱ";
  motionButton.title = reducedQuery.matches
    ? "Motion follows your device preference"
    : paused
      ? "Resume animations"
      : "Pause animations";
  world?.setMotion(mode);
  if (world) mode === "running" ? world.start() : world.stop();
}
motionButton.addEventListener("click", () => {
  paused = !paused;
  try {
    localStorage.setItem("orion-site-motion", paused ? "paused" : "running");
  } catch {
    /* Ignore unavailable storage. */
  }
  syncMotion();
});
reducedQuery.addEventListener("change", syncMotion);
syncMotion();

/* ---------- measuring and scroll ---------- */
let tops = [];
let vh = innerHeight;
let travel1 = 1;
function measure() {
  vh = probe.offsetHeight || innerHeight;
  tops = sections.map((s) => s.getBoundingClientRect().top + scrollY);
  tops.push(document.documentElement.scrollHeight - 0);
  // The footer belongs to the last chapter, so end it where the footer begins.
  const footer = document.querySelector(".site-footer");
  tops[tops.length - 1] = footer.getBoundingClientRect().top + scrollY;
  travel1 = Math.max(1, tops[2] - tops[1] - vh);
}

let current = { index: 0, local: 0, u: 0, collection: -1 };
let ticking = false;
let lastCollection = -2;
function setCollection(i) {
  const shown = i < 0 ? 0 : i;
  covers.forEach((c, k) => c.setAttribute("aria-hidden", String(k !== shown)));
  listButtons.forEach((b, k) =>
    b.setAttribute("aria-current", String(k === shown)),
  );
  capStar.textContent = STARS.find((s) => s.collection === shown).name;
  capTitle.textContent = collections[shown].title;
  capDetail.textContent = collections[shown].detail;
}
let lastIndex = -1;
function apply() {
  ticking = false;
  const info = locate(tops, scrollY, vh);
  const collection = activeCollection(info.index, info.local);
  current = { ...info, collection };
  if (info.index !== lastIndex) {
    lastIndex = info.index;
    html.dataset.chapter = chapterIds[info.index];
    const [title] = pageMeta[chapterIds[info.index]];
    document.title = `${title} · Orion`;
    document
      .querySelectorAll("#primary-navigation [data-route]")
      .forEach((a) =>
        a.setAttribute(
          "aria-current",
          String(a.dataset.route === chapterIds[info.index]),
        ),
      );
  }
  if (collection !== lastCollection && collection >= 0) {
    lastCollection = collection;
    setCollection(collection);
    labelButtons.forEach(
      (b, k) => (b.dataset.active = String(k === collection)),
    );
  }
  // Fade each pinned chapter's text in and out around its own scroll range.
  sections.forEach((section, i) => {
    const near = Math.abs(i - info.index) <= 1;
    section.classList.toggle("is-near", near);
    if (!near) return;
    let local;
    if (i < info.index) local = 1.01;
    else if (i > info.index) local = -0.01;
    else local = info.local;
    const enter = i === 0 ? 1 : clamp(local / 0.1);
    const leave = i >= sections.length - 2 ? 1 : clamp((1 - local) / 0.12);
    section.style.setProperty("--enter", enter.toFixed(3));
    section.style.setProperty("--leave", leave.toFixed(3));
  });
  world?.setScroll({ u: info.u, index: info.index, collection });
}
function onScroll() {
  if (!ticking) {
    ticking = true;
    requestAnimationFrame(apply);
  }
}
addEventListener("scroll", onScroll, { passive: true });
addEventListener("resize", () => {
  measure();
  onScroll();
});
new ResizeObserver(() => {
  measure();
  onScroll();
}).observe(main);
document.fonts?.ready.then(() => {
  measure();
  onScroll();
});

/* ---------- star labels: real buttons positioned over the 3D stars ---------- */
const labelHost = document.querySelector(".star-labels");
const mapped = STARS.map((s, i) => ({ ...s, i })).filter(
  (s) => s.collection >= 0,
);
const labelButtons = [];
for (const s of mapped) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "star-label";
  b.dataset.collection = String(s.collection);
  b.setAttribute(
    "aria-label",
    `${s.name}: ${collections[s.collection].name}. Go to this collection`,
  );
  b.innerHTML = `<span class="hit"></span><span class="name">${s.name}<small>${collections[s.collection].name}</small></span>`;
  labelHost.append(b);
  labelButtons[s.collection] = b;
  b.addEventListener("click", () => goToCollection(s.collection));
  b.addEventListener("pointerenter", () => world?.setHover(s.collection));
  b.addEventListener("pointerleave", () => world?.setHover(-1));
  b.addEventListener("focus", () => world?.setHover(s.collection));
  b.addEventListener("blur", () => world?.setHover(-1));
}
function onProject(points, amount, amountActive, stars) {
  for (let k = 0; k < stars.length; k++) {
    const star = stars[k];
    if (star.collection < 0) continue;
    const b = labelButtons[star.collection];
    // In the collections chapter only the chosen star keeps a bright label.
    const chosen = current.collection === star.collection;
    const a =
      current.index >= 1 ? (chosen ? amountActive : amount * 0.35) : amount;
    const visible = a > 0.04 && points[k * 3 + 2] === 1;
    if (visible)
      b.style.transform = `translate3d(${points[k * 3].toFixed(1)}px, ${points[k * 3 + 1].toFixed(1)}px, 0)`;
    b.style.opacity = visible ? a.toFixed(2) : "0";
    b.style.visibility = visible ? "visible" : "hidden";
  }
}
function goToCollection(i) {
  const top = tops[1] + ((i + 0.5) / collections.length) * travel1;
  scrollTo({
    top,
    behavior: html.dataset.motion === "running" ? "smooth" : "auto",
  });
}
listButtons.forEach((b, i) => {
  b.addEventListener("click", () => goToCollection(i));
  b.addEventListener("pointerenter", () => world?.setHover(i));
  b.addEventListener("pointerleave", () => world?.setHover(-1));
  b.addEventListener("focus", () => world?.setHover(i));
  b.addEventListener("blur", () => world?.setHover(-1));
});

/* ---------- load the 3D world after the first paint ---------- */
measure();
apply();
async function boot() {
  try {
    const { createWorld } = await import("./world/index.js");
    const created = createWorld(document.querySelector("#world"), {
      onProject,
      onTier: (tier, index) => (html.dataset.tier = tier.name || String(index)),
      onLost: () => (html.dataset.scene = "lost"),
      onRestored: () => (html.dataset.scene = "webgl"),
      onStats: ({ frames, ms, tier }) => {
        html.dataset.frames = String(frames);
        html.dataset.frameMs = ms.toFixed(1);
        html.dataset.tier = ["high", "medium", "low"][tier];
      },
    });
    if (!created) throw new Error("WebGL is unavailable");
    world = created;
    html.dataset.scene = "webgl";
    html.dataset.tier = ["high", "medium", "low"][world.tier()];
    syncMotion();
    world.setScroll({
      u: current.u,
      index: current.index,
      collection: current.collection,
    });
    world.start();
  } catch (error) {
    html.dataset.scene = "fallback";
    console.info("Orion 3D scene not started:", error?.message ?? error);
  }
}
requestAnimationFrame(() => requestAnimationFrame(boot));
