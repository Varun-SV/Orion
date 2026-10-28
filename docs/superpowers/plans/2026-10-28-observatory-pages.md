# Orion Observatory Pages Implementation Plan

> **For agentic workers:** Use focused parallel tasks and regression-first behavioral checks. The user has selected the design direction and requested Luna agents for smaller tasks.

**Goal:** Deliver the animated observatory site and complete on-site documentation to Orion GitHub Pages.
**Architecture:** Preserve Vite static delivery and existing fixture behavior; split documentation generation, guide content and the presentation/motion implementation into separate modules.
**Tech Stack:** Node 24, Vite, vanilla ES modules, native SVG/CSS animation, build-time Markdown and Playwright.
**Spec:** `docs/superpowers/specs/2026-10-28-observatory-pages-design.md`.

## Global constraints

- Preserve `/Orion/` prefix and static hosting; no app API or personal-file access.
- Guides remain on site, including existing install/recovery/licences links.
- Default night theme, retained ivory/clay preferences, keyboard and reduced-motion support.
- Use existing accurate product capabilities and labelled fictional sample data; no invented users, performance or release claims.
- Keep implementation isolated from the installed app and respect branch protections.

## Review focus

- Direct docs reloads and links must work on Pages, without a development-server fallback.
- Search and guide text must be complete and safe even for punctuation and external source links.
- Repeated navigation and sample interactions must not leave stale animation state or duplicate listeners.
- Mobile menus, search, code blocks and media paths must remain usable at 360px.
- Pausing motion or changing OS motion preference must stop decorative animation without hiding content.

### Task 1: Documentation generation and navigation

**Owner:** Focused Luna implementer. **Files:** `site/scripts/*`, `site/vite.config.js`, `site/package.json`, `site/package-lock.json`, `site/public/docs/*`, `site/docs/manifest.mjs`, and focused generator tests.
**Produces:** Built `/Orion/docs/index.html` plus `.html` guides, `search-index.json`, local styles/runtime; docs index supports `?q=`.

- [x] Add failing build/link/search generation checks.
- [x] Generate static HTML from the guide manifest; implement responsive dark docs, sidebar, ToC, local search, code-copy and previous/next links.
- [x] Verify build output, source-link rewriting, static deep routes, accessible script enhancement and preserved legacy guide URLs.

### Task 2: Guide content

**Owner:** Focused Luna writer. **Files:** New `site/docs/{index,install,workflow,collections,naming,providers,recovery,troubleshooting}.md` only.
**Produces:** Accurate user-facing guides; engine also imports `docs/{runtime,integrations,github-delivery}.md` and repository licence text.

- [x] Ground commands, consent, lifecycle and recovery guidance in current code and existing docs.
- [x] Use local `.html` guide links, practical examples and no secret/sample-key leakage.
- [x] Review links and command syntax.

### Task 3: Observatory presentation and motion

**Owner:** Coordinator. **Files:** `site/index.html`, `site/src/*`, public screenshot assets and site README.
**Consumes:** Task 1 docs URLs. **Produces:** Interactive homepage, redesigned existing routes, persistent motion/theme controls and responsive visual system.

- [x] Add meaningful failing behavioral checks for the new hero/demo and motion control.
- [x] Build semantic presentation, interactive fixture showcase, constellation SVG and careful motion lifecycle.
- [x] Preserve existing seven-collection demo, routes and accessible interaction behavior.
- [x] Inspect screenshots and refine desktop/mobile typography, spacing, contrast and motion.

### Task 4: Verification and delivery

- [x] Run documentation/unit checks, production build and complete site browser suite with responsive visual QA.
- [x] Review the integrated patch independently and fix confirmed issues with regressions.
- [x] Verify unchanged application scope and local workflow/release checks; record evidence and limits. Hosted CI validates the full application matrix.
- [ ] Publish to a new PR, wait for required hosted checks, then merge within the user's ongoing delivery request and verify Pages serves the new design and docs.
