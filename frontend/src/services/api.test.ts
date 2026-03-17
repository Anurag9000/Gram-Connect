import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { API_BASE_URL } from '../config';

describe('api service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('throws backend detail when recommendation fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'bad request' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(
      api.getRecommendations({
        proposal_text: 'x',
        task_start: '2026-01-01T10:00:00',
        task_end: '2026-01-01T11:00:00',
      }),
    ).rejects.toThrow('bad request');
  });

  it('posts volunteer assignment payload correctly', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'success', match: { id: 'm1' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.assignTask('prob-1', 'vol-1');

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/problems/prob-1/assign`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ volunteer_id: 'vol-1' }),
      }),
    );
  });
});
