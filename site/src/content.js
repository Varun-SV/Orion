import { collections } from "./collections.js";
import { mediaArtwork } from "./media-art.js";
import { showcaseMarkup } from "./showcase.js";
import { STARS } from "./stars-data.js";

const REPO = "https://github.com/Varun-SV/Orion";
const words = (text, start = 0) =>
  text
    .split(" ")
    .map((w, i) => `<span class="w" style="--i:${start + i}">${w}</span>`)
    .join(" ");
const starFor = (collection) => STARS.find((s) => s.collection === collection);

export const chapterIds = [
  "overview",
  "features",
  "scan",
  "preview",
  "recovery",
  "demo",
  "install",
];
export const pageMeta = {
  overview: [
    "Overview",
    "A local media workspace for movies, series, anime, web series, music and books.",
  ],
  features: [
    "Features",
    "Seven collections, each a star: review metadata, preview paths and organise with Orion.",
  ],
  scan: [
    "Scan",
    "Scan sources, review provider candidates or correct metadata by hand.",
  ],
  preview: [
    "Preview",
    "Every file move is shown as an exact path before you approve it.",
  ],
  recovery: [
    "Recovery & privacy",
    "Persistent jobs, guarded undo and verified transfers. Local by design.",
  ],
  demo: [
    "Demo",
    "Try a clearly labelled sample organiser with fictional files, in your browser.",
  ],
  install: [
    "Install",
    "Build and run Orion from source. No published installer is linked before a release exists.",
  ],
};

