import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import VolunteerDashboard from './VolunteerDashboard';

const navigateMock = vi.fn();
const getVolunteerTasksMock = vi.fn();
const requestJugaadHelpMock = vi.fn();
const mockProfile = {
  id: 'mock-volunteer-uuid',
  full_name: 'Test Volunteer',
  role: 'volunteer',
};

vi.mock('../contexts/auth-shared', () => ({
  useAuth: () => ({
    profile: mockProfile,
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

vi.mock('../lib/liveRefresh', () => ({
  subscribeLiveRefresh: () => () => {},
}));

vi.mock('../services/api', () => ({
  api: {
    getVolunteerTasks: (...args: unknown[]) => getVolunteerTasksMock(...args),
    requestJugaadHelp: (...args: unknown[]) => requestJugaadHelpMock(...args),
    uploadMedia: vi.fn(),
    submitProof: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate">{to}</div>,
    useNavigate: () => navigateMock,
  };
});

describe('VolunteerDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    getVolunteerTasksMock.mockResolvedValue([
      {
        id: 'task-1',
        title: 'Broken Pump',
        village: 'Sundarpur',
        location: 'Ward 3',
        status: 'assigned',
        description: 'The handpump is leaking at the base.',
        category: 'infrastructure',
        severity: 'HIGH',
        severity_source: 'gemini',
        assigned_at: '2026-01-01T10:00:00Z',
        media_assets: [],
        proof_assets: [],
      },
    ]);
    requestJugaadHelpMock.mockResolvedValue({
      status: 'success',
      guidance: {
        source: 'gemini',
        confidence: 0.81,
        situation_summary: 'A temporary brace is feasible.',
        materials_identified: ['rubber tube', 'wire'],
        temporary_fix_steps: ['Shut off water', 'Brace the joint'],
        safety_warnings: ['Do not touch live wiring'],
        when_to_stop: 'Stop if the joint flexes.',
        escalation: 'Request the official replacement part.',
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sends the selected task context to the Jugaad helper', async () => {
    render(<VolunteerDashboard />);

    const taskCard = await screen.findByTestId('task-card-task-1');
    fireEvent.click(taskCard);

    const helperToggle = await screen.findByRole('button', { name: 'Open Helper' });
    fireEvent.click(helperToggle);

    const brokenFile = new File(['broken'], 'broken.jpg', { type: 'image/jpeg' });
    const materialsFile = new File(['materials'], 'materials.jpg', { type: 'image/jpeg' });

    fireEvent.change(screen.getByTestId('jugaad-broken-photo-input'), {
      target: { files: [brokenFile] },
    });
    fireEvent.change(screen.getByTestId('jugaad-materials-photo-input'), {
      target: { files: [materialsFile] },
    });

    fireEvent.click(screen.getByTestId('jugaad-help-button'));

    await waitFor(() => {
      expect(requestJugaadHelpMock).toHaveBeenCalledWith(
        expect.objectContaining({
          broken_photo: brokenFile,
          materials_photo: materialsFile,
          problem_title: 'Broken Pump',
          problem_description: 'The handpump is leaking at the base.',
          category: 'infrastructure',
          village_name: 'Sundarpur',
          problem_id: 'task-1',
        }),
      );
    });

    expect(await screen.findByText('A temporary brace is feasible.')).toBeInTheDocument();
  });
});
