import { defineConfig } from "vite";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { docsAssets, docsManifest } from "./docs/manifest.mjs";
import { generateDocs } from "./scripts/generate-docs.js";

const siteDir = path.dirname(fileURLToPath(import.meta.url));
const repoDir = path.resolve(siteDir, "..");
const generatedDir = path.join(siteDir, ".generated", "docs");

function documentationPlugin() {
  let generated;
  const prepare = () =>
    (generated ??= generateDocs({
      sourceDir: repoDir,
      outputDir: generatedDir,
      manifest: docsManifest,
      assets: docsAssets,
    }));
  return {
    name: "orion-static-documentation",
    async buildStart() {
      await prepare();
    },
    async generateBundle() {
      await prepare();
      for (const name of await readdir(generatedDir)) {
        this.emitFile({
          type: "asset",
          fileName: `docs/${name}`,
          source: await readFile(path.join(generatedDir, name)),
        });
      }
    },
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url || "/", "http://localhost");
        let pathname = decodeURIComponent(url.pathname);
        if (pathname.startsWith("/Orion/"))
          pathname = pathname.slice("/Orion".length);
        if (pathname === "/docs" || pathname === "/docs/")
          pathname = "/docs/index.html";
        if (!pathname.startsWith("/docs/")) return next();
        try {
          await prepare();
          const name = path.basename(pathname);
          const allowed = new Set([
            "search-index.json",
            ...docsAssets.map(
              (asset) => asset.filename ?? path.basename(asset.source),
            ),
          ]);
          if (!/^[a-z0-9-]+\.html$/i.test(name) && !allowed.has(name))
            return next();
          const body = await readFile(path.join(generatedDir, name));
          res.statusCode = 200;
          res.setHeader(
            "Content-Type",
            name.endsWith(".json")
              ? "application/json; charset=utf-8"
              : "text/html; charset=utf-8",
          );
          res.end(body);
        } catch (error) {
          next(error);
        }
      });
    },
  };
}

export default defineConfig({
  base: "/Orion/",
  plugins: [documentationPlugin()],
});
