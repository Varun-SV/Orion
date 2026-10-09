import { CheckCircle, HardDrive } from 'react-feather';
import { useWorkspace } from '../state/WorkspaceProvider';
import { useResource } from '../api/useResource';
import { navigate } from '../state/navigation';
import { collections, bytes, type Source, type Page, type MediaItem } from '../types';
import { Cover, statusLabel } from '../components/MediaCard';
export function Overview() {
  const { overview: o } = useWorkspace();
  const { data: sources } = useResource<Source[]>('/sources');
  const { data: recent } = useResource<Page<MediaItem>>('/items?limit=6');
  if (!o) return null;
  return (
    <>
      {!o.sources && (
        <section className="banner">
          <div>
            <strong>Make yourself at home.</strong>
            <p>Add a source folder to discover movies, music, books and more.</p>
          </div>
          <button className="secondary" onClick={() => navigate('sources')}>
            Configure folders
          </button>
        </section>
      )}
      <section className="summary" aria-label="Library summary">
        {[
          ['In your library', o.total, 'Across seven collections'],
          ['Ready for review', o.review, 'Your choices, made thoughtfully'],
          ['Indexed files', bytes(o.indexed_bytes), 'Size of indexed media'],
          ['Active sources', o.sources, 'Folders on this computer'],
        ].map(([label, value, note]) => (
          <div className="stat" key={label}>
            <p className="stat-label">{label}</p>
            <p className="stat-value">{value}</p>
            <p className="stat-foot">{note}</p>
          </div>
        ))}
      </section>
      {!!o.review && (
        <section className="banner">
          <CheckCircle />
          <div>
            <strong>A few things could use your eye.</strong>
            <p>{o.review} items awaiting identification, correction or recovery.</p>
          </div>
          <button className="text-button" onClick={() => navigate('review')}>
            Open match review →
          </button>
        </section>
      )}
      <div className="section-head">
        <h2>Your collection</h2>
        <button className="text-button" onClick={() => navigate('library')}>
          See everything →
        </button>
      </div>
      <div className="collection-counts">
        {Object.entries(collections).map(([id, label]) => (
          <button className="collection-count" key={id} onClick={() => navigate(id)}>
            <span>{label}</span>
            <strong>{o.counts[id as keyof typeof collections] ?? 0}</strong>
            <small>
              {id === 'books'
                ? `${o.counts.books} books`
                : id === 'music'
                  ? `${o.counts.music} music item${o.counts.music === 1 ? '' : 's'}`
                  : 'Browse collection'}
            </small>
          </button>
        ))}
      </div>
      <div className="collection">
        {recent?.items.map((item) => (
          <button className="media-card" key={item.id} onClick={() => navigate(item.kind)}>
            <div className="poster-wrap">
              <Cover item={item} />
              <span className="poster-label">{statusLabel(item)}</span>
            </div>
            <span className="media-title">
              {String(item.decision?.metadata.title ?? item.metadata.title ?? item.path)}
            </span>
          </button>
        ))}
      </div>
      <div className="lower-grid">
        <section className="panel">
          <div className="section-head">
            <h2>Designed for peace of mind.</h2>
          </div>
          <p className="subtitle">
            Confirm a match, review the exact paths, then organise. Every operation is recorded,
            verified and recoverable.
          </p>
          <div className="panel-foot">
            <span>{o.jobs_running} jobs active</span>
            <button className="text-button" onClick={() => navigate('jobs')}>
              View jobs →
            </button>
          </div>
        </section>
        <section className="panel">
          <div className="section-head">
            <h2>Your sources</h2>
            <button className="text-button" onClick={() => navigate('sources')}>
              Manage →
            </button>
          </div>
          {sources
            ?.filter((s) => !s.archived)
            .slice(0, 3)
            .map((source) => (
              <div className="source-row" key={source.id}>
                <span className="source-icon">
                  <HardDrive />
                </span>
                <div className="row-content">
                  <strong>{source.label}</strong>
                  <p className="path-text">{source.path}</p>
                </div>
              </div>
            ))}
          {!o.sources && <p className="subtitle">Your first source will appear here.</p>}
        </section>
      </div>
    </>
  );
}
