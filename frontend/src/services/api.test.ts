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

  it('posts Jugaad guidance payload correctly', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        problem_id: 'prob-1',
        summary: 'Temporary fix',
        problem_read: 'Broken pump',
        observed_broken_part: 'handpump',
        observed_materials: 'wire and tube',
        temporary_fix: 'Wrap externally',
        step_by_step: [],
        safety_notes: [],
        materials_to_use: [],
        materials_to_avoid: [],
        when_to_stop: [],
        needs_official_part: true,
        confidence: 0.8,
        source: 'gemini',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.requestJugaadRepair({
      problem_id: 'prob-1',
      broken_media_id: 'media-1',
      materials_media_id: 'media-2',
      volunteer_id: 'vol-1',
      notes: 'wire, tube, bamboo',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/jugaad/assist`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          problem_id: 'prob-1',
          broken_media_id: 'media-1',
          materials_media_id: 'media-2',
          volunteer_id: 'vol-1',
          notes: 'wire, tube, bamboo',
        }),
      }),
    );
  });

  it('posts instant problem guidance payload correctly', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        topic: 'water',
        summary: 'Keep the pump stable with a temporary wrap.',
        what_you_can_do_now: ['Shut off flow', 'Wrap the joint'],
        materials_to_find: ['cloth', 'tape'],
        safety_notes: ['Keep pressure low'],
        when_to_stop: ['If the crack widens'],
        best_duration: 'Temporary only',
        confidence: 0.82,
        source: 'gemini',
        visual_tags: ['handpump'],
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.requestProblemGuidance({
      title: 'Broken handpump',
      description: 'The joint is leaking',
      category: 'water-sanitation',
      severity: 'HIGH',
      visual_tags: ['handpump'],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/problems/instant-guidance`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          title: 'Broken handpump',
          description: 'The joint is leaking',
          category: 'water-sanitation',
          severity: 'HIGH',
          visual_tags: ['handpump'],
        }),
      }),
    );
  });
});
