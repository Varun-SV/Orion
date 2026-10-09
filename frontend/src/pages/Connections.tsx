import { useState, type FormEvent } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type Provider, type Job } from '../types';
import { navigate } from '../state/navigation';
import { ServerControls } from '../components/ServerControls';
function ProviderCard({ provider: p }: { provider: Provider }) {
  const { refresh } = useWorkspace();
  const [key, setKey] = useState(''),
    [sessionOnly, setSessionOnly] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api(
        '/providers/' + p.id + '/credentials',
        json('POST', { key, session_only: sessionOnly }),
      );
      setKey('');
      setMessage('Credential replacement saved. Test the connection before relying on it.');
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function testConnection() {
    setBusy(true);
    setError('');
    try {
      await api<Job>('/providers/' + p.id + '/test', { method: 'POST' });
      refresh();
      navigate('jobs');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const presence = p.requires_key
    ? p.configured
      ? 'Configured'
      : 'Key not configured'
    : 'No key required';
  const checked =
    p.health === 'not_checked' ? 'not tested' : 'last check: ' + p.health.replaceAll('_', ' ');
  return (
    <section className="panel provider-card">
      <div className="section-head">
        <h2>{p.label}</h2>
        <span className="state">
          {p.storage === 'session'
            ? 'Session only'
            : p.requires_key
              ? 'OS keychain'
              : 'Public catalogue'}
        </span>
      </div>
      <p className="subtitle">
        {presence} · {checked}
      </p>
      {p.detail && <p className="notice">{p.detail}</p>}
      {!p.consent_enabled && (
        <p className="notice">
          Opt-in identification is disabled. Enable it in settings before identifying a music item.
        </p>
      )}
      {p.requires_key && (
        <form onSubmit={(e) => void save(e)}>
          <label className="field">
            Replacement API key
            <input
              type="password"
              value={key}
              autoComplete="new-password"
              onChange={(e) => setKey(e.target.value)}
              placeholder="Saved values are never displayed"
            />
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={sessionOnly}
              onChange={(e) => setSessionOnly(e.target.checked)}
            />
            Use for this session only
          </label>
          <p className="notice">
            Session-only keys disappear when the engine stops. Clear key removes the saved
            credential from the selected storage.
          </p>
          <div className="actions">
            <button className="secondary" type="submit" disabled={busy || !key.trim()}>
              Save key
            </button>
            <button
              className="text-button"
              type="button"
              disabled={busy || !p.configured}
              onClick={() =>
                void (async () => {
                  setBusy(true);
                  try {
                    await api(
                      '/providers/' + p.id + '/credentials',
                      json('POST', { key: '', session_only: sessionOnly }),
                    );
                    setKey('');
                    refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                })()
              }
            >
              Clear key
            </button>
          </div>
        </form>
      )}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <button
        className="secondary test-connection"
        disabled={busy || !p.configured}
        onClick={() => void testConnection()}
      >
        Test connection
      </button>
    </section>
  );
}
export function Connections() {
  const { data, error } = useResource<Provider[]>('/providers');
  return (
    <>
      <section className="banner">
        <div>
          <strong>Filesystem-only mode is always available</strong>
          <p>
            Your local library works without a media server. Providers supply metadata when you
            choose to identify an item.
          </p>
        </div>
      </section>
      <p className="notice">
        Configured credentials and successful connectivity are separate states. Public providers
        need no API key; external requests run as bounded, cancellable jobs. Saved secret values are
        never returned to this page.
      </p>
      {error && <p role="alert">{error}</p>}
      <ServerControls />
      <div className="settings-grid">
        {data?.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} />
        ))}
      </div>
    </>
  );
}
