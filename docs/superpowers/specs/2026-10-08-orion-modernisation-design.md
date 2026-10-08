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
