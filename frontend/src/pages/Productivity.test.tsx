import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';
const profile = {
  id: 'default-movies',
  label: 'Movies',
  kind: 'movies',
  version: 1,
  movie_template: '{title}{ext}',
  folder_template: '{title}',
  episode_template: '{title} - S{season:02d}E{episode:02d}{ext}',
  music_template: '{artist}/{title}{ext}',
  book_template: '{author}/{title}{ext}',
  quality_keys: ['screen_size'],
};
test('preset examples require an explicit preview and invalid saves stay visible', async () => {
  const requests = mockApi([], {
    '/profiles': [profile],
    'POST /profiles/preview': { examples: { movies: 'Arrival.mkv' }, fictional: true },
    'PUT /profiles/default-movies': new Response(
      JSON.stringify({ message: 'Naming cannot escape its selected root' }),
      { status: 400 },
    ),
  });
  location.hash = 'profiles';
  render(<App />);
  await screen.findByRole('option', { name: 'Movies · v1' });
  await userEvent.selectOptions(
    screen.getByRole('combobox', { name: 'Naming preset' }),
    profile.id,
  );
  expect(screen.getByRole('textbox', { name: 'Movie template' })).toHaveValue('{title}{ext}');
  await userEvent.click(screen.getByRole('button', { name: 'Preview examples' }));
  expect(await screen.findByText('Arrival.mkv')).toBeVisible();
  expect(screen.getByText(/fictional examples/i)).toBeVisible();
  await userEvent.clear(screen.getByRole('textbox', { name: 'Movie template' }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Movie template' }), '../escape.mkv');
  await userEvent.click(screen.getByRole('button', { name: 'Save preset' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('cannot escape');
  expect(
    requests.find((r) => r.method === 'PUT' && r.path === '/profiles/default-movies')?.body,
  ).toMatchObject({ version: 1, movie_template: '../escape.mkv' });
  expect(requests.some((r) => r.path.endsWith('/execute'))).toBe(false);
});
test('comparison explicitly selects copies, hashes only on request, and offers no delete action', async () => {
  const requests = mockApi([makeItem('a'), makeItem('b')], {
    'POST /comparisons': {
      id: 'compare',
      kind: 'comparison',
      state: 'completed',
      progress: {},
      result: {
        exact: true,
        items: [
          {
            item_id: 'a',
            path: 'C:\\a.mkv',
            title: 'a',
            quality: { screen_size: '1080p' },
            edition: '',
            bytes: 5,
          },
        ],
        exact_groups: [['a', 'b']],
        version_groups: [],
        errors: [],
      },
      error: null,
    },
  });
  location.hash = 'comparison';
  render(<App />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Compare a' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Compare b' }));
  await userEvent.click(
    screen.getByRole('checkbox', { name: 'Verify exact content with SHA-256' }),
  );
  await userEvent.click(screen.getByRole('button', { name: 'Compare selected' }));
  expect(await screen.findByText(/1 exact content group/i)).toBeVisible();
  expect(requests.find((r) => r.path === '/comparisons' && r.method === 'POST')?.body).toEqual({
    item_ids: ['a', 'b'],
    exact: true,
  });
  expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  expect(requests.some((r) => r.method === 'DELETE' || r.path.endsWith('/execute'))).toBe(false);
});
test('source watching persists opt-in stability without submitting an organisation job', async () => {
  const requests = mockApi([], {
    '/sources': [
      {
        id: 's',
        path: 'C:\\Incoming',
        label: 'Incoming',
        kind: 'movies',
        watch: 0,
        archived: false,
      },
    ],
    '/sources/s/watch': { enabled: false, stability_seconds: 30, next_attempt: 0 },
    'PUT /sources/s/watch': { enabled: true, stability_seconds: 45, next_attempt: 0 },
  });
  location.hash = 'sources';
  render(<App />);
  await userEvent.click(
    await screen.findByRole('checkbox', { name: 'Watch Incoming for stable arrivals' }),
  );
  const interval = screen.getByRole('spinbutton', {
    name: 'Stability interval for Incoming (seconds)',
  });
  await userEvent.clear(interval);
  await userEvent.type(interval, '45');
  await userEvent.click(screen.getByRole('button', { name: 'Save watching for Incoming' }));
  await waitFor(() =>
    expect(requests.find((r) => r.path === '/sources/s/watch' && r.method === 'PUT')?.body).toEqual(
      { enabled: true, stability_seconds: 45, identify_arrivals: false },
    ),
  );
  expect(screen.getByText(/watching indexes stable arrivals/i)).toBeVisible();
  expect(requests.some((r) => r.method === 'POST' && r.path === '/jobs')).toBe(false);
});
test('jobs expose explicit exports of saved outcomes', async () => {
  mockApi([], {
    '/jobs': [
      {
        id: 'done',
        kind: 'scan',
        state: 'completed',
        progress: {},
        result: { processed: 2 },
        error: null,
      },
    ],
  });
  location.hash = 'jobs';
  render(<App />);
  expect(await screen.findByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    '/api/v1/jobs/done/report?format=csv',
  );
  expect(screen.getByRole('link', { name: 'Export JSON' })).toHaveAttribute(
    'href',
    '/api/v1/jobs/done/report?format=json',
  );
});

test('preview requests bind the selected stored preset rather than rebuilding its templates', async () => {
  const item = makeItem('confirmed', 'movies', 'approved');
  item.decision = {
    item_id: item.id,
    provider: 'manual',
    provider_id: '',
    metadata: { title: 'confirmed' },
    evidence: [],
  };
  const requests = mockApi([item], {
    '/profiles': [profile],
    '/destinations': [{ id: 'd', label: 'Library', path: 'D:\\Library' }],
    'POST /plans': { id: 'preview', revision: 1, operations: [], issues: [] },
  });
  location.hash = 'movies';
  render(<App />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Select confirmed' }));
  await userEvent.click(screen.getByRole('button', { name: 'Preview changes' }));
  await screen.findByRole('option', { name: 'Movies · v1' });
  await userEvent.selectOptions(
    screen.getByRole('combobox', { name: 'Naming preset' }),
    'default-movies',
  );
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Destination' }), 'd');
  await userEvent.click(screen.getByRole('button', { name: 'Create preview' }));
  await waitFor(() =>
    expect(requests.find((r) => r.path === '/plans' && r.method === 'POST')?.body).toMatchObject({
      options: { profile_id: 'default-movies' },
    }),
  );
  expect(requests.some((r) => r.path.endsWith('/execute'))).toBe(false);
});

test('preset output switches are off until explicitly saved', async () => {
  const requests = mockApi([], {
    '/profiles': [
      { ...profile, nfo_enabled: false, artwork_enabled: false, episode_nfo_enabled: false },
    ],
    'PUT /profiles/default-movies': {
      ...profile,
      nfo_enabled: true,
      artwork_enabled: false,
      episode_nfo_enabled: false,
    },
  });
  location.hash = 'profiles';
  render(<App />);
  await screen.findByRole('option', { name: 'Movies · v1' });
  await userEvent.selectOptions(
    screen.getByRole('combobox', { name: 'Naming preset' }),
    profile.id,
  );
  expect(screen.getByRole('checkbox', { name: 'Write NFO metadata' })).not.toBeChecked();
  await userEvent.click(screen.getByRole('checkbox', { name: 'Write NFO metadata' }));
  await userEvent.click(screen.getByRole('button', { name: 'Save preset' }));
  await waitFor(() =>
    expect(requests.find((r) => r.method === 'PUT')?.body).toMatchObject({
      nfo_enabled: true,
      artwork_enabled: false,
      episode_nfo_enabled: false,
    }),
  );
});
