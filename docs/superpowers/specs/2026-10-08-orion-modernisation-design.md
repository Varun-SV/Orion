# Orion modernisation design

Date: 2026-10-08
Status: Proposed for user review. No production migration has begun.

## Intent and agreed direction

Modernise Orion into a polished local media organisation app using the visual direction in `design-preview/`: warm ivory surfaces, Newsreader headings, IBM Plex text, teal accents, a restrained sidebar, media artwork and light/clay/dark appearances. Preserve the seven collections and the scan → identify → review → preview → organise workflow. The user liked the prototype and requested the feature additions discussed alongside the UI change.

The organising engine continues to operate on files accessible to the user's machine. Claude is the aesthetic reference. The user did not request cloud storage or media upload hosting.

Success means the production interface performs real operations, explains matches and planned changes, recovers from interrupted transfers, supports guarded undo, preserves existing configuration and library decisions, and remains responsive during long jobs.

## Technology choice

- Frontend: React + TypeScript, built with Vite. CSS variables and component styles preserve the prototype's design. Bundle fonts/icons locally for the installed app; respect reduced motion and keyboard navigation. Node is build/development tooling, not a production service.
- Backend: Python 3.11+, FastAPI, Pydantic request/response schemas, Uvicorn. Reuse providers and media parsers. Extract Qt-dependent worker logic into plain Python services.
- Persistence: SQLite through Python's sqlite3 module, WAL mode, short explicit transactions, a connection per worker/unit of work, versioned migrations and database backups.
- Jobs: bounded Python worker executor with persisted job and operation state. Poll versioned job endpoints initially; push streaming can be added only if polling proves insufficient. One filesystem-writing job runs at a time. Provider-specific request limits apply across jobs.
- Packaging: compile the frontend to static assets served by the backend; a local launcher starts Orion and opens the system browser. Retain the existing desktop entry point during migration. Windows standalone packaging uses PyInstaller once the production path is verified. A native webview/tray wrapper is a separate packaging decision, not a dependency of the first local browser build.
- Validation: pytest for engine/API/integration behavior, Vitest and React Testing Library for meaningful UI state transitions, plus browser interaction/layout checks with the available installed browser. Use temporary fixtures rather than personal media.

Alternative choices considered: restyling PyQt would preserve native desktop integration with less engine work but would require rebuilding the approved web interaction model in Qt. Rewriting the engine in Rust/Node introduces extensive metadata and filesystem behavior to port without a measured performance justification. React + Python gives the strongest reuse boundary here. No RAM, CPU or installer-size superiority is claimed without measurement.

Official references: https://react.dev/learn/typescript · https://vite.dev/guide/ · https://fastapi.tiangolo.com/ · https://docs.python.org/3/library/sqlite3.html

## Component boundaries

1. Frontend shell: navigation, theme, onboarding, collection search/filter/list/grid, detail dialogs and activity.
2. Library service: stable item identity, indexed source paths, metadata, candidates, decisions and incremental scan checkpoints.
3. Provider service: existing TMDb, AniList, AniDB, MusicBrainz, AcoustID, AudD and Open Library clients behind common result/error types. Preserve existing opt-in provider behavior, including AudD audio-sample transmission. No new media-upload integration is added.
4. Organisation planner: names and destination paths, sidecar association, conflicts, space/access checks and immutable plans.
5. Operation executor: filesystem changes, copy verification, checkpoints and guarded rollback.
6. Job manager: progress, cancellation, restart reconciliation, retry and concurrency limits.
7. Settings/integrations: sources, destinations, naming profiles, keychain-backed credentials, watchers, Jellyfin connection and export preferences.

Core filesystem modules and provider clients already have useful Qt-free boundaries. Music/book scan logic currently lives in QThread workers and must move into engine services. Naming rules currently distributed through UI handlers must also become engine functions so preview and execution share one implementation.

## Data and compatibility

