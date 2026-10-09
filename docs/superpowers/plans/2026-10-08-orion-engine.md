# Orion engine and recovery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver a real local engine/API with persistent media identity, reviewed decisions, immutable plans, verified transfers and guarded recovery/undo.

**Architecture:** Add a Qt-free `orion/` runtime alongside the legacy app. Reuse the current providers/parsers; extract worker algorithms into services. All filesystem writes use a persisted planner/journal, with short SQLite transactions on separate worker connections.

**Tech Stack:** Python 3.11+, FastAPI/Pydantic/Uvicorn, sqlite3, existing media libraries, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-10-08-orion-modernisation-design.md`, including both consolidated PR goal sets.

## Global constraints

- Python 3.11+.
- One filesystem-writing job runs at a time.
- Read-only preview never performs metadata writes, renames or moves.
- The initial implementation does not overwrite an existing destination.
- Remove the source only after destination verification and finalisation.
- Secret values never enter the operation log or frontend library payloads.
- Do not interpret an unavailable source drive as deletion of all its indexed items.
- Do not enable broad CORS or LAN listening by default.
- Use generated temporary media fixtures; real personal-media mutation is outside automated verification.
- Preserve OS keychain service names so existing keys are available.
- Work on `codex/orion-modernisation`, update PR #3, do not merge main.

## Review focus

1. Identical names across sources must not share decisions: task 1.
2. Crash after filesystem success before SQLite completion must reconcile: task 4.
3. Offline drives must retain indexed items: task 2.
4. Failed approved items remain visible for recovery: tasks 5/6.
5. Cross-origin loopback requests cannot start moves: task 6.

## File structure

Create `orion/models.py`, `store.py`, `config.py`, `library.py`, `discovery.py`, `providers.py`, `naming.py`, `planner.py`, `filesystem.py`, `executor.py`, `jobs.py`, `app.py`, `__main__.py`, focused `routes/`, web/dev requirements and `tests/`. Keep modules focused; legacy `core/`, `api/`, `ui/` remain during migration. Add pytest configuration within task 1.

Shared records: `MediaItem{id,source_id,path,kind,status,signature,metadata,decision}`, `MatchDecision{item_id,provider,provider_id,metadata,evidence}`, `OperationPlan{id,revision,operations,issues}`, `Operation{id,plan_id,item_id,kind,source,destination,expected_signature,state,verification}`, `Job{id,kind,state,progress,result,error}`. Pydantic mutation models reject unknown fields; enums constrain kinds/states. Index IDs/paths/search fields; JSON is for typed metadata/details.


Define `Page[T]{items,total,offset,limit}`, `Candidate{provider,provider_id,title,year,metadata,evidence}`, and the shared `JobContext` protocol in `orion/models.py` during task 1; protocol methods are `cancelled() -> bool` and `progress(phase: str, items_done: int, items_total: int, bytes_done: int = 0, bytes_total: int = 0) -> None`. Discovery/task-2 tests may provide a plain fixture context before the durable manager exists. Task 3 owns `NamingProfile`, `RelativeLayout` and `PlanOptions`; task 4 owns `BatchResult`/`RecoverySummary`; task 5 implements the shared context. Define `ScanSummary` alongside discovery. Test snippets use fixture helpers in `tests/conftest.py` for seeded stores and fault reports; they are not extra undocumented production APIs. Integration `SidecarSpec` and server/gap records belong to their named integration modules.
### Task 1: Versioned storage and legacy import

**Files:** Create `orion/models.py`, `store.py`, `config.py`, `tests/test_migrations.py`, `tests/test_identity.py`, dependency/test configuration and `tests/conftest.py` fixture helpers.
**Interfaces:** `Store(db_path: Path).migrate() -> Path | None`, `Store.transaction()` gives a short-lived connection; `Config(data_dir: Path | None = None)` preserves existing keychain names and allows isolated test roots.

- [x] Write migration/identity tests against actual old SQLite schemas. Test all-media/settings preservation, upgrade backup, rollback after injected migration failure, same-name sources, ambiguous legacy choices and secret exclusion. Core assertions:
```python
assert upgraded.counts() == {'video': 2, 'music': 1, 'books': 1}
assert upgraded.decision(second_source_item.id) is None
assert original_backup.exists()
```
- [x] Run `python -m pytest tests/test_migrations.py tests/test_identity.py -q`; expect failures for the absent runtime.
- [x] Implement schema versioning, backups, per-connection WAL/foreign keys and stable source-scoped IDs. Import ambiguous name-only choices into review; do not guess. Preserve existing preferences/providers and document incompatible old-app writes after migration.
- [x] Run `python -m pytest -q`; expect all collected tests passing. Commit `feat: add versioned Orion storage and legacy import`.

### Task 2: Incremental discovery and metadata review

**Files:** Create `orion/library.py`, `discovery.py`, `providers.py`, `tests/test_discovery.py`, `test_providers.py`; extract Qt worker algorithms; reuse existing parser/provider modules.
**Interfaces:** `Library.query(query='', kind=None, status=None, offset=0, limit=100) -> Page[MediaItem]`; `Library.decide(item_id: str, decision: MatchDecision) -> MediaItem`; `Discovery.scan(source_ids: list[str], deep: bool, context: JobContext) -> ScanSummary`; `Providers.candidates(item: MediaItem, context: JobContext) -> list[Candidate]`.

- [x] Write tests for all seven categories, unchanged/changed signatures, offline sources, symlink exclusion, cancellation during walking, embedded audio/book metadata, distinct no-match/error states and shared provider rate limits. Assertions include:
```python
assert second_scan.processed == 0
assert offline_scan.unavailable_sources == [source.id]
assert library.get(item.id).decision == prior_decision
```
- [x] Run `python -m pytest tests/test_discovery.py tests/test_providers.py -q`; expect missing-service failures.
- [x] Implement incremental indexing with child manifests for directory identity, source isolation, evidence-bearing candidates and bounded requests. Persist item/provider IDs rather than original names. Use joined/batched review queries; only defined evidence can support auto-approval.
- [x] Run full pytest; expect passing behavior without Qt imports in the new runtime. Commit `feat: add incremental discovery and evidence-based review`.

### Task 3: Shared naming and immutable preflight

**Files:** Create `orion/naming.py`, `planner.py`, `tests/test_naming.py`, `test_planner.py`.
**Interfaces:** `Naming.render(item: MediaItem, profile: NamingProfile) -> RelativeLayout`; `Planner.create(item_ids: list[str], options: PlanOptions) -> OperationPlan`; `Planner.validate(plan_id: str, revision: int) -> OperationPlan`.

- [x] Write tests for immutable preview, stale revisions/signatures, existing/case-colliding destinations, unavailable roots/access/space, overlap/traversal, quality/episode naming, subtitles/directory manifests and in-place music/books without destination roots:
```python
assert source.read_bytes() == original_bytes
assert conflicting_plan.issues[0].code == 'destination_exists'
assert inplace_plan.issues == []
```
- [x] Run `python -m pytest tests/test_naming.py tests/test_planner.py -q`; expect missing planner failures.
- [x] Implement one renderer for preview/execution; persist full file/sidecar plans, expected signatures and revisions. Allow skip/new-name/keep-separate resolutions, never overwrite. Check transfer bytes per destination volume; no-op/same-volume moves do not need a second full copy's space. Validate configured-root containment; skip symlinks explicitly.
- [x] Run full pytest, confirm fixture hashes unchanged by preview. Commit `feat: add immutable organisation plans and preflight`.

### Task 4: Verified transfers, recovery and undo

**Files:** Create `orion/filesystem.py`, `executor.py`, `tests/test_transfers.py`, `test_recovery.py`, `test_undo.py`.
**Interfaces:** `Executor.execute(plan_id: str, revision: int, context: JobContext) -> BatchResult`; `Executor.reconcile() -> RecoverySummary`; `Executor.undo_plan(batch_id: str) -> OperationPlan`. `JobContext.cancelled() -> bool`; `progress(phase: str, items_done: int, items_total: int, bytes_done=0, bytes_total=0) -> None`.

- [x] Test same-volume and forced cross-volume behavior, source change/verification failure, no-replace races, cancellation, partial directory batches and crashes at intent/copy/finalise/source-delete/completion boundaries. Use injectable adapter fault hooks from test utilities, not production test flags. Test undo of externally changed files, occupied originals and unchanged batch-created sidecars:
```python
assert failed_copy.source.read_bytes() == original_bytes
assert retry.completed_operation_ids == [operation.id]
assert undo.conflicts[0].code == 'target_changed'
assert unrelated_original.read_bytes() == unrelated_bytes
```
- [x] Run `python -m pytest tests/test_transfers.py tests/test_recovery.py tests/test_undo.py -q`; expect missing-executor failures.
- [x] Implement durable stages/platform no-replace primitives. Cross-volume: owned temporary path, streamed copy with checkpoints, flush, SHA-256 verification, no-overwrite finalisation, rechecked source deletion. Reconcile actual state after crashes. Directory batches journal each child; only remove empty completed source directories. Undo builds inverse plans and uses the same verified executor. Individual interrupted files may restart; completed files must not recopy.
- [x] Run full pytest and fault-injection cases; expect original bytes retained on failure and guarded reverse results. Commit `feat: add verified transfers guarded undo and crash recovery`.

### Task 5: Durable jobs and lifecycle

**Files:** Create `orion/jobs.py`, `tests/test_jobs.py`.
**Interfaces:** `JobManager(store, services).submit(kind: str, payload: dict) -> Job`, `.get(job_id) -> Job`, `.cancel(job_id) -> Job`, `.retry(job_id) -> Job`, `.shutdown() -> None`; supplies task 4's `JobContext`.

- [x] Test single writer, bounded independent discovery/provider jobs, cancellation with in-flight timeouts, graceful shutdown, restart interruption, retries retaining completed members, failed-approved queue visibility and progress persistence:
```python
assert manager.active_writer_count == 1
assert reopened.get(job.id).state == 'interrupted'
assert library.get(failed_item.id).status == 'error'
```
- [x] Run `python -m pytest tests/test_jobs.py -q`; expect missing lifecycle behavior.
- [x] Implement persisted job states/progress/results, bounded workers, writer serialisation, restart reconciliation and cooperative shutdown. Closing/reloading browser must not reset a job. Queue active-writer conflicts rather than racing.
- [x] Run full pytest; expect passing lifecycle tests. Commit `feat: add persistent Orion jobs and restart reconciliation`.

### Task 6: Local API and launcher

**Files:** Create `orion/app.py`, `routes/library.py`, `settings.py`, `jobs.py`, `plans.py`, `__main__.py`, `tests/test_api.py`, `test_launcher.py`, runtime/API documentation.
**Interfaces:** `create_app(data_dir: Path | None = None, frontend_dir: Path | None = None) -> FastAPI`. Versioned API resources: overview/items/candidates/decisions, sources/destinations/categories/settings/providers, plans/revalidate/execute, batches/undo-plan, jobs/cancel/retry, activity. Return typed pagination and stable error codes. Mutations take IDs/revisions, not arbitrary operation paths.

- [x] Test actual all-media metrics, joined review/search, errors on approved items, settings updates, strict payload validation, secret write-only handling, host/origin checks and session enforcement:
```python
assert hostile_client.post(execute_url, json=plan_ref).status_code == 403
assert response.json()['counts']['books'] == 1
assert 'api_key' not in provider_status.json()
```
Also test isolated data root, existing instance/occupied port, static SPA fallback and clean stop.
- [x] Run `python -m pytest tests/test_api.py tests/test_launcher.py -q`; expect route/launcher failures.
- [x] Implement same-origin static serving and local session rules. Add `python -m orion --data-dir PATH --port PORT --no-browser` and a stop command. New dependencies exclude Qt; the production frontend is built static data, so Node is unnecessary at runtime. Preserve legacy launch until replacement validation.
- [x] Run full pytest and `python -m compileall orion`; expect passing. Commit/push `feat: serve Orion local API and launcher` to PR #3.

Next execute the UI plan, then integrations/release. The engine/API is independently testable before UI connection.

