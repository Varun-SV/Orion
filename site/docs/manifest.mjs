export const docsManifest = [
  {
    slug: "index",
    title: "Documentation",
    source: "site/docs/index.md",
    description: "Start here: install Orion and organize your first files.",
  },
  {
    slug: "install",
    title: "Install Orion",
    source: "site/docs/install.md",
    description: "Requirements, build and launch instructions.",
  },
  {
    slug: "workflow",
    title: "First workflow",
    source: "site/docs/workflow.md",
    description: "Scan, review, preview and organize safely.",
  },
  {
    slug: "collections",
    title: "Collections",
    source: "site/docs/collections.md",
    description: "Understand the seven destination collections.",
  },
  {
    slug: "naming",
    title: "Naming and output",
    source: "site/docs/naming.md",
    description: "Configure filenames and output folders.",
  },
  {
    slug: "providers",
    title: "Providers and consent",
    source: "site/docs/providers.md",
    description: "Optional metadata, fingerprints and credentials.",
  },
  {
    slug: "recovery",
    title: "Recovery and privacy",
    source: "site/docs/recovery.md",
    description: "Backups, restore and local data.",
  },
  {
    slug: "troubleshooting",
    title: "Troubleshooting",
    source: "site/docs/troubleshooting.md",
    description: "Resolve common setup and workflow issues.",
  },
  {
    slug: "runtime",
    title: "Runtime data",
    source: "docs/runtime.md",
    description: "Application data and database lifecycle.",
  },
  {
    slug: "integrations",
    title: "Jellyfin and Emby",
    source: "docs/integrations.md",
    description: "Configure local media server integrations.",
  },
  {
    slug: "github-delivery",
    title: "Developer delivery",
    source: "docs/github-delivery.md",
    description: "Validation, CI and GitHub Pages delivery.",
  },
  {
    slug: "licenses",
    title: "Licences",
    source: "LICENSE",
    description: "Project license and third-party notices.",
    supplementalHeading: "Font licences",
    supplemental: [
      {
        title: "Newsreader",
        label: "Newsreader",
        source: "site/public/fonts/NEWSREADER-LICENSE.txt",
        href: "/Orion/fonts/NEWSREADER-LICENSE.txt",
      },
      {
        title: "IBM Plex Sans",
        label: "IBM Plex Sans",
        source: "site/public/fonts/PLEX-LICENSE.txt",
        href: "/Orion/fonts/PLEX-LICENSE.txt",
      },
    ],
  },
];

export const docsAssets = [
  {
    source: "docs/validation/package-smoke.json",
    filename: "package-smoke.json",
  },
  {
    source: "docs/validation/github-settings.json",
    filename: "github-settings.json",
  },
];
