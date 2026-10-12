import { render, screen, within } from '@testing-library/react';
import { expect, test } from 'vitest';
import App from '../App';
import { mockApi } from '../test/fixtures';
import type { Job } from '../types';

test('undo jobs retain reports and details without offering another undo', async () => {
  const jobs: Job[] = [
    { id: 'undo-completed', kind: 'undo', state: 'completed', progress: {}, result: { batch_id: 'undo-batch' }, error: null },
    { id: 'undo-partial', kind: 'undo', state: 'failed', progress: {}, result: { batch_id: 'partial-batch', state: 'partial' }, error: 'partial' },
    { id: 'organise-completed', kind: 'organise', state: 'completed', progress: {}, result: { batch_id: 'forward-batch' }, error: null },
    { id: 'sidecars-completed', kind: 'sidecars', state: 'completed', progress: {}, result: { batch_id: 'sidecar-batch' }, error: null },
  ];
  mockApi([], { '/jobs': jobs });
  location.hash = 'jobs';
  render(<App />);
  for (const job of jobs) {
    const card = (await screen.findByText(job.id, { exact: true })).closest('article')!;
    expect(within(card).getByRole('button', { name: 'Operation details' })).toBeVisible();
    expect(within(card).getByRole('link', { name: 'Export JSON' })).toBeVisible();
    if (job.kind === 'undo') {
      expect(within(card).queryByRole('button', { name: 'Preview undo' })).not.toBeInTheDocument();
    } else {
      expect(within(card).getByRole('button', { name: 'Preview undo' })).toBeVisible();
    }
  }
  const partial = screen.getByText('undo-partial', { exact: true }).closest('article')!;
  expect(within(partial).getByRole('button', { name: 'Retry job' })).toBeVisible();
});