export function contentMarkup() {
  const sample = collections[0];
  return `
<section class="chapter chapter--landing" id="overview" data-chapter="0" aria-labelledby="hero-title">
  <div class="pin"><div class="panel hero">
    <p class="eyebrow reveal-line" style="--i:0"><span class="eyebrow-dot"></span>ORION &nbsp;·&nbsp; A LOCAL MEDIA WORKSPACE</p>
    <h1 id="hero-title"><span class="h1-line">${words("Make room.", 1)}</span> <em class="h1-line">${words("For everything.", 3)}</em></h1>
    <p class="lede reveal-line" style="--i:6">Organise movies, series, anime, anime films, web series, music and books. Review every match, preview every path, keep every move recoverable. Your media stays on your PC or the NAS folders you choose.</p>
    <div class="actions reveal-line" style="--i:8">
      <a class="button primary" href="#features">Begin the descent <span aria-hidden="true">↓</span></a>
      <a class="button secondary" href="#install">Get started</a>
      <a class="button ghost" href="${REPO}" target="_blank" rel="noreferrer">Source <span aria-hidden="true">↗</span></a>
    </div>
  </div>
  <a class="scroll-cue" href="#features" aria-label="Scroll to the seven collections"><span>SCROLL</span><i aria-hidden="true"></i></a></div>
</section>

<section class="chapter chapter--collections" id="features" data-chapter="1" aria-labelledby="features-title">
  <div class="pin"><div class="split">
    <div class="panel">
      <p class="eyebrow"><span class="eyebrow-dot"></span>01 &nbsp;·&nbsp; SEVEN COLLECTIONS</p>
      <h2 id="features-title">Seven collections. <em>One sky.</em></h2>
      <p class="lede">Each collection is one of the seven brightest stars in Orion. Scroll, or choose one.</p>
      <ol class="collection-list">${collections
        .map(
          (c, i) =>
            `<li><button type="button" data-collection="${i}" aria-current="${i === 0}"><span class="num">${c.glyph}</span><span class="cname">${c.name}</span><span class="ckind">${c.kind}</span><span class="cstar">${starFor(i).name}</span></button></li>`,
        )
        .join("")}</ol>
    </div>
    <figure class="cover-stage" aria-live="polite">
      <div class="cover-frame">${collections.map((_, i) => `<div class="cover" data-cover="${i}" aria-hidden="${i !== 0}">${mediaArtwork(i)}</div>`).join("")}</div>
      <figcaption><span class="cap-star" data-cap-star>${starFor(0).name}</span><strong data-cap-title>${collections[0].title}</strong><span data-cap-detail>${collections[0].detail}</span><span class="tag">FICTIONAL SAMPLE</span></figcaption>
    </figure>
  </div></div>
</section>

<section class="chapter chapter--scan" id="scan" data-chapter="2" aria-labelledby="scan-title">
  <div class="pin"><div class="panel panel--right">
    <p class="eyebrow"><span class="eyebrow-dot"></span>02 &nbsp;·&nbsp; SCAN</p>
    <h2 id="scan-title">Point it at <em>the pile.</em></h2>
    <p class="lede">Add a source folder and a destination you control. Orion scans, offers candidates from TMDb, AniList, AniDB, MusicBrainz and Open Library, and lets you correct any match by hand.</p>
    <p class="fine">Providers are optional and configured separately. Keys are write-only and kept in your operating system's keychain.</p>
  </div></div>
</section>

<section class="chapter chapter--preview" id="preview" data-chapter="3" aria-labelledby="preview-title">
  <div class="pin"><div class="panel panel--left-bottom">
    <p class="eyebrow"><span class="eyebrow-dot"></span>03 &nbsp;·&nbsp; PREVIEW</p>
    <h2 id="preview-title">See every path <em>first.</em></h2>
    <p class="lede">Orion shows the exact destination before anything moves. Choose a versioned naming preset, decide how conflicts resolve, add NFO and artwork if you want them. Then you approve.</p>
    <div class="path-card" role="group" aria-label="Example plan using fictional files">
      <span class="tag">FICTIONAL SAMPLE</span>
      <code class="from">${sample.source}</code>
      <span class="arrow" aria-hidden="true">↓</span>
      <code class="to">${sample.destination}</code>
    </div>
  </div></div>
</section>

<section class="chapter chapter--recover" id="recovery" data-chapter="4" aria-labelledby="recovery-title">
  <div class="pin"><div class="panel panel--right">
    <p class="eyebrow"><span class="eyebrow-dot"></span>04 &nbsp;·&nbsp; RECOVERABLE</p>
    <h2 id="recovery-title">Made to <em>be undone.</em></h2>
    <p class="lede">Jobs are persistent. Cancel or retry them, inspect an interrupted operation, and preview a guarded undo before it runs.</p>
    <ul class="facts">
      <li><strong>Verified transfers</strong><span>Bytes are checked, and an existing file is never replaced.</span></li>
      <li><strong>Guarded undo</strong><span>Undo revalidates what it recorded and leaves changed files alone.</span></li>
      <li><strong>Local by design</strong><span>Your media stays on your PC or NAS. This website never touches your files.</span></li>
    </ul>
    <p class="fine"><a href="/Orion/docs/recovery.html">Recovery, undo and backups →</a></p>
  </div></div>
</section>

<section class="chapter chapter--try" id="demo" data-chapter="5" aria-labelledby="demo-title">
  <div class="stack">
    <div class="panel panel--center">
      <p class="eyebrow"><span class="eyebrow-dot"></span>05 &nbsp;·&nbsp; TRY IT</p>
      <h2 id="demo-title">Try the sample. <em>Move nothing.</em></h2>
      <p class="lede">Fictional files, simulated in your browser. It never reads your computer or the local app.</p>
    </div>
    ${showcaseMarkup()}
  </div>
</section>

<section class="chapter chapter--install" id="install" data-chapter="6" aria-labelledby="install-title">
  <div class="stack">
    <div class="panel panel--center">
      <p class="eyebrow"><span class="eyebrow-dot"></span>06 &nbsp;·&nbsp; BEGIN</p>
      <h2 id="install-title">Bring your own <em>universe.</em></h2>
    </div>
    <figure class="shots">
      <div class="shot-row">
        <img src="/Orion/images/production-plan.png" width="1440" height="1000" loading="lazy" decoding="async" alt="Orion's preview screen listing each source file beside its exact destination path." />
        <img src="/Orion/images/production-jobs.png" width="1440" height="1000" loading="lazy" decoding="async" alt="Orion's jobs screen showing persistent organisation jobs and their results." />
        <img src="/Orion/images/production-night.png" width="1440" height="1000" loading="lazy" decoding="async" alt="Orion's library workspace in the Night theme." />
      </div>
      <figcaption>The real app: preview, jobs and the Night theme. Screenshots use generated test media.</figcaption>
    </figure>
    <div class="cards">
      <article class="card">
        <h3>Run from source</h3>
        <p>Use Python 3.11 or 3.12 and Node 24. Build the interface, then start the local app.</p>
        <pre><code>npm --prefix frontend ci
npm --prefix frontend run build
python -m orion --port 0</code></pre>
        <p class="fine">Create the Python environment first. <a href="/Orion/docs/install.html">Full install guide →</a></p>
      </article>
      <article class="card">
        <h3>Windows bundle</h3>
        <p>No published installer is linked here. A verified release will carry its own Python runtime and needs no Node. Windows builds are unsigned.</p>
        <p class="fine"><a href="/Orion/docs/github-delivery.html">Packaging and release checks →</a></p>
      </article>
      <article class="card">
        <h3>Your media server</h3>
        <p>Connect Jellyfin or Emby with an explicit user to review duplicate hints and episode gaps. Plex is not implemented.</p>
        <p class="fine"><a href="/Orion/docs/integrations.html">Integrations →</a></p>
      </article>
    </div>
    <div class="actions actions--center">
      <a class="button primary" href="/Orion/docs/">Read the documentation <span aria-hidden="true">→</span></a>
      <a class="button secondary" href="${REPO}" target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a>
    </div>
  </div>
</section>`;
}
