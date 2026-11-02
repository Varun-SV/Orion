# Constellation site validation

The public site was rebuilt as a scroll-driven 3D flight through Orion's real star field (design: `docs/superpowers/specs/2026-11-02-orion-constellation-design.md`). This records what was actually run and what was not.

## Local evidence

- Site unit tests: **14 passed** (6 existing documentation-generator tests and 8 new tests for star data, scroll director and quality governor). The director test walks every scroll pixel across all chapter boundaries and fails on any backwards step or jump; the world test walks the whole flight and fails on any non-finite or discontinuous camera or state value.
- Playwright suite against the production build: **40 passed** in 2.8 minutes with software WebGL. It covers scene start-up with no console, page or network errors; the headline being readable with the 3D chunk blocked; every chapter activating in order; the seven stars mapping to the seven collections (list, scroll and clicking a star in the sky); pause stopping the render loop; recovery from a lost WebGL context; the SVG fallback with WebGL removed (chapters, sample and overflow); reduced motion; no horizontal overflow or clipped headings at 360, 390, 768, 1280 and 1600px; the mobile menu; hash routes after reload; truthful install claims with no release download linked; the sample making no request outside the site or to the local app; and the existing documentation, search and licence tests.
- Production bundle: the page's entry JavaScript is 10.9 KB gzip and its CSS 5.4 KB gzip. The three.js scene is a separate lazily loaded chunk of 134.9 KB gzip, started after first paint. The headline and every fact are HTML, so nothing waits on it.

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
