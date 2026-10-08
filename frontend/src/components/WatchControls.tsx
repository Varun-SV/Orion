import { useEffect, useState } from 'react';
import { api, json } from '../api/client';
import { type Source } from '../types';
import { useWorkspace } from '../state/WorkspaceProvider';
interface WatchSettings {
  enabled: boolean;
  identify_arrivals: boolean;
  stability_seconds: number;
  next_attempt: number;
}
export function WatchControls({ source }: { source: Source }) {
  const { refresh } = useWorkspace();
  const [identify, setIdentify] = useState(false);
  const [enabled, setEnabled] = useState(!!source.watch),
    [interval, setInterval] = useState(30),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false),
    [next, setNext] = useState(0);
  useEffect(() => {
    let mounted = true;
    void api<WatchSettings>('/sources/' + source.id + '/watch')
      .then((data) => {
        if (mounted) {
          setEnabled(data.enabled);
          setIdentify(!!data.identify_arrivals);
          setInterval(data.stability_seconds);
          setNext(data.next_attempt);
        }
      })
      .catch((e) => {
        if (mounted) setError(e.message);
      });
    return () => {
      mounted = false;
    };
  }, [source.id, source.watch]);
  async function save() {
    setBusy(true);
    setError('');
    try {
      await api(
        '/sources/' + source.id + '/watch',
        json('PUT', { enabled, stability_seconds: interval, identify_arrivals: identify }),
      );
      setMessage('Watching preferences saved.');
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="watch-controls">
      <label className="check-field">
        <input
          type="checkbox"
          disabled={source.archived || busy}
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Watch {source.label} for stable arrivals
      </label>
      <label className="check-field">
        <input
          type="checkbox"
          checked={identify}
          disabled={source.archived || busy}
          onChange={(e) => setIdentify(e.target.checked)}
        />
        Identify stable arrivals for {source.label}
      </label>
      <p className="notice">
        Identification contacts the selected metadata provider and requires any configured key or
        fingerprint consent. Matches remain unconfirmed; files are never automatically organised.
      </p>
      <label className="field">
        Stability interval for {source.label} (seconds)
        <input
          type="number"
          min={5}
          max={3600}
          value={interval}
          disabled={source.archived || busy}
          onChange={(e) => setInterval(Number(e.target.value))}
        />
      </label>
      <button
        className="secondary"
        disabled={source.archived || busy || interval < 5 || interval > 3600}
        onClick={() => void save()}
      >
        Save watching for {source.label}
      </button>
      {next > Date.now() / 1000 && (
        <p className="notice">
          Source unavailable; next check after {new Date(next * 1000).toLocaleTimeString()}.
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
