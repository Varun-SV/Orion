# Public project site validation — 9 October 2026

Scoped implementation of task 2 in `docs/superpowers/plans/2026-10-08-orion-github-delivery.md`. GitHub workflows, repository settings and final integration are owned by the parent delivery task.

The public site is an independent Vite build at `/Orion/`, with Overview, Features, Install, Recovery & privacy and Demo hash routes. It uses the approved ivory, clay and night tokens, locally bundled Newsreader/IBM Plex Sans, actual production screenshots and seven explicitly fictional sample collections. The static site does not import the installed runtime or call its API. Source installation guidance remains usable without a published release, and there are no invented installer URLs.

## Test-first record

The initial empty site build ran successfully and the first browser requirement failed waiting for the missing Primary / Overview navigation link. The implementation followed that observed failure. A subsequent build exposed a multiline JavaScript install-command string parse error; `node --check` located it, and the string was corrected before browser verification. The complete initial eight-test suite then passed. Further checks covered scroll-visible demo labelling, action request isolation, all three themes, standalone documents and keyboard route activation. A final skip-link fragment reload regression failed with an empty page, then passed after the renderer was corrected to render initial content before applying skip-link focus.

Ruling: use lightweight HTML/JavaScript with Vite rather than React/TypeScript — this is explicitly permitted by the delegated plan and keeps this static site independent of the installed app. Commit/push, shared runbook changes, Actions publication and first live deployment remain with the parent delivery task.

## Fresh final commands and observed results

- `npm --prefix site ci`: 18 packages installed, zero audit findings.
- `npm --prefix site run build`: passed; only five source modules transformed. The explicit distribution is 404,045 bytes including local fonts, font licences, three production screenshots and standalone documentation. Generated JS is 16.60 kB (6.39 kB gzip); CSS is 13.73 kB (3.70 kB gzip).
- `npm --prefix site test -- --reporter=list,json`: **16 passed**, with installed Edge 154.0.4258.62 and Node 25.9.0 on this Windows PC. CI is configured separately to use Node 24 / Playwright Chromium.
- Screenshot capture: `SITE_CAPTURE_SCREENSHOTS=1 npm --prefix site test -- --grep "sample actions"`: **5 passed**, capturing overview/demo at 360, 390, 768, 1280 and 1600px.

For Windows, the browser command sets `PLAYWRIGHT_EXECUTABLE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`. Linux CI installs Chromium using `npm --prefix site exec -- playwright install --with-deps chromium`. The suite builds the real static artifact and serves it at `http://127.0.0.1:4174/Orion/`, with no app backend or API response interception. The inherited terminal's NO_COLOR/FORCE_COLOR disagreement emits environment warnings; production builds have no asset or parse warnings.

## Covered behavior

- Every primary navigation link, route title, active state, direct hash URL and browser reload at the repository prefix.
- Keyboard activation of every primary route, skip-to-main focus, native keyboard collection activation and reduced motion.
- Persisted clay/night choices, ivory/clay/night demo actions at every requested width.
- All seven fixture collections, search/empty state, source/destination preview, simulated completion and reset.
- Fixture indicator remaining inside the viewport after scrolling to the bottom at all five widths and three themes.
- No horizontal overflow, broken production images, missing asset responses, failed asset requests or uncaught browser errors across all five routes at each width.
- No outbound requests beyond the local `/Orion/` artifact, including while simulating organisation. No localhost media API requests and no visitor filesystem access.
- Local installation/recovery/licence documentation and licence downloads exist in the built artifact. There are no nonexistent executable/download links.

## Evidence

The desktop overview, narrow overview and narrow demo were opened and visually inspected. Screenshot captures start at scroll position zero to avoid Edge full-page capture placing sticky/fixed elements at an earlier scrolled viewport.

- [Overview at 360px](screenshots/site-overview-360.png)
- [Overview at 390px](screenshots/site-overview-390.png)
- [Overview at 768px](screenshots/site-overview-768.png)
- [Overview at 1280px](screenshots/site-overview-1280.png)
- [Overview at 1600px](screenshots/site-overview-1600.png)
- [Demo at 360px](screenshots/site-demo-360.png)
- [Demo at 390px](screenshots/site-demo-390.png)
- [Demo at 768px](screenshots/site-demo-768.png)
- [Demo at 1280px](screenshots/site-demo-1280.png)
- [Demo at 1600px](screenshots/site-demo-1600.png)
- [Machine-readable final browser results](screenshots/site-browser-results.json)

Production imagery is copied explicitly from the existing connected-runtime validation screenshots. These pictured files are generated fixtures, not personal media. Fonts include their SIL Open Font License text.

## Verification limits

This records local Windows Edge validation, not a GitHub CI run or live GitHub Pages deployment. The first successful main deployment, public HTTPS URL, live asset checks and live interactions remain pending the user-controlled merge and delivery workflow. Live authenticated providers/server connections and native packages are not tested by the public demo.

