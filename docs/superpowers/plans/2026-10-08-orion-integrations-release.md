# Orion integrations and release implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the productivity features and preserved PR goals, then validate/package the whole replacement app.

**Architecture:** Build on completed library/job/planner/executor interfaces. Sidecars participate in immutable plans and the journal; external refresh remains independently retryable. Opt-in watching discovers stable arrivals without silently organising unreviewed items.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript, requests/provider clients, pytest/Vitest, Windows PyInstaller packaging.

**Spec:** `docs/superpowers/specs/2026-10-08-orion-modernisation-design.md`, especially Consolidated pull-request goals.
**Dependencies:** `2026-10-08-orion-engine.md` and `2026-10-08-orion-ui.md`.

## Global constraints

- Opt-in NFO and artwork output, off by default and remembered per collection/profile.
- Never overwrite an existing user sidecar.
- Integration failure does not undo successful local operations; provide independent retry.
- Watching does not auto-organise uncertain or unreviewed files.
- Server/catalogue failures show unavailable results rather than declaring an entire season missing.
- Do not advertise Plex as implemented.
- No RAM, CPU or installer-size superiority is claimed without measurement.
- Verify packaging on each supported OS before promising native installers there.
- Do not merge main or delete source PR branches.

## Review focus

1. Offline/unauthorised lookup cannot appear as an empty server: task 2.
2. Pagination cannot truncate library/episode completeness: task 2.
3. Existing/changed sidecars survive generation and undo: task 3.
4. Files still downloading do not trigger unstable identification: task 1.
5. Packaged runtime must work without Node/Qt: task 4.

## File structure

Create `orion/profiles.py`, `duplicates.py`, `watcher.py`, `reports.py`, `integrations/server.py`, `gaps.py`, `sidecars.py`, integration routes/tests. Add matching frontend profile/comparison/gaps/server/report controls and tests. Update build scripts, README and CI. Adapt useful PR #1 code; do not import its Qt wrappers or assume its error handling/pagination is complete.

### Task 1: Profiles, comparison, stable folder watching and reports

**Files:** `orion/profiles.py`, `duplicates.py`, `watcher.py`, `reports.py`, their routes/tests, frontend controls/tests.
**Interfaces:** `Profiles.save(profile: NamingProfile) -> NamingProfile`; `Duplicates.compare(item_ids: list[str], exact: bool, context: JobContext) -> Comparison`; `Watcher.tick(context: JobContext) -> DiscoverySummary`; `Reports.export(job_id: str, format: Literal['csv','json']) -> bytes`.

- [ ] Write tests for valid/invalid templates, traversal rejection, renderer consistency, exact hashes versus versions, download stability intervals, offline drive backoff, opt-in persistence and CSV/JSON escaping/secrets. Core assertions:
```python
assert comparison.exact_groups == [[first.id, identical.id]]
assert alternate.id not in comparison.exact_groups[0]
assert unstable_tick.queued == 0
assert stable_tick.queued == 1
assert 'api_key' not in report.decode()
```
UI tests ensure comparison cannot silently delete and watching cannot auto-organise.
- [ ] Run new backend/UI tests; expect missing services and controls.
- [ ] Implement presets with the shared renderer. Compare IDs/tags/signatures and on-demand SHA-256; distinct editions are versions, not exact duplicates. Use bounded periodic watching initially with configurable file-stability/debounce and persisted checkpoints. Generate actual stored plan/result exports only on user request.
- [ ] Run full backend/UI suites/typecheck/build; expect passing. Commit `feat: add presets version comparison watchers and reports`.

### Task 2: Jellyfin/Emby integration and episode gaps

**Files:** `orion/integrations/server.py`, `gaps.py`, integration routes, `tests/test_media_server.py`, `test_episode_gaps.py`, frontend server settings/duplicate hints/EpisodeGaps and tests.
**Interfaces:** `MediaServerClient(config, credentials)` exposes `test_connection() -> ServerInfo`, `users() -> list[ServerUser]`, `items(query: ServerQuery) -> list[ServerItem]`, `episodes(series_id: str) -> list[ServerEpisode]`, `refresh() -> RefreshResult`; unavailable/error is distinct from empty. `EpisodeGaps.compare(series_id: str, provider_mapping: ProviderMapping, include_specials: bool, context: JobContext) -> GapReport`.

