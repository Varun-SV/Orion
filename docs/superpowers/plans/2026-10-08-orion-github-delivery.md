# Orion GitHub delivery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship verifiable CI/CD, protected main and a public Orion project site in PR #3.

**Architecture:** A reusable CI workflow validates the app, Windows bundle and static site at the same commit. An aggregate `CI` job gates protected main and Pages deployment; deployment and draft release jobs receive write permissions only on trusted events. Repository configuration is documented and read back independently of code.

**Tech Stack:** GitHub Actions, Python 3.11/3.12, Node 24, pytest, TypeScript/Vitest, Playwright Chromium, PyInstaller, GitHub Pages, gh CLI.

**Spec:** `docs/superpowers/specs/2026-10-08-orion-modernisation-design.md`, GitHub delivery and public project site.
**Dependencies:** Engine, connected UI and integrations/release plans. Site design can proceed independently; required app check activation follows real successful CI.

## Global constraints

- Same replacement PR #3; no direct push or merge to main; no old branch deletion.
- PR checks run on drafts and all changes, without path filtering the required aggregate.
- Site path is `/Orion/`; fixture demo only; seven collections; approved visual identity.
- CI providers/filesystem fixtures are isolated and require no real credentials or user media.
- Deployment only after successful checks on a main push. No publishing PR artifacts.
- Default token permission is contents read; Pages/write and release/write are job scoped.
- Pin external Actions to reviewed full commit SHAs with readable version comments; lock dependencies.
- Main protection includes administrators, requires PR/conversation resolution, blocks force pushes/deletion; reviewer count zero while only one collaborator exists.
- Require exact `CI` check after it has successfully run; never configure an invented check name.
- Pages enablement is not proof of deployment. Live deployment verification follows merge.

## Review focus

1. A failed/cancelled matrix job must fail the aggregate even when another dependency is skipped: task 1.
2. Fork PRs must run validation without deployment credentials or privileged checkout: task 1.
3. `/Orion/` assets, internal links and reloads must work outside a root localhost URL: task 2.
4. A tag outside main or with a mismatched version must not create release assets: task 3.
5. Repository settings must match the documented state rather than exist only as JSON: task 3.

## File structure

Create `.github/workflows/ci.yml`, `pages.yml`, `release.yml`, `.github/dependabot.yml`, `site/package.json`, lockfile, `site/index.html`, `site/src/`, `site/vite.config.ts`, `site/tests/`, `scripts/check_workflows.py`, `scripts/verify_release.py`, `docs/github-delivery.md`, and `.github/main-protection.json`. Extend production build scripts and README from integrations task 4. Use small shared visual tokens/assets, not runtime dependencies on the local API. Do not publish `design-preview/` or the repository wholesale.

### Task 1: Required app/build/site CI

**Files:** `.github/workflows/ci.yml`, `.github/dependabot.yml`, `scripts/check_workflows.py`, `tests/test_workflow_policy.py`, existing backend/frontend/package tests and dependency locks.
**Interfaces:** `ci.yml` supports `pull_request` (base main), `push` (main), and `workflow_call`; jobs have stable IDs `backend`, `frontend`, `browser`, `package`, `site`, `gate`. `gate` has display name `CI` and `if: always()`. Each required dependency result must equal `success`. Site job uploads an explicit `github-pages` artifact only for trusted main pushes. `scripts/check_workflows.py` exits nonzero on policy violations and prints concise diagnostics.

- [x] Write policy assertions for all trigger events, no PR path filters, aggregate dependency results, no `pull_request_target`, no PR write permissions, pinned external action SHAs, bounded timeouts, trusted deployment conditions and correct artifact directory. Fail a required job in a fixture and assert gate cannot pass.
- [x] Run `python -m pytest tests/test_workflow_policy.py -q`; expect failure before workflow/policy implementation.
- [x] Implement workflows with locked installs, Python 3.11/3.12 x Ubuntu/Windows backend matrix, frontend typecheck/tests/build, actual local-backend Chromium E2E and Windows packaged smoke. Use Node 24 for frontend/site builds. Reuse engine/UI/release test commands, never substitute prototype QA. Add weekly dependency update configuration for Python/npm/Actions. Cache dependency downloads, not private runtime state. Cancel obsolete PR CI; allow release runs to finish.
- [x] Run workflow policy tests, all constituent commands and an official actionlint binary. Open/check PR #3 runs at the exact latest SHA; all required jobs and `CI` must succeed before recording success. An intentional failure-policy test stays local, not an artificial failing commit. Commit `ci: validate Orion runtime UI packaging and site`.

### Task 2: Public site and gated Pages deployment

