# Codex review corrections, fifth pass — 9 October 2026

Fourteen additional comments were checked against the runtime and reproduced with regression tests before correction. Eight arrived initially; six more appeared during verification. Independent planner and server work used separate owned files, followed by a read-only review of the combined patch.

| Review comment | Correction and verification |
| --- | --- |
| [Restore directory ownership](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503805) | Reject a populated original directory or another indexed arrival at preview and execution. Retry accepts only unchanged, verified members restored by this batch. Unreadable contents are a conflict. Excluding a member does not permit merging into a new arrival. |
| [Provider credential clearing](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503813) | Clear according to the provider's reported active storage mode, independently of the checkbox for its replacement key. Both saved/session directions have UI regressions. |
| [Paused-source retries](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503821) | Validate current source/archive/watch state before requeueing scans. Discovery also skips sources paused after submission. Resumed sources remain retryable. |
| [Imported preferences](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503834) | Hydrate the runtime preferences from supported, validated imported settings after migration. Existing explicit preferences win; credentials, incompatible providers and removed destinations are excluded. Upgrade/startup remains idempotent. |
| [In-flight decision edits](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503847) | Refuse decision replacement/clearing for items owned by running/cancelling filesystem work in the same writer transaction. Other items remain editable. Actual paused file/directory transfers exercise the guard. |
| [Bounded episode previews](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503855) | Operation previews make no external catalogue requests. Read fresh cached seasons once per show/season across selected items. Missing/expired/invalid data gives an explicit warning and confirmed-show/filename fallback. Episode-gap jobs populate the existing cache. |
| [Excluded media sidecars](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503864) | Partial undo retains generated NFO/artwork for media left organised and reports the retention. Original companions still restore where safe. |
| [Server-hint publication](https://github.com/Varun-SV/Orion/pull/3#discussion_r4230503873) | Publish success/error hints atomically only for the observed signature, decision and server revision, preserving concurrent annotations. Cached reads validate provenance; obsolete/untagged caches require a new check. |
| [Imported category paths](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658317) | Choose the first imported category by rowid, matching provider-preference authority, rather than silently replacing its output path with a seeded row. |
| [Clearing organised decisions](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658325) | Clearing and reconfirming metadata retains organised status, path and signature. Undo still restores original bytes and returns to approved/pending according to the current decision. |
| [Gap mapping revisions](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658329) | Recheck the submitted server revision under the configuration lock before publishing a gap report/mapping. Store under that exact revision. URL/type/user changes cannot receive old mappings or health failures. |
| [Case-only renames](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658339) | Keep exact spelling changes in the plan. Windows uses two exclusive, journalled rename legs through an owned temporary file. Recovery checks actual directory entries and never unlinks the old spelling's alias to the published file. Tests cover both media kinds, conflict policies, undo, races, staging tampering and every journal boundary. |
| [Destination history paths](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658346) | Inspect parsed operation roots and actual path ancestry. Substrings, SQL wildcard characters and warning text no longer block deletion, while real recovery references remain protected. |
| [Disconnected-source sidecars](https://github.com/Varun-SV/Orion/pull/3#discussion_r4231658354) | Generated-output retries no longer require the original source after all media dependencies completed. Destination ancestry, identity and hashes still validate; pending media still requires its source. |

The independent review found an additional edge case in the new server-hint provenance: recursive secret-field filtering could remove directory signature filenames containing secret/token/password/credential/api_key. Canonical signature fingerprints preserve freshness without persisting filename keys as metadata. Regression tests reproduce this before correction and confirm immediate saved-hint reads afterwards.

An initial full-suite run passed 406 tests and caught one older assertion expecting partial undo to merge into a newly occupied restore directory. That assertion now checks the required ownership conflict and preservation of the new arrival's bytes. Final combined verification follows below.

Final local verification:

- **454 backend tests passed, one POSIX-only control skipped on Windows**, 134.51 seconds, using the freshly rebuilt standalone executable through `ORION_PACKAGE_EXE`. This pass adds 94 backend regressions/controls; all applicable controls pass.
- **52 UI tests passed**, plus TypeScript and the production build. All 52 bundled UI resources match that build byte-for-byte.
- **109 real-backend browser checks passed**, no uncaught exceptions; generated media and subtitle bytes restored. The browser engine explicitly uses `keyring.backends.null.Keyring`; fixture credentials cannot query or delete the user's saved OS-vault keys.
- Fresh standalone Windows smoke: **52 assets**, isolated database, empty system PATH, occupied-port rejection, instance reuse and graceful stop passed. Observed startup 2.575 seconds; bundle 57,070,066 bytes.
- Archive `dist/review-round5-final-release/Orion-0.2.0-windows-x64.zip`: 30,225,347 bytes; SHA256 `fffa7e6fae13fb330754b17f115b297771d24015d7c510b8af3e1feaad540f77`. Release/checksum verification passed.
- Workflow delivery policy and Git whitespace checks passed. Main protection and Pages settings were read back from GitHub and retain their required policies.
- Independent scoped review: no Critical or Important findings remain after the signature-provenance correction. Its fresh planner tests passed 20 applicable cases (one POSIX skip), and all 28 hint tests passed.
- The updated local preview is healthy at `http://127.0.0.1:58475/`, with its existing preview data preserved.


All earlier thirty-two threads were resolved after successful exact-source hosted runs, most recently [run 37949222622](https://github.com/Varun-SV/Orion/actions/runs/37949222622). Hosted results and resolution for this pass are recorded on PR #3. Main protection and workflow-only/main-only Pages delivery remain applied. No merge, branch deletion, tag or release publication was performed. Live authenticated providers/personal servers remain unverified without credentials; package timings are observations from this PC.