- [ ] Test both servers with local HTTP fixtures: key headers without logs/secrets, explicit user context, paginated items/episodes, resolution metadata, bounded timeouts, mapping ambiguity, unaired entries/specials, cached catalogue data and failed refresh independent of file success:
```python
assert len(client.items(query)) == 125 # spans fixture pages
assert gap_report.missing == [(1, 3)]
assert gap_report.unaired == [(1, 4)]
assert offline_report.state == 'unavailable'
assert completed_batch.state == 'completed'
assert refresh_job.state == 'failed'
```
UI tests cover connection/user selection and unavailable gap reports.
- [ ] Run new tests; expect absent typed adapters/gap logic.
- [ ] Verify official current Jellyfin/Emby API contracts before adapting PR #1. Implement pagination, typed errors, duplicate evidence, credential settings, explicit connection tests and opt-in successful-batch refresh. Gap analysis uses confirmed provider mapping plus rate-limited cached TMDb season/episode data. Server/catalogue failure cannot imply a full missing season.
- [ ] Run all suites/mock-server full flows; expect passing. Record live-server checks separately when available. Commit `feat: add Jellyfin Emby discovery and episode gap analysis`.

### Task 3: Persisted provider metadata and journalled sidecars

**Files:** `orion/integrations/sidecars.py`, provider/planner/executor extensions, `tests/test_sidecars.py`, frontend sidecar profile controls/tests.
**Interfaces:** `Sidecars.plan(item: MediaItem, profile: NamingProfile) -> list[SidecarSpec]`. Specs have kind/path/provider metadata/optional artwork origin; execution uses recorded no-replace operations. Decisions/plans retain title/year/plot/provider IDs/cover URLs/release MBID.

- [ ] Test metadata round-trip/migration, XML escaping/unique IDs, movie/series/artist/album/episode layouts, defaults off, existing-file races, interrupted generation/downloads, tag-only audio without cover ID and undo preserving external changes:
```python
assert parsed_nfo.findtext('title') == 'A & B'
assert existing_poster.read_bytes() == user_poster
assert original_sidecar.read_bytes() == original_bytes
assert undo.created_sidecars_removed == [unchanged_batch_sidecar]
assert tag_only_item.artwork_state == 'release_id_unavailable'
```
- [ ] Run sidecar/backend/UI tests; expect missing journalled output behavior.
- [ ] Adapt PR #1 writers using bounded fetches, temporary output/no-replace finalisation. Include enabled sidecar operations in preview/journal; preserve existing associated files. Cache/rate-limit per-episode metadata. Unavailable optional art is an explicit warning/retryable result, not destructive failure. Store credential-free metadata only.
- [ ] Run complete suites; expect passing no-overwrite/recovery/undo tests. Commit `feat: add recoverable opt-in NFO and artwork generation`.

### Task 4: Review, CI, standalone packaging and release handoff

**Files:** Production build spec/scripts, README/runtime/migration docs, `.github/workflows/ci.yml`, validation report and dependency locks.
**Interfaces:** Packaged launcher serves `frontend/dist`, API and local data without Node/Qt. Preserve legacy launch instructions during migration review. Installation tests use an isolated data directory; do not overwrite the user's installed app.

- [ ] Write package smoke tests for bundle resources, explicit data-dir launch, frontend/API routing, occupied ports and graceful stop; assert:
```python
assert packaged_health.status_code == 200
assert packaged_index.headers['content-type'].startswith('text/html')
assert fixture_db.exists()
assert process.wait(timeout=10) == 0
```
Run before packaging updates; expect missing bundle-resource behavior.
- [ ] Implement static resource bundling, compatible dependency locks, CI and documented install/upgrade/backup/recovery/server/keychain/fingerprint setup. Measure actual package size/startup; do not promise unmeasured savings. Retain cross-platform source support while qualifying installer verification by OS.
- [ ] Run all backend/UI suites/typecheck/build, production browser QA, migration/fault fixtures and isolated Windows package smoke tests. Report unavailable live-server/other-platform checks explicitly.
- [ ] Request an independent whole-branch review using the chosen execution workflow; fix important actionable findings with regression tests, then rerun affected and full checks. Commit/push all completed code to PR #3.
- [ ] Rewrite PR title/body around final implemented behavior and observed validation; remove spec-only status. Mark ready only when required work/checks are complete. Attach PR and hand off actual production preview with material verification limits. Do not merge.

## Completion contract

Every approved spec section and both source PR goal sets must map to implemented behavior/tests. No demo percentages, simulated jobs or static success badges may remain in production. PR history shows documentation first, then reviewable code commits. No merge or source-branch deletion is authorised.

GitHub delivery is additionally required by the user's follow-up. Packaging in task 4 supplies the bundle/build commands consumed by [the GitHub delivery plan](2026-10-08-orion-github-delivery.md); that plan owns exact CI gating, release automation, branch protection and Pages implementation/verification. These are part of PR #3, not a later optional project.
