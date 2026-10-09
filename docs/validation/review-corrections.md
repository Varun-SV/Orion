# Independent review corrections

Review scope: complete implementation, base `839853e47b3e851866dedd2b33a05c3ba1a1b85c` through `d4ce13d944fe53ed576530148d938e09d92e0911`. A fresh independent reviewer reproduced engine failures in disposable fixtures and made no checkout changes. Assessment was “With fixes”; no Critical defects were found.

The subsequent single fix pass addressed every finding:

1. **Important — discovery identity:** resolve existing items by their current source-scoped path; allocate a fresh stored identity for a new arrival at a retired path, while rejecting stale observations racing organisation. Movie arrivals and in-place books/music rescans retain correct records and journal references.
2. **Important — partial loose-file retries:** outstanding companions validate the completed primary at its recorded destination, including signature and hash, and independently validate their own unchanged sources. Edited published media blocks retry; a new arrival at the original primary filename remains untouched. Partial inverse transfers also retry.
3. **Important — skip conflicts:** skip the complete incoming item and its companions when any destination member conflicts. A skipped folder has no move or generated-output operations, and its record remains approved at its incoming location.
4. **Important — copy metadata recovery:** checkpoint after metadata application; safely recognise a crash before that checkpoint using the recorded complete inode/size/content digest. Cancellation at verification and a crash after `copystat` recover without recopying. Modified temporary content remains untouched and cannot be published.
5. **Important — undo conflicts:** users explicitly exclude individual conflicted members and create a new immutable preview. Safe remaining transfers execute; excluded files/occupied originals stay untouched. Results report partial restoration and skipped IDs, and split-location items remain marked for recovery at the actual media location.
6. **Minor — skip link:** focus the main landmark without changing the current route. A landmark-fragment reload renders the overview.
7. **Minor — clearing metadata:** explicitly empty artist/album/series/track/filename edits overwrite their saved values while untouched metadata and provider evidence remain retained.

Regression evidence: the new engine suite initially reproduced 11 failures across five findings (plus a passing stale-observation guard); the four new UI cases initially failed. The partial-primary-only restoration extension also initially failed and was corrected. Final validation is recorded in [production validation](2026-10-09-connected-runtime.md).

No review findings are deferred. Live authenticated providers/media servers, native macOS/Linux installers, runtime CPU/memory comparisons, and byte-level copy resumption were not promised by the approved initial delivery. Hosted CI and Pages/protection state are reported separately, without treating local tests as hosted evidence.
