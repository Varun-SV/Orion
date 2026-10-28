import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import App from '../App';
import { makeItem, mockApi } from '../test/fixtures';

const completed = {
  id: 'comparison-1',
  kind: 'comparison',
  state: 'completed',
  progress: { phase: 'complete' },
  result: {
    exact: true,
    items: [
      {
        item_id: 'a',
        path: 'C:\\a.mkv',
        title: 'a',
        quality: {},
        edition: '',
        bytes: 5,
      },
      {
        item_id: 'b',
        path: 'C:\\b.mkv',
        title: 'b',
        quality: {},
        edition: '',
        bytes: 5,
      },
    ],
    exact_groups: [['a', 'b']],
    version_groups: [],
    errors: [],
  },
  error: null,
};

test('polls a submitted comparison by ID after it falls outside the recent jobs list', async () => {
  const requests = mockApi([makeItem('a'), makeItem('b')], {
    '/jobs': [],
    'POST /comparisons': { ...completed, state: 'running', result: null, progress: {} },
    '/jobs/comparison-1': completed,
  });
  location.hash = 'comparison';
  render(<App />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Compare a' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Compare b' }));
  await userEvent.click(screen.getByRole('button', { name: 'Compare selected' }));

  expect(await screen.findByText(/1 exact content group/i, {}, { timeout: 10000 })).toBeVisible();
  expect(requests.some((r) => r.path === '/jobs/comparison-1')).toBe(true);
  expect(screen.getByRole('button', { name: 'Compare selected' })).toBeEnabled();
});

test('shows a comparison failure returned by the job endpoint', async () => {
  mockApi([makeItem('a'), makeItem('b')], {
    '/jobs': [],
    'POST /comparisons': {
      ...completed,
      state: 'running',
      result: null,
      progress: {},
    },
    '/jobs/comparison-1': { ...completed, state: 'failed', result: null, error: 'hash failed' },
  });
  location.hash = 'comparison';
  render(<App />);
  await userEvent.click(await screen.findByRole('checkbox', { name: 'Compare a' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Compare b' }));
  await userEvent.click(screen.getByRole('button', { name: 'Compare selected' }));

  expect(await screen.findByRole('alert', {}, { timeout: 10000 })).toHaveTextContent('hash failed');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Compare selected' })).toBeEnabled());
});
