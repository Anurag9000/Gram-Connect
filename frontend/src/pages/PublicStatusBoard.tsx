import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, Loader2, MapPin, Search } from 'lucide-react';
import { api, type PublicStatusBoardResponse, type PublicStatusBoardItem } from '../services/api';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Resolved' },
];

function statusTone(status: string) {
  if (status === 'completed') return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  if (status === 'in_progress') return 'bg-amber-100 text-amber-700 border-amber-200';
  return 'bg-rose-100 text-rose-700 border-rose-200';
}

export default function PublicStatusBoard() {
  const [board, setBoard] = useState<PublicStatusBoardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [villageName, setVillageName] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'in_progress' | 'completed'>('all');
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [feedbackBusyId, setFeedbackBusyId] = useState<string | null>(null);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getPublicStatusBoard({
        village_name: villageName.trim() || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        days_back: 60,
      });
      setBoard(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load public status board.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, villageName]);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const items = useMemo(() => board?.items ?? [], [board]);

  const sendFeedback = useCallback(async (item: PublicStatusBoardItem, response: 'resolved' | 'still_broken' | 'needs_more_help') => {
    setFeedbackBusyId(item.id);
    setFeedbackMessage(null);
    try {
      await api.submitFollowUpFeedback(item.id, {
        source: 'public-board',
        response,
      });
      setFeedbackMessage(`Feedback recorded for ${item.title}.`);
      await loadBoard();
    } catch (err) {
      setFeedbackMessage(err instanceof Error ? err.message : 'Failed to submit feedback.');
    } finally {
      setFeedbackBusyId(null);
    }
  }, [loadBoard]);

  const summaryCards = [
    { label: 'Open', value: board?.open_count ?? 0, icon: AlertTriangle, tone: 'text-rose-700' },
    { label: 'In progress', value: board?.in_progress_count ?? 0, icon: Clock3, tone: 'text-amber-700' },
    { label: 'Resolved', value: board?.completed_count ?? 0, icon: CheckCircle2, tone: 'text-emerald-700' },
    { label: 'Total', value: board?.total_count ?? 0, icon: MapPin, tone: 'text-slate-700' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-emerald-50 px-4 py-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">
            Public status board
          </div>
          <h1 className="mt-3 text-3xl font-extrabold text-slate-900">Village issue status</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            A read-only board showing recent open, in-progress, and resolved cases so residents can see what is happening without needing an account.
          </p>
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

        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1.5fr)_auto] md:items-center">
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <Search size={18} className="text-slate-400" />
              <input
                value={villageName}
                onChange={(event) => setVillageName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void loadBoard();
                  }
                }}
                className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
                placeholder="Filter by village name"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {STATUS_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setStatusFilter(option.value as typeof statusFilter)}
                  className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                    statusFilter === option.value
                      ? 'border-emerald-600 bg-emerald-600 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:text-emerald-700'
                  }`}
                >
                  {option.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => void loadBoard()}
                className="rounded-full border border-slate-200 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                Refresh
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {feedbackMessage && (
          <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {feedbackMessage}
          </div>
        )}

        {loading ? (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            <Loader2 size={16} className="mr-2 inline animate-spin" />
            Loading public status board...
          </div>
        ) : items.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-sm text-slate-500 shadow-sm">
            No cases match the current filter.
          </div>
        ) : (
          <div className="mt-6 grid gap-4">
            {items.map((item: PublicStatusBoardItem) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wide ${statusTone(item.status)}`}>
                        {item.status.replace('_', ' ')}
                      </span>
                      {item.severity && (
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                          {item.severity}
                        </span>
                      )}
                    </div>
                    <h2 className="mt-3 text-lg font-bold text-slate-900">{item.title}</h2>
                    <div className="mt-1 text-sm text-slate-600">
                      {item.village_name || 'Unknown village'}
                      {item.village_address ? ` · ${item.village_address}` : ''}
                    </div>
                  </div>
                  <div className="text-xs text-slate-400">
                    Updated {item.updated_at ? new Date(item.updated_at).toLocaleString() : 'recently'}
                  </div>
                </div>
                <div className="mt-4 grid gap-3 text-sm text-slate-600 md:grid-cols-3">
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    Assigned volunteers <span className="font-semibold text-slate-900">{item.assigned_count}</span>
                  </div>
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    Duplicate reports <span className="font-semibold text-slate-900">{item.duplicate_count}</span>
                  </div>
                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    Media items <span className="font-semibold text-slate-900">{item.media_count}</span>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={feedbackBusyId === item.id}
                    onClick={() => void sendFeedback(item, 'resolved')}
                    className="rounded-full bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-60"
                  >
                    Resolved
                  </button>
                  <button
                    type="button"
                    disabled={feedbackBusyId === item.id}
                    onClick={() => void sendFeedback(item, 'still_broken')}
                    className="rounded-full bg-amber-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-amber-400 disabled:opacity-60"
                  >
                    Still broken
                  </button>
                  <button
                    type="button"
                    disabled={feedbackBusyId === item.id}
                    onClick={() => void sendFeedback(item, 'needs_more_help')}
                    className="rounded-full bg-slate-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
                  >
                    Need more help
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
