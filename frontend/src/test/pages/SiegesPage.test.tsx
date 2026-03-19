import { screen, waitForElementToBeRemoved } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, afterAll, afterEach, describe, it, expect } from 'vitest';
import { server } from '../server';
import { renderWithProviders } from '../utils';
import SiegesPage from '../../pages/SiegesPage';
import type { Siege } from '../../api/types';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('SiegesPage', () => {
  it('renders the page heading', () => {
    renderWithProviders(<SiegesPage />);
    expect(screen.getByRole('heading', { name: 'Sieges' })).toBeInTheDocument();
  });

  it('has a New Siege button', () => {
    renderWithProviders(<SiegesPage />);
    expect(screen.getByRole('button', { name: /new siege/i })).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    server.use(
      http.get('/api/sieges', async () => {
        await new Promise(() => {}); // never resolves
      }),
    );
    renderWithProviders(<SiegesPage />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows empty state when there are no sieges', async () => {
    renderWithProviders(<SiegesPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText(/no sieges yet/i)).toBeInTheDocument();
  });

  it('shows table column headers after loading', async () => {
    renderWithProviders(<SiegesPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText('Date')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Links')).toBeInTheDocument();
  });

  it('renders siege rows when API returns data', async () => {
    const sieges: Siege[] = [
      {
        id: 1,
        date: '2026-03-22',
        status: 'planning',
        defense_scroll_count: 0,
        computed_scroll_count: 0,
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
      {
        id: 2,
        date: '2026-03-29',
        status: 'active',
        defense_scroll_count: 2,
        computed_scroll_count: 2,
        created_at: '2026-03-19T00:00:00Z',
        updated_at: '2026-03-19T00:00:00Z',
      },
    ];
    server.use(http.get('/api/sieges', () => HttpResponse.json(sieges)));

    renderWithProviders(<SiegesPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));

    expect(screen.getByText('2026-03-22')).toBeInTheDocument();
    expect(screen.getByText('2026-03-29')).toBeInTheDocument();
    expect(screen.getByText('Planning')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('shows error message when the API call fails', async () => {
    server.use(
      http.get('/api/sieges', () => HttpResponse.error()),
    );
    renderWithProviders(<SiegesPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText(/failed to load sieges/i)).toBeInTheDocument();
  });
});
