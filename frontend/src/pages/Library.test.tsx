import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';
test('overview counts include books and music with seven real collections', async () => {
  mockApi([
    makeItem('Book one', 'books'),
    makeItem('Book two', 'books'),
    makeItem('Book three', 'books'),
    makeItem('Track', 'music'),
  ]);
  render(<App />);
  expect(await screen.findByText('3 books')).toBeVisible();
  expect(screen.getByText('1 music item')).toBeVisible();
});
test('global search resets music collection and hidden status filters', async () => {
  mockApi([makeItem('Interstellar'), makeItem('Track', 'music')]);
  render(<App />);
  await userEvent.click(screen.getByRole('button', { name: 'Music' }));
  expect(await screen.findByRole('button', { name: 'Review Track' })).toBeVisible();
  await userEvent.selectOptions(
    screen.getByRole('combobox', { name: 'Filter status' }),
    'organised',
  );
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search library' }), 'Interstellar');
  expect(await screen.findByRole('button', { name: 'Review Interstellar' })).toBeVisible();
  expect(screen.getByRole('combobox', { name: 'Filter status' })).toHaveValue('');
});
test('failed approved items remain selectable for preview and review', async () => {
  const item = makeItem('Arrival', 'movies', 'error');
  item.decision = {
    item_id: item.id,
    provider: 'manual',
    provider_id: '',
    metadata: { title: 'Arrival' },
    evidence: [],
  };
  mockApi([item]);
  location.hash = 'review';
  render(<App />);
  expect(await screen.findByText('Operation failed · match retained')).toBeVisible();
  expect(screen.getByRole('checkbox', { name: 'Select Arrival' })).toBeEnabled();
});
test('candidate selection requires explicit confirmation and manual correction preserves evidence', async () => {
  const item = makeItem('arrival');
  const requests = mockApi([item], {
    '/items/arrival/candidates': {
      state: 'ready',
      items: [
        {
          provider: 'tmdb',
          provider_id: '329865',
          title: 'Arrival',
          year: '2016',
          metadata: { title: 'Arrival', plot: 'A & B', year: '2016' },
          evidence: ['Title agrees', 'Year agrees'],
        },
      ],
      error: null,
    },
  });
  location.hash = 'review';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review arrival' }));
  const dialog = screen.getByRole('dialog');
  await userEvent.click(await within(dialog).findByRole('radio', { name: /Arrival.*2016/ }));
  expect(requests.some((r) => r.method === 'PUT')).toBe(false);
  expect(within(dialog).getByText('Title agrees')).toBeVisible();
  await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm match' }));
  await waitFor(() =>
    expect(
      requests.find((r) => r.method === 'PUT' && r.path.endsWith('/decision'))?.body,
    ).toMatchObject({
      item_id: 'arrival',
      provider: 'tmdb',
      metadata: { title: 'Arrival', plot: 'A & B' },
    }),
  );
  expect(requests.some((r) => r.path.endsWith('/execute'))).toBe(false);
});
test('empty collection distinguishes no matching search results', async () => {
  mockApi([]);
  location.hash = 'books';
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'No books yet' })).toBeVisible();
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search library' }), 'missing');
  expect(await screen.findByRole('heading', { name: 'No results found' })).toBeVisible();
});

test('review filters by collection without dropping other categories from its counts', async () => {
  mockApi([makeItem('Film'), makeItem('Book', 'books')]);
  location.hash = 'review';
  render(<App />);
  await screen.findByRole('button', { name: 'Review Film' });
  await userEvent.selectOptions(
    screen.getByRole('combobox', { name: 'Filter collection' }),
    'books',
  );
  expect(await screen.findByRole('button', { name: 'Review Book' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Review Film' })).not.toBeInTheDocument();
});
test('manual correction persists edited metadata and lookup errors are actionable', async () => {
  const item = makeItem('wrong-name');
  const requests = mockApi([item], {
    '/items/wrong-name/candidates': { state: 'error', items: [], error: 'missing_credentials' },
  });
  location.hash = 'review';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review wrong-name' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('missing_credentials');
  await userEvent.clear(screen.getByRole('textbox', { name: 'Title' }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Title' }), 'Corrected title');
  await userEvent.click(screen.getByRole('button', { name: 'Confirm match' }));
  await waitFor(() =>
    expect(
      requests.find((r) => r.method === 'PUT' && r.path.endsWith('/decision'))?.body,
    ).toMatchObject({ provider: 'manual', metadata: { title: 'Corrected title' } }),
  );
});
test('collections paginate and grid/list preferences use backend settings', async () => {
  const requests = mockApi(Array.from({ length: 50 }, (_, i) => makeItem(`Movie ${i}`)));
  location.hash = 'movies';
  render(<App />);
  await screen.findByRole('button', { name: 'Review Movie 0' });
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByRole('button', { name: 'Review Movie 49' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Review Movie 0' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'List view' }));
  await waitFor(() =>
    expect(requests.find((r) => r.method === 'PUT' && r.path === '/settings')?.body).toEqual({
      view: 'list',
    }),
  );
});

test('appearance save failure remains visible instead of looking successful', async () => {
  mockApi([], {
    'PUT /settings': new Response(JSON.stringify({ message: 'Cannot save preferences' }), {
      status: 400,
    }),
  });
  render(<App />);
  await screen.findByRole('heading', { name: 'Overview' });
  await userEvent.click(screen.getByRole('button', { name: 'Change appearance' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot save preferences');
});
test('view preference save failure is shown without an unhandled rejection', async () => {
  mockApi([makeItem('Arrival')], {
    'PUT /settings': new Response(JSON.stringify({ message: 'Cannot save preferences' }), {
      status: 400,
    }),
  });
  location.hash = 'movies';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'List view' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot save preferences');
});

test('music manual correction saves track_number used by the naming renderer', async () => {
  const requests = mockApi([makeItem('Track', 'music')]);
  location.hash = 'music';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review Track' }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Track number' }), '3');
  await userEvent.click(screen.getByRole('button', { name: 'Confirm match' }));
  await waitFor(() =>
    expect(
      requests.find((r) => r.path.endsWith('/decision') && r.method === 'PUT')?.body,
    ).toMatchObject({ metadata: { track_number: '3' } }),
  );
});
test('movie review only asks for relevant naming fields', async () => {
  mockApi([makeItem('Arrival')]);
  location.hash = 'movies';
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: 'Review Arrival' }));
  expect(screen.queryByRole('textbox', { name: 'Season' })).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'Episode' })).not.toBeInTheDocument();
});
