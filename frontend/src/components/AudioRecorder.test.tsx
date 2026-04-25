import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AudioRecorder from './AudioRecorder';

const transcribeMock = vi.fn();

vi.mock('../services/api', () => ({
  api: {
    transcribe: (...args: unknown[]) => transcribeMock(...args),
  },
}));

class FakeMediaRecorder {
  stream: MediaStream;
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(stream: MediaStream) {
    this.stream = stream;
  }

  start() {
    this.ondataavailable?.({ data: new Blob(['audio'], { type: 'audio/wav' }) } as BlobEvent);
  }

  stop() {
    this.onstop?.();
  }
}

describe('AudioRecorder', () => {
  beforeEach(() => {
    transcribeMock.mockReset();
    transcribeMock.mockResolvedValue({ text: 'Need pump repair', language: 'en', source: 'gemini' });
    const tracks = [{ stop: vi.fn() }] as unknown as MediaStreamTrack[];
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder);
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => tracks,
        }),
      },
    });
  });

  it('records and forwards the transcription text', async () => {
    const onTranscription = vi.fn();
    render(<AudioRecorder onTranscription={onTranscription} />);

    fireEvent.click(screen.getByRole('button', { name: /record audio/i }));
    fireEvent.click(await screen.findByRole('button', { name: /stop recording/i }));

    await waitFor(() => {
      expect(transcribeMock).toHaveBeenCalled();
      expect(onTranscription).toHaveBeenCalledWith({ text: 'Need pump repair', language: 'en', source: 'gemini' });
    });
  });
});
