import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CoordinatorDashboard from './CoordinatorDashboard';

const navigateMock = vi.fn();
const getProblemsMock = vi.fn();
const getVolunteersMock = vi.fn();
const getRecommendationsMock = vi.fn();
const assignTaskMock = vi.fn();
const mockProfile = {
  id: 'coord-1',
  full_name: 'Test Coordinator',
  role: 'coordinator' as const,
};

vi.mock('../contexts/auth-shared', () => ({
  useAuth: () => ({
    profile: mockProfile,
  }),
}));

vi.mock('../services/api', () => ({
  api: {
    getProblems: (...args: unknown[]) => getProblemsMock(...args),
    getVolunteers: (...args: unknown[]) => getVolunteersMock(...args),
    getRecommendations: (...args: unknown[]) => getRecommendationsMock(...args),
    assignTask: (...args: unknown[]) => assignTaskMock(...args),
    updateProblemStatus: vi.fn(),
  },
}));

vi.mock('../components/ProblemMap', () => ({
  default: () => <div data-testid="problem-map" />,
}));

vi.mock('../components/GramSahayakaPanel', () => ({
  default: () => <div data-testid="gram-sahayaka-panel" />,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe('CoordinatorDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('alert', vi.fn());
    assignTaskMock.mockResolvedValue({ status: 'success', match: { id: 'match-1' } });
    getProblemsMock.mockResolvedValue([
      {
        id: 'problem-1',
        title: 'Broken Well Pump',
        description: 'The main well pump is broken and needs repair.',
        category: 'infrastructure',
        village_name: 'Test Village',
        village_address: 'Main Square',
        status: 'pending',
        lat: 21.1,
        lng: 79.0,
        created_at: '2026-01-01T10:00:00',
        updated_at: '2026-01-01T10:00:00',
        profiles: { id: 'villager-1', full_name: 'Reporter', email: null, phone: null, role: 'villager', created_at: '2026-01-01T10:00:00' },
        matches: [],
      },
    ]);
    getVolunteersMock.mockResolvedValue([
      {
        id: 'vol-1',
        user_id: 'user-1',
        skills: ['Plumbing'],
        availability_status: 'available',
        created_at: '2026-01-01T10:00:00',
        profiles: { id: 'user-1', full_name: 'Skilled Sam', email: null, phone: null, role: 'volunteer', created_at: '2026-01-01T10:00:00' },
      },
    ]);
    getRecommendationsMock.mockResolvedValue({
      severity_detected: 'HIGH',
      severity_source: 'auto',
      proposal_location: 'Test Village',
      teams: [
        {
          team_ids: 'vol-1',
          team_names: 'Skilled Sam',
          team_size: 1,
          goodness: 0.88,
          coverage: 0.91,
          k_robustness: 0.77,
          redundancy: 0.1,
          set_size: 0.2,
          willingness_avg: 0.8,
          willingness_min: 0.8,
          members: [
            {
              person_id: 'vol-1',
              name: 'Skilled Sam',
              skills: ['Plumbing'],
              availability: 'available',
              home_location: 'Test Village',
            },
          ],
        },
      ],
    });
  });

  it('renders AI robustness from backend response fields', async () => {
    render(<CoordinatorDashboard />);

    await screen.findByText('Broken Well Pump');

    fireEvent.click(await screen.findByRole('button', { name: /Assign Team/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Generate Explainable Teams/i }));

    await waitFor(() => {
      expect(getRecommendationsMock).toHaveBeenCalled();
    });

    expect(await screen.findByText(/Robustness: 0.77/)).toBeInTheDocument();
    expect(screen.getByText(/Severity: HIGH/)).toBeInTheDocument();
    expect(screen.getByText(/Loc: Test Village/)).toBeInTheDocument();
  });

  it('assigns every member when an AI team is selected', async () => {
    render(<CoordinatorDashboard />);

    await screen.findByText('Broken Well Pump');

    fireEvent.click(await screen.findByRole('button', { name: /Assign Team/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Generate Explainable Teams/i }));

    await waitFor(() => {
      expect(getRecommendationsMock).toHaveBeenCalled();
    });

    const assignButtons = await screen.findAllByRole('button', { name: /^Assign Team$/i });
    fireEvent.click(assignButtons[assignButtons.length - 1]);

    await waitFor(() => {
      expect(assignTaskMock).toHaveBeenCalledWith('problem-1', 'vol-1');
    });
  });
});
