# Metadata providers and consent

Orion sends lookup queries to the selected metadata provider when you request identification. Candidate results are evidence for your review, not automatic approval. You can correct details manually or leave an item unconfirmed. See [collections](./collections.html) for provider compatibility by media type.

## Provider compatibility

- **TMDb** supports movies, series, anime, anime films and web series. Configure a TMDb API key in provider settings.
- **AniList** and **AniDB** support anime and anime films.
- **MusicBrainz** supports music and does not require a user API key for ordinary lookups.
- **AcoustID** supports music fingerprint lookups and requires the separately installed `fpcalc` tool plus explicit fingerprint consent.
- **AudD** supports music identification by sample upload. Its upload consent is separate and must be explicitly enabled.
- **Open Library** supports books.

A provider can be unavailable, rate-limited, reject credentials or return no match. Retry after checking the error and network access; changing provider is also an option where compatible. Fingerprinting and sample upload are optional. Do not enable either unless you understand and want that audio data sent to the service.

## Credentials and storage

Enter API keys only in Orion's write-only credential field. Orion stores credentials in the operating system keychain. If secure storage is unavailable, Orion requires you to explicitly choose session-only storage; credentials then do not persist between sessions. Never put keys in filenames, screenshots, exports or public issue reports.

Replacing a key does not display the old value. If a request returns `credentials_rejected`, replace or re-enter the key and retry the lookup. If it returns `credentials_required`, add a key when that provider requires one. Network failures and rate limits are not proof that the media metadata is wrong.

Orion can run without providers: scan files, review parsed metadata, edit fields and confirm decisions manually. For media-server connections, which are independent of metadata lookup, use the [Jellyfin and Emby guide](./integrations.html).
