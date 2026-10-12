import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { mockApi } from '../test/fixtures';

test('disabled server still permits idempotent credential removal', async () => {
  const requests = mockApi([], {
    '/server': {
      enabled: false,
      url: '',
      server_type: 'jellyfin',
      user_id: '',
      auto_refresh: false,
      configured: false,
      health: 'not_checked',
      storage: 'keychain',
      detail: '',
    },
  });
  location.hash = 'connections';
  render(<App />);
  const clear = await screen.findByRole('button', { name: 'Clear media server key' });
  expect(clear).toBeEnabled();
  await userEvent.click(clear);
  await waitFor(() =>
    expect(requests.some((r) => r.path === '/server/credentials' && r.method === 'DELETE')).toBe(
      true,
    ),
  );
  expect(await screen.findByText('Server credential cleared.')).toBeVisible();
});
test('undo with residual directory files displays recovery warning', async () => {
  mockApi([], {
    '/jobs': [
      {
        id: 'undo',
        kind: 'undo',
        state: 'failed',
        progress: {},
        error: 'partial',
        result: {
          batch_id: 'batch',
          state: 'partial',
          completed_operation_ids: ['one'],
          failed_operation_ids: [],
          pending_operation_ids: [],
          recovery_item_ids: ['item'],
        },
      },
    ],
  });
  location.hash = 'jobs';
  render(<App />);
  expect(await screen.findByText(/1 item.*files.*both locations/i)).toBeVisible();
});

test('item review shows the paths that need manual recovery', async () => {
  const item = {
    id: 'film',
    source_id: 's',
    path: 'C:\\Incoming\\Film',
    kind: 'movies' as const,
    status: 'error' as const,
    signature: { type: 'directory' },
    decision: null,
    metadata: {
      title: 'Film',
      recovery_note: 'Undo left files in both locations.',
      recovery_paths: ['C:\\Incoming\\Film', 'D:\\Library\\Film'],
    },
  };
  mockApi([item]);
  location.hash = 'review';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review Film' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Undo left files in both locations.');
  expect(screen.getByText('D:\\Library\\Film')).toBeVisible();
});