Keep the existing data directory convention and import sources, categories, destinations, preferences, provider credentials and match choices. Open existing databases only through a versioned upgrade path. Create a consistent SQLite backup before the first schema upgrade; failed upgrades must preserve the old usable database and stop startup with an actionable explanation. A restored older database must run with a compatible app version.

Add stable library-item IDs and source-scoped path records. Normalise paths according to the host filesystem; preserve display paths. Track size, high-resolution modification time and available filesystem identifiers. Directory scan checkpoints include relevant child file signatures. Content hashes are computed on demand for comparison or transfer verification rather than for every scan.

Saved title decisions attach to item IDs/provider IDs, not names alone. Import legacy name-based decisions only when their association is unambiguous; otherwise put them into review. Do not silently apply one name-based decision to multiple different sources.

Persist jobs, plan revisions, operation records and stage/checkpoint data. Keep timestamps, original/final paths, expected source identity, verification results and error categories. Secret values never enter the operation log or frontend library payloads.

## Scan and identification

Maintain category/panel isolation, fast/deep scan choices, optional providers, manual metadata editing, episode patterns, music/book layouts and quality-tag selection. Incremental scans process new/changed files and retain confirmed choices on unchanged items. Do not interpret an unavailable source drive as deletion of all its indexed items. A confirmed missing file is represented as unavailable rather than silently erased.

Review shows original path/name, parsed title/year/season/episode, provider and candidate identifiers, competing matches and reasons supporting or contradicting a suggestion. Any confidence score must come from defined evidence or the provider; do not reuse the prototype's illustrative percentages. One search result alone is not evidence of a correct match. Uncertain matches remain pending; batch approval exposes its criteria and excludes ambiguous items.

Cancellation is checked during directory walking and between lookups. In-flight external requests have bounded timeouts; UI explains when stopping awaits the current request. Provider failure has a distinct state from no match, with retry for transient failures and configuration guidance for unavailable credentials.

## Preflight and immutable plans

A plan is generated only from selected confirmed items and includes every rename/move, affected sidecar, expected source signature, destination and conflict result. Display before/after paths and same-volume rename versus cross-volume transfer.

Preflight checks missing/unavailable paths, source/destination overlap, symlink handling, traversal outside selected roots, duplicate destination names (including host case rules), destination access, free space per destination volume and files currently being changed. Files outside configured roots are rejected. Skip symlinks by default and explain skipped entries; do not recursively follow them.

Use an explicit conflict resolution flow: skip, choose another name/location or retain separate versions. The initial implementation does not overwrite an existing destination. Space validation accounts for temporary copy requirements and avoids treating a rename as an entire additional copy.

Execution takes a server-stored plan revision and rechecks source signatures, destination conflicts and relevant availability before changing files. Changed conditions invalidate affected operations and require renewed review. Read-only preview never performs metadata writes, renames or moves.

## File operations and cross-drive transfers

For same-volume moves, persist intent, perform the move/rename, then persist the observed result. Filesystem actions and SQLite commits cannot be one atomic transaction; startup reconciliation must recognise a move that succeeded before its completion record was written.

For cross-volume files, write a uniquely named temporary file beside the target, record progress, stream copy with cancellation checkpoints, flush and verify byte count and SHA-256 against the source, preserve supported file metadata, then finalise within the destination volume without overwriting another file. Remove the source only after destination verification and finalisation. Recheck source stability during copying. Any source change or verification mismatch preserves the source and marks the operation failed.

Directory moves consist of a manifest and per-file operations, including subtitles and existing sidecars. Delete original directories only when planned children have transferred successfully and the directory is empty. A partially completed batch shows completed, failed and pending members separately.

Cancellation retains source files and records owned temporary copies for safe cleanup/retry. Retry skips verified completed operations. After restart, incomplete copies are reconciled and verified temporary/final states are reused where safe; uncertain state requires review rather than destructive guessing. Byte-level copy resumption is not required initially; interrupted individual files may restart while completed files remain complete.

