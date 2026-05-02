import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Bot, Loader2, Send, Sparkles, TrendingUp } from 'lucide-react';
import { api, type InsightChatResponse, type InsightOverview, type InsightCluster, type WeeklyBriefing } from '../services/api';
import { subscribeLiveRefresh } from '../lib/liveRefresh';

const QUICK_PROMPTS = [
  'Which villages have had the most water-related issues this month?',
  'Show me all volunteers in Nirmalgaon who know masonry but have not been assigned anything in 2 weeks.',
  'Summarize the major complaints from Sundarpur.',
  'Scan for outbreak risk and systemic infrastructure clusters.',
];

type ChatMessage = {
  role: 'user' | 'assistant';
  text: string;
  meta?: string;
};

function formatClusterSummary(cluster: InsightCluster) {
  const villages = cluster.villages.join(', ');
  const score = Math.round(cluster.risk_score * 100);
  return `${cluster.summary} ${villages ? `Villages: ${villages}.` : ''} Risk score: ${score}%.`;
}

export default function GramSahayakaPanel() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text: 'Ask me for village trends, idle volunteers, complaint summaries, or risk clusters.',
      meta: 'Gram-Sahayaka',
    },
  ]);
  const [overview, setOverview] = useState<InsightOverview | null>(null);
  const [briefing, setBriefing] = useState<WeeklyBriefing | null>(null);
  const [latestResponse, setLatestResponse] = useState<InsightChatResponse | null>(null);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingAnswer, setLoadingAnswer] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoadingOverview(true);
    setError(null);
    try {
      const [overviewData, briefingData] = await Promise.all([
        api.getInsightOverview(),
        api.getWeeklyBriefing(7),
      ]);
      setOverview(overviewData);
      setBriefing(briefingData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights overview.');
    } finally {
      setLoadingOverview(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    const unsubscribe = subscribeLiveRefresh(() => {
      loadOverview();
    });
    const handleFocus = () => loadOverview();
    window.addEventListener('focus', handleFocus);
    return () => {
      unsubscribe();
      window.removeEventListener('focus', handleFocus);
    };
  }, [loadOverview]);

  const askQuestion = useCallback(async (rawQuery: string) => {
    const trimmed = rawQuery.trim();
    if (!trimmed || loadingAnswer) {
      return;
    }

    setError(null);
    setLoadingAnswer(true);
    setMessages((current) => [
      ...current,
      { role: 'user', text: trimmed },
    ]);

    try {
      const response = await api.askInsights({ query: trimmed, days_back: 30, limit: 5 });
      setLatestResponse(response);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          text: response.answer,
          meta: response.intent.replace(/_/g, ' '),
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to analyze the question.';
      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          text: message,
          meta: 'Error',
        },
      ]);
    } finally {
      setLoadingAnswer(false);
    }
  }, [loadingAnswer]);

  const alertClusters = overview?.alerts || [];
  const topClusters = overview?.clusters || [];
  const payload = latestResponse?.payload;
  const payloadVillages = payload?.villages;
  const payloadVolunteers = payload?.volunteers;
  const payloadExamples = payload?.examples;
  const payloadAlerts = payload?.alerts;
  const villageRows = Array.isArray(payloadVillages) ? (payloadVillages as { village_name: string; count: number }[]) : [];
  const volunteerRows = Array.isArray(payloadVolunteers) ? (payloadVolunteers as { volunteer_id: string; name: string; home_location?: string; idle_days: number }[]) : [];
  const exampleRows = Array.isArray(payloadExamples) ? (payloadExamples as { id?: string; title?: string; category?: string; status?: string }[]) : [];
  const alertRows = Array.isArray(payloadAlerts) ? (payloadAlerts as InsightCluster[]) : [];

  return (
    <section className="rounded-3xl border border-emerald-200 bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-950 text-white shadow-xl">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <div className="p-6 lg:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                <Bot size={14} /> Gram-Sahayaka
              </div>
              <h2 className="mt-3 text-2xl font-bold text-white">Conversational analyst over live operations data</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Ask natural-language questions about problems, volunteers, and trends. The assistant routes each query to structured analytics and returns a concise answer with live evidence.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
              <div>
                <div className="text-slate-400">Problems</div>
                <div className="mt-1 text-lg font-semibold text-white">{overview?.stats.problem_count ?? '...'}</div>
              </div>
              <div>
                <div className="text-slate-400">Volunteers</div>
                <div className="mt-1 text-lg font-semibold text-white">{overview?.stats.volunteer_count ?? '...'}</div>
              </div>
              <div>
                <div className="text-slate-400">Water issues</div>
                <div className="mt-1 text-lg font-semibold text-white">{overview?.stats.water_problem_count ?? '...'}</div>
              </div>
              <div>
                <div className="text-slate-400">Health issues</div>
                <div className="mt-1 text-lg font-semibold text-white">{overview?.stats.health_problem_count ?? '...'}</div>
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-3">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-3 shadow-inner">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200">
                <Sparkles size={14} /> Ask Gram-Sahayaka
              </div>
              <div className="flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setQuery(prompt)}
                    className="rounded-full border border-white/10 bg-white/8 px-3 py-1.5 text-left text-xs text-slate-200 transition hover:bg-white/14"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void askQuestion(query);
              }}
              className="rounded-2xl border border-white/10 bg-white/5 p-4"
            >
              <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">
                Natural language query
              </label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  rows={3}
                  className="min-h-[84px] flex-1 rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white placeholder:text-slate-500 outline-none ring-0 focus:border-emerald-400"
                  placeholder="Which villages have the most water-related issues this month?"
                />
                <button
                  type="submit"
                  disabled={loadingAnswer || !query.trim()}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-500 disabled:text-slate-300"
                >
                  {loadingAnswer ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  Ask
                </button>
              </div>
            </form>

            {error && (
              <div className="rounded-2xl border border-red-300/20 bg-red-500/10 p-3 text-sm text-red-100">
                {error}
              </div>
            )}

            <div className="grid gap-3">
              {messages.slice(-4).map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                    message.role === 'user'
                      ? 'ml-auto bg-emerald-500 text-slate-950'
                      : 'bg-slate-950/60 text-slate-100 border border-white/10'
                  }`}
                >
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                    {message.role === 'user' ? 'You' : message.meta || 'Assistant'}
                  </div>
                  <div>{message.text}</div>
                </div>
              ))}
            </div>

            {latestResponse?.payload && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200">
                  Latest answer details
                </div>
                {latestResponse.intent === 'top_villages_by_topic' && villageRows.length > 0 && (
                  <div className="space-y-2">
                    {villageRows.map((item) => (
                      <div key={item.village_name} className="rounded-xl bg-slate-950/50 px-3 py-2 text-sm text-slate-100">
                        <div className="font-semibold">{item.village_name}</div>
                        <div className="text-xs text-slate-300">{item.count} matching issues</div>
                      </div>
                    ))}
                  </div>
                )}
                {latestResponse.intent === 'volunteer_skill_gap' && volunteerRows.length > 0 && (
                  <div className="space-y-2">
                    {volunteerRows.map((item) => (
                      <div key={item.volunteer_id} className="rounded-xl bg-slate-950/50 px-3 py-2 text-sm text-slate-100">
                        <div className="font-semibold">{item.name}</div>
                        <div className="text-xs text-slate-300">
                          {item.home_location || 'Unknown location'} · idle {item.idle_days} days
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {latestResponse.intent === 'village_summary' && exampleRows.length > 0 && (
                  <div className="space-y-2">
                    {exampleRows.map((item) => (
                      <div key={item.id} className="rounded-xl bg-slate-950/50 px-3 py-2 text-sm text-slate-100">
                        <div className="font-semibold">{item.title}</div>
                        <div className="text-xs text-slate-300">{item.category} · {item.status}</div>
                      </div>
                    ))}
                  </div>
                )}
                {(latestResponse.intent === 'risk_clusters' || latestResponse.intent === 'overview') && alertRows.length > 0 && (
                  <div className="space-y-2">
                    {alertRows.slice(0, 3).map((cluster) => (
                      <div key={cluster.cluster_id} className="rounded-xl bg-slate-950/50 px-3 py-2 text-sm text-slate-100">
                        <div className="font-semibold">{cluster.summary}</div>
                        <div className="text-xs text-slate-300">{cluster.villages.join(', ')} · score {(cluster.risk_score * 100).toFixed(0)}%</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <aside className="border-t border-white/10 bg-black/20 p-6 lg:border-l lg:border-t-0 lg:p-7">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
            <TrendingUp size={14} /> Risk radar
          </div>
          <h3 className="mt-3 text-xl font-bold text-white">Active cluster alerts</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Embedding-based clustering scans recent complaints for co-located issues that may be part of a broader health or infrastructure pattern.
          </p>

          <div className="mt-5 space-y-3">
            {loadingOverview && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                Loading live risk scan...
              </div>
            )}
            {!loadingOverview && alertClusters.length === 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                No strong cluster alerts right now.
              </div>
            )}
            {alertClusters.slice(0, 4).map((cluster) => (
              <div key={cluster.cluster_id} className="rounded-2xl border border-amber-300/20 bg-amber-500/10 p-4 text-sm text-slate-100">
                <div className="flex items-start gap-2">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-300" />
                  <div>
                    <div className="font-semibold text-white">{cluster.summary}</div>
                    <div className="mt-1 text-xs leading-5 text-amber-100/80">
                      {cluster.villages.join(', ')} · {cluster.problem_count} complaints · {(cluster.risk_score * 100).toFixed(0)}% risk
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              Weekly briefing
            </div>
            {briefing ? (
              <div className="space-y-3">
                <div className="rounded-xl bg-slate-950/50 p-3 text-sm text-slate-100">
                  <div className="font-semibold text-white">{briefing.summary}</div>
                  {briefing.highlights.length > 0 && (
                    <ul className="mt-2 space-y-1 text-xs text-slate-300">
                      {briefing.highlights.slice(0, 3).map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  )}
                </div>
                {briefing.root_cause_graph.summary && (
                  <div className="rounded-xl bg-emerald-500/10 p-3 text-xs text-emerald-100">
                    <div className="font-semibold text-white">Root-cause signal</div>
                    <div className="mt-1 leading-5 text-emerald-100/85">{briefing.root_cause_graph.summary}</div>
                  </div>
                )}
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-lg bg-slate-950/50 p-2">
                    <div className="text-slate-400">Open</div>
                    <div className="mt-1 font-semibold text-white">{briefing.stats.open_problem_count}</div>
                  </div>
                  <div className="rounded-lg bg-slate-950/50 p-2">
                    <div className="text-slate-400">Risk</div>
                    <div className="mt-1 font-semibold text-white">{briefing.risk_alerts.length}</div>
                  </div>
                  <div className="rounded-lg bg-slate-950/50 p-2">
                    <div className="text-slate-400">Load</div>
                    <div className="mt-1 font-semibold text-white">{briefing.volunteer_load.length}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl bg-slate-950/50 px-3 py-2 text-sm text-slate-400">
                No briefing available yet.
              </div>
            )}
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
              Recent clusters
            </div>
            <div className="space-y-2">
              {topClusters.slice(0, 3).map((cluster) => (
                <div key={cluster.cluster_id} className="rounded-xl bg-slate-950/50 px-3 py-2 text-xs text-slate-200">
                  <div className="font-semibold text-white">{cluster.topic || 'general'}</div>
                  <div className="mt-0.5 text-slate-400">{formatClusterSummary(cluster)}</div>
                </div>
              ))}
              {!loadingOverview && topClusters.length === 0 && (
                <div className="text-sm text-slate-400">No clusters detected in the current window.</div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
