import { createContext } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Home from '../pages/Home';
import SubmitProblem from '../pages/SubmitProblem';
import VolunteerDashboard from '../pages/VolunteerDashboard';
import CoordinatorDashboard from '../pages/CoordinatorDashboard';
import SupervisorDashboard from '../pages/SupervisorDashboard';
import PartnerDashboard from '../pages/PartnerDashboard';
import PublicStatusBoard from '../pages/PublicStatusBoard';
import { AuthProvider } from '../contexts/AuthContext';

let mockedProfile: { id: string; full_name: string; role: 'villager' | 'volunteer' | 'coordinator' | 'supervisor' | 'partner' } | null = null;

const apiMocks = vi.hoisted(() => ({
  getVolunteerTasks: vi.fn(),
  requestProblemGuidance: vi.fn(),
  getProblems: vi.fn(),
  getVolunteers: vi.fn(),
  getRecommendations: vi.fn(),
  assignTask: vi.fn(),
  getEscalations: vi.fn(),
  getReputation: vi.fn(),
  getRouteOptimization: vi.fn(),
  getPlaybooks: vi.fn(),
  getInventory: vi.fn(),
  getSeasonalRiskForecast: vi.fn(),
  getMaintenancePlan: vi.fn(),
  getHotspotHeatmap: vi.fn(),
  getCampaignMode: vi.fn(),
  getProblemTimeline: vi.fn(),
  getEvidenceComparison: vi.fn(),
  updateProblemStatus: vi.fn(),
  deleteProblem: vi.fn(),
  unassignVolunteer: vi.fn(),
  upsertInventory: vi.fn(),
  getWeeklyBriefing: vi.fn(),
  getPublicStatusBoard: vi.fn(),
  submitFollowUpFeedback: vi.fn(),
  submitProof: vi.fn(),
  requestJugaadRepair: vi.fn(),
}));