## Undo and recovery

Expose batch details and an Undo preview. Build reverse operations from recorded paths, identities and verified content. Undo checks that current files still correspond to the organised result and original paths are free. Never overwrite unrelated or externally modified files. Conflicted members can be skipped individually, with a clear partial result.

Same-volume undo uses a guarded reverse rename. Cross-volume undo uses the same verified transfer pipeline. Undo is a new persisted job with its own progress and recovery state, linked to the original batch. It is not presented as a guarantee that arbitrary later user edits can be reversed.

On startup, classify formerly running jobs as interrupted, reconcile pending operations and present Recover/Retry options. The Job centre survives browser reload and closing/reopening the UI while the backend runs. Backend shutdown requests cooperative cancellation and durable checkpoints; abrupt termination is handled on next startup.

## User experience

Implement real Overview, all seven collections, Match review, Sources & destinations, Job centre, Activity and Settings. Add first-run setup for sources, categories, destinations and optional credentials. Validate configuration before enabling a real organisation action.

Overview reports actual counts and storage data. Collections have search, status/category filters, grid/list layouts and persistent decisions. Keep media titles clear, distinguish no results from no content, and show helpful offline/error states. The detail/review screen supports competing candidates, manual correction and associated files.

Organise opens a real preview containing conflicts and transfer implications. It launches a job only for an explicitly confirmed plan. Jobs show phases, items/bytes, useful estimates where available, failures and actionable retry/cancel controls. Announce meaningful state changes accessibly rather than every progress tick. All routes and primary actions remain accessible at narrow widths.

## Additional requested capabilities

These remain in the authorised scope and follow the core engine/UI migration:

- Naming presets: versioned per-category templates for movies, episodes, music and books. Preview examples and reject invalid placeholders/paths. Use the same renderer in preview and execution.
- Duplicate/version comparison: distinguish exact-content duplicates from different encodings, cuts and editions. Compute exact hashes on demand; compare title/provider ID, file size and available media tags. Offer keep-both or user-selected organisation; do not automatically delete copies.
- Folder watching: opt-in per source, using a watcher or bounded periodic scan with a file-stability/debounce interval. Discover completed arrivals and queue identification. Network-drive failures must back off. Watching does not auto-organise uncertain or unreviewed files.
- Jellyfin refresh: optional configured server connection, credentials in the keychain, an explicit connection check and refresh after a successful selected batch. Integration failure does not undo successful local operations; provide independent retry.
- Reports: export job plans/results to CSV and JSON with original/final paths, decisions and outcome. Exclude credentials. Export only when requested in the UI.

## Local runtime and credentials

Serve UI and API from the same loopback origin. Node/Vite is required during development only. The production launcher owns one backend instance, communicates an existing-instance URL when appropriate, and clearly reports port/startup problems. Closing the browser leaves backend work running; the launcher provides a stop command.

Use origin/host validation and a local session mechanism for state-changing endpoints; do not treat loopback binding alone as authorisation for arbitrary webpages to initiate moves. Do not enable broad CORS or LAN listening by default. Remote/multiuser hosting is outside this design.

Preserve OS keychain service names so existing keys are available. Return configured/not-configured states, never saved secret values. If secure persistence is unavailable, offer explicitly described session-only keys. User-configured paths are validated by the backend; the browser does not gain unrestricted filesystem access.

## Delivery stages and acceptance

1. Engine and data foundations: migrations/backups, source-scoped decisions, extracted media services, durable jobs, immutable plans and tested transfer/undo/recovery behavior.
2. Connected interface: React UI matching the prototype, onboarding, live collections and provider review, real previews/organisation, job centre, settings and activity.
3. Productivity/integration features: presets, incremental scans, duplicate/version comparison, watchers, Jellyfin refresh and reports.
4. Release: end-to-end verification, accessibility/layout review, standalone Windows packaging, documented installation/data migration and a recoverable release path. Maintain cross-platform source support; verify packaging on each supported OS before promising native installers there.

