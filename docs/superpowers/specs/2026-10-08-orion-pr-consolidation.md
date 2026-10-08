# Open PR consolidation — 2026-10-08

The user approved the modernisation spec and instructed closure of all open Orion PRs after preserving their goals, then a new PR containing the spec followed by the implementation.

| Source PR | Preserved goals | New design location |
| --- | --- | --- |
| [#1](https://github.com/Varun-SV/Orion/pull/1) | Jellyfin + Emby configuration/test/search/refresh; server duplicate hints; episode gaps; optional NFO/artwork; provider metadata through moves; nonblocking downloads | Consolidated pull-request goals, PR #1 |
| [#2](https://github.com/Varun-SV/Orion/pull/2) | Workflow-oriented workspace; all-media review; operation plans; libraries; connections; persistent themes; honest capability states and real counts | User experience and Consolidated pull-request goals, PR #2 |

PR #1 head: `88f06377a380ecf91e3b1ae2caff1583a54fdcf9`.
PR #2 head: `a3a65128da550a93ea6c9f6a5815c76b4bbfb81e`.

Both targeted main. Closing supersedes these proposals rather than merging their legacy PyQt implementations. No source branches are deleted. Their public PR history/diffs remain available.

The accepted visual target is the interactive prototype created in this chat. Navigator's workflow intentions are preserved without replacing that accepted appearance. Its historical review feedback is included as regression criteria, not treated as fresh findings against the latest head.

The replacement PR begins with documentation only. Implementation commits will follow on `codex/orion-modernisation`; it remains draft until the implementation and validation are complete. No merge to main is authorised by this task.
