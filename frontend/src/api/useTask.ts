import { useEffect, useState } from 'react';
import { api } from './client';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type Job, active } from '../types';
export function useTask() {
  const { jobs, refresh } = useWorkspace();
  const [submitted, setSubmitted] = useState<Job | null>(null),
    [sending, setSending] = useState(false),
    [error, setError] = useState('');
  // Recent-job lists are capped. Keep the submitted job independently
  // refreshed by ID until its terminal state is observed.
  useEffect(() => {
    if (!submitted || !active(submitted)) return;
    let mounted = true;
    let timer: ReturnType<typeof setTimeout>;
    const id = submitted.id;
    async function poll() {
      try {
        const latest = await api<Job>('/jobs/' + encodeURIComponent(id));
        if (!mounted) return;
        setSubmitted((previous) => previous?.id === id ? latest : previous);
        if (!active(latest)) {
          refresh();
          return;
        }
      } catch (e) {
        if (mounted) setError((e as Error).message);
      }
      if (mounted) timer = setTimeout(poll, 2000);
    }
    timer = setTimeout(poll, 2000);
    return () => { mounted = false; clearTimeout(timer); };
  }, [submitted?.id, submitted?.state, refresh]);
  const listed = jobs.find((j) => j.id === submitted?.id);
  const job = submitted && !active(submitted) ? submitted : listed ?? submitted;
  async function submit(path: string, options: RequestInit = { method: 'POST' }) {
    setSending(true);
    setError('');
    try {
      setSubmitted(await api<Job>(path, options));
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  return {
    job,
    busy: sending || (!!job && active(job)),
    error,
    submit,
    clear: () => setSubmitted(null),
  };
}
