import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SupervisorDashboard from './SupervisorDashboard';
import PartnerDashboard from './PartnerDashboard';

let mockedProfile: { role: 'supervisor' | 'partner'; full_name: string; id: string } | null = null;

const apiMocks = vi.hoisted(() => ({
  getEscalations: vi.fn(),
  getSeasonalRiskForecast: vi.fn(),
  getMaintenancePlan: vi.fn(),
  getHotspotHeatmap: vi.fn(),
  getCampaignMode: vi.fn(),
  getWeeklyBriefing: vi.fn(),
  getPublicStatusBoard: vi.fn(),
}));

vi.mock('../contexts/auth-shared', () => ({
  useAuth: () => ({
    profile: mockedProfile,
  }),
}));

vi.mock('../services/api', () => ({
  api: apiMocks,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

describe('role dashboards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedProfile = null;
  });

  it('renders the supervisor dashboard view', async () => {
    mockedProfile = { role: 'supervisor', full_name: 'Test Supervisor', id: 'supervisor-1' };
    apiMocks.getEscalations.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 7, overdue_count: 0, items: [] });
    apiMocks.getSeasonalRiskForecast.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 365, summary: 'none', risks: [] });
    apiMocks.getMaintenancePlan.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 180, summary: 'none', items: [], top_assets: [] });
    apiMocks.getHotspotHeatmap.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 90, summary: 'none', cells: [] });
    apiMocks.getCampaignMode.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 30, summary: 'none', campaigns: [], top_topics: [] });

    render(<SupervisorDashboard />);

    expect(await screen.findByText(/Supervisor dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Oversight and escalation view/i)).toBeInTheDocument();
  });

  it('renders the partner dashboard view', async () => {
    mockedProfile = { role: 'partner', full_name: 'Test Partner', id: 'partner-1' };
    apiMocks.getWeeklyBriefing.mockResolvedValue({
      generated_at: '2026-01-01T00:00:00',
      window_days: 7,
      summary: 'Weekly briefing',
      highlights: [],
      stats: {
        problem_count: 0,
        open_problem_count: 0,
        completed_problem_count: 0,
        volunteer_count: 0,
        water_problem_count: 0,
        health_problem_count: 0,
        infrastructure_problem_count: 0,
      },
      risk_alerts: [],
      open_cases: [],
      volunteer_load: [],
      root_cause_graph: {
        generated_at: '2026-01-01T00:00:00',
        window_days: 30,
        nodes: [],
        edges: [],
        summary: 'No recent problems available for graphing.',
        top_topics: [],
        top_villages: [],
        top_assets: [],
        top_months: [],
      },
      duplicate_patterns: [],
    });
    apiMocks.getSeasonalRiskForecast.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 365, summary: 'none', risks: [] });
    apiMocks.getCampaignMode.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 30, summary: 'none', campaigns: [], top_topics: [] });
    apiMocks.getPublicStatusBoard.mockResolvedValue({
      generated_at: '2026-01-01T00:00:00',
      window_days: 30,
      open_count: 0,
      in_progress_count: 0,
      completed_count: 0,
      total_count: 0,
      items: [],
    });

    render(<PartnerDashboard />);

    expect(await screen.findByText(/Partner dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Program overview and public accountability/i)).toBeInTheDocument();
  });
});
