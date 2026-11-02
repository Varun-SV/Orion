# Orion: the constellation (3D scroll site)

The user asked for an exceptional, 3D, scroll-driven landing experience, built to the same standard as the EviCortex site, "without hiccups". Decisions made with the user on 2026-11-02: **rebuild the whole public site** (not only the hero), use **EviCortex as the quality reference** (pacing and polish, not its layout or code), and take an **Orion-constellation visual theme**. The previous midnight/teal canvas site is replaced.

## Concept

One continuous camera flight through a real star field. The page is a single 3D world; scrolling moves the camera along a fixed path and the HTML chapters ride on top of it.

- **The seven principal stars of Orion are the seven collections.** Betelgeuse, Bellatrix, Mintaka, Alnilam, Alnitak, Saiph and Rigel map to Movies, Series, Anime, Anime films, Web series, Music and Books. Star positions come from real right ascension and declination, projected onto the sky, so the shape is correct.
- **The Orion Nebula (M42) is the file pile.** It is a procedural volumetric-looking cloud: the "everything unsorted" state that Orion organises.
- **Files are particles.** They start as drifting dust, then align into ordered lanes (the preview), and can be wound back (guarded undo).

## Chapters (scroll order)

| # | Chapter | 3D state | Truthful content source |
|---|---------|----------|-------------------------|
| 0 | Landing | A single star ignites; the real constellation draws itself line by line; nebula blooms; headline "Make room. For everything." resolves | README tagline |
| 1 | Seven collections | Camera glides along the belt; each star brightens in turn and shows its original fictional cover | README "What you can do" |
| 2 | Scan | Camera dives into M42; unsorted file particles swirl | README bullet 1 |
| 3 | Preview, then approve | Particles settle into ordered lanes; exact source → destination path is shown | README bullet 2; fixture paths from `collections.js` |
| 4 | Recoverable | Lanes rewind to the origin; byte-verification ring; "never replaces existing files" | README bullet 3 |
| 5 | Try it | The existing labelled **fixture sample** (preview / simulate / reset), restyled | existing `showcase.js` behaviour |
| 6 | Connect and install | Camera pulls back to the whole constellation; Jellyfin/Emby, providers, source install, docs link | README, docs |

Claims stay limited to what the README and docs state: Windows builds are unsigned, no installer is linked before a release exists, Plex is not implemented, no performance superiority is claimed, and all demo data is labelled fictional.

## Assets (all free, nothing fetched at runtime)

- **three** (MIT) bundled through npm and tree-shaken; no CDN. Chosen directly instead of a scroll library: the site needs only a deterministic `progress → camera` function, which is easier to unit-test and removes scroll-hijacking.
- **Fonts**: the already bundled Newsreader and IBM Plex Sans (SIL OFL), licences retained.
- **Everything else is procedural**: stars, nebula, dust and glow are shaders; covers reuse the project's own original SVG art. No image downloads, so there is no third-party licence to attribute and the page weight stays small.
- Star coordinates are astronomical facts (public data); they are cited in `docs/validation` with the source used to check them.

## Rules that prevent hiccups

1. **Content first.** The HTML (headline, nav, text) is complete and readable before any 3D code loads. The 3D chunk is a separate dynamic import started after first paint. LCP is text, never the canvas.
2. **Native scrolling only.** No wheel hijacking, no smooth-scroll library (natural scrolling was an explicit earlier requirement). Camera follows `scrollY` through a damped follower so jumpy wheels still look smooth.
3. **Adaptive quality.** A frame-time governor measures real frames and steps resolution scale (1 → 0.75 → 0.5) and particle count down, and only steps up again after a sustained good period. Mobile and `Save-Data` start on the lite tier.
4. **Pause everything unseen.** The loop stops when the canvas is offscreen, the tab is hidden, the user pauses, or reduced motion is set. Reduced motion renders one still frame per chapter.
5. **Never a blank page.** No WebGL2, shader failure or context loss swaps in the SVG constellation fallback; a restored context rebuilds the scene.
6. **Budgets.** Initial JS (HTML, CSS, entry) small; 3D chunk ≤ 250 KB gzip; ≤ 15 draw calls; ≤ 12 000 particles desktop, ≤ 4 000 on the lite tier; no per-frame allocation in the render loop.
7. **Accessibility.** Canvas is `aria-hidden`; every fact is in real HTML; focus order follows reading order; visible focus; skip link; pause control; contrast checked against the dark scene with text on a scrim.

## Compatibility kept

Base URL `/Orion/`; hash routes `#overview #features #install #recovery #demo`; static documentation under `/Orion/docs/` with local search and copy-code; GitHub Pages workflow; CI job names. Documentation pages get the same header, footer and night-sky styling so the site feels like one product. Ivory/Clay themes remain for the reading experience in docs; the landing is always night.

## Acceptance

- Production build passes the unit tests, Playwright suite at 360/390/768/1280/1600px with WebGL on, WebGL off, and reduced motion.
- No console errors or page errors on any route.
- Scrolling the whole page at a steady rate keeps the governor above its lowest tier on the reference runner; a software-GL run reports frame statistics as evidence, not as a speed claim.
- Rendered screenshots of every chapter are inspected by eye at desktop and phone width.
- All repository CI jobs pass; Codex review has no open findings before merge.
