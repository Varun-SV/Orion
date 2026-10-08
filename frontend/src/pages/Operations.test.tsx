import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';
import type { Plan, Job } from '../types';
const plan: Plan = {
  id: 'preview',
  revision: 1,
  issues: [],
  operations: [
    {
      id: 'move',
      plan_id: 'preview',
      item_id: 'Arrival',
      kind: 'move',
      source: 'C:\\Incoming\\Arrival.mkv',
      destination: 'D:\\Library\\Arrival (2016)\\Arrival.mkv',
      state: 'pending',
      expected_signature: { size: 1048576 },
      verification: { transfer_mode: 'copy' },
    },
  ],
};
const running: Job = {
  id: 'durable',
  kind: 'organise',
  state: 'running',
  progress: {
    phase: 'Copying',
    items_done: 1,
    items_total: 3,
    bytes_done: 524288,
    bytes_total: 1048576,
  },
  result: null,
  error: null,
};
test('stored plan shows real paths and requires validation plus explicit confirmation', async () => {
  const requests = mockApi([], {
    '/plans': [plan],
    '/plans/preview': plan,
    'POST /plans/preview/revalidate': plan,
    'POST /plans/preview/execute': running,
  });
  location.hash = 'plans';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Open plan preview' }));
  expect(await screen.findByText(plan.operations[0].destination)).toBeVisible();
  expect(screen.getByText(/Cross-volume copy/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Organise' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Revalidate' }));
  await userEvent.click(screen.getByRole('checkbox', { name: /I reviewed these paths/ }));
  await userEvent.click(screen.getByRole('button', { name: 'Organise' }));
  await waitFor(() =>
    expect(requests.some((r) => r.path === '/plans/preview/execute' && r.method === 'POST')).toBe(
      true,
    ),
  );
});
test('stale source preflight disables execution and shows conflict explanation', async () => {
  const invalid = {
    ...plan,
    issues: [
      {
        code: 'source_changed',
        detail: 'Source changed; create a new preview',
        operation_id: 'move',
        item_id: 'Arrival',
      },
    ],
  };
  mockApi([], {
    '/plans': [plan],
    '/plans/preview': plan,
    'POST /plans/preview/revalidate': invalid,
  });
  location.hash = 'plans';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Open plan preview' }));
  await userEvent.click(screen.getByRole('button', { name: 'Revalidate' }));
  expect(await screen.findByText('Source changed; create a new preview')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Organise' })).toBeDisabled();
});
test('job centre restores persisted progress after reopening and supports cancellation', async () => {
  const requests = mockApi([], {
    '/jobs': [running],
    'POST /jobs/durable/cancel': { ...running, state: 'cancelling' },
  });
  location.hash = 'jobs';
  const first = render(<App />);
  expect(await screen.findByText('Copying')).toBeVisible();
  expect(screen.getByText('512.0 KB of 1.0 MB')).toBeVisible();
  first.unmount();
  render(<App />);
  expect(await screen.findByText('Copying')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Cancel job' }));
  await waitFor(() =>
    expect(requests.some((r) => r.path === '/jobs/durable/cancel' && r.method === 'POST')).toBe(
      true,
    ),
  );
});
test('partial batch retains successful members and enables independent retry', async () => {
  const partial = {
    ...running,
    state: 'failed',
    result: {
      batch_id: 'batch',
      state: 'partial',
      completed_operation_ids: ['a', 'b'],
      failed_operation_ids: ['c'],
      pending_operation_ids: [],
    },
    error: 'partial',
  };
  const requests = mockApi([], { '/jobs': [partial], 'POST /jobs/durable/retry': running });
  location.hash = 'jobs';
  render(<App />);
  expect(await screen.findByText('2 completed · 1 failed · 0 pending')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Retry job' }));
  await waitFor(() => expect(requests.some((r) => r.path === '/jobs/durable/retry')).toBe(true));
});
test('undo preview preserves occupied original paths and integration failure remains separate', async () => {
  const complete = {
    ...running,
    state: 'completed',
    progress: {},
    result: { batch_id: 'batch', state: 'completed', completed_operation_ids: ['move'] },
  };
  const undo = {
    ...plan,
    id: 'undo',
    issues: [
      {
        code: 'destination_exists',
        detail: 'Original path occupied; retain organised file',
        operation_id: 'move',
        item_id: 'Arrival',
      },
    ],
  };
  mockApi([], {
    '/jobs': [
      complete,
      {
        ...running,
        id: 'server-refresh',
        kind: 'server_refresh',
        state: 'failed',
        progress: {},
        error: 'server_unavailable',
      },
    ],
    '/batches': [
      { id: 'batch', plan_id: 'preview', state: 'completed', data: {}, created_at: '2026-10-09' },
    ],
    'POST /batches/batch/undo-plan': undo,
  });
  location.hash = 'jobs';
  render(<App />);
  expect(await screen.findByText('server_unavailable')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Preview undo' }));
  expect(await screen.findByText('Original path occupied; retain organised file')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Organise' })).toBeDisabled();
});
test('confirmed selected items produce preview without executing file changes', async () => {
  const item = makeItem('Arrival', 'movies', 'approved');
  item.decision = {
    item_id: item.id,
    provider: 'manual',
    provider_id: '',
    metadata: { title: 'Arrival' },
    evidence: [],
  };
  const requests = mockApi([item], {
    '/destinations': [{ id: 'dest', path: 'D:\\Library', label: 'Library' }],
    'POST /plans': plan,
  });
  location.hash = 'movies';
  render(<App />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Select Arrival' }));
  await userEvent.click(screen.getByRole('button', { name: 'Preview changes' }));
  await userEvent.selectOptions(
    await screen.findByRole('combobox', { name: 'Destination' }),
    'dest',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Create preview' }));
  expect(await screen.findByText(plan.operations[0].destination)).toBeVisible();
  expect(requests.find((r) => r.path === '/plans' && r.method === 'POST')?.body).toMatchObject({
    item_ids: ['Arrival'],
    options: { destination_id: 'dest' },
  });
  expect(requests.some((r) => r.path.endsWith('/execute'))).toBe(false);
});
