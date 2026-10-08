import { useEffect, useRef, useState } from 'react';
import { api, json } from '../api/client';
import { useWorkspace } from '../state/WorkspaceProvider';
import {
  type MediaItem,
  type Candidate,
  type Job,
  text,
  title,
  active,
  collections,
} from '../types';
import { Dialog } from './Dialog';
import { Cover } from './MediaCard';
import { ServerHints } from './ServerHints';
interface Lookup {
  items: Candidate[];
  state: string;
  error: string | null;
}
export function MatchDialog({ item, close }: { item: MediaItem; close: () => void }) {
  const { refresh } = useWorkspace();
  const [lookup, setLookup] = useState<Lookup>({ items: [], state: 'loading', error: null }),
    [choice, setChoice] = useState<Candidate | null>(null),
    [name, setName] = useState(
      text(item.decision?.metadata.title ?? item.metadata.title, title(item)),
    ),
    [year, setYear] = useState(text(item.decision?.metadata.year ?? item.metadata.year)),
    [filename, setFilename] = useState(text(item.decision?.metadata.filename)),
    [fields, setFields] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    api<Lookup>('/items/' + item.id + '/candidates')
      .then(setLookup)
      .catch((e) => setError(e.message));
    return () => {
      mounted.current = false;
    };
  }, [item.id]);
  async function identify() {
    setBusy(true);
    setError('');
    try {
      let job = await api<Job>('/items/' + item.id + '/candidates', json('POST', {}));
      while (active(job) && mounted.current) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        if (!mounted.current) return;
        job = await api<Job>('/jobs/' + job.id);
      }
      if (!mounted.current) return;
      setLookup(await api<Lookup>('/items/' + item.id + '/candidates'));
      if (job.state !== 'completed')
        setError('Identification ' + job.state + ': ' + (job.error ?? 'review provider settings'));
      refresh();
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function confirm() {
    setBusy(true);
    setError('');
    try {
      const metadata = {
        ...item.metadata,
        ...(choice?.metadata ?? item.decision?.metadata ?? {}),
        ...Object.fromEntries(Object.entries(fields).filter(([, v]) => v)),
        title: name.trim(),
        year,
        ...(filename ? { filename } : {}),
      };
      delete (metadata as Record<string, unknown>).candidates;
      await api(
        '/items/' + item.id + '/decision',
        json('PUT', {
          item_id: item.id,
          provider: choice?.provider ?? item.decision?.provider ?? 'manual',
          provider_id: choice?.provider_id ?? item.decision?.provider_id ?? '',
          metadata,
          evidence: choice?.evidence ?? item.decision?.evidence ?? ['Title confirmed manually'],
        }),
      );
      refresh();
      close();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  const extraFields =
    item.kind === 'music'
      ? ['artist', 'album', 'track_number']
      : item.kind === 'books'
        ? ['author', 'series']
        : ['series', 'anime', 'web_series'].includes(item.kind)
          ? ['season', 'episode']
          : [];
  return (
    <Dialog title="Review match" close={close}>
      <div className="modal-detail">
        <Cover item={item} />
        <div>
          <p className="eyebrow">{collections[item.kind]}</p>
          <h3>{title(item)}</h3>
          <p className="path-text">{item.path}</p>
          <p>
            Confirming metadata leaves your files where they are. You can preview every path change
            afterwards.
          </p>
        </div>
      </div>
      <div className="section-head">
        <h3>Candidate evidence</h3>
        <button className="secondary" onClick={() => void identify()} disabled={busy}>
          {busy ? 'Identifying…' : 'Find candidates'}
        </button>
      </div>
      {lookup.state === 'not_checked' && (
        <p className="notice">
          Not identified yet. Search a provider or confirm a manual correction below.
        </p>
      )}
      {lookup.state === 'no_match' && (
        <p className="notice">
          No provider match found. Try a different provider in settings or correct the title
          manually.
        </p>
      )}
      {lookup.error && <p role="alert">Provider unavailable: {lookup.error}</p>}
      <div className="candidate-list">
        {lookup.items.map((candidate) => (
          <label className="candidate" key={candidate.provider + candidate.provider_id}>
            <input
              type="radio"
              name="candidate"
              checked={choice === candidate}
              onChange={() => {
                setChoice(candidate);
                setName(candidate.title);
                setYear(candidate.year);
              }}
            />
            <span>
              <strong>
                {candidate.title} {candidate.year}
              </strong>
              <small>
                {candidate.provider} · {candidate.provider_id}
              </small>
              {candidate.evidence.map((e, i) => (
                <span className="evidence" key={i}>
                  {e}
                </span>
              ))}
            </span>
          </label>
        ))}
        <label className="candidate">
          <input type="radio" name="candidate" checked={!choice} onChange={() => setChoice(null)} />
          {item.decision?.provider_id
            ? `Keep confirmed ${item.decision.provider} identity (${item.decision.provider_id}) and correct fields`
            : 'Manual correction'}
        </label>
      </div>
      <div className="form-grid">
        <label className="field">
          Title
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="field">
          Year
          <input value={year} onChange={(e) => setYear(e.target.value)} />
        </label>
        {extraFields.map((field) => (
          <label className="field" key={field}>
            {field === 'track_number' ? 'Track number' : field[0].toUpperCase() + field.slice(1)}
            <input
              value={fields[field] ?? text(item.decision?.metadata[field] ?? item.metadata[field])}
              onChange={(e) => setFields({ ...fields, [field]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <ServerHints itemId={item.id} />
      <label className="field">
        Exact filename override (optional)
        <input
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          placeholder="Keep the extension, for example Arrival.mkv"
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <div className="modal-actions">
        <button className="secondary" onClick={close}>
          Close
        </button>
        <button className="primary" onClick={() => void confirm()} disabled={busy || !name.trim()}>
          Confirm match
        </button>
      </div>
    </Dialog>
  );
}
