# Recovery, undo and backups

Orion records jobs and file operations so interrupted work can be inspected. Open Jobs or the recovery view after a cancellation, shutdown or error. Read each result before retrying: a retry checks whether files still match their recorded identity, and changed or missing files may need manual review.

## Cancel and retry

Cancellation is cooperative. The current safe step may complete before the job stops. Check the final status and per-item results; do not assume that cancelling reversed completed operations. Retry stopped or failed work only after correcting its reported issue. If a destination became occupied, review the conflict and create a new preview. Orion does not overwrite the existing destination.

## Preview undo

For completed batches, request an undo preview and inspect its paths and conflicts. Undo revalidates recorded identities. It will not move a file that changed externally or overwrite something at its original location. If some members conflict, select **Leave conflicted member unchanged** where offered, create a new preview with those members excluded, and approve the revalidated plan. The result can be a partial restoration; protected members remain listed for follow-up.

Generated sidecars are removed only if they are still unchanged. If someone edited generated output after organisation, undo leaves it in place and reports a warning. Original companion files are restored when their recorded identity and location permit it.

## Back up the app database

The default Windows application data directory is `%APPDATA%\Orion`. Before an upgrade, close Orion and copy the entire data directory to a safe location, including `organizer.db`, preferences and existing migration or recovery backups. A SQLite database may have `-wal` or `-shm` files while the app is running; close Orion before copying so the backup is consistent. Do not restore over an open database.

For database recovery, stop Orion, preserve the current database and any WAL/SHM files with an incident note, then restore a known consistent backup as `organizer.db` and launch a compatible app version. The migration process creates a database snapshot before changing an existing legacy schema, but that snapshot is not a backup of your media.

## Back up actual media too

Database recovery records paths and operation state; it does not recreate or protect your original media. Maintain a separate backup of source and destination media on another disk or trusted backup system. Confirm that backup can be read before relying on it. Read [runtime migration details](./runtime.html) before moving legacy data, and never run two app versions against the same data directory at once.
