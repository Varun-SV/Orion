# Optional media-server integration

Orion can organise local files with no server connection. In Connections, enable Jellyfin or Emby, enter the API base URL (including a reverse-proxy or `/emby` prefix when applicable), and save the settings. Replace the API key through the write-only credential field. It is stored in the OS keychain; session-only storage is an explicit fallback. Test the saved connection, select your own user, and save that choice. Orion never takes the first account automatically.

Discovery and review hints use paginated recursive library queries, requesting provider IDs, paths and media stream evidence in those pages. A title, provider ID or version label is evidence for review, not a content hash or permission to delete. Authentication errors, repeated/truncated pages and unreachable servers fail explicitly. Server changes invalidate cached hints. Transport credentials and credential-bearing remote URL components are excluded from persisted server results.

Episode gaps require an explicitly confirmed numeric TMDb series mapping. The view separates aired missing episodes, unaired episodes, unknown air dates and specials. Multi-episode files count across their recorded range; virtual placeholders do not count as existing files. Season catalogues are cached for one hour and fetched per season. Incomplete or unavailable catalogues produce an unavailable report with no invented missing season. Reports include episode titles, dates and saved outcomes.

Automatic refresh is off by default. Enabling it queues an independent refresh job after a fully successful organisation batch. Retry that job in Jobs if it fails; successful file changes remain recorded. “Accepted” means the server accepted a refresh request, not that its scan finished. Changing server/user settings makes previously queued work require a new request; credential replacement permits retry against the same server context.

## API contracts checked on 2026-10-09

- [Jellyfin current authorization source](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Server.Implementations/Security/AuthorizationContext.cs): modern `Authorization: MediaBrowser` is used alongside the compatibility token header, so legacy-header mode is not required.
- [Jellyfin item query controller](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/ItemsController.cs): explicit user context, recursive queries, start index, limit and requested fields.
- [Jellyfin refresh controller](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs): refresh request acceptance.
- [Emby API key authentication](https://dev.emby.media/doc/restapi/API-Key-Authentication.html), [item queries](https://dev.emby.media/reference/RestAPI/ItemsService/getItems.html), and [refresh](https://dev.emby.media/reference/RestAPI/LibraryService.html).
- [TMDb series](https://developer.themoviedb.org/reference/tv-series-details) and [season details](https://developer.themoviedb.org/reference/tv-season-details).

Local HTTP fixtures cover both adapter types, 125-item pagination, metadata, user context, modern authorization, unavailable results, independent refresh retry and secret exclusion. No personal live server or authenticated TMDb catalogue has been supplied, so these checks do not establish live-server compatibility for a particular installation. Plex is not implemented.

## Optional local metadata files

Naming presets include **Write NFO metadata**, **Download artwork**, and **Write episode NFO metadata**. All three start off. Saved collection defaults apply when a preview uses default naming; choosing a preset binds its saved version to that preview.

A preview lists generated outputs alongside media and associated subtitle/NFO/image moves. Movies use `movie.nfo` in their dedicated folder (a flat custom layout uses the media stem); series use `tvshow.nfo`, music uses `artist.nfo`/`album.nfo`, and books can receive a cover image. Episode NFO includes the show, season/episode, and cached episode title/plot/air date/episode ID when TMDb is available. A series ID is never written as an episode ID. XML text is escaped. Episode catalogue requests are cached per season; unavailable details appear as a warning and retain filename-derived numbers.

Artwork comes only from supported credential-free HTTPS provider origins. Requests and decoding have byte, pixel, redirect and time limits; output is a real JPEG. An audio item without a release MBID or confirmed cover URL shows `release_id_unavailable`, rather than making up an album cover. The preview reserves up to 10 MiB for each artwork operation.

Existing sidecars are kept. Generation uses an exclusively created temporary file, stored hashes/identities and exclusive final publication. Restart reconciles recorded output; retries validate the already moved media. Failed optional output leaves successful media moves indexed at their new paths and can be retried separately within the batch. Guarded undo removes only unchanged generated output, restores moved original companions, and leaves externally edited generated output with a warning.

Watching has a separate **Identify stable arrivals** switch. By default it only scans. Enabling identification queues provider lookups for newly indexed or changed unconfirmed media after the whole source is stable; provider keys and fingerprint consent still apply. Download markers and later source changes prevent unstable scans. No watch operation confirms a match or organises files.
