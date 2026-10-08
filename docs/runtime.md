# Runtime data and migration

The modern browser runtime uses the existing `%APPDATA%/Orion/organizer.db` and keychain service `Orion`. A supplied `--data-dir` isolates configuration and data for testing. Node is only needed to build the UI; Qt remains part of the legacy app only.

Before upgrading an existing SQLite database, Orion creates a consistent `organizer.db.backup-<timestamp>-<id>` snapshot. The upgrade runs transactionally: failure preserves the old tables and schema version. Do not delete backups until the replacement runtime and imported decisions have been checked.

The new schema uses separate `orion_*` tables. Sources, destinations, categories, music/books, settings and unambiguous choices are imported once. Same-name choices across sources return to review; path-specific file choices take precedence. Credentials remain in the OS keychain, not database exports. Legacy tables remain for reference but later legacy-app writes will not be imported again. Run one app version at a time after migration.

To restore, stop Orion, preserve the current database and its WAL/SHM alongside an incident report, then restore the consistent backup as `organizer.db` and launch the compatible older app. Do not replace an open database. The launcher and complete recovery UI are added in subsequent implementation tasks.
