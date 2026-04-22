import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle, Clock, MapPinned } from 'lucide-react';
import { api, type ProblemRecord } from '../services/api';
import ProblemMap from '../components/ProblemMap';
import { useNavigate } from 'react-router-dom';

export default function MapView() {
  const navigate = useNavigate();
  const [problems, setProblems] = useState<ProblemRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'in_progress' | 'completed'>('all');

  useEffect(() => {
    let mounted = true;
    api.getProblems()
      .then((data) => {
        if (mounted) {
          setProblems(data);
        }
      })
      .catch((error) => {
        console.error('Failed to load map data:', error);
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const filteredProblems = useMemo(() => (
    statusFilter === 'all' ? problems : problems.filter((problem) => problem.status === statusFilter)
  ), [problems, statusFilter]);

  const completed = problems.filter((problem) => problem.status === 'completed').length;
  const pending = problems.filter((problem) => problem.status === 'pending').length;
  const active = problems.filter((problem) => problem.status === 'in_progress').length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50 px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">
              <MapPinned size={16} />
              Live Geospatial View
            </div>
            <h1 className="mt-3 text-4xl font-bold text-slate-900">Problem locations and volunteer deployments</h1>
            <p className="mt-2 max-w-2xl text-slate-600">
              Browse reported issues on the map, filter them by operational state, and inspect the live problem stream coming from the backend.
            </p>
          </div>

          <button
            onClick={() => navigate('/dashboard')}
            className="rounded-xl border border-emerald-200 bg-white px-4 py-2 font-semibold text-emerald-700 shadow-sm hover:bg-emerald-50"
          >
            Back to dashboard
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">Pending</span>
              <AlertTriangle className="text-rose-500" size={20} />
            </div>
            <div className="mt-2 text-3xl font-bold text-rose-600">{pending}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">In Progress</span>
              <Clock className="text-amber-500" size={20} />
            </div>
            <div className="mt-2 text-3xl font-bold text-amber-600">{active}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">Resolved</span>
              <CheckCircle className="text-emerald-500" size={20} />
            </div>
            <div className="mt-2 text-3xl font-bold text-emerald-600">{completed}</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {(['all', 'pending', 'in_progress', 'completed'] as const).map((value) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                statusFilter === value
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {value === 'all' ? 'All problems' : value.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">Problem map</h2>
              <span className="text-sm text-slate-500">{filteredProblems.length} markers</span>
            </div>
            <div className="h-[640px] overflow-hidden rounded-2xl">
              {loading ? (
                <div className="flex h-full items-center justify-center text-slate-500">Loading map...</div>
              ) : (
                <ProblemMap problems={filteredProblems} zoom={6} />
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Recent cases</h2>
              <p className="mt-1 text-sm text-slate-500">Problem cards reflect the same live state used by the dashboard.</p>
            </div>

            <div className="space-y-3">
              {filteredProblems.slice(0, 8).map((problem) => (
                <div key={problem.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-slate-900">{problem.title}</h3>
                      <p className="text-sm text-slate-500">{problem.village_name}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-bold uppercase tracking-wide ${
                      problem.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-700'
                        : problem.status === 'in_progress'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-rose-100 text-rose-700'
                    }`}>
                      {problem.status.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-3 text-sm text-slate-600">{problem.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
