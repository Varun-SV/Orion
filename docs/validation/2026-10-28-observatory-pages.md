# Observatory website validation

Date: 2026-10-28 (Asia/Kolkata). Base: `253912078abb1377ba5b0d41c0cb902bf20ac695`.

## Delivered experience

The user selected midnight/teal observatory styling, constellation details, natural scroll reveals/parallax and an interactive organising demonstration as the first experience. The public site now uses that direction across Overview, Features, Install, Recovery & privacy and Demo, with native page transitions, a labelled sample preview/simulate/reset workflow, seven-collection exploration, real product imagery and local documentation entry points.

The public documentation build contains 12 static guides with a shared reading layout, local full-text search, code-copy feedback, section anchors/contents and previous/next navigation. Existing install/recovery/licence URLs are preserved. Authoritative runtime/integration/delivery guides and both referenced first-party JSON evidence files are compiled into Pages. Guide content and evidence links do not redirect readers to GitHub Markdown; explicitly labelled repository links and external service references remain external.

The docs and showcase share persistent theme and motion preferences. Night is the default; Ivory and Clay remain available. Reduced motion disables decorative activity and parallax. A mobile native guide menu keeps the reading content near the top of the page, and the copy action reports unavailable clipboard access explicitly. Reading and guide navigation work without JavaScript because the text is present in built HTML.

## Local evidence

| Verification | Result |
| --- | --- |
| Clean locked site dependency install | Passed |
| Documentation generator tests | **6 passed**; also required by the build's prebuild hook |
| Complete production-site browser suite | **30 passed**, 19.9 seconds |
| Workflow and release policy regressions | **32 passed** |
| Workflow configuration validation | Passed |
| Production Vite build | Passed; static guide HTML, search index and evidence assets emitted |
| Prettier and `git diff --check` | Passed |

Browser coverage includes every public route at 360, 390, 768, 1280 and 1600px; documentation reading at those widths; the homepage and seven-collection sample workflows; keyboard reset focus; route reloads; theme/motion persistence; reduced motion; clipboard success/failure; search including no matches; all 12 guides with JavaScript disabled; and every first-party guide link and section anchor. Tests reject missing assets, private API calls, unexpected external requests and page errors.

Local visual inspection included desktop and phone homepages, the full homepage, the documentation reading layout and documentation search. The local browser was compatible Chromium 153 obtained as temporary test tooling outside the repository after the ordinary browser CDN download was unavailable. Production dependencies do not include that browser. Hosted CI uses the repository's pinned Playwright Chromium installation.

## Corrections verified during integration

- The new homepage and persistent motion-control tests failed against the previous site before implementation.
- Plain-text licence output originally lacked a heading; the heading and both font licence texts are now included, with a failing-then-passing generator regression.
- The Markdown compiler required an explicit unique heading renderer for functional contents/fragment links; generator and browser regressions verify the actual targets.
- Native view-transition cancellation rejects `ready`; that rejection is handled alongside `finished`, and repeated navigation produces no page errors.
- The image checks wait for actual decoding because a route heading can render before the image; missing assets still fail.
- Mobile documentation controls and collapsed guide navigation were reproduced before implementation and now pass keyboard and persistence checks.
- Independent review found stale removed guides/evidence could survive a local rebuild. A new regression failed before the generated directory lifecycle was corrected, then passed.
- A longer hashed installation command exposed grid min-content overflow at 360px. The prose/grid items now constrain their width and scroll the code block instead; the full responsive suite passes.

Two focused Luna implementation tasks produced guide content and the documentation engine; two independent Luna reviews covered documentation and showcase behavior. The coordinator integrated the design and verified the complete production build. The review's proposed reset-focus issue was checked against the current handler and withdrawn; the browser test verifies the actual keyboard focus behavior. No confirmed scoped findings remain deferred.

## Delivery requirements and limits

The new branch must pass the existing strict aggregate CI before merge, including the Ubuntu/Windows Python 3.11/3.12 backend matrix, installed-app frontend, real-backend browser checks, standalone Windows package smoke/archive verification and the new public-site tests. Exact published commit/run results belong to the PR's checks. The main-only workflow must deploy Pages after its own gate; the final handoff should verify the public homepage and docs URLs.

This change affects the public static website, guides and their build/tests. It does not change installed-app behavior or publish a release. No published releases were returned by the repository release API during validation, so the site continues to describe source installation and verified Windows-bundle guidance without inventing a download. The fixture demo never accesses personal media or the local API.
