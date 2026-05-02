import { useCallback, useEffect, useState } from 'react';
import { ClipboardList, Loader2, Megaphone, TrendingUp, Users } from 'lucide-react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/auth-shared';
import { api, type PublicStatusBoardResponse, type WeeklyBriefing, type SeasonalRiskRecord, type CampaignModeRecord } from '../services/api';

export default function PartnerDashboard() {
  const { profile } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<WeeklyBriefing | null>(null);
  const [seasonalRisks, setSeasonalRisks] = useState<SeasonalRiskRecord[]>([]);
  const [campaignPlans, setCampaignPlans] = useState<CampaignModeRecord[]>([]);
  const [publicBoard, setPublicBoard] = useState<PublicStatusBoardResponse | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [briefingData, seasonalData, campaignData, publicData] = await Promise.all([
        api.getWeeklyBriefing(7),
        api.getSeasonalRiskForecast(365),
        api.getCampaignMode(30),
        api.getPublicStatusBoard({ days_back: 30 }),
      ]);
      setBriefing(briefingData);
      setSeasonalRisks(seasonalData.risks || []);
      setCampaignPlans(campaignData.campaigns || []);
      setPublicBoard(publicData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load partner dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile) {
      void loadData();
    }
  }, [loadData, profile]);

  if (!profile || profile.role !== 'partner') {
    return <Navigate to="/partner-login" replace />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-emerald-50 px-4 py-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">
              Partner dashboard
            </div>
            <h1 className="mt-3 text-3xl font-extrabold text-slate-900">Program overview and public accountability</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Track the weekly briefing, current public status, campaign activity, and early warning signals across the program.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/status')}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-emerald-300 hover:text-emerald-700"
          >
            Open public status board
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            <Loader2 size={16} className="mr-2 inline animate-spin" />
            Loading partner dashboard...
          </div>
        ) : (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)]">
            <div className="grid gap-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Weekly briefing</h2>
                    <p className="text-sm text-slate-500">A compact program summary with root-cause context.</p>
                  </div>
                  <ClipboardList className="text-emerald-600" />
                </div>
                {briefing ? (
                  <div className="space-y-3">
                    <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{briefing.summary}</div>
                    <div className="grid gap-3 md:grid-cols-3">
                      {briefing.highlights.slice(0, 3).map((item) => (
                        <div key={item} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
                    No weekly briefing available yet.
                  </div>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Public status snapshot</h2>
                    <p className="text-sm text-slate-500">What residents can currently see on the board.</p>
                  </div>
                  <Users className="text-sky-600" />
                </div>
                {publicBoard ? (
                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-sm">
                      <div className="text-xs text-rose-700">Open</div>
                      <div className="mt-1 text-2xl font-extrabold text-rose-700">{publicBoard.open_count}</div>
                    </div>
                    <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm">
                      <div className="text-xs text-amber-700">In progress</div>
                      <div className="mt-1 text-2xl font-extrabold text-amber-700">{publicBoard.in_progress_count}</div>
                    </div>
                    <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm">
                      <div className="text-xs text-emerald-700">Resolved</div>
                      <div className="mt-1 text-2xl font-extrabold text-emerald-700">{publicBoard.completed_count}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                      <div className="text-xs text-slate-500">Total</div>
                      <div className="mt-1 text-2xl font-extrabold text-slate-800">{publicBoard.total_count}</div>
                    </div>
                  </div>
                ) : null}
              </section>
            </div>

            <div className="grid gap-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Seasonal risk watch</h2>
                    <p className="text-sm text-slate-500">Heuristic warning signals from recent operations data.</p>
                  </div>
                  <TrendingUp className="text-indigo-600" />
                </div>
                <div className="space-y-3">
                  {seasonalRisks.slice(0, 4).map((item) => (
                    <div key={item.risk_id} className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-3">
                      <div className="font-semibold text-slate-900">{item.topic}</div>
                      <div className="text-xs text-slate-500">{item.summary}</div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Campaigns in motion</h2>
                    <p className="text-sm text-slate-500">Village-wide drives and inspection rounds.</p>
                  </div>
                  <Megaphone className="text-green-600" />
                </div>
                <div className="space-y-3">
                  {campaignPlans.slice(0, 2).map((item) => (
                    <div key={item.campaign_id} className="rounded-xl border border-green-100 bg-green-50/60 p-3">
                      <div className="font-semibold text-slate-900">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.target_villages.join(', ') || 'No target villages yet'}</div>
                      <p className="mt-2 text-sm text-slate-700">{item.goal}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
