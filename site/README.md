# Orion public project site

The observatory website is a self-contained Vite build at the GitHub Pages repository prefix `/Orion/`. Its midnight/teal visual system opens with a luminous Canvas constellation and original illustrated media covers, followed immediately by an interactive sample organiser, a four-chapter scroll story, native page transitions, bounded parallax and reveals. The static site never accesses the installed app API or a visitor's files. Every simulated action remains labelled.

## Develop and verify

Use Node 24:

```sh
npm --prefix site ci
npm --prefix site run test:unit
npm --prefix site run build
npm --prefix site exec -- playwright install --with-deps chromium
npm --prefix site test
npm --prefix site run dev
```

Tests serve the production build at `http://127.0.0.1:4174/Orion/`. For local use with an installed compatible browser, set `PLAYWRIGHT_EXECUTABLE_PATH` to its absolute path. CI installs Playwright Chromium. Responsive checks cover 360, 390, 768, 1280 and 1600px, every public route, theme persistence, reduced motion, sample actions, static docs, local search and code copying.

## Documentation

`docs/manifest.mjs` defines the public guide set and first-party evidence assets. The Vite plugin in `vite.config.js` calls `scripts/generate-docs.js` to render Markdown from `site/docs/` and authoritative repository guides. It emits all guide text as static HTML under `dist/docs/`, so direct reloads and reading without JavaScript work on GitHub Pages. Existing install, recovery and licence URLs remain available. Headings have unique anchor IDs, internal guide links stay local, and the browser search index is generated from the same content. First-party JSON evidence is copied at build time rather than linked to GitHub.

`public/docs/docs.js` enhances the guides with local search and copy-code controls, with visible failure feedback. `public/docs/search.js` and `search.css` add a shared native dialog on the showcase and all guides: header search, Ctrl/Cmd+K, keyboard navigation, safe local results, focus restoration, and a browse-all fallback when the index is unavailable. `public/docs/document.css` provides the responsive reading layout. No network Markdown renderer or runtime CDN is required. Generated `.generated/`, dependencies, browser reports and `dist/` remain ignored.

## Motion and assets

`src/motion.js` owns page parallax, reveal/visibility observers and page transitions. `src/scene.js` renders deterministic orbital particles with Canvas 2D at a bounded frame rate; it stops offscreen or when hidden, refreshes on theme changes, and falls back to SVG when Canvas is unavailable. `src/story.js` connects natural scrolling and explicit chapter selection to the media journey, with passive listeners and route cleanup. Scrolling is never intercepted. Device reduced motion and the persistent Pause animations control disable decorative activity. `src/media-art.js` renders original SVG covers for all seven fictional collections. `src/gallery.js` lets visitors select a collection and continue into its matching fixture demo. The opening’s Explore button scrolls directly to the working sample; narrow screens use an expandable keyboard-accessible navigation menu. Visual-layout tests retain desktop, tablet and phone screenshots as QA artifacts. Night is the default; existing Ivory and Clay choices remain available. Local fonts and their full licence texts are included. Product screenshots show the real app with generated test media; the fixture showcase and story share fictional media.

Only `site/dist` is uploaded/deployed. The existing Pages workflow waits for the strict CI gate on main; no application backend, personal media or development files are included in the published artifact.
