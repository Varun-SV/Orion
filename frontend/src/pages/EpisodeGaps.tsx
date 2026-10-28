import { useEffect, useRef, useState } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useTask } from '../api/useTask';
import { type ServerStatus, type ServerItem, type GapReport } from '../types';
import { navigate } from '../state/navigation';
const pair = (value: [number, number]) =>
  `S${String(value[0]).padStart(2, '0')}E${String(value[1]).padStart(2, '0')}`;
export function EpisodeGaps() {
  const { data: server, error } = useResource<ServerStatus>('/server');
  const discovery = useTask(),
    gaps = useTask();
  const [series, setSeries] = useState(''),
    [providerId, setProviderId] = useState(''),
    [confirmed, setConfirmed] = useState(false),
    [specials, setSpecials] = useState(false),
    [search, setSearch] = useState('');
  const shows = Array.isArray(discovery.job?.result?.items)
    ? (discovery.job.result.items as ServerItem[])
    : [];
  const report = gaps.job?.result as unknown as GapReport | null;
  const [episodeFilter, setEpisodeFilter] = useState('missing'),
    [episodeOffset, setEpisodeOffset] = useState(0),
    [mappingError, setMappingError] = useState('');
  const selectedSeries = useRef(series);
  selectedSeries.current = series;
  useEffect(() => {
    setEpisodeOffset(0);
  }, [gaps.job?.id]);
  async function loadMapping() {
    const requested = series;
    try {
      const saved = await api<{ provider_id: string } | null>('/server/mapping/' + series);
      if (selectedSeries.current !== requested) return;
      setConfirmed(false);
      if (saved) {
        setProviderId(saved.provider_id);
        setMappingError('');
      } else setMappingError('No saved mapping for this series and server user.');
    } catch (e) {
      if (selectedSeries.current === requested) setMappingError((e as Error).message);
    }
  }
  const details = (report?.episodes ?? []).filter(
    (ep) => episodeFilter === 'all' || ep.state === episodeFilter,
  );
  return (
    <>
      <p className="notice">
        Compare your server's numbered episodes with a confirmed TMDb series mapping. Unaired
        episodes, specials and unknown air dates stay separate. Catalogue data is cached for one
        hour.
      </p>
      {!server?.configured || !server?.user_id ? (
        <section className="panel">
          <h2>Connect your media server</h2>
          <p>Select a Jellyfin or Emby user in Connections before checking completeness.</p>
          <button className="secondary" onClick={() => navigate('connections')}>
            Open connections
          </button>
        </section>
      ) : (
        <section className="panel">
          <label className="field">
            Find a server series
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <button
            className="secondary"
            disabled={discovery.busy}
            onClick={() => {
              setSeries('');
              setConfirmed(false);
              gaps.clear();
              void discovery.submit(
                '/server/discover',
                json('POST', { include_types: 'Series', search }),
              );
            }}
          >
            Load server series
          </button>
          {discovery.job && (
            <p role={discovery.job.error ? 'alert' : 'status'}>
              {discovery.job.state}
              {discovery.job.error ? ' · ' + discovery.job.error.replaceAll('_', ' ') : ''}
            </p>
          )}
          {discovery.job?.state === 'completed' && !shows.length && (
            <p>No server series matched this query.</p>
          )}
          <label className="field">
            Server series
            <select
              value={series}
              onChange={(e) => {
                setSeries(e.target.value);
                setProviderId(shows.find((s) => s.id === e.target.value)?.provider_ids?.tmdb ?? '');
                setConfirmed(false);
                gaps.clear();
              }}
            >
              <option value="">Choose a series</option>
              {shows.map((show) => (
                <option key={show.id} value={show.id}>
                  {show.name}
                  {show.year ? ' (' + show.year + ')' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Confirmed TMDb series ID
            <input
              value={providerId}
              inputMode="numeric"
              onChange={(e) => {
                setProviderId(e.target.value);
                setConfirmed(false);
                gaps.clear();
              }}
            />
          </label>
          <button className="text-button" disabled={!series} onClick={() => void loadMapping()}>
            Load saved mapping
          </button>
          {mappingError && <p role="status">{mappingError}</p>}
          <p className="notice">
            A provider ID found on your server is a suggestion. Check that it identifies this exact
            series, especially remakes and anime editions.
          </p>
          {providerId && /^\d+$/.test(providerId) && (
            <a
              className="text-button"
              href={'https://www.themoviedb.org/tv/' + providerId}
              target="_blank"
              rel="noreferrer"
            >
              Review the TMDb series
            </a>
          )}
          <label className="check-field">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I confirmed this TMDb mapping identifies the selected series
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={specials}
              onChange={(e) => setSpecials(e.target.checked)}
            />
            Include specials (season 0)
          </label>
          <button
            className="primary"
            disabled={gaps.busy || !series || !confirmed || !/^\d+$/.test(providerId)}
            onClick={() =>
              void gaps.submit(
                '/server/gaps',
                json('POST', {
                  series_id: series,
                  mapping: { provider: 'tmdb', provider_id: providerId, confirmed },
                  include_specials: specials,
                }),
              )
            }
          >
            Check episode gaps
          </button>
        </section>
      )}
      {(error || discovery.error || gaps.error) && (
        <p role="alert">{error || discovery.error || gaps.error}</p>
      )}
      {gaps.job && (
        <section className="panel">
          <h2>Episode completeness</h2>
          <p role="status">{gaps.job.state}</p>
          {gaps.job.error && (
            <p role="alert">Episode data unavailable: {gaps.job.error.replaceAll('_', ' ')}</p>
          )}
          {report?.state === 'unavailable' && (
            <p role="alert">
              Episode data unavailable: {report.error?.replaceAll('_', ' ')}. Missing episodes
              cannot be determined.
            </p>
          )}
          {report?.state === 'mapping_required' && (
            <p role="alert">Confirm the provider mapping before checking gaps.</p>
          )}
          {report?.state === 'ready' && (
            <>
              <p className="subtitle">
                Catalogue {report.catalogue_cached ? 'cached' : 'fetched'} ·{' '}
                {report.catalogue_updated_at
                  ? new Date(report.catalogue_updated_at).toLocaleString()
                  : ''}
              </p>
              <p>{report.present.length} numbered episodes present on the server</p>
              <div className="settings-grid">
                {[
                  ['Missing aired episodes', report.missing],
                  ['Unaired episodes', report.unaired],
                  ['Air date unknown', report.unknown_air_date],
                ].map(([heading, episodes]) => (
                  <section key={String(heading)}>
                    <h3>{String(heading)}</h3>
                    <p>
                      {(episodes as [number, number][]).map(pair).join(' · ') ||
                        'None in this comparison'}
                    </p>
                  </section>
                ))}
              </div>
              <h3>Episode details</h3>
              <label className="field">
                Episode status
                <select
                  value={episodeFilter}
                  onChange={(e) => {
                    setEpisodeFilter(e.target.value);
                    setEpisodeOffset(0);
                  }}
                >
                  <option value="missing">Missing aired</option>
                  <option value="unaired">Unaired</option>
                  <option value="unknown_air_date">Air date unknown</option>
                  <option value="present">Present</option>
                  <option value="all">All compared episodes</option>
                </select>
              </label>
              {details.slice(episodeOffset, episodeOffset + 48).map((ep) => (
                <article className="preview-item" key={ep.season + ':' + ep.episode}>
                  <strong>
                    {pair([ep.season, ep.episode])} · {ep.title || 'Title unavailable'}
                  </strong>
                  <p>{ep.air_date || 'Air date unknown'}</p>
                  <p>{ep.state.replaceAll('_', ' ')}</p>
                </article>
              ))}
              {!details.length && <p>No episodes in this status.</p>}
              <div className="actions">
                <button
                  className="secondary"
                  disabled={episodeOffset === 0}
                  onClick={() => setEpisodeOffset(Math.max(0, episodeOffset - 48))}
                >
                  Previous episodes
                </button>
                <button
                  className="secondary"
                  disabled={episodeOffset + 48 >= details.length}
                  onClick={() => setEpisodeOffset(episodeOffset + 48)}
                >
                  Next episodes
                </button>
              </div>
              <div className="actions">
                <a
                  className="secondary"
                  href={'/api/v1/jobs/' + gaps.job.id + '/report?format=csv'}
                >
                  Export CSV
                </a>
                <a
                  className="secondary"
                  href={'/api/v1/jobs/' + gaps.job.id + '/report?format=json'}
                >
                  Export JSON
                </a>
              </div>
            </>
          )}
        </section>
      )}
    </>
  );
}
