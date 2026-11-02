# Orion public project site

The public website is a self-contained Vite build at the GitHub Pages repository prefix `/Orion/`. It is one continuous scroll-driven flight through a real star field: Orion's seven brightest stars are the seven collections, the Orion Nebula is the unsorted pile, and files are particles that settle into ordered lanes and can be rewound. The page text is complete HTML before any 3D code loads. The static site never accesses the installed app API or a visitor's files, and every simulated action remains labelled fictional.

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

Tests serve the production build at `http://127.0.0.1:4174/Orion/`. For local use with an installed compatible browser, set `PLAYWRIGHT_EXECUTABLE_PATH` to its absolute path. CI installs Playwright Chromium. Tests run the 3D scene on software WebGL, and also with WebGL removed, with reduced motion, after a lost context, and at 360, 390, 768, 1280 and 1600px. They cover every chapter, the sample actions, static docs, local search and code copying.

## Documentation

`docs/manifest.mjs` defines the public guide set and first-party evidence assets. The Vite plugin in `vite.config.js` calls `scripts/generate-docs.js` to render Markdown from `site/docs/` and authoritative repository guides. It emits all guide text as static HTML under `dist/docs/`, so direct reloads and reading without JavaScript work on GitHub Pages. Existing install, recovery and licence URLs remain available. Headings have unique anchor IDs, internal guide links stay local, and the browser search index is generated from the same content. First-party JSON evidence is copied at build time rather than linked to GitHub.

`public/docs/docs.js` enhances the guides with local search and copy-code controls, with visible failure feedback. `public/docs/search.js` and `search.css` add a shared native dialog on the showcase and all guides: header search, Ctrl/Cmd+K, keyboard navigation, safe local results, focus restoration, and a browse-all fallback when the index is unavailable. `public/docs/document.css` provides the responsive reading layout. No network Markdown renderer or runtime CDN is required. Generated `.generated/`, dependencies, browser reports and `dist/` remain ignored.

## The 3D scene

| File | Role |
|------|------|
| `src/main.js` | Builds the page, owns scroll, header, hash routes and motion state, and loads the scene after first paint |
| `src/content.js` | Chapter markup; claims come from the README and docs |
| `src/director.js` | Pure functions: scroll position to chapter, camera pose and world state. Unit-tested |
| `src/quality.js` | Pure frame-time governor with three quality tiers. Unit-tested |
| `src/stars-data.js` | Right ascension and declination of Orion's principal stars and the nebula, projected onto the sky. Unit-tested |
| `src/world/` | three.js renderer, layers (backdrop, stars, constellation lines, nebula, file particles, verification ring), render loop and context-loss handling |

Rules the scene keeps: native scrolling only (no wheel hijacking); the loop stops when the tab is hidden, the user pauses or reduced motion is set; resolution and particle counts step down automatically when frames are slow and step up only after a sustained good period; no WebGL2, a failed start or a lost context shows an SVG constellation and keeps every fact available as HTML; reduced motion renders still frames per chapter. All stars, dust and the nebula are procedural, so there are no downloaded images or textures. `three` (MIT) is bundled from npm, with its licence on the generated licences page. Local fonts and their licence texts are included. Product screenshots show the real app with generated test media; the sample and covers use fictional media.

Only `site/dist` is uploaded/deployed. The existing Pages workflow waits for the strict CI gate on main; no application backend, personal media or development files are included in the published artifact.
