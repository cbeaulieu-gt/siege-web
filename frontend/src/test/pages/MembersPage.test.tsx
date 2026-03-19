import { screen, waitForElementToBeRemoved } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, afterAll, afterEach, describe, it, expect } from 'vitest';
import { server } from '../server';
import { renderWithProviders } from '../utils';
import MembersPage from '../../pages/MembersPage';
import type { Member } from '../../api/types';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('MembersPage', () => {
  it('renders the page heading', () => {
    renderWithProviders(<MembersPage />);
    expect(screen.getByRole('heading', { name: 'Members' })).toBeInTheDocument();
  });

  it('has an Add Member button', () => {
    renderWithProviders(<MembersPage />);
    expect(screen.getByRole('button', { name: /add member/i })).toBeInTheDocument();
  });

  it('renders the role filter select', () => {
    renderWithProviders(<MembersPage />);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders the Active only checkbox', () => {
    renderWithProviders(<MembersPage />);
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByText('Active only')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    server.use(
      http.get('/api/members', async () => {
        await new Promise(() => {});
      }),
    );
    renderWithProviders(<MembersPage />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows empty state when API returns no members', async () => {
    renderWithProviders(<MembersPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText(/no members found/i)).toBeInTheDocument();
  });

  it('shows table column headers after loading', async () => {
    renderWithProviders(<MembersPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    expect(screen.getByText('Power')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('renders member rows when API returns data', async () => {
    const members: Member[] = [
      {
        id: 1,
        name: 'Aethon',
        discord_username: 'aethon#1234',
        role: 'heavy_hitter',
        power_level: 'gt_25m',
        is_active: true,
      },
      {
        id: 2,
        name: 'Brint',
        discord_username: null,
        role: 'novice',
        power_level: 'lt_10m',
        is_active: false,
      },
    ];
    server.use(http.get('/api/members', () => HttpResponse.json(members)));

    renderWithProviders(<MembersPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));

    expect(screen.getByText('Aethon')).toBeInTheDocument();
    expect(screen.getByText('Brint')).toBeInTheDocument();
    expect(screen.getByText('Heavy Hitter')).toBeInTheDocument();
    expect(screen.getByText('Novice')).toBeInTheDocument();
    expect(screen.getByText('> 25M')).toBeInTheDocument();
    expect(screen.getByText('< 10M')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('shows error message when the API call fails', async () => {
    server.use(
      http.get('/api/members', () => HttpResponse.error()),
    );
    renderWithProviders(<MembersPage />);
    await waitForElementToBeRemoved(() => screen.queryByText('Loading...'));
    expect(screen.getByText(/failed to load members/i)).toBeInTheDocument();
  });
});