vi.mock('../contexts/auth-shared', () => ({
  AuthContext: createContext({
    user: null,
    profile: null,
    session: null,
    loading: false,
    signUp: async () => ({ error: new Error('mocked') }),
    signIn: async () => ({ error: null }),
    signOut: async () => undefined,
  }),
  useAuth: () => ({
    profile: mockedProfile,
    loading: false,
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

function seedApiMocks() {
  apiMocks.getVolunteerTasks.mockResolvedValue([
    {
      id: 'problem-1',
      title: 'Broken handpump',
      village: 'Sundarpur',
      location: 'Ward 1',
      status: 'in_progress',
      description: 'Water pump leak',
      category: 'water-sanitation',
      severity: 'HIGH',
      severity_source: 'auto',
      assigned_at: '2026-01-01T10:00:00',
    },
  ]);
  apiMocks.requestProblemGuidance.mockResolvedValue({
    topic: 'water',
    department: 'Public works / water',
    urgency: 'same-day',
    response_path: 'Route to public works and keep a watch.',
    summary: 'Use a temporary wrap to stabilize the leak.',
    what_you_can_do_now: ['Lower pressure'],
    materials_to_find: ['cloth'],
    safety_notes: ['Keep clear of fittings'],
    when_to_stop: ['If the leak worsens'],
    best_duration: 'Temporary only',
    confidence: 0.8,
    source: 'stub',
    visual_tags: ['handpump'],
    duplicate_candidates: [
      {
        problem_id: 'problem-1',
        title: 'Broken handpump',
        village_name: 'Sundarpur',
        category: 'water-sanitation',
        status: 'pending',
        created_at: '2026-01-01T10:00:00',
        distance_km: 0,
        score: 0.96,
        semantic_score: 0.94,
        reason: 'same village, same water topic',
        suggested_action: 'Attach to this case instead of opening a new one.',
      },
    ],
    similar_problem_count: 1,
    root_cause_hint: 'Repeated water problems often indicate a shared asset.',
  });
  apiMocks.getProblems.mockResolvedValue([
    {
      id: 'problem-1',
      title: 'Broken handpump',
      description: 'Main handpump is leaking.',
      category: 'water-sanitation',
      village_name: 'Sundarpur',
      village_address: 'Ward 1',
      status: 'pending',
      created_at: '2026-01-01T10:00:00',
      updated_at: '2026-01-01T10:00:00',
      profiles: { id: 'resident-1', full_name: 'Reporter', email: null, phone: null, role: 'villager', created_at: '2026-01-01T09:00:00' },
      matches: [],
      media_assets: [],
      proof: null,
    },
  ]);
  apiMocks.getVolunteers.mockResolvedValue([
    {
      id: 'vol-1',
      user_id: 'vol-1',
      skills: ['Plumbing'],
      availability_status: 'available',
      created_at: '2026-01-01T10:00:00',
      profiles: { id: 'vol-1', full_name: 'Skilled Sam', email: null, phone: null, role: 'volunteer', created_at: '2026-01-01T09:00:00' },
    },
  ]);
  apiMocks.getRecommendations.mockResolvedValue({
    severity_detected: 'HIGH',
    severity_source: 'auto',
    proposal_location: 'Sundarpur',
    teams: [
      {
        team_ids: 'vol-1',
        team_names: 'Skilled Sam',
        team_size: 1,
        goodness: 0.91,
        team_score: 0.91,
        coverage: 1,
        k_robustness: 0.8,
        redundancy: 0.1,
        set_size: 1,
        willingness_avg: 0.9,
        willingness_min: 0.9,
        avg_distance_km: 0,
        members: [
          {
            person_id: 'vol-1',
            name: 'Skilled Sam',
            skills: ['Plumbing'],
            availability: 'available',
            home_location: 'Sundarpur',
          },
        ],
      },
    ],
  });
  apiMocks.getEscalations.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 7, overdue_count: 0, items: [] });
  apiMocks.getReputation.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 90, volunteers: [] });
  apiMocks.getRouteOptimization.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 14, routes: [] });
  apiMocks.getPlaybooks.mockResolvedValue([
    {
      id: 'pb-1',
      topic: 'water',
      title: 'Handpump quick fix',
      summary: 'Temporary clamp plan',
      materials: ['tape'],
      safety_notes: ['Keep pressure low'],
      steps: ['Drain pressure'],
      created_at: '2026-01-01T00:00:00',
    },
  ]);
  apiMocks.getInventory.mockResolvedValue([
    {
      id: 'inv-1',
      owner_type: 'village',
      owner_id: 'Sundarpur',
      item_name: 'tape',
      quantity: 2,
      updated_at: '2026-01-01T00:00:00',
    },
  ]);
  apiMocks.getSeasonalRiskForecast.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 365, summary: 'seasonal risk', risks: [], top_topics: [], top_months: [] });
  apiMocks.getMaintenancePlan.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 180, summary: 'maintenance', items: [], top_assets: [] });
  apiMocks.getHotspotHeatmap.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 90, summary: 'heatmap', cells: [] });
  apiMocks.getCampaignMode.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', window_days: 30, summary: 'campaigns', campaigns: [], top_topics: [] });
  apiMocks.getProblemTimeline.mockResolvedValue({ problem_id: 'problem-1', problem: { id: 'problem-1' }, timeline: [], summary: { event_count: 0, media_count: 0, assignment_count: 0, duplicate_count: 0, completed: false } });
  apiMocks.getEvidenceComparison.mockResolvedValue({
    generated_at: '2026-01-01T00:00:00',
    problem_id: 'problem-1',
    title: 'Broken handpump',
    status: 'completed',
    before_media_id: null,
    after_media_id: null,
    before_url: null,
    after_url: null,
    accepted: true,
    confidence: 0.9,
    summary: 'Looks fixed',
    detected_change: 'Leak reduced',
    source: 'stored-proof',
  });
  apiMocks.updateProblemStatus.mockResolvedValue({ status: 'success', problem: { id: 'problem-1' } });
  apiMocks.deleteProblem.mockResolvedValue({ status: 'success' });
  apiMocks.unassignVolunteer.mockResolvedValue({ status: 'success' });
  apiMocks.upsertInventory.mockResolvedValue({ id: 'inv-2' });
  apiMocks.getWeeklyBriefing.mockResolvedValue({
    generated_at: '2026-01-01T00:00:00',
    window_days: 7,
    summary: 'Weekly briefing',
    highlights: ['Water issues rising'],
    stats: {
      problem_count: 1,
      open_problem_count: 1,
      completed_problem_count: 0,
      volunteer_count: 1,
      water_problem_count: 1,
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
      summary: 'Graph',
      top_topics: [],
      top_villages: [],
      top_assets: [],
      top_months: [],
    },
    duplicate_patterns: [],
  });
  apiMocks.getPublicStatusBoard.mockResolvedValue({
    generated_at: '2026-01-01T00:00:00',
    window_days: 30,
    open_count: 1,
    in_progress_count: 0,
    completed_count: 0,
    total_count: 1,
    items: [
      {
        id: 'problem-1',
        title: 'Broken handpump',
        category: 'water-sanitation',
        village_name: 'Sundarpur',
        village_address: 'Ward 1',
        status: 'pending',
        severity: 'HIGH',
        created_at: '2026-01-01T10:00:00',
        updated_at: '2026-01-01T10:00:00',
        assigned_count: 1,
        duplicate_count: 0,
        media_count: 0,
      },
    ],
  });
  apiMocks.submitFollowUpFeedback.mockResolvedValue({ status: 'success' });
  apiMocks.submitProof.mockResolvedValue({ status: 'success', problem: { id: 'problem-1' }, proof: { verification: { accepted: true, confidence: 0.95, summary: 'ok' } } });
  apiMocks.requestJugaadRepair.mockResolvedValue({
    problem_id: 'problem-1',
    summary: 'Temporary fix',
    problem_read: 'Broken handpump',
    observed_broken_part: 'handpump',
    observed_materials: 'wire, cloth',
    temporary_fix: 'Clamp the loose fitting',
    step_by_step: ['Drain pressure', 'Clamp the fitting'],
    safety_notes: ['Keep clear of pressure'],
    materials_to_use: ['wire'],
    materials_to_avoid: ['sharp metal'],
    when_to_stop: ['If the crack widens'],
    needs_official_part: true,
    confidence: 0.9,
    source: 'stub',
    broken_analysis: { top_label: 'handpump', confidence: 0.99 },
    materials_analysis: { top_label: 'wire', confidence: 0.99 },
  });
}

