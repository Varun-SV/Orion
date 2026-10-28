# The seven collections

Orion keeps seven distinct collections so each can use suitable metadata and naming defaults. A folder scan can infer a collection from its configured category or source choice; check the collection during review rather than relying on folder names alone.

| Collection | Typical items | Identification notes |
| --- | --- | --- |
| Movies | Feature films and editions | TMDb candidates; review title, year and edition. |
| TV series | Episodic television | TMDb candidates; confirm series and episode details. |
| Anime | Anime series | AniList or AniDB, with TMDb also available. |
| Anime films | Anime feature films | AniList or AniDB, with TMDb also available. |
| Web series | Episodic online series | TMDb candidates; review series and episode evidence. |
| Music | Audio tracks and album folders | MusicBrainz; optional AcoustID or AudD identification has additional requirements and consent. |
| Books | Book files | Open Library candidates; review author, title and series. |

The provider list is a compatibility list, not a guarantee that a match exists. A lookup may return no candidates or an unavailable-provider error. You can edit and confirm metadata manually. See [provider setup and consent](./providers.html).

For a first run, choose a small source containing a single collection. Scan it, review a few items, and create a preview before adding more folders. Keep distinct source and destination locations. If you organise music or books in place, the preview must still be reviewed carefully; in-place renaming is limited to those two collections.

For collection-specific output behavior, see [naming and output](./naming.html). The [Jellyfin and Emby guide](./integrations.html) describes optional library hints and refresh requests; a media server is not required to use any collection.
