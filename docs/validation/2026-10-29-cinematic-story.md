# Cinematic Orion website validation

The user's EviCortex site informed a second design pass: expressive mixed typography, floating navigation, a locally rendered orbital field, and an explanatory scroll story. Orion retains its midnight/teal direction, natural scrolling, interactive sample, seven collections, three themes, and twelve on-site guides.

## Local verification

- Production site browser suite: **41 passed** in 21.3 seconds.
- Documentation generator tests: **6 passed**, enforced by `prebuild` during the browser run.
- Repository workflow and release-policy tests: **32 passed**.
- Production Vite build, JavaScript syntax checks, Prettier, and `git diff --check`: passed.
- Responsive checks cover 360, 390, 768, 1280, and 1600px, every showcase route, and static documentation.

The new checks verify orbital rendering, a stable paused canvas, theme refresh while paused, usable SVG fallback when Canvas is unavailable, keyboard chapter controls, natural-scroll chapter changes, chapter selection and focus, reduced motion, command-search shortcuts, local result navigation, focus restoration, empty results, and failed-index recovery. Existing tests continue to verify every sample collection, search, preview/simulation/reset, navigation/reloads, images, local-only network requests, docs without JavaScript, guide links/anchors, code copying, and theme persistence.

Run with Node 24 and a compatible Chromium:

```sh
PLAYWRIGHT_EXECUTABLE_PATH=/absolute/path/to/chromium npm --prefix site test
.venv/bin/python -m pytest -q tests/test_workflow_policy.py tests/test_release_policy.py
```

CI uses its pinned Playwright browser rather than the local browser override.

## Independent review

A separate Luna reviewer inspected the new scene, story, search, shared presentation changes, and route integration. It identified a chapter-selection mismatch: selecting a new illustration left the previous chapter's text in view. A regression test reproduced the problem, the handler now brings the selected chapter into view while keeping focus, and subsequent scrolling still changes stages. The reviewer rechecked the fix and returned **ready to merge** with no remaining concrete findings.

## Deployment gate

All required hosted checks must pass before the protected-main merge. The existing main workflow then builds and deploys the Pages artifact. The final public homepage, organising sample, chapter selection, search, and local docs are verified against that deployed result before handoff.

No application/backend, personal media, live-provider credentials, release/tag, or repository-protection changes are included.
