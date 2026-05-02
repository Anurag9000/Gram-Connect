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
        department: 'Public works / water',
        urgency: 'same-day',
        response_path: 'Route to the local water/public works crew and keep a volunteer watch until the repair is scheduled.',
        summary: 'Keep the pump stable with a temporary wrap.',
        what_you_can_do_now: ['Shut off flow', 'Wrap the joint'],
        materials_to_find: ['cloth', 'tape'],
        safety_notes: ['Keep pressure low'],
        when_to_stop: ['If the crack widens'],
        best_duration: 'Temporary only',
        confidence: 0.82,
        source: 'gemini',
        visual_tags: ['handpump'],
        duplicate_candidates: [],
        similar_problem_count: 0,
        root_cause_hint: 'Repeated water complaints often point to a shared pump or pipe issue.',
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

  it('fetches problem timeline and weekly briefing from the API', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          problem_id: 'prob-1',
          problem: { id: 'prob-1', title: 'Broken pump', description: 'Leaking', status: 'pending' },
          timeline: [],
          summary: {
            event_count: 0,
            media_count: 0,
            assignment_count: 0,
            duplicate_count: 0,
            completed: false,
          },
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
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
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    await api.getProblemTimeline('prob-1');
    await api.getWeeklyBriefing(7);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/problems/prob-1/timeline`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/insights/briefing?days_back=7`,
      expect.objectContaining({ cache: 'no-store' }),
    );
  });

  it('fetches the public status board from the API', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        generated_at: '2026-01-01T00:00:00',
        window_days: 60,
        village_name: 'Sundarpur',
        status_filter: 'pending',
        open_count: 1,
        in_progress_count: 0,
        completed_count: 0,
        total_count: 1,
        items: [],
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await api.getPublicStatusBoard({ village_name: 'Sundarpur', status: 'pending', days_back: 60 });

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/public/status-board?village_name=Sundarpur&status=pending&days_back=60`,
      expect.objectContaining({ cache: 'no-store' }),
    );
  });

  it('fetches operations data from the API', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 'playbook-1' }]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 'inv-1' }]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 7, overdue_count: 0, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 90, volunteers: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 14, routes: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 365, summary: 'none', risks: [], top_topics: [], top_months: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 180, summary: 'none', items: [], top_assets: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 90, summary: 'none', cells: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', window_days: 30, summary: 'none', campaigns: [], top_topics: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'success', feedback: { id: 'fb-1' }, problem: { id: 'prob-1' } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ generated_at: '2026-01-01T00:00:00', problem_id: 'prob-1', title: 'Broken Pipe', status: 'completed', before_media_id: null, after_media_id: null, before_url: null, after_url: null, accepted: true, confidence: 0.9, summary: 'Looks fixed', detected_change: 'repaired', source: 'stored-proof' }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await api.getPlaybooks({ topic: 'water' });
    await api.getInventory({ owner_type: 'village' });
    await api.getEscalations(7);
    await api.getReputation(90);
    await api.getRouteOptimization(14);
    await api.getSeasonalRiskForecast(365);
    await api.getMaintenancePlan(180);
    await api.getHotspotHeatmap(90);
    await api.getCampaignMode(30);
    await api.submitFollowUpFeedback('prob-1', { source: 'public-board', response: 'resolved' });
    await api.getEvidenceComparison('prob-1');

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/playbooks?topic=water&limit=25`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/inventory?owner_type=village`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `${API_BASE_URL}/api/v1/escalations?days_back=7`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      `${API_BASE_URL}/api/v1/reputation?days_back=90`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      `${API_BASE_URL}/api/v1/routes/optimizer?days_back=14`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      `${API_BASE_URL}/api/v1/insights/seasonal-risk?days_back=365`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      `${API_BASE_URL}/api/v1/maintenance/plan?days_back=180`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      `${API_BASE_URL}/api/v1/hotspots/heatmap?days_back=90`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      9,
      `${API_BASE_URL}/api/v1/campaigns/plan?days_back=30`,
      expect.objectContaining({ cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      10,
      `${API_BASE_URL}/problems/prob-1/follow-up-feedback`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ source: 'public-board', response: 'resolved' }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      11,
      `${API_BASE_URL}/api/v1/problems/prob-1/evidence-comparison`,
      expect.objectContaining({ cache: 'no-store' }),
    );
  });
});
