import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { mockApi } from '../test/fixtures';

test.each([
  { storage: 'session', replacementSession: false, expectedSession: true },
  { storage: 'keychain', replacementSession: true, expectedSession: false },
])(
  'clears the stored $storage credential independently of replacement storage',
  async ({ storage, replacementSession, expectedSession }) => {
    const requests = mockApi([], {
      '/providers': [
        {
          id: 'tmdb',
          label: 'TMDb',
          requires_key: true,
          configured: true,
          storage,
          health: 'not_checked',
          detail: '',
          consent_enabled: true,
        },
      ],
    });
    location.hash = 'connections';
    render(<App />);
    const panel = (await screen.findByRole('heading', { name: 'TMDb' })).closest('section')!;
    const replacement = within(panel).getByRole('checkbox', { name: 'Use for this session only' });
    if (replacementSession) await userEvent.click(replacement);
    expect(replacement).toHaveProperty('checked', replacementSession);

    await userEvent.click(within(panel).getByRole('button', { name: 'Clear key' }));

    await waitFor(() =>
      expect(
        requests.find((r) => r.method === 'POST' && r.path === '/providers/tmdb/credentials')?.body,
      ).toEqual({
        key: '',
        session_only: expectedSession,
      }),
    );
  },
);
