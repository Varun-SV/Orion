# Orion: a media universe

The user rejected the previous presentation after comparing it with EviCortex. They now explicitly chose a **more original and dramatic** design and a **visual-first opening**, with the interactive demo immediately below. Midnight/teal, natural scrolling, animated pages and on-site documentation remain requirements.

## Approach

Three directions were offered: follow EviCortex closely, create a more original dramatic presentation, or prioritise restrained product clarity. The user selected the second. A dashboard panel in the hero competed with the headline and left the scene as background decoration. Replace that composition with an open, spatial media constellation: a luminous orbital nucleus, floating original fictional cover artwork, larger readable labels and a short headline. Narrow screens use a compact expandable navigation menu. Use EviCortex's compositional confidence and pacing, not its layout or code.

## Experience

- Hero: “Make room. For everything.” Big sans/italic serif type, open space, teal eclipse and orbiting film/music/book artwork. “Explore Orion” scrolls naturally to the sample; “Get started” opens installation.
- First section below: the existing fully working sample, with a clear heading and fictional-data disclosure. No duplicate sample IDs.
- Collection gallery: seven accessible selectors, a large changing cover and a direct route into the corresponding sample collection. Original SVG/CSS art, no external assets.
- File journey, product UI, docs and closing sections retain truthful content, but use greater scale, fewer small decorative labels, clearer contrast and purposeful motion. Secondary pages share the same composition and typography.
- Docs stay on GitHub Pages with existing static content, search, theme controls and local navigation.

## Implementation choices

Keep vanilla ESM/Vite and the current base URL `/Orion/`. Keep the existing scene API and Canvas fallback. Use local SVG/CSS art and Canvas2D for the spatial scene; no new dependency or runtime CDN. Animation stops offscreen, on hidden tabs, on explicit pause and for reduced motion. Pointer parallax applies only to fine pointers and running motion. Keep normal scrolling and keyboard controls. Existing route, theme and demo behavior remain compatible.

## Acceptance

Visually inspect desktop and mobile compositions, not only DOM assertions. Verify sample preview/simulate/reset, all seven gallery destinations, keyboard activation, route cleanup, canvas fallback, pause/reduced motion and no horizontal overflow at 360/390/768/1280/1600px. Run the whole site suite and documentation generator tests, then all required repository CI before the already-authorized merge/deployment.
