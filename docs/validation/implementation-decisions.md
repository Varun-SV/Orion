# Implementation decisions and review record

- Reused the dedicated clone instead of adding another worktree. The branch is isolated; explicit staging protects the accepted untracked prototype. Cost if wrong: an extra checkout would be needed for conflicting work.
- Retained Python for filesystem/metadata work, removed Qt from the modern runtime, and used React/TypeScript/FastAPI/SQLite. Node is build-only. Installer/startup sizes are measured without unsupported performance-superiority claims.
- Adapted provider transports into typed errors rather than importing legacy silent-empty behavior. Maintenance cost: response normalization and fixture coverage.
- AniDB uses its public cached title XML rather than an unsupported search endpoint. Live catalogue access remains separately unverified; unavailable results are explicit.
- Existing directory destinations block or use a separate keep-both folder; no implicit directory merge. Cost: a future merge feature needs its own preview/recovery design.
- Generated-sidecar undo was implemented with the sidecar milestone rather than the earlier media-transfer milestone, so ownership/hash/removal semantics share the same journal.
- The user's latest instruction to test/fix everything before pushing overrides interim code-push plan steps. Documentation remains the first remote commits; implementation stays local through validation/review.
- Independent site and delivery work used scoped parallel agents after loading the dispatching-parallel-agents skill; core media changes remained with the primary agent. Files and tests were integrated centrally.
- The public site uses lightweight JavaScript/Vite, permitted by its static-site plan, while the installed app uses React/TypeScript. Cost: separate static UI code; no production API dependency.
- Release tags use a narrower read-only reusable validation workflow. Required jobs are duplicated with policy-enforced equality because GitHub reusable permission ceilings apply even to skipped deployment jobs. Cost: updates must satisfy the drift test.
- Legacy activity imports action/status/timestamp and a summary, keeping free-form details in original tables/backups to prevent old credential-bearing errors appearing in the browser. Cost: detailed legacy incident investigation reads the backup.

Final independent review and any deferred minor findings will be appended here after review.