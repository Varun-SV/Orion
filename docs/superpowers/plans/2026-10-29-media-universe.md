# Media Universe Implementation Plan

> **For agentic workers:** Implement the bounded tasks below, preserving the shared contracts. Use focused Luna delegation as requested by the user.

**Goal:** Replace the panel-heavy opening with an original visual media universe and carry its scale and motion through the site.

**Architecture:** Keep existing routes, sample and documentation engine. Rewrite the presentation layer, enhance the existing canvas scene, and add an isolated collection gallery module. All assets remain local.

**Tech Stack:** Vanilla ESM, CSS, SVG, Canvas2D, Vite, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-29-media-universe-design.md`

## Global constraints

- Midnight/teal default; preserve Ivory/Clay, pause and OS reduced motion.
- Natural scrolling, `/Orion/` base URL, on-site docs, no new dependency.
- Fictional samples; no real file operations or invented release availability.

## Review focus

- Tablet scene/text overlap and 360px horizontal overflow.
- Animation freezing on pause, hidden tabs and offscreen.
- Gallery selectors mapping to the correct demo collection with keyboard support.
- Navigation cleanup leaving no duplicate animation handlers.
- Source and destination explanations remaining readable in all themes.

### Task 1: Visual opening and sample placement

Files: `site/src/main.js`, `scene.js`, `cinematic.css`, new `media-art.js`; `site/tests/observatory.spec.js` and `cinematic.spec.js`.

- [x] Update the sample-placement assertion to the explicitly requested below-hero position; verify it fails.
- [x] Build the visual-first hero, original cover artwork, richer orbital scene and Explore scroll behavior.
- [x] Verify scene painting/fallback, pause, theme repaint, sample operation and reduced motion.

### Task 2: Collection gallery

Files: new `site/src/gallery.js`, `gallery.css`, `site/tests/gallery.spec.js`.

Interface: `galleryMarkup()` returns the section, `mountGallery(root)` returns cleanup. Links use `data-demo-select` and `#demo`; the current route layer owns collection selection.

- [x] Implement seven keyboard-accessible selectors and large locally rendered art; retain existing fixture names.
- [x] Verify selection updates, correct demo destination and reduced-motion/mobile behavior.

### Task 3: Composition and delivery

Files: presentation CSS, main composition, validation record.

- [x] Refine section scale, story, product framing, navigation and secondary-page appearance.
- [x] Run full production-site browser suite, generator tests, syntax/build and diff checks.
- [x] Inspect rendered desktop/mobile views and resolve observed visual issues.
- [x] Independent review.
- [ ] Publish branch/PR, required CI, normal merge and deployment verification.
