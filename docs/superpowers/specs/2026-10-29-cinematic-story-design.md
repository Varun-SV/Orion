# Orion cinematic product story

The user supplied their EviCortex site as the standard for Orion's design and animation. This refines the already selected midnight/teal observatory direction, natural scrolling, interactive media demonstration, and on-site documentation.

## Experience

Use EviCortex's expressive typography, floating navigation, cinematic spatial visual, and explanatory scroll narrative as a reference. Build original Orion visuals and copy around media organisation. Keep all current working routes, seven demo collections, twelve local documentation guides, themes, and motion preferences.

The homepage opens with a large sans-serif/italic-serif headline, a locally rendered animated orbital field, and the existing working organising sample. A four-chapter sticky story turns scattered fictional files into reviewed metadata, an exact plan with conflict awareness, and an organised library with a journal. Visitors can choose a chapter directly or let natural scrolling advance the illustration. Existing product screenshots and specific feature explanations remain available below the story.

Search is available from the header and Ctrl/Cmd+K on showcase and guide pages. It searches the existing local index, supports keyboard use, and links directly to on-site guides. Documentation remains static HTML readable without JavaScript.

## Implementation choices

Extend the existing Vite/vanilla JavaScript site. Render the decorative orbital scene using Canvas 2D with an SVG fallback; no new runtime dependencies, externally hosted scripts, scroll interception, or WebGL requirement. Use bounded pointer/scroll effects, CSS transitions, and requestAnimationFrame. Pause offscreen/hidden animation; honor both the stored motion preference and the OS reduced-motion setting.

We considered merely increasing existing reveals, which would not provide the explanatory narrative the reference demonstrates, and a Three.js/GSAP recreation, which would add complexity without improving Orion's organising explanation. The chosen approach uses the reference's storytelling and visual ambition within Orion's existing architecture.

## Requirements and boundaries

- The first viewport contains the interactive sample at desktop widths.
- Every simulation remains explicitly fictional and moves no personal files.
- Every chapter remains readable without animation; controls remain functional when motion is paused.
- Fit 360, 390, 768, 1280, and 1600 pixel viewports without horizontal page overflow.
- Search content is inserted as text, and result links stay under `/Orion/docs/`.
- Existing app/backend behavior and release status claims remain accurate.
- Merge through the protected main workflow after checks, then verify GitHub Pages.

## Verification

Run the complete production site browser suite and documentation generator tests. Add meaningful interaction checks for story selection/scroll, keyboard search, reduced motion, and Canvas fallback. Review responsive screenshots, run repository policy checks, and require all GitHub CI checks before merging.
