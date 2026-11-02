# Constellation site validation

The public site was rebuilt as a scroll-driven 3D flight through Orion's real star field (design: `docs/superpowers/specs/2026-11-02-orion-constellation-design.md`). This records what was actually run and what was not.

## Local evidence

- Site unit tests: **15 passed** (6 existing documentation-generator tests and 9 new tests for star data, scroll director, damping and quality governor). The director test walks every scroll pixel across all chapter boundaries and fails on any backwards step or jump; the world test walks the whole flight and fails on any non-finite or discontinuous camera or state value.
- Playwright suite against the production build: **46 passed** with software WebGL. It covers scene start-up with no console, page or network errors; the headline being readable with the 3D chunk blocked; every chapter activating in order; the seven stars mapping to the seven collections (list, scroll and clicking a star in the sky); pause stopping the render loop; recovery from a lost WebGL context; the SVG fallback with WebGL removed (chapters, sample and overflow); reduced motion; no horizontal overflow or clipped headings at 360, 390, 768, 1280 and 1600px; the mobile menu; hash routes after reload; truthful install claims with no release download linked; the sample making no request outside the site or to the local app; and the existing documentation, search and licence tests.
- Production bundle: the page's entry JavaScript is 10.9 KB gzip and its CSS 5.4 KB gzip. The three.js scene is a separate lazily loaded chunk of 134.9 KB gzip, started after first paint. The headline and every fact are HTML, so nothing waits on it.

## Review round 1 (Codex)

Three valid findings, each fixed with a regression test:

- Anchor links landed on a chapter whose text was still at zero opacity. Text is now fully visible once its chapter is pinned and fades in while the chapter scrolls up into view. New test follows the nav links and reloads each hash route and checks the panel's computed opacity.
- Changing collection cut the camera by about six world units. The focus position now follows the chosen star through a frame-rate-independent damper (unit-tested), and snaps only for reduced motion.
- On a landscape phone the pinned chapters clipped their controls. A short-viewport layout (two-column collections, tighter type) keeps every control inside the screen. New tests check 844x390, 667x375 and 740x360 for each pinned chapter. The same check showed the nebula over-exposed on short screens, so point sizes now follow screen height.

## Review round 2 (Codex)

One valid finding: loading with a saved pause preference (or pausing during the opening) left the opening reveal at zero, so the stars, lines, nebula and star labels never appeared. The opening is decorative, so when motion is not running it now completes at once and the finished sky is shown. Two new tests (saved preference at load, and pausing mid-opening) fail without the change and pass with it.

## CI timing

The first CI run of the site job failed one docs-search test (45 of 46 passed): the software-rendered 3D scene kept the two-core runner busy long enough for a keyboard navigation to miss a 5 second wait. The application was not at fault. Tests that are not about the scene now start with animations paused, the site job runs one worker, and the default expect timeout is 10 seconds. The full suite passed locally with one worker (46 of 46 in 3.1 minutes).

## Star data

All eight star positions (right ascension and declination) were compared with the Wikipedia "List of stars in Orion" and the individual star articles for Alnilam, Mintaka and Meissa. Coordinates agree to the precision stored (0.0001 hour, 0.0001 degree). Magnitudes are rounded and several of these stars are variable, so they only scale how large a star is drawn. The seven collections map to the seven brightest stars, in the order Betelgeuse, Bellatrix, Mintaka, Alnilam, Alnitak, Saiph, Rigel.

## Visual inspection

Rendered 1440px and 390px screenshots of every chapter were inspected, plus 768px and 1600px views. Problems found and corrected: a headline line that was invisible because gradient text does not paint through animated inline-block words; star labels that inherited a pill style from the sample tag; labels crossing body text after the collections chapter; the constellation sitting under the headline on phones; and a hero too narrow for its type size. Evidence: `screenshots/constellation-landing-1440.png`, `constellation-collections-1440.png`, `constellation-landing-390.png`.

## Limits

- This environment has no GPU. All rendering here is software WebGL: about 230 ms per frame at 1440 by 900, which made the quality governor step down to its lowest tier as designed. **No real-GPU frame rate was measured, and no frame-rate claim is made.** The scene was built within a budget (about 12 000 file particles, 1 100 nebula sprites, under 15 draw calls, no per-frame allocation in the loop) and adapts at run time, but the first real-device check should be done by opening the deployed page on a laptop and a phone.
- Only Chromium was exercised. Firefox and Safari were not run.
- Live authenticated providers and media servers are not touched by the site.

## Review and deployment gate

The branch merges only through the repository's protected-branch rules: the aggregate CI check must pass and review conversations must be resolved. Publishing uses the existing Pages deployment; no application code, protection settings, releases or provider connections change.
