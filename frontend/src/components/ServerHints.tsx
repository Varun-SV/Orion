import { useResource } from '../api/useResource';
import { useTask } from '../api/useTask';
import { type ServerStatus, type ServerItem } from '../types';
export function ServerHints({ itemId }: { itemId: string }) {
  const { data: server } = useResource<ServerStatus>('/server');
  const { data: saved } = useResource<{ items: ServerItem[]; state: string; error: string | null }>(
    '/items/' + itemId + '/server-hints',
  );
  const task = useTask();
  const hints = Array.isArray(task.job?.result?.items)
    ? (task.job.result.items as ServerItem[])
    : (saved?.items ?? []);
  if (!server?.configured || !server.user_id) return null;
  return (
    <section className="server-hints">
      <h3>Copies on your server</h3>
      <p className="notice">
        Server search provides title, ID and resolution evidence. Content has not been hashed, and a
        server copy never approves a match.
      </p>
      <button
        className="secondary"
        disabled={task.busy}
        onClick={() => void task.submit('/items/' + itemId + '/server-hints')}
      >
        Check server copies
      </button>
      {task.job && (
        <p role={task.job.error ? 'alert' : 'status'}>
          {task.job.state}
          {task.job.error ? ' · ' + task.job.error.replaceAll('_', ' ') : ''}
        </p>
      )}
      {task.error && <p role="alert">{task.error}</p>}
      {saved?.state === 'unavailable' && (
        <p role="alert">Server hints unavailable: {saved.error?.replaceAll('_', ' ')}</p>
      )}
      {hints.map((hint) => (
        <div className="preview-item" key={hint.id}>
          <strong>
            {hint.name}
            {hint.year ? ' (' + hint.year + ')' : ''} ·{' '}
            {hint.resolution || 'Resolution unavailable'}
          </strong>
          {hint.edition && <p>Version label: {hint.edition}</p>}
          <p className="path-text">{hint.path}</p>
          <p>{hint.evidence?.join(' · ')}</p>
        </div>
      ))}
      {(task.job?.state === 'completed' || saved?.state === 'ready') && !hints.length && (
        <p>No server copies matched this search.</p>
      )}
    </section>
  );
}
