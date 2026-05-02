import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CalendarDays, Loader2, Megaphone, MapPin, Wrench } from 'lucide-react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/auth-shared';
import { api, type CampaignModeRecord, type HeatmapCell, type MaintenancePlanRecord, type SeasonalRiskRecord, type EscalationRecord } from '../services/api';

export default function SupervisorDashboard() {
  const { profile } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [escalations, setEscalations] = useState<EscalationRecord[]>([]);
  const [seasonalRisks, setSeasonalRisks] = useState<SeasonalRiskRecord[]>([]);
  const [maintenanceRows, setMaintenanceRows] = useState<MaintenancePlanRecord[]>([]);
  const [heatmapCells, setHeatmapCells] = useState<HeatmapCell[]>([]);
  const [campaignPlans, setCampaignPlans] = useState<CampaignModeRecord[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [escalationsData, seasonalData, maintenanceData, heatmapData, campaignData] = await Promise.all([
        api.getEscalations(7),
        api.getSeasonalRiskForecast(365),
        api.getMaintenancePlan(180),
        api.getHotspotHeatmap(90),
        api.getCampaignMode(30),
      ]);
      setEscalations(escalationsData.items || []);
      setSeasonalRisks(seasonalData.risks || []);
      setMaintenanceRows(maintenanceData.items || []);
      setHeatmapCells(heatmapData.cells || []);
      setCampaignPlans(campaignData.campaigns || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load supervisor dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile) {
      void loadData();
    }
  }, [loadData, profile]);

  if (!profile || profile.role !== 'supervisor') {
    return <Navigate to="/supervisor-login" replace />;
  }

  const summaryCards = [
    { label: 'Escalations', value: escalations.length, icon: AlertTriangle, tone: 'text-red-700' },
    { label: 'Seasonal risks', value: seasonalRisks.length, icon: CalendarDays, tone: 'text-indigo-700' },
    { label: 'Maintenance items', value: maintenanceRows.length, icon: Wrench, tone: 'text-amber-700' },
    { label: 'Hotspots', value: heatmapCells.length, icon: MapPin, tone: 'text-rose-700' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-amber-50 px-4 py-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-amber-700">
              Supervisor dashboard
            </div>
            <h1 className="mt-3 text-3xl font-extrabold text-slate-900">Oversight and escalation view</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Monitor stalled issues, preventive maintenance, hotspot formation, and campaign activity across villages.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-amber-300 hover:text-amber-700"
          >
            Open coordinator dashboard
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          {summaryCards.map((card) => (
            <div key={card.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-slate-500">{card.label}</div>
                <card.icon size={18} className={card.tone} />
              </div>
              <div className={`mt-3 text-3xl font-extrabold ${card.tone}`}>{card.value}</div>
            </div>
          ))}
        </div>

        {error && (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            <Loader2 size={16} className="mr-2 inline animate-spin" />
            Loading supervisor view...
          </div>
        ) : (
          <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div className="grid gap-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Escalations due</h2>
                    <p className="text-sm text-slate-500">Items that need human review now.</p>
                  </div>
                  <AlertTriangle className="text-rose-600" />
                </div>
                <div className="space-y-2">
                  {escalations.slice(0, 5).map((item) => (
                    <div key={item.problem_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="font-semibold text-slate-900">{item.title || item.problem_id}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {item.village_name || 'Unknown village'} · {item.escalation_level} · {item.age_hours.toFixed(0)}h
                      </div>
                      <div className="mt-1 text-sm text-rose-700">{item.next_action}</div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Seasonal risk and heatmap</h2>
                    <p className="text-sm text-slate-500">Heuristic forecast of what may spike next.</p>
                  </div>
                  <CalendarDays className="text-indigo-600" />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
                    <div className="text-sm font-bold text-slate-900">Seasonal risks</div>
                    <div className="mt-2 space-y-2">
                      {seasonalRisks.slice(0, 3).map((item) => (
                        <div key={item.risk_id} className="rounded-lg bg-white px-3 py-2 text-sm">
                          <div className="font-semibold text-slate-900">{item.topic}</div>
                          <div className="text-xs text-slate-500">{item.summary}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-rose-100 bg-rose-50/60 p-4">
                    <div className="text-sm font-bold text-slate-900">Hotspot villages</div>
                    <div className="mt-2 space-y-2">
                      {heatmapCells.slice(0, 3).map((item) => (
                        <div key={item.cell_id} className="rounded-lg bg-white px-3 py-2 text-sm">
                          <div className="font-semibold text-slate-900">{item.village_name}</div>
                          <div className="text-xs text-slate-500">{item.top_topic} · {item.problem_count} cases</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <div className="grid gap-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Preventive maintenance</h2>
                    <p className="text-sm text-slate-500">Recurring asset issues turned into inspection reminders.</p>
                  </div>
                  <Wrench className="text-amber-600" />
                </div>
                <div className="space-y-3">
                  {maintenanceRows.slice(0, 4).map((item) => (
                    <div key={item.plan_id} className="rounded-xl border border-amber-100 bg-amber-50/60 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-semibold text-slate-900">{item.village_name} · {item.asset_type}</div>
                          <div className="text-xs text-slate-500">{item.related_problem_count} recent issues</div>
                        </div>
                        <div className={`rounded-full px-2 py-1 text-xs font-bold ${item.priority === 'high' ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'}`}>
                          {item.priority}
                        </div>
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{item.recommended_action}</p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Campaign mode</h2>
                    <p className="text-sm text-slate-500">Village drives that supervisors can launch or monitor.</p>
                  </div>
                  <Megaphone className="text-green-600" />
                </div>
                <div className="space-y-3">
                  {campaignPlans.slice(0, 2).map((item) => (
                    <div key={item.campaign_id} className="rounded-xl border border-green-100 bg-green-50/60 p-3">
                      <div className="font-semibold text-slate-900">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.target_villages.join(', ')}</div>
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
