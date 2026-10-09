import { useState } from 'react';
import { api } from './client';
import { useWorkspace } from '../state/WorkspaceProvider';
import { type Job, active } from '../types';
export function useTask() {
  const { jobs, refresh } = useWorkspace();
  const [submitted, setSubmitted] = useState<Job | null>(null),
    [sending, setSending] = useState(false),
    [error, setError] = useState('');
  const job = jobs.find((j) => j.id === submitted?.id) ?? submitted;
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
