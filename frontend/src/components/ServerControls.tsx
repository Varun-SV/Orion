import { useEffect, useRef, useState } from 'react';
import { api, json } from '../api/client';
import { useResource } from '../api/useResource';
import { useTask } from '../api/useTask';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type ServerStatus } from '../types';
const defaults = {
  enabled: false,
  url: '',
  server_type: 'jellyfin' as const,
  user_id: '',
  auto_refresh: false,
};
export function ServerControls() {
  const { refresh } = useWorkspace();
  const { data: status, error: loadError } = useResource<ServerStatus>('/server');
  const loaded = useRef(false);
  const [draft, setDraft] = useState<{
      enabled: boolean;
      url: string;
      server_type: 'jellyfin' | 'emby';
      user_id: string;
      auto_refresh: boolean;
    }>(defaults),
    [key, setKey] = useState(''),
    [session, setSession] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  const task = useTask();
  useEffect(() => {
    if (status?.server_type && !loaded.current) {
      setDraft({
        enabled: status.enabled,
        url: status.url,
        server_type: status.server_type,
        user_id: status.user_id,
        auto_refresh: status.auto_refresh,
      });
      loaded.current = true;
    }
  }, [status]);
  const users = Array.isArray(task.job?.result?.users)
    ? (task.job.result.users as { id: string; name: string }[])
    : [];
  async function action(work: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError('');
    try {
      await work();
      setMessage(success);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel server-controls">
      <h2>Media server</h2>
      <p className="subtitle">
        Optional Jellyfin or Emby connection. Filesystem organisation works with this disabled.
      </p>
      {(error || loadError || task.error) && <p role="alert">{error || loadError || task.error}</p>}
      {message && <p role="status">{message}</p>}
      <p className="notice">
        {status?.configured ? 'Configured' : 'Not configured'} ·{' '}
        {status?.health?.replaceAll('_', ' ') ?? 'not checked'}
        {status?.detail ? ' · ' + status.detail : ''}
      </p>
      <label className="check-field">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        Enable media server integration
      </label>
      <div className="form-grid">
        <label className="field">
          Server type
          <select
            value={draft.server_type}
            onChange={(e) => {
              setDraft({
                ...draft,
                server_type: e.target.value as 'jellyfin' | 'emby',
                user_id: '',
              });
              task.clear();
            }}
          >
            <option value="jellyfin">Jellyfin</option>
            <option value="emby">Emby</option>
          </select>
        </label>
        <label className="field">
          Media server URL
          <input
            type="url"
            value={draft.url}
            placeholder="http://localhost:8096"
            onChange={(e) => {
              setDraft({ ...draft, url: e.target.value, user_id: '' });
              task.clear();
            }}
          />
        </label>
      </div>
      <p className="notice">
        Use the server's API base URL, including any reverse-proxy prefix or /emby prefix. Keys are
        sent in request headers, and are never displayed.
      </p>
      {users.length > 0 && (
        <label className="field">
          Media server user
          <select
            value={draft.user_id}
            onChange={(e) => setDraft({ ...draft, user_id: e.target.value })}
          >
            <option value="">Select your user explicitly</option>
            {users.map((u) => (
              <option value={u.id} key={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="field">
        Direct server user ID
        <input
          value={draft.user_id}
          maxLength={100}
          onChange={(e) => setDraft({ ...draft, user_id: e.target.value })}
          placeholder="Select after testing, or enter your known user ID"
        />
      </label>
      <label className="check-field">
        <input
          type="checkbox"
          checked={draft.auto_refresh}
          onChange={(e) => setDraft({ ...draft, auto_refresh: e.target.checked })}
        />
        Request server refresh after a successful organisation batch
      </label>
      <p className="notice">
        Refresh is a separate job. Its failure leaves successful file changes intact; retry it in
        Jobs. A request accepted by the server does not mean its scan has finished.
      </p>
      <div className="actions">
        <button
          className="primary"
          disabled={busy}
          onClick={() =>
            void action(
              () => api('/server', json('PUT', draft)),
              'Media server settings saved. Test the saved connection next.',
            )
          }
        >
          Save media server
        </button>
        <button
          className="secondary"
          disabled={busy || task.busy || !status?.configured}
          onClick={() => void task.submit('/server/test')}
        >
          Test media server
        </button>
        <button
          className="secondary"
          disabled={busy || task.busy || !status?.configured}
          onClick={() => void task.submit('/server/refresh')}
        >
          Request library refresh
        </button>
      </div>
      {task.job && (
        <p role={task.job.error ? 'alert' : 'status'}>
          {task.job.kind.replaceAll('_', ' ')}: {task.job.state}
          {task.job.error ? ' · ' + task.job.error.replaceAll('_', ' ') : ''}
          {task.job.result?.accepted ? ' · request accepted; scan runs on your server' : ''}
        </p>
      )}
      <hr />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action(async () => {
            await api('/server/credentials', json('POST', { key, session_only: session }));
            setKey('');
          }, 'Server credential replacement saved.');
        }}
      >
        <label className="field">
          Replacement media server API key
          <input
            type="password"
            value={key}
            autoComplete="new-password"
            maxLength={1000}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Saved values stay hidden"
          />
        </label>
        <label className="check-field">
          <input type="checkbox" checked={session} onChange={(e) => setSession(e.target.checked)} />
          Keep media server key for this engine session only
        </label>
        <div className="actions">
          <button className="secondary" disabled={busy || !key.trim()} type="submit">
            Replace media server key
          </button>
          <button
            className="text-button"
            type="button"
            disabled={busy || !status?.configured}
            onClick={() =>
              void action(
                () => api('/server/credentials', { method: 'DELETE' }),
                'Server credential cleared.',
              )
            }
          >
            Clear media server key
          </button>
        </div>
      </form>
    </section>
  );
}
