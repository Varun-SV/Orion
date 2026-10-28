# Orion PR #3 Completion Plan

> **For agentic workers:** Use the systematic-debugging, dispatching-parallel-agents and test-driven-development workflows. The user requested GPT-6 Luna for focused tasks and authorized fixes, testing and merge.

**Goal:** Correct every outstanding PR finding, verify the application's documented functionality, and merge PR #3 to main after required checks pass.

**Architecture:** Preserve the existing local FastAPI/SQLite engine and React workspace. Make narrowly scoped fixes to plan lifecycle validation, comparison task tracking and media-server publication locking; add behavioral regressions before each fix.

**Tech Stack:** Python 3.11/3.12, FastAPI, SQLite, React, TypeScript, Node 24, pytest, Vitest and Playwright.

**Spec:** Existing modernization specification in `docs/superpowers/specs/2026-10-08-orion-modernisation-design.md`; open findings on https://github.com/Varun-SV/Orion/pull/3.

## Global Constraints

- Never overwrite media or mutate user media during testing; use isolated generated fixtures.
- Preserve retry/recovery semantics and the single filesystem-writer queue.
- Keep dependency locks and branch protections intact.
- Use the observed PR head for publication leases and merge validation.

## Review Focus

- An undone completed preview must not silently republish nonexistent destinations.
- Interrupted, cancelled and partial operations must remain safely retryable.
- Comparison results must arrive after eviction from the recent-jobs window, including failures.
- Cancellation and failure publication must have a consistent order without deadlocks.
- Existing organize/undo, all seven media collections, integrations, reports, launcher and packaging remain covered by broad validation.

### Task 1: Forward plan lifecycle

**Files:** `orion/executor.py`; new `tests/test_review13_executor.py`.
**Interface:** `Executor.execute(plan_id, revision, context) -> BatchResult`.

- [x] Reproduce execute → undo → execute using real files; assert the final execution is rejected and the restored path/status remain accurate.
- [x] Verify the regression fails, add the lifecycle guard, then verify it passes, including a recreated hard-link destination.
- [x] Exercise repeated completion and partial/interrupted retries with the existing executor tests.

### Task 2: Comparison task tracking

**Files:** `frontend/src/pages/Comparison.tsx`; new `frontend/src/pages/Comparison.test.tsx`.
**Interface:** Existing `useTask()` and `/jobs/{id}` endpoint.

- [x] Reproduce a submitted active comparison missing from `/jobs`; assert its independently retrieved result is rendered and controls reenable.
- [x] Verify the regression fails, reuse the shared task hook, then verify completion and failure behavior.
- [x] Run the frontend type check and relevant component tests.

### Task 3: Failed server publication

**Files:** `orion/integrations/manager.py`, `orion/jobs.py`; new `tests/test_review13_server.py`.
**Interface:** `ServerIntegration.run(kind, payload, context)` and the existing per-job publication guard.

- [x] Reproduce cancellation during a failed server health publication using deterministic synchronization.
- [x] Verify the regression fails, serialize publication with cancellation, then verify both possible cancellation orders.
- [x] Check existing server health/configuration and cancellation regressions.

### Task 4: Verification and merge

- [x] Review changes independently; reproduce and correct any additional confirmed defects with regressions.
- [ ] Run the full backend, frontend, real-backend browser, site and workflow policy checks.
- [x] Record exact results and material environment limits in `docs/validation/2026-10-28-pr3-completion.md`.
- [ ] Publish fixes to the existing PR branch with a head lease; resolve only corrected review threads.
- [ ] Wait for all required hosted checks, including Ubuntu/Windows Python 3.11/3.12 and Windows standalone packaging, on the final SHA.
- [ ] Merge to main without bypassing protections; verify GitHub reports the PR merged.
