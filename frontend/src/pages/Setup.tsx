import { useState, type FormEvent } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { navigate } from '../state/navigation';
import { collections, type Source, type Destination, type Job } from '../types';
import { WatchControls } from '../components/WatchControls';
export function Setup() {
  const { refresh, overview } = useWorkspace();
  const { data: sources, error: sourceError } = useResource<Source[]>('/sources'),
    { data: destinations, error: destinationError } = useResource<Destination[]>('/destinations');
  const [sourcePath, setSourcePath] = useState(''),
    [sourceLabel, setSourceLabel] = useState(''),
    [kind, setKind] = useState('auto'),
    [destinationPath, setDestinationPath] = useState(''),
    [destinationLabel, setDestinationLabel] = useState('Library'),
    [deep, setDeep] = useState(false),
    [chosen, setChosen] = useState<string[] | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const active = sources?.filter((s) => !s.archived) ?? [],
    selected =
      chosen === null
        ? active.map((s) => s.id)
        : chosen.filter((id) => active.some((s) => s.id === id));
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await work();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addSource(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      await api('/sources', json('POST', { path: sourcePath, label: sourceLabel, kind }));
      setSourcePath('');
      setSourceLabel('');
      setMessage('Source added. Ready to scan.');
    });
  }
  async function addDestination(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      await api('/destinations', json('POST', { path: destinationPath, label: destinationLabel }));
      setDestinationPath('');
      setMessage('Destination added.');
    });
  }
  return (
    <>
      {(error || sourceError || destinationError) && (
        <p role="alert">{error || sourceError || destinationError}</p>
      )}
      {message && (
        <p role="status" className="banner">
          {message}
        </p>
      )}
      <div className="setup-steps">
        <div>
          <strong>1. Connect sources</strong>
          <small>{overview?.sources ?? 0} sources</small>
        </div>
        <div>
          <strong>2. Choose a destination</strong>
          <small>{overview?.destinations ?? 0} destinations</small>
        </div>
        <div>
          <strong>3. Optional connections</strong>
          <button className="text-button" onClick={() => navigate('connections')}>
            Configure providers →
          </button>
        </div>
      </div>
      <p className="notice">
        Enter a folder path accessible to this computer. The browser cannot browse your drive. Music
        and books can be renamed in place without a separate destination. Paths and overlap checks
        are validated by the engine.
      </p>
      <p className="notice">
        Watching indexes stable arrivals for review. It never confirms matches or organises files
        automatically.
      </p>
      <div className="settings-grid">
        <section className="panel">
          <h2>Source folders</h2>
          {sources?.map((source) => (
            <article className="folder-row" key={source.id}>
              <label className="check-field">
                <input
                  type="checkbox"
                  disabled={source.archived}
                  checked={selected.includes(source.id)}
                  onChange={(e) =>
                    setChosen(
                      e.target.checked
                        ? [...selected, source.id]
                        : selected.filter((id) => id !== source.id),
                    )
                  }
                />
                <strong>{source.label}</strong>
              </label>
              <p className="path-text">{source.path}</p>
              <WatchControls source={source} />
              <p className="subtitle">
                {source.kind === 'auto' ? 'Auto-detect collections' : collections[source.kind]} ·{' '}
                {source.archived ? 'Paused' : 'Configured'}
              </p>
              <button
                className="text-button"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    await api('/sources/' + source.id + (source.archived ? '/resume' : ''), {
                      method: source.archived ? 'POST' : 'DELETE',
                    });
                  })
                }
              >
                {source.archived ? 'Resume source' : 'Pause source'}
              </button>
            </article>
          ))}
          <form onSubmit={(e) => void addSource(e)}>
            <label className="field">
              Source folder path
              <input
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
                placeholder="C:\Media\Incoming"
                required
              />
            </label>
            <label className="field">
              Source label
              <input
                value={sourceLabel}
                onChange={(e) => setSourceLabel(e.target.value)}
                placeholder="Optional friendly name"
              />
            </label>
            <label className="field">
              Source collection
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="auto">Auto-detect</option>
                {Object.entries(collections).map(([id, name]) => (
                  <option value={id} key={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <button className="secondary" disabled={busy || !sourcePath.trim()} type="submit">
              Add source
            </button>
          </form>
        </section>
        <section className="panel">
          <h2>Destination folders</h2>
          {destinations?.map((destination) => (
            <article className="folder-row" key={destination.id}>
              <strong>{destination.label}</strong>
              <p className="path-text">{destination.path}</p>
              <button
                className="text-button"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    await api('/destinations/' + destination.id, { method: 'DELETE' });
                  })
                }
              >
                Remove destination
              </button>
            </article>
          ))}
          <form onSubmit={(e) => void addDestination(e)}>
            <label className="field">
              Destination folder path
              <input
                value={destinationPath}
                onChange={(e) => setDestinationPath(e.target.value)}
                placeholder="D:\Media\Library"
                required
              />
            </label>
            <label className="field">
              Destination label
              <input
                value={destinationLabel}
                onChange={(e) => setDestinationLabel(e.target.value)}
                required
              />
            </label>
            <button className="secondary" type="submit" disabled={busy || !destinationPath.trim()}>
              Add destination
            </button>
          </form>
        </section>
      </div>
      <section className="panel scan-panel">
        <h2>Discover your collection</h2>
        <p className="subtitle">
          Scanning indexes files and reads available tags. Provider lookup and match confirmation
          stay in your hands.
        </p>
        <label className="check-field">
          <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} />
          Deep scan
        </label>
        <button
          className="primary"
          disabled={busy || !selected.length}
          onClick={() =>
            void action(async () => {
              await api<Job>(
                '/jobs',
                json('POST', { kind: 'scan', payload: { source_ids: selected, deep } }),
              );
              navigate('jobs');
            })
          }
        >
          Scan sources
        </button>
        <p className="notice">
          Pausing sources or removing destination configuration preserves files and recorded
          recovery history.
        </p>
      </section>
    </>
  );
}
