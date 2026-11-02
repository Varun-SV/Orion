# Orion constellation site: implementation plan

Design: [`../specs/2026-11-02-orion-constellation-design.md`](../specs/2026-11-02-orion-constellation-design.md).

## Module map (`site/src/`)

| File | Responsibility |
|------|----------------|
| `main.js` | Boot: render content, header/nav/menu, hash routes, motion state, lazy-load 3D after first paint |
| `content.js` | Chapter markup built from `collections.js` and README-truthful copy |
| `director.js` | **Pure** functions: scroll progress → chapter index, local progress, camera pose, uniforms. No DOM, no three. Unit-tested |
| `quality.js` | **Pure** frame-time governor: tiers, step-down/step-up rules, initial tier from device hints. Unit-tested |
| `stars-data.js` | Orion star table (RA, Dec, magnitude, collection index) and projection helper. Unit-tested |
| `world/index.js` | Renderer, loop, resize, visibility/offscreen pause, context loss/restore, applies director output |
| `world/starfield.js`, `nebula.js`, `constellation.js`, `files.js` | Points/shader layers. Shared buffers, no allocation per frame |
| `fallback.js` | SVG constellation + still-poster mode |
| `showcase.js`, `collections.js`, `media-art.js` | Kept (fixture sample and covers), restyled |
| `style.css`, `chapters.css` | Night-sky design tokens and layout |

`site/docs`, the docs generator, search and Pages workflow are kept; `document.css` is restyled to match.

## Steps

1. **Foundations** (pure, tested first): `director.js`, `quality.js`, `stars-data.js` with `node --test` unit tests written before the code that uses them.
2. **Static page**: `index.html` + `content.js` + CSS. It must look finished with 3D disabled (this is the fallback, and what visitors see first).
3. **World**: renderer, starfield, constellation draw-in, nebula, files; wire scroll through the director; add governor, pause rules, context-loss handling.
4. **Interaction**: hover/focus on a star highlights its collection and cover; "Explore" and nav scroll naturally; sample section reused.
5. **Docs restyle**: shared header/footer and tokens on generated docs; existing docs/search tests keep passing.
6. **Tests**: replace the old DOM-specific specs with chapter, fallback, reduced-motion, overflow, console-error and interaction specs; keep search/docs/evidence coverage.
7. **Visual QA**: screenshot each chapter at 1440 and 390px; look at them; fix; repeat.
8. **Validation doc**: `docs/validation/2026-11-02-constellation.md` with real numbers; update `site/README.md`.
9. **PR and review loop**: push branch, open PR, wait for Codex (arrives 15 to 40 minutes after each push), fix every finding in a new commit, resolve threads, repeat until Codex gives a 👍 and the CI gate is green.
10. **Merge** with the repository's normal merge commit once approved, then confirm the Pages deployment.

## Test matrix

| Layer | Cases |
|-------|-------|
| Unit | director monotonic and continuous across chapter edges; clamps at 0 and 1; quality tiers step down fast and up slowly and never oscillate; star table has 7 mapped stars and valid projections |
| E2E, WebGL on | scene reaches `data-scene="webgl"`; no console/page errors; each chapter becomes active when scrolled to; seven stars map to seven collections; sample preview/simulate/reset; hash routes; nav menu on phone; no horizontal overflow at 360/390/768/1280/1600 |
| E2E, WebGL off | SVG fallback visible, all text and links present, sample works |
| E2E, reduced motion | no running loop, still frames only, pause control state correct |
| E2E, context loss | `WEBGL_lose_context` then restore recovers without errors |
| Evidence | per-chapter screenshots and software-GL frame-time stats saved as artifacts |

## Risks and answers

| Risk | Answer |
|------|--------|
| Heavy GPU load on phones | Lite tier by default on touch devices, adaptive resolution, particle cap, pause offscreen |
| Scroll jank from layout work | Camera and shaders only read `scrollY` in one passive listener; chapter text uses transform/opacity only |
| Fallback never tested | Dedicated WebGL-off project in the suite |
| Existing links break | Hash routes and docs paths kept and tested |
| Review loop is slow | Keep PR focused; run full local suite before each push so CI failures do not cost a review cycle |