All stages are required to fulfil the requested scope. Deliver the first connected app for review without pretending later capabilities are complete. Execution tasks, ordering and validation commands belong in the implementation plan after written-spec approval.

Acceptance fixtures cover: safe dry run, no-overwrite conflicts, partial directory batches, cross-volume verification/cancellation, crashes at each journal boundary, source disappearance, externally changed files during undo, identical names across sources, ambiguous legacy choices, unchanged incremental scans, provider errors/rate limits, subtitle/sidecar preservation and database upgrade failure. User-flow checks cover all collections, confirmation alternatives, manual edits, real job progress, reopen/reload, conflict resolution, settings, presets, exports and optional integrations. Finish with a production build and screenshots at desktop/narrow widths. Use generated temporary media fixtures; real personal-media mutation is outside automated verification.

## Consolidated pull-request goals

The user requested closure of every currently open PR after capturing its intended goals, and replacement by one spec-first modernisation PR. Source PR branches are retained; their code is reference material to adapt and verify, not evidence that these capabilities already exist on main.

### PR #1 — Add Jellyfin/Emby server integration and NFO + artwork sidecars

Source: https://github.com/Varun-SV/Orion/pull/1
Head: 88f06377a380ecf91e3b1ae2caff1583a54fdcf9 (`claude/application-uniqueness-review-eau5e0`).

Carry forward these requirements in addition to the original spec:

- Support both Jellyfin and Emby through an explicit server type/URL/key configuration; retain credentials in the OS keychain. Connection tests show the actual server name/version or a specific error. Select a configured server user when required rather than silently taking the first account.
- During review, search the configured server library and show potential existing titles, provider IDs where available, and resolution/edition evidence. Treat lookup failure as unavailable, not as proof that no duplicate exists. Pagination must avoid truncating server-library discovery.
- Optional auto-refresh after successful video/music/book batches is an explicit persisted setting; report/retry refresh failures independently of successful file operations.
- Add an Episode gaps view comparing mapped server series/episodes with TMDb season data. Show season/episode/title/air-date; exclude unaired entries and explicitly handle specials. Missing/ambiguous provider mappings require selection. Server/catalogue failures show unavailable results rather than declaring an entire season missing.
- Opt-in NFO and artwork output, off by default and remembered per collection/profile. Preserve provider ID, title, year, plot, cover URL and MusicBrainz release ID from selection through planning and execution. Generate movie.nfo, tvshow.nfo, artist.nfo and album.nfo, plus available poster.jpg, album cover.jpg and book covers from the existing providers. XML content is escaped correctly. Never overwrite an existing user sidecar.
- Include enabled sidecar creation in the immutable plan and journal. Fetch artwork through bounded background jobs; provider failures must not destroy media or existing sidecars. Undo removes only unchanged sidecars created by the recorded batch. Music covers require a release ID; when only embedded tags exist, show the unavailable-artwork reason. Existing subtitles/NFO/artwork remain preserved during moves.
- Per-episode NFO generation is an optional profile setting using fetched episode metadata and the same no-overwrite/journal rules; rate-limit and cache episode lookups.

### PR #2 — UI: introduce Orion Navigator workspace

Source: https://github.com/Varun-SV/Orion/pull/2
Head: a3a65128da550a93ea6c9f6a5815c76b4bbfb81e (`feat/orion-navigator-ui`).

Keep the user-approved Claude/Argus-inspired prototype as the visual authority while carrying forward the workflow goals:

- Unified review queue across video, music and books; searchable across all media, with status/category filters and live counts.
- Operation Plans surface backed by the actual planner/executor, and a Libraries hub that keeps every category reachable. Preserve an Orion-specific brand identity and persistent light/dark choices, including the approved clay alternative.
- Connections surface lists every provider, including AcoustID, and distinguishes locally configured credentials from a successful live health check. Describe filesystem-only mode when no server is configured. Do not advertise Plex as implemented.
- All newly migrated screens use native light/dark design tokens; no unreadable legacy dark-panel islands. Settings changes update sidebar/overview state immediately.
- Overview metrics aggregate all media tables. Failed approved operations remain visible in the queue/job centre. Queue queries use indexed joins/batched queries rather than one synchronous SQL query per item. Global search resets hidden category filters. In-place music/book plans do not require a separate destination root.