describe('Comprehensive feature coverage', () => {
  beforeEach(() => {
    mockedProfile = null;
    vi.clearAllMocks();
    seedApiMocks();
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: false,
    });
    localStorage.setItem('gram-connect-volunteer-offline-drafts', JSON.stringify([
      {
        id: 'draft-proof-1',
        kind: 'proof',
        problemId: 'problem-1',
        taskTitle: 'Broken handpump',
        volunteerId: 'vol-1',
        createdAt: '2026-01-01T10:00:00',
        afterImage: 'data:image/jpeg;base64,AAAA',
      },
    ]));
  });

  it('renders the public entry and role dashboards', () => {
    const { rerender } = render(
      <BrowserRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByRole('button', { name: /Supervisor access/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Partner access/i })).toBeInTheDocument();

    mockedProfile = { id: 'coord-1', full_name: 'Test Coordinator', role: 'coordinator' };
    rerender(
      <BrowserRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </BrowserRouter>
    );
    expect(screen.getByText(/Go to dashboard/i)).toBeInTheDocument();

    mockedProfile = { id: 'vol-1', full_name: 'Test Volunteer', role: 'volunteer' };
    rerender(
      <BrowserRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </BrowserRouter>
    );
    expect(screen.getByText(/Repair assistant/i, { selector: 'h2' })).toBeInTheDocument();

    mockedProfile = { id: 'sup-1', full_name: 'Test Supervisor', role: 'supervisor' };
    rerender(
      <BrowserRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </BrowserRouter>
    );
    expect(screen.getByText(/Open supervisor view/i)).toBeInTheDocument();

    mockedProfile = { id: 'part-1', full_name: 'Test Partner', role: 'partner' };
    rerender(
      <BrowserRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </BrowserRouter>
    );
    expect(screen.getByText(/Open partner view/i)).toBeInTheDocument();
  });

  it('renders the operational dashboards and intake surfaces', async () => {
    mockedProfile = { id: 'coord-1', full_name: 'Test Coordinator', role: 'coordinator' };
    const coordinator = render(<CoordinatorDashboard />);
    expect(await screen.findByText(/Conversational analyst over live operations data/i)).toBeInTheDocument();
    expect(screen.getByText(/Escalations due/i)).toBeInTheDocument();
    expect(screen.getByText(/Route clusters/i)).toBeInTheDocument();
    expect(screen.getByText(/Playbooks saved/i)).toBeInTheDocument();
    expect(screen.getByText(/Inventory items tracked/i)).toBeInTheDocument();
    expect(screen.getByText(/Seasonal risk forecast/i, { selector: 'h2' })).toBeInTheDocument();
    expect(screen.getByText(/Preventive maintenance plan/i, { selector: 'h2' })).toBeInTheDocument();
    expect(screen.getByText(/Hotspot map/i, { selector: 'h2' })).toBeInTheDocument();
    expect(screen.getByText(/Campaign mode/i, { selector: 'h2' })).toBeInTheDocument();
    coordinator.unmount();

    mockedProfile = { id: 'vol-1', full_name: 'Test Volunteer', role: 'volunteer' };
    const volunteer = render(<VolunteerDashboard />);
    expect(await screen.findByText('Broken handpump')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('task-card-problem-1'));
    fireEvent.click(screen.getByRole('button', { name: /Repair Assistant/i }));
    expect(await screen.findByText(/Help me fix this/i, { selector: 'h3' })).toBeInTheDocument();
    expect(screen.getByText(/Help me fix this/i)).toBeInTheDocument();
    expect(screen.getByText(/Offline drafts waiting to sync/i)).toBeInTheDocument();
    volunteer.unmount();

    mockedProfile = null;
    const submit = render(
      <BrowserRouter>
        <AuthProvider>
          <SubmitProblem />
        </AuthProvider>
      </BrowserRouter>
    );
    fireEvent.change(screen.getByTestId('village-name-input'), { target: { value: 'Sundarpur' } });
    fireEvent.change(screen.getByTestId('problem-title-input'), { target: { value: 'Broken handpump near school' } });
    fireEvent.change(screen.getByTestId('problem-description-input'), { target: { value: 'Same leak as yesterday and still no water' } });
    await waitFor(() => expect(apiMocks.requestProblemGuidance).toHaveBeenCalled());
    expect(await screen.findByText(/Instant help/i)).toBeInTheDocument();
    expect(screen.getByText(/Possible duplicate cases nearby/i)).toBeInTheDocument();
    submit.unmount();
  });

  it('renders the public accountability, supervisor, and partner surfaces', async () => {
    mockedProfile = { id: 'sup-1', full_name: 'Test Supervisor', role: 'supervisor' };
    const supervisor = render(<SupervisorDashboard />);
    expect(await screen.findByText(/Supervisor dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Oversight and escalation view/i)).toBeInTheDocument();
    expect(screen.getByText(/Seasonal risk and heatmap/i)).toBeInTheDocument();
    supervisor.unmount();

    mockedProfile = { id: 'part-1', full_name: 'Test Partner', role: 'partner' };
    const partner = render(<PartnerDashboard />);
    expect(await screen.findByText(/Partner dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Program overview and public accountability/i)).toBeInTheDocument();
    expect(screen.getByText(/Public status snapshot/i)).toBeInTheDocument();
    partner.unmount();

    mockedProfile = null;
    const publicBoard = render(<PublicStatusBoard />);
    expect(await screen.findByText(/Village issue status/i)).toBeInTheDocument();
    expect(screen.getByText(/Public status board/i)).toBeInTheDocument();
    expect(screen.getByText(/^Resolved$/i, { selector: 'div' })).toBeInTheDocument();
    publicBoard.unmount();
  });
});