**Files:** `site/`, `.github/workflows/pages.yml`, README links and `docs/github-delivery.md` site/deploy sections.
**Interfaces:** `npm --prefix site ci`, `npm --prefix site run build`, `npm --prefix site test` produce/validate `site/dist`. Vite base is `/Orion/`. The site uses anchor/hash navigation so direct links and reloads work on static Pages without server rewrites; it includes Overview, Features, Install, Recovery/Privacy and a Demo route with sample data and an always-visible demo indicator. `pages.yml` is reusable only, consumes the `github-pages` artifact from this successful main run and declares environment `github-pages`; caller job in `ci.yml` needs `gate`, and only `push` on `refs/heads/main` can invoke it. Deployment permissions are `pages: write` and `id-token: write` in that caller/job, with contents read. Serialize deployments without cancelling one in progress.

- [x] Write browser tests at `/Orion/` for every nav link, demo fixtures, theme persistence, narrow screens, keyboard access, no horizontal overflow, missing asset responses and no requests to localhost/private media API. Assert install guidance stays usable before any release exists. Check linked local documentation exists in the built site.
- [x] Run site tests; expect missing routes/assets before implementation.
- [x] Implement the approved-style product site using actual production screenshots and licensed local assets, honest feature/install/release copy, fixture-only interactive demo, per-page titles/metadata and readable responsive content. Upload only `site/dist` using official Pages artifact tooling. Reuse Actions Pages configure/upload/deploy and verify official pinned revisions when implementing. No deployment on PRs or tag CI.
- [x] Run build/tests and browser checks at 360, 390, 768, 1280 and 1600px. Record screenshots and verify PR CI site artifact. Commit `feat: add Orion project site and gated Pages publishing`.
- [ ] Post-merge follow-up requiring the user's merge: inspect the successful Pages run, HTTPS URL, assets and interactions; deployment remains pending until those checks exist.

### Task 3: Protection, draft releases and repository runbook

**Files:** `.github/main-protection.json`, `.github/workflows/release.yml`, `scripts/verify_release.py`, `tests/test_release_policy.py`, `docs/github-delivery.md`, packaging scripts and README.
**Interfaces:** `verify_release.py --tag <tag> --version <version>` verifies a `v<version>` tag, the tag resolves to the checked-out commit and that commit is an ancestor of origin/main; exit nonzero before packaging/publishing if any assertion fails. Release workflow is tag-only (`v*`), reuses CI at the tagged SHA then builds the Windows bundle and checksum manifest, creating a draft release. `.github/main-protection.json` records the final API request: strict status checks with actual Actions app ID/context `CI`, admins enforced, PR reviews count zero, conversation resolution, no force pushes/deletion and unrestricted approved-PR merger identities.

- [x] Write release-policy tests for version mismatch, non-main tag, missing history, absent assets and checksum mismatches. Test correct tag passes validation. Run tests before adding the validator; expect failure.
- [x] Implement version/history guard, Windows artifact/checksum upload, least-privilege draft release creation after passing CI, and a reproducible repository-settings runbook. Document unsigned Windows builds and no untested native platform claims. Do not create a tag/release just to test this task without a version decision.
- [x] After PR CI emits a real successful `CI` check, resolve its GitHub Actions app ID from that check run, add it as the strict required status check through the branch API, and GET/read back the full main policy. Verify Pages mode workflow/HTTPS and environment branch restriction to main; PR/deployment workflows stay incapable of publishing other refs. Record API observations and timestamp in the runbook. Never add an admin token to repository workflow secrets for settings mutation.
- [x] Run release-policy/workflow-policy tests, full required CI, settings read-back and package checksum verification. Commit `chore: document enforceable main policy and draft releases`. Keep PR draft until all app/site scope and independent branch review are complete; retain user control over main merge and final release publication.

## Initial repository observations (2026-10-08)

The original repository had no workflows, no protection, no rulesets and no Pages site; Actions were enabled. Only Varun-SV was listed as collaborator. API updates now enforce PRs/conversation resolution/no-force/no-delete including admins, with approval count zero. Required CI is not active yet because the replacement PR still contains documentation only. Pages was created with `build_type=workflow`, URL `https://varun-sv.github.io/Orion/`, `https_enforced=true`, and no deployment status. A redundant HTTPS-setting request reported certificate not yet present; verify provisioned HTTPS after first successful deployment. Do not describe the site as live until then.

References: [protected branches API](https://docs.github.com/en/rest/branches/branch-protection), [Pages API](https://docs.github.com/en/rest/pages/pages), [custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Completed PR delivery scope (2026-10-09)

All app/site/package/workflow/protection implementation and review contracts passed at `93cb00218f0c23a7e7825c5a82bb1e180421fb81`, hosted run `37885330767`. PR #3 was marked ready after all required jobs passed. The PR artifact was downloaded and checked for the static index/assets/docs and absence of private runtime files. The single unchecked post-merge follow-up above requires the user-controlled main merge; it is not represented as a live deployment.
