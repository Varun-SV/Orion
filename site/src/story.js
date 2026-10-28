import "./story.css";
import { collections } from "./collections";

const stages = ["scan", "review", "preview", "organise"];
const stageNames = ["Scan", "Review", "Preview", "Organise"];
const storyFiles = [0, 5, 6].map((collection) => collections[collection]);

const storySteps = [
  {
    id: "scan",
    number: "01",
    title: "Start with the names you have.",
    accent: "Everything begins with a scan.",
    copy: "Orion indexes supported media and parsed details where they are. Scanning gives you a clear starting point; it never moves or renames a file.",
    note: "SOURCE · INDEXED IN PLACE",
  },
  {
    id: "review",
    number: "02",
    title: "A match is a suggestion.",
    accent: "Your review makes it yours.",
    copy: "Compare candidate details for a movie, an album, and a book. Confirm a match, correct it by hand, or leave it uncertain. Nothing moves when you confirm metadata.",
    note: "MOVIE · MUSIC · BOOK · REVIEWED BY YOU",
  },
  {
    id: "preview",
    number: "03",
    title: "See the exact path first.",
    accent: "Every destination is on the plan.",
    copy: "Preview the source and destination for every file, including conflicts and optional outputs. If a destination is occupied, Orion marks it for review and never replaces it.",
    note: "REVALIDATE THE PLAN BEFORE APPROVAL",
  },
  {
    id: "organise",
    number: "04",
    title: "Follow the work, then recover.",
    accent: "A record keeps the way back clear.",
    copy: "Approved operations become recorded jobs. Transfers verify bytes and preserve existing files; a guarded undo preview checks the recorded file state before reversing anything.",
    note: "VERIFIED TRANSFER · RECORDED JOB · GUARDED UNDO",
  },
];

function fileGlyph(label, detail, kind) {
  return `<div class="story-file story-file--${kind}"><span class="story-file-icon" aria-hidden="true"><svg viewBox="0 0 24 28"><path d="M4 1h10l6 6v20H4zM14 1v7h6"/><path d="M8 15h8M8 19h6"/></svg></span><span class="story-file-copy"><strong>${label}</strong><small>${detail}</small></span><span class="story-file-state" aria-hidden="true">${kind === "done" ? "✓" : "· · ·"}</span></div>`;
}

function diagramFrame(id) {
  const isScan = id === "scan";
  const isReview = id === "review";
  const isPreview = id === "preview";
  const isOrganise = id === "organise";
  const nodeKind = isOrganise ? "done" : "source";
  const targetHeading = isScan
    ? "Your library"
    : isReview
      ? "Confirmed details"
      : isPreview
        ? "Planned destinations"
        : "Verified and recorded";
  const destinations = isPreview
    ? [
        [storyFiles[0].destination, `From ${storyFiles[0].source}`, "path"],
        [storyFiles[1].destination, `From ${storyFiles[1].source}`, "path"],
        [storyFiles[2].destination, `From ${storyFiles[2].source}`, "conflict"],
      ]
    : isOrganise
      ? [
          [storyFiles[0].destination, "Verified · job 1042", "done"],
          [storyFiles[1].destination, "Verified · job 1042", "done"],
          [storyFiles[2].destination, "Occupied · left in place", "conflict"],
        ]
      : isReview
        ? [
            [
              "Movie match",
              `${storyFiles[0].title} · ${storyFiles[0].year}`,
              "match",
            ],
            [
              "Music match",
              `${storyFiles[1].title} · ${storyFiles[1].detail}`,
              "match",
            ],
            [
              "Book match",
              `${storyFiles[2].title} · ${storyFiles[2].detail}`,
              "match",
            ],
          ]
        : [
            ["Incoming", "3 files indexed", "count"],
            ["Original paths", "Left in place", "count"],
            ["No file changes", "Scan only", "count"],
          ];

  return `<div class="story-diagram-frame" data-diagram-stage="${id}" aria-hidden="true">
    <div class="story-source-stack">
      ${storyFiles.map((file, index) => fileGlyph(file.source.split("/").at(-1), `${["MOVIE", "MUSIC", "BOOK"][index]} · FICTIONAL SAMPLE`, nodeKind)).join("")}
    </div>
    <svg class="story-wires" viewBox="0 0 500 330" preserveAspectRatio="none"><path class="wire wire--one" d="M214 59 C286 59 255 62 316 62"/><path class="wire wire--two" d="M214 165 C268 165 270 165 316 165"/><path class="wire wire--three" d="M214 272 C286 272 258 269 316 269"/><circle class="wire-dot wire-dot--one" cx="286" cy="59" r="3"/><circle class="wire-dot wire-dot--two" cx="286" cy="165" r="3"/><circle class="wire-dot wire-dot--three" cx="286" cy="272" r="3"/><circle class="wire-packet wire-packet--one" cx="226" cy="59" r="2.5"/><circle class="wire-packet wire-packet--two" cx="226" cy="165" r="2.5"/><circle class="wire-packet wire-packet--three" cx="226" cy="272" r="2.5"/></svg>
    <div class="story-destination-stack"><span class="story-target-label">${targetHeading}</span>${destinations
      .map(
        ([name, detail, status]) =>
          `<div class="story-destination story-destination--${status}"><span class="story-destination-mark" aria-hidden="true">${status === "conflict" ? "!" : status === "done" ? "✓" : status === "match" ? "✦" : status === "path" ? "↗" : "·"}</span><span><strong>${name}</strong><small>${detail}</small></span></div>`,
      )
      .join("")}</div>
    ${isPreview ? '<div class="story-conflict-callout"><span aria-hidden="true">!</span> Occupied path · review required · never overwrite</div>' : ""}
    ${isOrganise ? '<div class="story-job-chip"><span class="story-job-check">✓</span><span><strong>Job 1042</strong><small>Bytes verified · result recorded</small></span></div>' : ""}
  </div>`;
}

