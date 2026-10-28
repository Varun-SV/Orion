# Orion observatory website design

Date: 2026-10-28. The user selected the proposed cinematic observatory direction, natural scrolling with expressive reveals and parallax, and an interactive organising demonstration as the first experience. They also require animated pages and documentation hosted on GitHub Pages without routing readers to GitHub for the guides.

## Experience

The public site at `/Orion/` becomes a midnight observatory for a personal media library. Deep ink surfaces, teal light, fine constellation lines, oversized editorial typography and precise monospace annotations form the visual identity. Motion describes media moving from scattered incoming files into a considered library. The initial viewport contains a usable, explicitly labelled sample demonstration alongside the headline; visitors can preview, simulate organisation, switch sample collections and reset. It never accesses local files or the installed app's API.

The homepage progresses through the interactive demonstration, local/review/no-overwrite principles, the scan-review-preview-organise workflow, seven collections, a real product screenshot and documentation/install calls to action. The existing Features, Install, Recovery & privacy and Demo destinations remain useful complete pages. All routes share the new visual system and animated entrances/transitions. The current ivory and clay preferences remain supported; night is the new default.

## Motion

Use natural browser scrolling, layered reveals, small bounded parallax, slowly moving constellation/orbital details and deliberate button/demo feedback. No scroll hijacking, forced timing, autoplay audio or blocking intro. View transitions progressively enhance navigation and have a simple CSS fallback. A persistent pause control and `prefers-reduced-motion` disable decorative animation and parallax while keeping every function usable. Offscreen animation is paused and event/observer lifecycle is bounded.

## Documentation

Create a real `/Orion/docs/` index and static deep-linked `.html` guide pages, preserving install/recovery/licenses URLs. Include getting started, installation, first workflow, collections, naming/output, providers/consent, Jellyfin/Emby, runtime data, recovery, troubleshooting, developer delivery and licences. Build from local Markdown plus authoritative existing repository guides. No production network renderer, CDN, telemetry or secret-bearing sample configuration is needed.

Docs use the same dark visual identity, a responsive sidebar, local full-text search, an in-page contents list, copy-code buttons and previous/next navigation. Their text is present in built HTML, so deep reloads and reading work without JavaScript. Search and code-copy work with enhancement scripts; failures are visible. Local guide links remain within `/Orion/docs/`; explicit external references and the labelled repository link may leave the site. A home search may enter `/Orion/docs/?q=...` and should show the matching guide results.

## Implementation choices

Extend the existing Vite/vanilla ES modules instead of introducing an application framework. Use native SVG/CSS/Web Animation APIs for the observatory and interface, keeping artwork exact and light. Use a pinned build-time Markdown compiler for robust guide generation. The compiled site remains a self-contained static Pages artifact. No backend application changes or release publication are required.

The alternatives offered were warm editorial or luminous futuristic styling, pinned chapters or mixed scrolling, and feature-story or installation-first entry. The user's MCQ selections establish the chosen direction above. Routine composition, implementation and verification details are delegated to the builder.

## Acceptance

- Responsive, visually reviewed layouts at 360, 390, 768, 1280 and 1600 pixels, with no horizontal overflow or clipped interaction.
- A complete labelled fixture workflow, all seven demo collections, keyboard navigation, accessible focus and errors, search, preview, simulation and reset.
- Working local docs links, static deep reloads, search results and code-copy feedback; no guide navigation to GitHub Markdown.
- Night by default, persistent existing theme choices, decorative-motion pause and reduced-motion behavior.
- No missing assets, page errors, private API calls or unexpected external requests.
- Appropriate unit/build/link checks and the complete browser suite, independent review, required hosted CI and a verified Pages deployment.
