# Connected runtime validation — 9 October 2026

The approved interface is connected to the local FastAPI engine. These results cover the engine and connected UI milestones; profiles, watching, server integrations, sidecars, packaging and GitHub delivery are still being implemented in the following approved plans.

## Commands and observed results

- `.venv\Scripts\python -m pytest -q`: 115 passed. Includes SQLite upgrade/backup/import, seven media collections, unavailable sources, provider response/error/rate fixtures, immutable plans, no-overwrite transfers, copy verification/cancellation, crash checkpoints, guarded undo, durable jobs, API origin/session validation and an isolated native launcher start/stop.
- `npm --prefix frontend run check`: TypeScript passed, 27 component tests passed, production build passed. All fonts and Feather SVG icons are bundled locally with licences.
- `node scripts/browser_qa.mjs`: 88 checks passed in installed Edge 154.0.4258.62. Production UI and backend, with no simulated jobs or browser API response interception. The in-app automation helper failed before startup with `apply deny-read ACLs`; Playwright used installed Edge instead.

The browser run created one source/destination and 64 generated fixtures totalling 256 MiB. It scanned, manually confirmed a movie folder, previewed 64 actual paths, revalidated and explicitly organised. It reloaded while the stored job was **running**, observed its completed result, verified every destination SHA-256 and absent source, then previewed/approved undo and verified every original byte restored. Successful fixture runs are removed only after a resolved-path boundary check. Failed runs remain isolated for diagnosis.

All 15 current routes passed no-horizontal-overflow checks at 1440, 1024, 768, 390 and 320px. Review dialogs fit each width and their final actions remain reachable. Escape restores focus, reduced-motion removes transitions, three persisted themes apply, and no uncaught JavaScript exceptions occurred.

## Production screenshots

The pictured media and paths are generated test fixtures, not personal media. Empty collections show genuine counts; artwork-free items use their file-kind icon. No sample posters or illustrative confidence percentages are injected into the installed runtime.

- [Ivory overview](screenshots/production-ivory.png)
- [Clay overview](screenshots/production-clay.png)
- [Night overview](screenshots/production-night.png)
- [Mobile overview](screenshots/production-mobile.png)
- [Match review](screenshots/production-review.png)
- [Mobile review](screenshots/production-review-mobile.png)
- [Immutable path preview](screenshots/production-plan.png)
- [Persisted job result](screenshots/production-jobs.png)
- [Machine-readable browser results](screenshots/browser-results.json)

The accepted prototype remains in `design-preview/` locally. Production uses the same Newsreader/IBM Plex typography, warm surfaces, restrained teal/clay accents, thin rules and native-theme panels. The browser comparison led to compact mobile collection summaries and relevant manual naming fields. Sources are formatted for review rather than shipped as compressed one-line components.

## Verification limits

Generated video/subtitle fixtures test discovery, path planning, byte preservation and recovery; they are not playable media. This browser run uses explicit manual confirmation and same-volume transfers on this PC. Cross-volume transfers, candidate alternatives, provider failures and crash interruption are covered by injected filesystem/HTTP fixtures in the backend and component suites. Live authenticated providers and Jellyfin/Emby servers have not been tested. Windows standalone packaging, other platforms, GitHub CI and live Pages deployment are not yet verified at this milestone. No runtime-memory or CPU superiority is claimed.
