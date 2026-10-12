import { useState } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type Page, type MediaItem, type Job, type Comparison, title, bytes, text } from '../types';
export function ComparisonPage() {
  const [query, setQuery] = useState(''),
    [offset, setOffset] = useState(0),
    [chosen, setChosen] = useState<string[]>([]),
    [exact, setExact] = useState(false),
    [job, setJob] = useState<Job | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const { data, error: listError } = useResource<Page<MediaItem>>(
    '/items?' + new URLSearchParams({ query, offset: String(offset), limit: '48' }),
  );
  const { jobs, refresh } = useWorkspace();
  const latest = jobs.find((j) => j.id === job?.id) ?? job;
  const result = latest?.result as unknown as Comparison | null;
  async function compare() {
    setBusy(true);
    setError('');
    try {
      setJob(await api<Job>('/comparisons', json('POST', { item_ids: chosen, exact })));
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <p className="notice">
        Compare copies and editions without changing files. Metadata agreement suggests versions;
        exact content requires a fresh SHA-256 check of every selected file, including folder
        companions.
      </p>
      {(error || listError) && <p role="alert">{error || listError}</p>}
      <section className="panel">
        <label className="field">
          Find copies
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <p className="subtitle">
          {chosen.length} selected · {data?.total ?? 0} indexed items
        </p>
        {data?.items.map((item) => (
          <div className="folder-row" key={item.id}>
            <label className="check-field">
              <input
                type="checkbox"
                aria-label={'Compare ' + title(item)}
                disabled={item.status === 'unavailable'}
                checked={chosen.includes(item.id)}
                onChange={(e) =>
                  setChosen(
                    e.target.checked ? [...chosen, item.id] : chosen.filter((id) => id !== item.id),
                  )
                }
              />
              <strong>{title(item)}</strong>
            </label>
            <p className="path-text">{item.path}</p>
          </div>
        ))}
        {!data?.total && <p>No indexed items match. Scan a source to compare your files.</p>}
        <div className="actions">
          <button
            className="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 48))}
          >
            Previous
          </button>
          <button
            className="secondary"
            disabled={!data || offset + 48 >= data.total}
            onClick={() => setOffset(offset + 48)}
          >
            Next
          </button>
          <button className="text-button" onClick={() => setChosen([])}>
            Clear comparison selection
          </button>
        </div>
        <label className="check-field">
          <input type="checkbox" checked={exact} onChange={(e) => setExact(e.target.checked)} />
          Verify exact content with SHA-256
        </label>
        <button
          className="primary"
          disabled={
            busy ||
            chosen.length < 2 ||
            chosen.length > 500 ||
            ['queued', 'running', 'cancelling'].includes(latest?.state ?? '')
          }
          onClick={() => void compare()}
        >
          Compare selected
        </button>
      </section>
      {latest && (
        <section className="panel">
          <h2>Comparison result</h2>
          <p role="status">
            {latest.state}
            {latest.progress.phase ? ' · ' + latest.progress.phase : ''}
          </p>
          {latest.error && <p role="alert">{latest.error}</p>}
          {result?.items && (
            <>
              <p>
                {result.exact_groups.length} exact content groups · {result.version_groups.length}{' '}
                possible version groups
              </p>
              {!result.exact && (
                <p className="notice">
                  Content was not hashed. Metadata groups are not verified duplicates.
                </p>
              )}
              {result.exact_groups.map((ids, index) => (
                <div className="preview-item" key={index}>
                  <strong>Exact content group {index + 1}</strong>
                  {ids.map((id) => (
                    <p className="path-text" key={id}>
                      {result.items.find((i) => i.item_id === id)?.path ?? id}
                    </p>
                  ))}
                </div>
              ))}
              {result.version_groups.map((group, index) => (
                <div className="preview-item" key={index}>
                  <strong>Possible versions {index + 1}</strong>
                  <p>{group.evidence.join(' · ')}</p>
                  {group.item_ids.map((id) => (
                    <p className="path-text" key={id}>
                      {result.items.find((i) => i.item_id === id)?.path ?? id}
                    </p>
                  ))}
                </div>
              ))}
              {result.items.map((item) => (
                <div className="preview-item" key={item.item_id}>
                  <strong>{item.title}</strong>
                  <p className="path-text">{item.path}</p>
                  <p>
                    {bytes(item.bytes)} ·{' '}
                    {Object.values(item.quality)
                      .map((v) => text(v))
                      .join(' · ')}
                    {item.edition ? ' · ' + item.edition : ''}
                  </p>
                  {item.sha256 && <p className="path-text">SHA-256 {item.sha256}</p>}
                </div>
              ))}
              {result.errors.map((e) => (
                <p role="alert" key={e.item_id}>
                  {e.item_id}: {e.code.replaceAll('_', ' ')}
                </p>
              ))}
              <div className="actions">
                <a className="secondary" href={'/api/v1/jobs/' + latest.id + '/report?format=csv'}>
                  Export CSV
                </a>
                <a className="secondary" href={'/api/v1/jobs/' + latest.id + '/report?format=json'}>
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
