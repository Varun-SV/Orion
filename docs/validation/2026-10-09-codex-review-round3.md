# Codex review corrections, third pass — 9 October 2026

Seven new findings arrived while the second-pass CI ran. Each was checked against the implementation and reproduced before correction. Twenty-two naming, destination, undo, lookup and comparison regressions failed initially. After correcting the startup fixture to use the application's actual database filename, both restart regressions also failed for stale item/job state. Four further controls check preserved confirmations, unchanged layouts, whole-series comparison and externally modified recovery targets.

| Review comment | Correction and verification |
| --- | --- |
| [Linked destination ancestors](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192448) | Destination registration and planning reject links anywhere in the root's ancestry. Source/destination overlap uses resolved paths, and recorded-root containment rejects linked ancestors during execution/recovery. A normal child below a real Windows junction/POSIX symlink is rejected without creating a destination record. |
| [Rendered media extensions](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192453) | Check the final rendered filename's suffix against the source, case-insensitively, after any explicit override. Movies, episodes, music and books reject extensionless/incorrect templates; correct differently cased suffixes and directory layouts remain valid. |
| [Portable path characters](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192459) | Shared relative-path validation rejects Windows punctuation and control characters in category subpaths and rendered components. Eight invalid-character cases fail before filesystem execution. Existing reserved-name/containment rules remain applied. |
| [Undo snapshot freshness](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192465) | Persist the complete original operation-state snapshot with the inverse plan. Before reconciliation or movement, reject undo execution if the original batch's states changed or the old preview lacks this snapshot. A loose movie/subtitle partial batch is retried after preview; the obsolete undo is rejected with every destination byte intact, and a fresh undo restores both members. |
| [Atomic lookup publication](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192474) | Serialize candidate values once, then validate the observed item signature and publish candidates/status inside one SQLite writer transaction. The SQL status update checks the current decision. Replacement after provider completion rejects stale candidates without annotating the new arrival; a concurrent confirmation survives an empty lookup. |
| [Episode comparison identities](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192487) | For file-backed episodic items, confirmed show identity includes normalized season/episode from merged metadata. TMDb, AniList and AniDB examples separate distinct episodes while grouping alternate versions of the same episode. Whole-series directories retain show identity. |
| [Completed-operation startup recovery](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230192504) | Startup also queues recovery for running batches and interrupted writer jobs linked to batches. Recovery verifies recorded roots and final destination identities, updates items/batches and publishes the interrupted job result when every operation is already complete. It also closes the later crash window between batch completion and job publication. Audit writes are idempotent. Both crash windows recover automatically; an externally edited destination is retained for review without finalizing its batch. |

Final local validation:

- **324 backend tests passed, no skips**, 89.96 seconds, with the freshly rebuilt standalone executable supplied through `ORION_PACKAGE_EXE`.
- **50 UI tests passed**; TypeScript and production frontend build passed.
- **109 real-backend browser checks passed**, no uncaught exceptions; all generated media/subtitle bytes restored, including the partial-undo recovery/retry scenario.
- Fresh standalone Windows smoke checked **52 assets**, isolated database, empty system PATH, occupied-port rejection, instance reuse and graceful stop. Observed startup 2.615 seconds; bundle 57,058,282 bytes.
- All 52 bundled frontend resources match the final production build byte-for-byte.
- Archive `dist/review-round3-release/Orion-0.2.0-windows-x64.zip`: 30,213,178 bytes; SHA256 `0856a4b9699c8fc777f0da7a1672b8c6545ec19f00e3c19efbf51b679c97e13a`. Release/checksum verification passed.
- Workflow delivery policy and Git whitespace checks passed. Hosted validation of the pushed source is recorded on PR #3.

The preceding second-pass compatibility commit passed every required hosted job in [run 37931987342](https://github.com/Varun-SV/Orion/actions/runs/37931987342), including Windows Python 3.11 and the headless Linux browser. Its eleven review threads were then resolved. The initial eight review threads also remain resolved.

Main protection and main-only Pages deployment remain applied. No merge, tag, source-branch deletion or release publication was performed. Authenticated live providers/personal media servers remain unverified without credentials; startup/package measurements are observations from this PC.