Regression goals above were grounded in PR #2 review comments on commit e8e6109a8349f4c06a8904e67c9cf600cc8135b4. Some may have been addressed in later commits; retain them as regression tests for the new runtime.

Delivery stage 2 additionally includes Libraries, Operation Plans and Connections. Stage 3 additionally includes both-server discovery/duplicate checks, Episode gaps, optional NFO/artwork and per-episode sidecars. Acceptance adds failed-approved queue visibility, all-media metrics, global search after filtering, in-place readiness, provider-list coverage, theme legibility, paginated server results, offline episode catalogue behavior, metadata persistence and no-overwrite sidecar output/undo.

## GitHub delivery and public project site (added 2026-10-08)

CI/CD, `main` protection and GitHub Pages are required deliverables of replacement PR #3, alongside the engine, UI and integrations. GitHub configuration is applied through the repository API and its desired state/read-back evidence is documented in the PR; these settings are not changed merely by merging workflow files.

CI runs on every PR targeting main, including drafts, and pushes to main. Backend checks cover Python 3.11 and 3.12 on Ubuntu and Windows, migration/recovery/fault-injection fixtures, API behavior and offline provider/server mocks. Frontend checks cover TypeScript, component tests, production builds, and Chromium end-to-end tests against an isolated local backend. Windows packaging smoke tests validate the compiled UI/API bundle. The public site receives separate link, repository-prefix and responsive browser checks. A stable required check named `CI` succeeds only when all required jobs succeed; no path filters skip that check. Actions use least-privilege permissions, pinned reviewed action revisions, dependency locks, bounded timeouts and cancellation of superseded PR runs. Untrusted PR code does not receive deployment permissions or secrets.

Main protection requires PRs, resolved review conversations and successful up-to-date CI, blocks force pushes/deletion, and includes administrators. Orion currently has one collaborator, so mandatory approval count is zero; independent review is still part of implementation completion. Add an approval requirement if a second maintainer is appointed. Stage protection safely: PR/conversation/no-force/no-delete protection is active immediately; require the exact GitHub Actions `CI` check after the real workflow has emitted it successfully on PR #3. No direct push/merge to main is part of this task.

GitHub Pages hosts an Argus-style public Orion project site at `https://varun-sv.github.io/Orion/`: product overview, real UI screenshots, seven supported collections, install/download guidance, recovery/privacy documentation and a clearly labelled interactive demo using fixture data only. Share the approved ivory/teal/clay/night visual identity. The local backend remains the installed app; the public demo cannot access a visitor's media or pretend sample organisation affects files. Repository-prefix assets/links must work at `/Orion/`. Before a release exists, download links point honestly to source/install guidance rather than a nonexistent installer.

Pages uses GitHub Actions publishing with HTTPS and the `github-pages` environment. Build and validate on PRs; publish only tested main commits through the same pipeline, after CI succeeds. Public files are an explicit site artifact, never the entire checkout. A successful deployment and live URL/assets/browser smoke check are release acceptance criteria after the user merges PR #3; enabling Pages alone is not a deployed site. Repository settings have been enabled now, ahead of the workflow implementation.

Release automation validates version tags against main history, reruns the same required CI for the tagged commit, produces a Windows bundle plus SHA-256 checksums and creates a draft GitHub Release. It does not claim signing or installers on untested platforms. Pages updates follow main; publishing a production release remains a deliberate maintainer action. Document reruns, rollback to an earlier tested site artifact/commit, failed deploy behavior and the distinction between repository settings, shipped workflow code and first deployment.