export function storyMarkup() {
  return `<section class="file-story" aria-label="From scattered files to an organised library" data-active-stage="scan">
    <header class="file-story-intro"><div><span class="file-story-kicker">A QUIETER WAY TO ORGANISE</span><h2>Four considered steps.<br><em>Your media, in orbit.</em></h2></div><p>From loose filenames to a library you understand, with a clear decision at every turn.</p></header>
    <div class="file-story-layout">
      <aside class="file-story-visual" aria-label="Story stage illustration">
        <div class="story-visual-top"><span><i aria-hidden="true"></i> ORION / FILE JOURNEY</span><span>LOCAL WORKSPACE</span></div>
        <div class="story-scene-wrap" data-story-scene data-stage="scan" aria-hidden="true">${stages.map(diagramFrame).join("")}</div>
        <div class="story-stage-controls">
          <div class="story-stage-current"><span>NOW SHOWING</span><strong data-story-current>01 / Scan</strong></div>
          <div class="story-stage-tabs" role="group" aria-label="Story stages">${stages
            .map(
              (stage, index) =>
                `<button type="button" data-story-control="${stage}" aria-label="${String(index + 1).padStart(2, "0")} ${stageNames[index]}" aria-pressed="${index === 0}"><span>${String(index + 1).padStart(2, "0")}</span><i aria-hidden="true"></i></button>`,
            )
            .join("")}</div>
        </div>
        <p class="story-sticky-disclosure">FICTIONAL SAMPLE <span>·</span> No files are moved.</p>
      </aside>
      <div class="file-story-narrative">${storySteps
        .map(
          (step, index) =>
            `<article data-story-article="${step.id}" data-active="${index === 0}" aria-labelledby="story-heading-${step.id}"><span class="story-step-index">${step.number} <i aria-hidden="true"></i> ${step.note}</span><h3 id="story-heading-${step.id}">${step.title}<br><em>${step.accent}</em></h3><p>${step.copy}</p><span class="story-step-tail" aria-hidden="true">ORION / ${step.number}</span></article>`,
        )
        .join("")}</div>
    </div>
    <p class="file-story-disclosure">FICTIONAL SAMPLE <span>·</span> Fictional sample. No files are moved.</p>
  </section>`;
}

export function mountStory(rootElement) {
  const root = rootElement.matches?.(".file-story")
    ? rootElement
    : rootElement.querySelector(".file-story");
  if (!root) return () => {};

  const scene = root.querySelector("[data-story-scene]");
  const current = root.querySelector("[data-story-current]");
  const controls = [...root.querySelectorAll("[data-story-control]")];
  const articles = [...root.querySelectorAll("[data-story-article]")];
  let activeStage = "scan";
  let frame = 0;
  let visibilityObserver;
  let observedScrollY = window.scrollY;

  function setStage(stage) {
    if (!stages.includes(stage)) return;
    activeStage = stage;
    root.dataset.activeStage = stage;
    scene.dataset.stage = stage;
    current.textContent = `${String(stages.indexOf(stage) + 1).padStart(2, "0")} / ${stageNames[stages.indexOf(stage)]}`;
    controls.forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.storyControl === stage),
      ),
    );
    articles.forEach(
      (article) =>
        (article.dataset.active = String(
          article.dataset.storyArticle === stage,
        )),
    );
  }

  function onClick(event) {
    const button = event.target.closest("[data-story-control]");
    if (button && root.contains(button)) {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      const stage = button.dataset.storyControl;
      setStage(stage);
      articles
        .find((article) => article.dataset.storyArticle === stage)
        ?.scrollIntoView({ block: "center", behavior: "instant" });
      observedScrollY = window.scrollY;
    }
  }

  function updateFromScroll() {
    frame = 0;
    const center = window.innerHeight / 2;
    let nearest = articles[0];
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const article of articles) {
      const rect = article.getBoundingClientRect();
      const distance = Math.abs((rect.top + rect.bottom) / 2 - center);
      if (distance < nearestDistance) {
        nearest = article;
        nearestDistance = distance;
      }
    }
    if (nearest) setStage(nearest.dataset.storyArticle);
  }

  function onScroll() {
    if (window.scrollY === observedScrollY) return;
    observedScrollY = window.scrollY;
    if (!frame) frame = requestAnimationFrame(updateFromScroll);
  }

  root.addEventListener("click", onClick);
  window.addEventListener("scroll", onScroll, { passive: true });
  if ("IntersectionObserver" in window) {
    visibilityObserver = new IntersectionObserver(([entry]) => {
      root.classList.toggle("is-in-view", entry.isIntersecting);
    });
    visibilityObserver.observe(root);
  }
  setStage(activeStage);
  return () => {
    root.removeEventListener("click", onClick);
    window.removeEventListener("scroll", onScroll);
    if (frame) cancelAnimationFrame(frame);
    visibilityObserver?.disconnect();
  };
}
