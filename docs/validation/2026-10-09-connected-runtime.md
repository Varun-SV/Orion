# Production validation — 9 October 2026

The approved modernisation is implemented locally: all seven collections, explicit match review, immutable operation previews, persistent recoverable jobs, guarded undo, versioned presets, content/version comparison, opt-in stable watching/identification, CSV/JSON exports, Jellyfin/Emby evidence/refresh/episode gaps and optional journalled NFO/artwork. The standalone Windows bundle and independent public site are built and tested. Final whole-branch review, hosted exact-commit CI and required-check activation are recorded separately below as they occur.

## Observed local checks

- Full backend suite with `ORION_PACKAGE_EXE=dist/Orion/Orion.exe`: **223 passed, no skips**, 68.40 seconds. Covers migration/backup/import, concurrent confirmations, seven kinds, providers, signatures/no-overwrite/copy/interruptions/recovery/undo, persistent jobs, strict local API, two-instance session isolation, profiles, watching, reports, server HTTP pagination/errors, episode catalogue cache/date classification, sidecar preservation/retry and release/workflow policy.
- `npm --prefix frontend run check`: TypeScript, **38 component tests** and production build passed. Fonts/icons are bundled with licences.
- `node scripts/browser_qa.mjs`: **104 checks** against the production frontend and real backend in installed Edge 154.0.4258.62. This is generated-file operation evidence, without API response interception or simulated jobs. In-app automation could not start because its deny-read ACL helper failed; installed Edge automation was used instead.
- `npm --prefix site test`: **16 passed**, including `/Orion/` direct-link/reload, keyboard access, skip-link reload, all themes, seven fixture collections, no private API/outbound requests, working docs/assets and five widths. [Site report](site-validation.md).
- Official checksum-verified actionlint 1.7.12 and workflow policy passed. Failure/cancellation/skip/missing dependency tests reject the aggregate; nested read-only permission ceilings and required job equality are enforced.
- Windows executable smoke passed with an **empty system PATH**, no Qt resources, **52 static resources**, an isolated database, instance reuse, occupied-port rejection and graceful shutdown. Measured startup **2.099 seconds**, unpacked **57,046,286 bytes**; verified ZIP **30,204,679 bytes**. [Package result](package-smoke.json), [delivery evidence](delivery-validation.json).

The browser run created 64 generated media/subtitle fixtures totalling 256 MiB. It scanned and confirmed a movie folder, explicitly saved the optional NFO preference, previewed **65 operations**, revalidated and approved organisation, reloaded a running persistent job, verified every moved byte's SHA-256 and generated XML, then approved guarded undo and verified every original byte restored and generated output removed. Successful fixtures are removed after resolved-path boundary checks; failures remain isolated for diagnosis.

All **18 routes** passed overflow checks at 1440, 1024, 768, 390 and 320px. Review dialogs fit and final actions remain reachable. Escape restores focus, reduced motion removes transitions, persisted themes apply and no uncaught JavaScript exceptions occurred.

## Screenshots

Pictured files are generated fixtures. Empty collections show actual counts; artwork-free records use their file-kind icon. Production contains no sample posters, invented confidence percentages or simulated success badges.

- [Ivory](screenshots/production-ivory.png), [Clay](screenshots/production-clay.png), [Night](screenshots/production-night.png), [mobile](screenshots/production-mobile.png).
- [Match review](screenshots/production-review.png), [mobile review](screenshots/production-review-mobile.png), [exact preview](screenshots/production-plan.png), [job outcome](screenshots/production-jobs.png), [preset controls](screenshots/production-presets.png).
- [Browser result](screenshots/browser-results.json), [site overview](screenshots/site-overview-1280.png), [labelled demo](screenshots/site-demo-390.png).

The accepted local prototype remains in `design-preview/`. Production follows its typography, warm surfaces, teal/clay accents and restrained motion; the public demo is separately and persistently labelled.

## Limits and delivery state

Generated video/subtitle fixtures are byte-preservation test data, not playable media. Browser transfers are same-volume on this PC; cross-volume/cancellation/interruptions are covered by injected filesystem tests. Provider/server behavior uses local HTTP/response fixtures. Live authenticated providers and personal Jellyfin/Emby servers have not been verified. Native macOS/Linux installers and runtime memory/CPU comparisons have not been measured; Windows builds are unsigned.

PR #3 must pass hosted CI at its final SHA before required `CI` protection is activated using the observed Actions app ID. Pages is configured for workflow publishing; its first live deployment awaits the user's merge to main. No tag/release or merge is created solely for validation.