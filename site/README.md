# Orion public project site

Standalone Vite site, served at the GitHub Pages repository prefix `/Orion/`.
Hash routes: Overview, Features, Install, Recovery & privacy and Demo.
The demo is fictional fixture data and makes no API requests or filesystem changes.

```sh
npm --prefix site ci
npm --prefix site run build
npm --prefix site exec -- playwright install --with-deps chromium
npm --prefix site test
```

CI uses Node 24 and Playwright Chromium. For local Windows verification with an installed Edge, set `PLAYWRIGHT_EXECUTABLE_PATH` to its absolute executable path before testing. Tests build the production artifact and serve it at `http://127.0.0.1:4174/Orion/`.

Only `site/dist` is published. Local fonts and production screenshots are copied intentionally into `public/`; no runtime import depends on the app or its private API. Font licences are included in `public/fonts/`. Generated test results, dependencies and the distribution are ignored.

Screenshots show the production app using generated media fixtures, with no personal media. The interactive demo uses its own explicitly labelled fictional fixtures. The approved prototype in `design-preview/` is not part of this site.

