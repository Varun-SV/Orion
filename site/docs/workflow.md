# Your first organisation

Orion keeps identification and file changes as separate decisions. Start with a small folder you can inspect, and confirm the destination has enough free space.

1. **Choose folders.** In Settings, add an accessible source folder and a destination folder. Sources cannot overlap one another. Point the destination somewhere you control and can back up.
2. **Scan.** Start a scan from the source. Scanning indexes discovered media and parsed metadata; it does not move or rename files. Wait for the job to finish, then open the relevant collection.
3. **Identify.** Request provider candidates for items that need identification. You can also keep parsed details and edit the decision manually. Provider matches are suggestions: compare title, year, artist, edition or other evidence before confirming.
4. **Review.** Confirm the metadata and collection for each item. Resolve no-match and error states, or leave uncertain items unconfirmed. Confirming metadata does not move a file.
5. **Preview.** Select confirmed items and create a plan. Choose the destination, naming preset, and conflict behavior. Review every proposed media and companion path, warning and optional output. Revalidate the preview before approval because the source, metadata or destination may have changed.
6. **Organise.** Approve the revalidated preview. Orion queues the operation and records per-file results. Follow progress in Jobs; do not start another operation on the same files while work is pending.

For example, a fictional movie folder `Incoming/Arrival.2016.mkv` might be reviewed as *Arrival* (2016), then previewed under `Movies/Arrival (2016)/Arrival (2016).mkv`. The preview—not this example—shows the exact paths Orion will use for your settings.

## If you need to stop or try again

Cancel a scan, lookup or operation from its job controls. Cancellation is cooperative, so an operation may finish its current safe step before stopping. Inspect job and operation results before retrying. A retry rechecks the recorded file identities and will report changed or missing files rather than blindly repeating the move.

Completed batches can offer an inverse plan in recovery. Undo is also previewed and revalidated; it restores only files whose recorded identities still match and whose original locations are available. See [recovery](./recovery.html) for partial undo and backup guidance.

## What the website demo does

The public demo is a simulation with labelled fictional fixtures. Its scan, review, preview and organise actions change only the sample shown in that page. They do not call Orion, inspect local folders or perform real file operations.
