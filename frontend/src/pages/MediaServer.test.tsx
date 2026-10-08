import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';
const server = {
  enabled: true,
  url: 'http://localhost:8096',
  server_type: 'jellyfin',
  user_id: '',
  auto_refresh: false,
  configured: true,
  storage: 'keychain',
  health: 'not_checked',
  detail: '',
};
const tested = {
  id: 'test-server',
  kind: 'server_test',
  state: 'completed',
  progress: {},
  result: {
    server: { id: 's', name: 'Home server', version: '12.0' },
    users: [
      { id: 'user-1', name: 'My profile' },
      { id: 'user-2', name: 'Other profile' },
    ],
  },
  error: null,
};
test('server connection tests expose explicit user choices and saved keys stay blank', async () => {
  const requests = mockApi([], {
    '/server': server,
    'POST /server/test': tested,
    'PUT /server': { ...server, user_id: 'user-2' },
  });
  location.hash = 'connections';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Test media server' }));
  await userEvent.selectOptions(
    await screen.findByRole('combobox', { name: 'Media server user' }),
    'user-2',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Save media server' }));
  await waitFor(() =>
    expect(requests.find((r) => r.method === 'PUT' && r.path === '/server')?.body).toMatchObject({
      user_id: 'user-2',
      auto_refresh: false,
    }),
  );
  expect(screen.getByLabelText('Replacement media server API key')).toHaveValue('');
  expect(requests.find((r) => r.method === 'POST' && r.path === '/server/test')?.body).toBeNull();
});
test('episode gaps require confirmed mapping and show unavailable without invented missing episodes', async () => {
  const requests = mockApi([], {
    '/server': { ...server, user_id: 'user-1' },
    'POST /server/discover': {
      id: 'discover',
      kind: 'server_discover',
      state: 'completed',
      progress: {},
      result: {
        items: [{ id: 'show', name: 'Example show', type: 'Series', provider_ids: { tmdb: '42' } }],
        complete: true,
      },
      error: null,
    },
    'POST /server/gaps': {
      id: 'gaps',
      kind: 'episode_gaps',
      state: 'completed',
      progress: {},
      result: {
        state: 'unavailable',
        missing: [],
        unaired: [],
        unknown_air_date: [],
        error: 'server_unauthorised',
      },
      error: null,
    },
  });
  location.hash = 'gaps';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Load server series' }));
  await screen.findByRole('option', { name: 'Example show' });
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Server series' }), 'show');
  expect(screen.getByRole('button', { name: 'Check episode gaps' })).toBeDisabled();
  expect(screen.getByRole('textbox', { name: 'Confirmed TMDb series ID' })).toHaveValue('42');
  await userEvent.click(screen.getByRole('checkbox', { name: /I confirmed this TMDb mapping/i }));
  await userEvent.click(screen.getByRole('button', { name: 'Check episode gaps' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('unavailable');
  expect(screen.queryByText(/entire season missing/i)).not.toBeInTheDocument();
  expect(
    requests.find((r) => r.method === 'POST' && r.path === '/server/gaps')?.body,
  ).toMatchObject({
    series_id: 'show',
    mapping: { provider: 'tmdb', provider_id: '42', confirmed: true },
    include_specials: false,
  });
});
test('server hints show resolution and evidence without approving or moving the item', async () => {
  const requests = mockApi([makeItem('Arrival')], {
    '/server': { ...server, user_id: 'user-1' },
    'POST /items/Arrival/server-hints': {
      id: 'hints',
      kind: 'server_hints',
      state: 'completed',
      progress: {},
      result: {
        items: [
          {
            id: 'existing',
            name: 'Arrival',
            resolution: '2160p',
            path: '/media/Arrival.mkv',
            provider_ids: { tmdb: '329865' },
            evidence: ['Title agrees; identity needs review'],
          },
        ],
      },
      error: null,
    },
  });
  location.hash = 'movies';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review Arrival' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Check server copies' }));
  expect(await screen.findByText(/2160p/)).toBeVisible();
  expect(screen.getByText(/content has not been hashed/i)).toBeVisible();
  expect(requests.some((r) => r.method === 'PUT' && r.path.endsWith('/decision'))).toBe(false);
  expect(requests.some((r) => r.path.endsWith('/execute'))).toBe(false);
});

test('ready gap reports show actual episode title, air date and status', async () => {
  mockApi([], {
    '/server': { ...server, user_id: 'user-1' },
    'POST /server/discover': {
      id: 'discover',
      kind: 'server_discover',
      state: 'completed',
      progress: {},
      result: {
        items: [{ id: 'show', name: 'Example show', type: 'Series', provider_ids: { tmdb: '42' } }],
      },
      error: null,
    },
    'POST /server/gaps': {
      id: 'gaps',
      kind: 'episode_gaps',
      state: 'completed',
      progress: {},
      result: {
        state: 'ready',
        missing: [[1, 3]],
        unaired: [],
        unknown_air_date: [],
        present: [
          [1, 1],
          [1, 2],
        ],
        catalogue_cached: true,
        catalogue_updated_at: '2026-10-09',
        episodes: [
          {
            season: 1,
            episode: 3,
            title: 'The missing chapter',
            air_date: '2020-01-01',
            state: 'missing',
          },
        ],
      },
      error: null,
    },
  });
  location.hash = 'gaps';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Load server series' }));
  await screen.findByRole('option', { name: 'Example show' });
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Server series' }), 'show');
  await userEvent.click(screen.getByRole('checkbox', { name: /I confirmed this TMDb mapping/i }));
  await userEvent.click(screen.getByRole('button', { name: 'Check episode gaps' }));
  expect(await screen.findByText(/The missing chapter/)).toBeVisible();
  expect(screen.getByText('2020-01-01')).toBeVisible();
});
