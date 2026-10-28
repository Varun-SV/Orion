# Orion cinematic story implementation plan

> **For agentic workers:** Use focused Luna agents for independent components; the coordinator integrates and verifies the complete site.

**Goal:** Match the ambition of the supplied EviCortex reference with an original animated Orion product story.

**Architecture:** Extend the existing static Vite site with isolated scene, story, and search components. Reuse current docs, collection fixtures, route rendering, and motion settings.

**Tech stack:** Vanilla JavaScript, CSS, Canvas 2D, static generated Markdown documentation, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-29-cinematic-story-design.md`

## Constraints

No new runtime dependencies or external asset requests. Preserve `/Orion/`, all current routes and guides, fixture disclosures, three themes, and stored/OS motion preferences. No scroll hijacking.

## Review focus

Keyboard focus after dialog dismissal and story selection; stale asynchronous search; canvas unavailable or motion paused; route cleanup and repeated navigation; narrow screens and long file paths.

## Tasks

- [x] Add the shared local search dialog with failing interaction checks, safe results, failure feedback, keyboard shortcut, and focus restoration (Luna).
- [x] Add the four-stage natural-scroll media story with failing interaction checks, selectable stages, cleanup, and reduced-motion fallback (Luna).
- [x] Integrate a cinematic hero and original orbital canvas scene, with static fallback and visibility/motion lifecycle (coordinator).
- [x] Integrate components into route cleanup, refine shared typography/navigation/secondary pages, and retain all existing working examples (coordinator).
- [x] Run all site tests, generator tests, responsive layout checks, repository policy checks, and independent focused review. Correct observed failures.
- [ ] Publish a verified tree to a branch, open a PR, wait for required CI, merge, and verify Pages deployment and live interactions.
