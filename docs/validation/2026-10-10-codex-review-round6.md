# Codex review corrections, sixth pass — 10 October 2026

Ten more comments arrived after the fifth-pass push. Each was reproduced with a failing regression, corrected, and verified with compatibility controls. Independent recovery, planner/settings and lookup/gap work used separate files; a read-only review then checked their interactions.

| Review comment | Correction and verification |
| --- | --- |
| [Scans after partial moves](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106575) | Discovery preserves the decision and original signature for items whose unfinished journal has evidence of actual moves/publication/staging. Real manual scans and Watcher jobs after partial failure/cancellation remain retryable. A complete undo releases ownership; failures/cancellations before the first move still permit normal replacement scans. |
| [Undoing an undo](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106585) | Reject undo plans for prior undo batches. Jobs keeps retry, reports and operation details but omits another Preview undo action on undo jobs. Legitimate organisation and sidecar batches retain undo. |
| [Directory companion case](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106592) | Match relative media/companion prefixes using host case rules while retaining original suffixes. Real Windows movie/episode organisation and undo preserve association and bytes; POSIX controls remain case-sensitive. |
| [Authoritative category forms](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106601) | Categories lists only the first row per kind, matching provider/planner authority. Updates to hidden seeded duplicates are rejected without changing settings; editing the displayed imported category changes preview paths. |
| [Overlapping auto items](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106609) | A directory candidate owns its whole subtree, so embedded audio/books are not also indexed as independent items. Standalone media remains independently discoverable. |
| [Indexed destination conflicts](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106617) | Preview and execution validation reject another same-source indexed final item path even if its file was deleted externally. File, directory and arrivals after preview are covered; current-item paths remain permitted. |
| [Sidecar-only finalization](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106624) | Fully successful create-only in-place plans become organised. Their removal-only undo restores approved/pending according to the decision without changing media path, signature or bytes. |
| [Excluded specials counts](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106633) | Filter season-zero server episodes from the present set unless explicitly included. Jellyfin/Emby mixed/ranged fixtures, cached catalogues and persisted CSV/JSON counts agree. |
| [Late lookup cancellation](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106638) | Recheck cancellation after provider work before publishing candidates or provider errors. Real in-flight JobManager tests retain prior candidates, decisions, status and signatures for pending/approved/organised items. |
| [Stale instance shutdown](https://github.com/Varun-SV/Orion/pull/3#discussion_r4232106648) | Require a held data-directory lock and verify an opaque canonical workspace identity in the session response before sending stop. Real process fixtures cover crash-record port reuse, the restart window before record replacement, legitimate shutdown and equivalent directory paths with spaces. |

The initial hosted run of fifth-pass source passed every backend matrix job, frontend, site and standalone package validation, but its browser job read a previous terminal state before the retry request was accepted ([run 37955100500](https://github.com/Varun-SV/Orion/actions/runs/37955100500)). Delaying the retry POST by 250 ms reproduces the failure on this PC. The browser harness now waits for the actual retry response before polling completion; the latency remains in the fixture to prevent regression. The delayed-request run passes all 109 checks.

Independent review caught and corrected two refinements: non-mutating failed/cancelled journals must not freeze subsequent discovery, and a held startup lock alone cannot bind a still-stale URL to the responding workspace. The final ownership predicate and shutdown identity handshake have explicit failing-then-passing controls.

Final local verification:

- **501 backend tests passed, one POSIX-only control skipped on Windows**, 170.12 seconds, using the freshly rebuilt standalone executable through `ORION_PACKAGE_EXE`. This pass adds 47 backend regressions/controls; all applicable tests pass.
- **53 UI tests passed**, plus TypeScript and the production build. All 52 bundled UI resources match that build byte-for-byte.
- **109 real-backend browser checks passed**, including deliberate retry-request latency and the undo action guard. No uncaught exceptions; generated media and subtitle bytes restored. The browser engine uses `keyring.backends.null.Keyring`; test credentials cannot query/delete the user's OS-vault keys.
- Fresh standalone Windows smoke: **52 assets**, isolated database, empty system PATH, occupied-port rejection, instance reuse and graceful stop passed. Observed startup 2.773 seconds; bundle 57,073,114 bytes.
- Archive `dist/review-round6-release/Orion-0.2.0-windows-x64.zip`: 30,227,254 bytes; SHA256 `7ec0257eb4bda77d18ec9373dfeb71e511328342710ee8414a95c239bdbe894f`. Release/checksum verification passed.
- Workflow delivery policy and Git whitespace checks passed. Independent scoped review reports no Critical or Important findings remaining; its original restart-window reproduction now rejects the stop and preserves both fixture processes.
- Updated packaged preview healthy at `http://127.0.0.1:61134/`, with existing preview data retained and the expected workspace identity verified.


The preceding fourteen threads remain pending until the final exact-source hosted run passes together with these ten corrections. Earlier thirty-two threads remain resolved. Hosted results and resolution are recorded on PR #3. Main protection and workflow-only/main-only Pages delivery remain applied; live Pages publishing awaits a merge to main. No merge, branch deletion, tag or release publication was performed. Live authenticated providers/personal servers remain unverified without credentials; package timings are observations from this PC.
