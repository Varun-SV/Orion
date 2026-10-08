# Orion implementation sequence

Design: [approved spec and consolidated PR goals](../specs/2026-10-08-orion-modernisation-design.md).
Replacement PR: https://github.com/Varun-SV/Orion/pull/3.

1. [Engine and recovery](2026-10-08-orion-engine.md): storage/import, discovery/review, immutable plans, verified transfers/undo/recovery, persistent jobs, local API/launcher.
2. [Connected UI](2026-10-08-orion-ui.md): approved appearance, real collections/review, plans/jobs/activity, onboarding/settings/connections, production browser QA.
3. [Integrations and release](2026-10-08-orion-integrations-release.md): presets/comparison/watching/reports, Jellyfin/Emby/gaps, journalled sidecars, full review/CI/packaging.

All three plans are required for the requested scope. Each has failing-test-first tasks, exact service boundaries and acceptance checks. Engine task 6 supplies UI and integration API contracts. Integration tasks extend those contracts; corresponding frontend components/tests are included in their deliverables. No task can claim completion using prototype-only checks.

Execution choice pending user review: native execution in this chat is recommended to maintain continuity across the shared engine interfaces, with one independent whole-branch review. Subagent-driven execution is also available with per-task review gates. Source PRs #1 and #2 are closed without branch deletion; their intentions are traced in the spec.

Self-review: covered original design and PR goals; matched shared JobContext/record signatures; assigned source identity, crash boundaries, offline sources, failed-approved visibility, global search, in-place readiness, pagination, sidecar undo and packaging tests. Further ambiguous platform/server behavior is resolved against official APIs and recorded in the execution ledger.

The replacement PR currently contains documentation only. Code follows the written-plan review and execution-method selection required by the planning workflow.
