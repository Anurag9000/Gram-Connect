import { createContext } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import PlatformStudio from './PlatformStudio';

let mockedProfile: { id: string; full_name: string; role: 'coordinator' | 'supervisor' | 'partner' | 'volunteer' | 'villager' } | null = null;

const apiMocks = vi.hoisted(() => ({
  getPlatformOverview: vi.fn(),
  savePlatformRecord: vi.fn(),
  createBroadcast: vi.fn(),
  submitResidentConfirmation: vi.fn(),
  getAuditPack: vi.fn(),
  autofillProblemForm: vi.fn(),
  getCaseSimilarity: vi.fn(),
  askPolicyQuestion: vi.fn(),
  getPlatformExport: vi.fn(),
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

function seedMocks() {
  apiMocks.getPlatformOverview.mockResolvedValue({
    generated_at: '2026-01-01T00:00:00',
    window_days: 180,
    asset_registry: { assets: [{ asset_id: 'asset-1', village_name: 'Sundarpur' }] },
    procurement_tracker: { items: [{ procurement_id: 'proc-1', village_name: 'Sundarpur' }] },
    district_hierarchy: { districts: [{ district: 'Nagpur Rural', problem_count: 1 }] },
    work_order_templates: [{ template_id: 'template-water', title: 'Water work order', steps: ['Inspect'] }],
    proof_spoofing: [{ problem_id: 'problem-1', accepted: true }],
    resident_confirmation: [{ problem_id: 'problem-1', prompt: 'Confirm' }],
    skill_certifications: [{ volunteer_id: 'vol-1', badges: [{ skill: 'Plumbing', level: 'verified' }] }],
    shift_plan: [{ shift_id: 'shift-1', assigned_problem_ids: ['problem-1'] }],
    training_mode: [{ module_id: 'training-intake', title: 'Reporting quality' }],
    burnout_signals: [{ volunteer_id: 'vol-1', signal: 'low' }],
    suggestion_box: [{ id: 's-1', text: 'Improve response times' }],
    community_polls: [{ id: 'p-1', question: 'What should we fix first?' }],
    announcements: [{ id: 'a-1', title: 'Water repair day' }],
    village_champions: [{ id: 'c-1', name: 'Local champion' }],
    broadcasts: [{ id: 'broadcast-1', title: 'Water camp', message: 'Camp starts on Saturday.', event_type: 'community_event', audience_type: 'villages', tags: ['water camp'], target_villages: ['Sundarpur'], target_volunteers: [], target_skills: [], media_ids: [], created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' }],
    impact: { closure_rate: 0.5, reopen_rate: 0.1 },
    ab_tests: [{ test_id: 'ab-water', variant_b: 'duplicate-aware dispatch' }],
    anomalies: [{ anomaly_id: 'anom-1', village_name: 'Sundarpur' }],
    budget_forecast: { total_estimated_budget: 5000 },
    forms: [{ id: 'form-1' }],
    webhook_events: [{ id: 'web-1' }],
    conversation_memory: { items: [{ id: 'mem-1' }] },
    record_counts: {
      asset: 1,
      procurement: 1,
      privacy_setting: 1,
      certification: 1,
      shift_plan: 1,
      training_module: 1,
      burnout_signal: 1,
      suggestion: 1,
      poll: 1,
      announcement: 1,
      champion: 1,
      custom_form: 1,
      webhook_event: 1,
      conversation_memory: 1,
      broadcasts: 1,
    },
  });
  apiMocks.savePlatformRecord.mockResolvedValue({
    id: 'asset-1',
    record_type: 'asset',
    subtype: 'pump',
    owner_id: 'Sundarpur',
    status: 'healthy',
    data: { label: 'Handpump A' },
    updated_at: '2026-01-01T00:00:00',
  });
  apiMocks.createBroadcast.mockResolvedValue({
    status: 'success',
    broadcast: {
      id: 'broadcast-2',
      record_type: 'broadcast',
      title: 'Water camp',
      message: 'Camp starts on Saturday.',
      event_type: 'community_event',
      audience_type: 'villages',
      tags: ['water camp'],
      target_villages: ['Sundarpur'],
      target_volunteers: [],
      target_skills: [],
      media_ids: [],
      created_at: '2026-01-01T00:00:00',
      updated_at: '2026-01-01T00:00:00',
    },
  });
  apiMocks.submitResidentConfirmation.mockResolvedValue({
    status: 'success',
    confirmation: { id: 'confirm-1', response: 'resolved' },
    problem: { id: 'problem-1' },
  });
  apiMocks.getAuditPack.mockResolvedValue({ problem: { id: 'problem-1' }, timeline: [] });
  apiMocks.autofillProblemForm.mockResolvedValue({ title: 'Broken handpump', category: 'water-sanitation' });
  apiMocks.getCaseSimilarity.mockResolvedValue({ matches: [{ problem_id: 'problem-1' }] });
  apiMocks.askPolicyQuestion.mockResolvedValue({ question: 'How?', answer: 'Use the playbook.' });
  apiMocks.getPlatformExport.mockResolvedValue({ generated_at: '2026-01-01T00:00:00', problems: [], volunteers: [], platform_records: [] });
}

describe('PlatformStudio', () => {
  beforeEach(() => {
    mockedProfile = { id: 'coord-1', full_name: 'Coordinator', role: 'coordinator' };
    vi.clearAllMocks();
    seedMocks();
  });

  it('renders the management studio and exercises the core platform actions', async () => {
    render(
      <BrowserRouter>
        <PlatformStudio />
      </BrowserRouter>,
    );

    expect(await screen.findByRole('heading', { name: /Operations, trust, people, analytics, AI, and platform tools/i })).toBeInTheDocument();
    expect(screen.getByText(/Platform studio/i)).toBeInTheDocument();
    expect(screen.getByText(/Asset lifecycle registry/i)).toBeInTheDocument();
    expect(screen.getByText(/Trust and verification/i)).toBeInTheDocument();
    expect(screen.getByText(/Community broadcasts/i)).toBeInTheDocument();
    expect(screen.getByText(/AI control room/i)).toBeInTheDocument();
    expect(screen.getByText(/Platform admin/i)).toBeInTheDocument();

    fireEvent.change(screen.getAllByPlaceholderText('Record ID (optional)')[0], { target: { value: 'asset-1' } });
    fireEvent.change(screen.getAllByPlaceholderText('Subtype')[0], { target: { value: 'pump' } });
    fireEvent.change(screen.getAllByPlaceholderText('Owner / village ID')[0], { target: { value: 'Sundarpur' } });
    fireEvent.change(screen.getAllByPlaceholderText('Status')[0], { target: { value: 'healthy' } });
    fireEvent.change(screen.getAllByPlaceholderText('{"title":"Example"}')[0], { target: { value: '{"label":"Handpump A"}' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Asset record/i }));
    await waitFor(() => expect(apiMocks.savePlatformRecord).toHaveBeenCalledWith(
      'asset',
      expect.objectContaining({
        record_id: 'asset-1',
        subtype: 'pump',
        owner_id: 'Sundarpur',
        status: 'healthy',
        data: { label: 'Handpump A' },
      }),
    ));

    fireEvent.change(screen.getAllByPlaceholderText('Problem ID')[0], { target: { value: 'problem-1' } });
    fireEvent.change(screen.getByPlaceholderText('Confirmation note'), { target: { value: 'Resident says it is fixed.' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit confirmation/i }));
    await waitFor(() => expect(apiMocks.submitResidentConfirmation).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText('Describe a problem...'), { target: { value: 'Broken handpump near the school' } });
    fireEvent.click(screen.getByRole('button', { name: /Autofill/i }));
    await waitFor(() => expect(apiMocks.autofillProblemForm).toHaveBeenCalled());

    fireEvent.change(screen.getAllByPlaceholderText('Problem ID')[1], { target: { value: 'problem-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Find similar/i }));
    await waitFor(() => expect(apiMocks.getCaseSimilarity).toHaveBeenCalledWith('problem-1'));

    fireEvent.change(screen.getByPlaceholderText('Ask about privacy, escalation, or procurement...'), { target: { value: 'How do we protect privacy?' } });
    fireEvent.click(screen.getByRole('button', { name: /Ask policy/i }));
    await waitFor(() => expect(apiMocks.askPolicyQuestion).toHaveBeenCalledWith('How do we protect privacy?'));

    fireEvent.change(screen.getByPlaceholderText('Broadcast title'), { target: { value: 'Water camp' } });
    fireEvent.change(screen.getByPlaceholderText('Message, notice, event details, or call to action'), { target: { value: 'Camp starts on Saturday.' } });
    fireEvent.click(screen.getByRole('button', { name: /Send broadcast/i }));
    await waitFor(() => expect(apiMocks.createBroadcast).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Build export pack/i }));
    await waitFor(() => expect(apiMocks.getPlatformExport).toHaveBeenCalled());
  });
});
