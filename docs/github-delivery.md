# GitHub delivery and Windows packaging

Orion validates backend, production frontend, browser interactions, Windows packaging and the public site on every pull request targeting `main`, including draft pull requests. Changes to documentation still run the required checks. The required aggregate check is named **CI**. Its `always()` job reads all five dependency results and rejects failure, cancellation, skips and missing results.

## Local validation

Use Python 3.11 or 3.12 and Node 24 or later. CI uses Python 3.11/3.12 on Ubuntu and Windows, with Node 24 for production builds.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements-dev.lock
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts/check_workflows.py
npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix site ci
npm --prefix site run build
npm --prefix site test
```

`requirements-web.txt` and `requirements-dev.txt` are the dependency inputs. The checked-in universal locks include exact versions, platform/Python markers and package hashes. CI installs the locks with pip's `--require-hashes`. Regenerate both together with `uv pip compile --universal --python-version 3.11 --generate-hashes`, review the resulting versions and hashes, then rerun validation. Do not hand-edit a hash to accept an unexpected package.

Production browser QA starts the actual local backend, uses generated media and an isolated data directory, and saves screenshots/report evidence. Install the Playwright Chromium browser before running locally. Windows can use installed Edge by setting `BROWSER_CHANNEL=msedge`; CI uses Chromium.

```powershell
$env:ORION_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
$env:BROWSER_CHANNEL = 'msedge'
$env:ORION_QA_OUTPUT = 'test-results/production-browser'
node scripts/browser_qa.mjs
```

External Actions use immutable full commit SHAs with readable major-version comments. The pins were resolved from official `actions/*` repositories on 2026-10-09. Default token permission is `contents: read`; checkout credentials are never persisted. Pull requests receive no deployment or release write permission, and no workflow uses `pull_request_target`. Dependency download caches contain no user media, catalogue, credentials or application data.

Workflow policy tests mutate real parsed workflows and prove unsafe triggers, permissions, unpinned Actions, missing uploads/guards, unrestricted deployment and failed required jobs are rejected. Validate workflow syntax using the [official actionlint release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12); verify its archive against the release's checksum manifest before running it. The locally verified official Windows amd64 binary is a build tool, not a tracked runtime dependency.

## Standalone Windows bundle

Build on Windows x64. The bundle serves `frontend/dist` and the local API with its bundled Python runtime. Node, Qt and an installed Python interpreter are unnecessary on the target machine. Source operation on other platforms remains available; native macOS/Linux installers have not been validated.

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python scripts/build_package.py
.venv\Scripts\python scripts/smoke_package.py --executable dist/Orion/Orion.exe --output test-results/package-smoke.json
.venv\Scripts\python scripts/archive_package.py --bundle dist/Orion --output dist/release
.venv\Scripts\python scripts/verify_release.py --assets dist/release
```

The build validates index-linked assets, snapshots the production frontend to avoid concurrent Vite rebuilds, and bundles resources under `Orion/_internal/frontend`. The smoke runs the executable with an empty system PATH and generated temporary data; verifies API health, every bundled static file, actual database creation, repeated launch reuse, occupied-port failure and graceful shutdown; rejects bundled Qt resources; and records measured startup and uncompressed size. Archive output must be empty to avoid accidentally publishing stale assets. The ZIP contains the entire `Orion` directory and `SHA256SUMS.txt` covers every release asset.

Extract the entire ZIP into a new directory, retaining `_internal`. Start `Orion.exe`; it opens the local browser. Console output shows the loopback address and explains an occupied port. `Orion.exe run --data-dir "D:\OrionData" --port 0 --no-browser` uses an explicit data directory and an automatically chosen local port. `Orion.exe stop --data-dir "D:\OrionData"` stops that instance. The default data directory is `%APPDATA%\Orion` on Windows. The executable is unsigned; this project has no code-signing certificate.

Before upgrade, stop Orion and back up the **whole data directory**, including `organizer.db`, preferences and any migration/recovery backups. Install a new bundle in a separate application directory. Keep application files and persistent data separate. The app's schema migration creates a backup before changing an existing legacy database. On interruption, reopen the same data directory and review recovery results before another organisation job. Undo preserves files changed externally. Credentials use the configured OS keyring and are not contained in media exports or release assets; keyring availability still depends on the OS user session. Optional `fpcalc` fingerprinting remains a separately installed tool. Jellyfin/Emby integrations require user-supplied server details and have fixture validation; live-server verification is recorded separately. Plex is not implemented.

## Pages deployment

The product site builds at `/Orion/` into `site/dist`, uses fixture-only demo data and hash/anchor routes suitable for static hosting, and never connects to the local media API. The `site` job uploads the explicitly named `github-pages` artifact using official Pages tooling only for a `push` to `refs/heads/main`. The reusable Pages workflow is called only after `CI` passes. Its deploy job repeats the main-push guard, declares environment `github-pages`, grants only `pages: write`, `id-token: write` and `contents: read`, and serializes deployments without cancelling an in-progress deployment. PR runs and release-tag validation cannot deploy.

The configured URL is [https://varun-sv.github.io/Orion/](https://varun-sv.github.io/Orion/). Pages enablement alone is not deployment evidence. Until a main merge, successful deployment run and HTTPS/asset/interaction checks are recorded, deployment is pending. Repository Pages source must have `build_type=workflow`; the `github-pages` environment must permit deployments only from `main`.

## Draft release guard

`release.yml` responds only to `v*` tag pushes. The guard fetches full history and verifies that `v<runtime version>` exists, resolves to the checked-out commit, and is an ancestor of `origin/main`. It rejects version mismatch, absent main history and branch-only commits before CI/packaging or publication. The read-only `validation.yml` workflow runs the same five required jobs and aggregate at the tag commit. The policy validator enforces equality with the direct CI jobs (excluding the main-only Pages upload), and checks nested permission ceilings. This prevents a tag caller from requesting Pages/id-token write permission through a skipped nested deployment job. CI is validated at the tag commit; publishing requires guard, complete CI and checked package assets. The Windows artifact comes from that same run and is verified again before publication. `create_draft_release.py` rechecks history/checksums, forces `gh release create --verify-tag --draft`, and cannot create a tag. Release publication remains a human action. No tag or release is created merely to test the workflow.

For an approved existing tag, guard/checksum validation can be run without publishing:

```powershell
python scripts/verify_release.py --tag v0.2.0 --version 0.2.0
python scripts/verify_release.py --assets dist/release
```

Do not run the tag example unless that tag has actually been approved and created on merged main history.

## Main protection runbook and observed state

Initial read/write-back on 2026-10-08: main protection enforces administrators, requires pull requests and resolved conversations, disallows force pushes and deletion, and uses zero required approving reviews while the repository has one collaborator. Required status checks were deliberately unset while PR #3 contained documentation only. Pages was enabled with workflow mode and HTTPS requested; no successful deployment had occurred. `.github/main-protection.json` records this interim request with `required_status_checks: null` until an actual successful aggregate check exists.

After the latest PR commit emits a successful `CI`, query its check runs, record the real check's name and `app.id`, and update `.github/main-protection.json` to `required_status_checks: {"strict": true, "checks": [{"context": "CI", "app_id": <observed Actions app id>}]}`. Apply the complete policy through the protected-branch API, then GET it back and verify every requirement. Never invent a check name/app ID or store a settings/admin token in workflow secrets. The approved-PR merger identities remain unrestricted; administrator enforcement remains enabled.

Read-only verification commands (run with a separately authenticated maintainer CLI):

```powershell
gh api repos/Varun-SV/Orion/commits/<exact-PR-head-sha>/check-runs
gh api repos/Varun-SV/Orion/branches/main/protection
gh api repos/Varun-SV/Orion/pages
gh api repos/Varun-SV/Orion/environments/github-pages
gh api repos/Varun-SV/Orion/environments/github-pages/deployment-branch-policies
```

Record the UTC observation time, exact commit/run/check IDs, app ID and read-back evidence in the validation report after applying protection. Following user-controlled merge, inspect the Pages workflow and deployment, then check HTTPS URL, referenced assets, `/Orion/` navigation/reload, demo interactions and narrow-screen behavior. Do not describe a pending site as live.

Official references: [Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [branch protection API](https://docs.github.com/en/rest/branches/branch-protection), [PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html).

### Observed Windows package validation (2026-10-09)

The local Windows x64 smoke measured **1.982 seconds** from executable launch to API readiness, **57,050,775 bytes** unpacked bundle size, and **30,207,115 bytes** for the ZIP. This is a single observed run on this PC, not a performance guarantee or a comparison against the previous app. The executable served the actual production index and 51 other bundled static files with matching bytes, created an isolated database, reused an existing instance, rejected an occupied port and exited cleanly through its packaged stop command. The smoke environment had an empty system PATH and found no Qt resources. See [package-smoke.json](validation/package-smoke.json).

The ZIP SHA-256 is `4f00919b4dffbe889ce8d4ef28a716eff41c0a5762a4fea6c0dd00009c295cc4`. It exists locally under `dist/final-release`; no tag, GitHub release or published download was created for validation. CI will rebuild and verify the artifact from its exact checked-out commit.
