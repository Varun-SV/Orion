# Naming and generated output

Orion creates an immutable preview from confirmed metadata, a destination and a saved naming preset. Review the full relative path for each item before approval. Paths are constrained to remain inside the selected root; invalid or incompatible templates block planning.

## Presets and versions

Each collection starts with a default preset. You can create or edit presets in Naming settings. A preset is collection-specific or set to auto, and includes templates for files, folders and episodes, plus switches for NFO metadata, artwork and episode NFO output. Quality tags can include screen size, video/audio codec, channels, source, release group and edition.

Templates support fields such as `{title}`, `{year_suffix}`, `{ext}`, `{quality}`, `{season:02d}`, `{episode:02d}`, `{episode_title_suffix}`, `{artist}`, `{album}`, `{track_prefix}`, `{author}` and `{series_path}`. Keep `{ext}` in file templates: Orion requires the original media extension to be preserved. A fictional default movie result is `Arrival (2016)/Arrival (2016).mkv`; a fictional episode result is `Example series/Season 01/Example series - S01E03.mkv`.

Saving a preset creates a new version. A preview records the preset version used when it was created, so later edits do not silently change an existing plan. Reload if Orion reports the profile version changed, then create and review a fresh preview.

## Conflicts and safety

The plan preview shows conflicts before execution. Orion never replaces an existing file. Depending on the operation, choose a supported conflict action such as block, skip the affected item, or keep both with a generated available name. Skip leaves the whole item and its companions at the source. A changed file, occupied destination or stale preview requires resolving the issue and creating or revalidating a preview again.

## Sidecars and artwork

NFO, artwork and episode NFO are off by default. Enable them in the preset only when wanted, then inspect each generated output in the preview. Existing sidecars are preserved. Optional outputs use exclusive creation and are recorded for recovery. Artwork comes only from supported credential-free HTTPS provider sources; unavailable artwork is reported rather than fabricated.

Episode NFO details rely on a fresh local episode catalogue cache. Refresh the catalogue through Episode gaps before previewing if you need provider episode titles or dates. Missing or stale cache data produces a warning; it does not invent episode identifiers. Learn about [provider credentials](./providers.html) and [recovery of generated output](./recovery.html).
