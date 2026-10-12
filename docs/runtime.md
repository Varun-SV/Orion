# Runtime data and migration

The modern browser runtime uses the existing `%APPDATA%/Orion/organizer.db` and keychain service `Orion`. A supplied `--data-dir` isolates configuration and data for testing. Node is only needed to build the UI; Qt remains part of the legacy app only.

Before upgrading an existing SQLite database, Orion creates a consistent `organizer.db.backup-<timestamp>-<id>` snapshot. The upgrade runs transactionally: failure preserves the old tables and schema version. Do not delete backups until the replacement runtime and imported decisions have been checked.

The new schema uses separate `orion_*` tables. Sources, destinations, categories, music/books, settings and unambiguous choices are imported once. Same-name choices across sources return to review; path-specific file choices take precedence. Credentials remain in the OS keychain, not database exports. Legacy activity imports action, status and timestamp; its free-form detail stays in the original tables and migration backup because old HTTP errors can contain credentials. Legacy tables remain for reference but later legacy-app writes will not be imported again. Run one app version at a time after migration.

To restore, stop Orion, preserve the current database and its WAL/SHM alongside an incident report, then restore the consistent backup as `organizer.db` and launch the compatible older app. Do not replace an open database. The launcher and recovery UI show stored job/operation status; retries and undo always revalidate recorded identities.

## Local browser runtime

Build the interface with `npm --prefix frontend ci` and `npm --prefix frontend run build`, then launch `.venv\Scripts\python -m orion` (or `python -m orion` in an activated environment). `--data-dir PATH --no-browser --port 0` starts an isolated instance on a free loopback port; the URL is printed after startup. `python -m orion stop --data-dir PATH` requests cooperative shutdown. The data directory has a kernel-held single-instance lock; a second launch opens the existing instance. An occupied explicit port fails without terminating another process.

The UI and `/api/v1` share one origin. The client obtains an HttpOnly SameSite cookie and CSRF token from `/api/v1/session`, then supplies `X-Orion-CSRF` on mutations. Cross-origin requests and non-loopback Host headers are rejected. This is a local desktop runtime; public network hosting is unsupported.

Scan jobs discover files; lookup jobs return provider candidates; PUT item decisions confirms metadata without moving files. POST plans creates a persisted preview, revalidation checks its exact revision, and execution queues the single writer. Jobs/progress survive reloads, stopped jobs can retry, and batches produce guarded inverse plans. Startup interruption reconciliation runs as a cancellable writer job, without delaying the dashboard. Source removal pauses scanning while preserving item and recovery history. Credential replacement is write-only and secure storage failure requires an explicit session-only choice.


## Partially restoring a batch

If an organised file changed or its original path is occupied, the undo preview keeps it protected. In Plans, explicitly select “Leave conflicted member unchanged” and create a new preview with exclusions. Revalidate and approve that preview to restore its safe members. The old preview remains immutable, the result lists skipped members as partial restoration, and split-location items remain marked for recovery in operation history. Conflict skipping during organisation leaves the whole item and its companions at the source; it never attaches incoming metadata to an existing unrelated destination.
