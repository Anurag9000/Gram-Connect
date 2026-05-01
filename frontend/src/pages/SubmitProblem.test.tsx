import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SubmitProblem from './SubmitProblem';

const navigateMock = vi.fn();
const analyzeImageMock = vi.fn();
const requestProblemGuidanceMock = vi.fn();
const uploadMediaMock = vi.fn();
const submitProblemMock = vi.fn();

vi.mock('../contexts/auth-shared', () => ({
  useAuth: () => ({
    profile: {
      id: 'mock-coordinator-uuid',
      full_name: 'Test Coordinator',
      role: 'coordinator',
    },
  }),
}));

vi.mock('../components/AudioRecorder', () => ({
  default: ({ onTranscription }: { onTranscription: (text: string) => void }) => (
    <button type="button" onClick={() => onTranscription('Audio context')}>
      Mock Audio Recorder
    </button>
  ),
}));

vi.mock('../services/api', () => ({
  api: {
    analyzeImage: (...args: unknown[]) => analyzeImageMock(...args),
    requestProblemGuidance: (...args: unknown[]) => requestProblemGuidanceMock(...args),
    uploadMedia: (...args: unknown[]) => uploadMediaMock(...args),
    submitProblem: (...args: unknown[]) => submitProblemMock(...args),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe('SubmitProblem', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    analyzeImageMock.mockResolvedValue({
      top_label: 'digital literacy',
      confidence: 0.88,
      tags: ['digital literacy', 'education'],
    });
    requestProblemGuidanceMock.mockResolvedValue({
      topic: 'digital',
      summary: 'Stabilize the device with basic cleanup and cable checks.',
      what_you_can_do_now: ['Restart the device', 'Check the power cable', 'Keep the area dry'],
      materials_to_find: ['dry cloth', 'spare cable'],
      safety_notes: ['Do not open live electrical parts'],
      when_to_stop: ['If there is smoke or heat'],
      best_duration: 'Temporary stabilization until a technician or replacement arrives.',
      confidence: 0.81,
      source: 'gemini',
      visual_tags: ['digital literacy', 'education'],
    });
    uploadMediaMock.mockResolvedValue({ status: 'success', media: { id: 'media-1' } });
    submitProblemMock.mockResolvedValue({ status: 'success', id: 'prob-new' });
  });

  it('shows analyzed tags and submits them to the API', async () => {
    render(<SubmitProblem />);

    fireEvent.change(screen.getByTestId('village-name-input'), { target: { value: 'Nirmalgaon' } });
    fireEvent.change(screen.getByTestId('village-address-input'), { target: { value: 'Panchayat Hall' } });
    fireEvent.change(screen.getByTestId('problem-title-input'), { target: { value: 'Digital Help Needed' } });
    fireEvent.change(screen.getByTestId('problem-description-input'), { target: { value: 'Villagers need help with spreadsheets.' } });

    const imageFile = new File(['ppm'], 'fixture.ppm', { type: 'image/x-portable-pixmap' });
    fireEvent.change(screen.getByTestId('problem-image-input'), {
      target: { files: [imageFile] },
    });

    await waitFor(() => {
      expect(analyzeImageMock).toHaveBeenCalled();
      expect(requestProblemGuidanceMock).toHaveBeenCalled();
      expect(screen.getByTestId('image-analysis-tags')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Education & Digital/i }));

    fireEvent.click(screen.getByRole('button', { name: 'Submit Problem' }));

    await waitFor(() => {
      expect(submitProblemMock).toHaveBeenCalledWith(
        expect.objectContaining({
          category: 'education-digital',
          visual_tags: ['digital literacy', 'education'],
        }),
      );
    });
  });
});
