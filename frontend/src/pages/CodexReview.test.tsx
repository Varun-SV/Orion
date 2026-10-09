import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';
import { type Kind } from '../types';

const providers = [
  'tmdb',
  'anilist',
  'anidb',
  'musicbrainz',
  'acoustid',
  'audd',
  'openlibrary',
].map((id) => ({
  id,
  label: id,
  requires_key: false,
  configured: true,
  storage: 'not_required',
  health: 'not_checked',
  detail: '',
  consent_enabled: true,
}));
test('seven providers share one media-server form and one status request', async () => {
  const requests = mockApi([], {
    '/providers': providers,
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
  await screen.findByRole('heading', { name: 'openlibrary' });
  expect(screen.getAllByRole('button', { name: 'Save media server' })).toHaveLength(1);
  expect(screen.getAllByLabelText('Replacement media server API key')).toHaveLength(1);
  expect(requests.filter((r) => r.path === '/server' && r.method === 'GET')).toHaveLength(1);
});
test('collection preference dropdown offers only compatible providers', async () => {
  mockApi([], {
    '/categories': [
      {
        id: 'movies',
        name: 'Movies',
        kind: 'movies',
        dest_subpath: 'Movies',
        api_pref: 'tmdb',
        compatible_providers: ['tmdb'],
      },
    ],
  });
  location.hash = 'settings';
  render(<App />);
  const select = await screen.findByRole('combobox', { name: 'Preferred provider' });
  expect(within(select).queryByRole('option', { name: 'AudD' })).not.toBeInTheDocument();
  expect(within(select).getByRole('option', { name: 'TMDb' })).toBeVisible();
});

test.each([
  ['music', { artist: 'Selected artist', album: 'Selected album', track_number: '8' }],
  ['books', { author: 'Selected author', series: 'Selected series' }],
  ['series', { season: '2', episode: '7' }],
] as [Kind, Record<string, string>][])(
  'selected %s candidate displays and saves its metadata, replacing stale edits',
  async (kind, metadata) => {
    const item = makeItem('Original', kind);
    item.decision = {
      item_id: item.id,
      provider: 'manual',
      provider_id: '',
      metadata: {
        title: 'Original',
        filename: 'old.mkv',
        ...Object.fromEntries(Object.keys(metadata).map((k) => [k, 'Old'])),
      },
      evidence: [],
    };
    const candidates = [
      {
        provider: 'catalogue',
        provider_id: '1',
        title: 'First',
        year: '2020',
        metadata: {
          title: 'First',
          ...Object.fromEntries(Object.keys(metadata).map((k) => [k, 'First'])),
        },
        evidence: [],
      },
      {
        provider: 'catalogue',
        provider_id: '2',
        title: 'Second',
        year: '2021',
        metadata: { title: 'Second', ...metadata },
        evidence: [],
      },
    ];
    const requests = mockApi([item], {
      ['/items/' + item.id + '/candidates']: { state: 'ready', error: null, items: candidates },
    });
    location.hash = kind;
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: 'Review Original' }));
    const dialog = screen.getByRole('dialog');
    await userEvent.click(await within(dialog).findByRole('radio', { name: /First.*2020/ }));
    const label = (key: string) =>
      key === 'track_number' ? 'Track number' : key[0].toUpperCase() + key.slice(1);
    const first = Object.keys(metadata)[0];
    expect(within(dialog).getByRole('textbox', { name: label(first) })).toHaveValue('First');
    await userEvent.clear(within(dialog).getByRole('textbox', { name: label(first) }));
    await userEvent.type(
      within(dialog).getByRole('textbox', { name: label(first) }),
      'Stale override',
    );
    await userEvent.click(within(dialog).getByRole('radio', { name: /Second.*2021/ }));
    for (const [key, value] of Object.entries(metadata))
      expect(within(dialog).getByRole('textbox', { name: label(key) })).toHaveValue(value);
    expect(within(dialog).getByRole('textbox', { name: /Exact filename override/ })).toHaveValue(
      '',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm match' }));
    await waitFor(() =>
      expect(
        requests.find((r) => r.method === 'PUT' && r.path.endsWith('/decision'))?.body,
      ).toMatchObject({
        provider_id: '2',
        metadata: { title: 'Second', filename: '', ...metadata },
      }),
    );
  },
);
