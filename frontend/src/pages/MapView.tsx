import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle, Clock, MapPin, MapPinned, Search, X } from 'lucide-react';
import { api, type ProblemRecord } from '../services/api';
import ProblemMap from '../components/ProblemMap';
import { useNavigate } from 'react-router-dom';
import { subscribeLiveRefresh } from '../lib/liveRefresh';
import { useTranslation } from 'react-i18next';

type Village = { name: string; district: string; state: string; lat?: number; lng?: number };

const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  in_progress: 'bg-amber-100 text-amber-700',
  pending: 'bg-rose-100 text-rose-700',
};

export default function MapView() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [problems, setProblems] = useState<ProblemRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'in_progress' | 'completed'>('all');

  // Village search / autocomplete
  const [villages, setVillages] = useState<Village[]>([]);
  const [locationSearch, setLocationSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedVillage, setSelectedVillage] = useState<Village | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  // Map center / zoom (controlled by village selection)
  const [mapCenter, setMapCenter] = useState<[number, number]>([21.5, 79.5]);
  const [mapZoom, setMapZoom] = useState(6);

  const loadProblems = useCallback(() => {
    setLoading(true);
    api.getProblems()
      .then(setProblems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadProblems();
    api.getVillages().then(setVillages).catch(() => {});

    const unsubscribe = subscribeLiveRefresh(loadProblems);
    const handleFocus = () => loadProblems();
    window.addEventListener('focus', handleFocus);
    return () => { unsubscribe(); window.removeEventListener('focus', handleFocus); };
  }, [loadProblems]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filteredVillages = useMemo(() => {
    if (!locationSearch.trim()) return villages;
    const q = locationSearch.toLowerCase();
    return villages.filter(v =>
      v.name.toLowerCase().includes(q) ||
      v.district.toLowerCase().includes(q) ||
      v.state.toLowerCase().includes(q)
    );
  }, [villages, locationSearch]);

  const filteredProblems = useMemo(() => {
    let base = statusFilter === 'all' ? problems : problems.filter(p => p.status === statusFilter);
    if (selectedVillage) {
      base = base.filter(p => p.village_name === selectedVillage.name);
    }
    return base;
  }, [problems, statusFilter, selectedVillage]);

  const selectVillage = (v: Village) => {
    setSelectedVillage(v);
    setLocationSearch(v.name);
    setShowDropdown(false);
    if (v.lat && v.lng) {
      setMapCenter([v.lat, v.lng]);
      setMapZoom(11);
    }
  };

  const clearVillage = () => {
    setSelectedVillage(null);
    setLocationSearch('');
    setMapCenter([21.5, 79.5]);
    setMapZoom(6);
  };

  const completed = problems.filter(p => p.status === 'completed').length;
  const pending = problems.filter(p => p.status === 'pending').length;
  const active = problems.filter(p => p.status === 'in_progress').length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50 px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">
              <MapPinned size={16} /> {t('map.live_geospatial_view')}
            </div>
            <h1 className="mt-3 text-4xl font-bold text-slate-900">{t('map.title')}</h1>
            <p className="mt-2 max-w-2xl text-slate-600">
              {t('map.subtitle')}
            </p>
          </div>
          <button
            onClick={() => navigate('/dashboard')}
            className="rounded-xl border border-emerald-200 bg-white px-4 py-2 font-semibold text-emerald-700 shadow-sm hover:bg-emerald-50"
          >
            {t('map.back_to_dashboard')}
          </button>
        </div>

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { label: t('map.pending', 'Pending'), count: pending, icon: <AlertTriangle className="text-rose-500" size={20} />, color: 'text-rose-600' },
            { label: t('map.in_progress', 'In Progress'), count: active, icon: <Clock className="text-amber-500" size={20} />, color: 'text-amber-600' },
            { label: t('map.resolved', 'Resolved'), count: completed, icon: <CheckCircle className="text-emerald-500" size={20} />, color: 'text-emerald-600' },
          ].map(s => (
            <div key={s.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-500">{s.label}</span>
                {s.icon}
              </div>
              <div className={`mt-2 text-3xl font-bold ${s.color}`}>{s.count}</div>
            </div>
          ))}
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap gap-3 items-center">
          {/* Status filter pills */}
          <div className="flex flex-wrap gap-2">
            {(['all', 'pending', 'in_progress', 'completed'] as const).map(v => (
              <button
                key={v}
                onClick={() => setStatusFilter(v)}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  statusFilter === v
                    ? 'bg-emerald-600 text-white shadow-md'
                    : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {v === 'all' ? t('map.all_problems') : t('map.' + v, v.replace('_', ' '))}
              </button>
            ))}
          </div>

          {/* Village location search */}
          <div ref={searchRef} className="relative ml-auto w-full md:w-72">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm focus-within:border-emerald-400 focus-within:ring-2 focus-within:ring-emerald-100">
              <Search size={16} className="text-slate-400 shrink-0" />
              <input
                type="text"
                placeholder={t('map.filter_village')}
                className="flex-1 text-sm outline-none bg-transparent text-slate-800 placeholder-slate-400"
                value={locationSearch}
                onChange={e => { setLocationSearch(e.target.value); setShowDropdown(true); if (!e.target.value) clearVillage(); }}
                onFocus={() => setShowDropdown(true)}
              />
              {locationSearch && (
                <button onClick={clearVillage} className="text-slate-400 hover:text-slate-600">
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Dropdown */}
            {showDropdown && filteredVillages.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 z-50 rounded-xl border border-slate-200 bg-white shadow-xl max-h-64 overflow-y-auto">
                {filteredVillages.map(v => (
                  <button
                    key={v.name}
                    className="w-full text-left px-4 py-3 hover:bg-emerald-50 transition flex items-start gap-3 border-b border-slate-100 last:border-0"
                    onClick={() => selectVillage(v)}
                  >
                    <MapPin size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                    <div>
                      <div className="font-semibold text-sm text-slate-800">{t('seed.' + v.name, v.name)}</div>
                      {(v.district || v.state) && (
                        <div className="text-xs text-slate-500">{[v.district, v.state].filter(Boolean).join(', ')}</div>
                      )}
                    </div>
                    {v.lat && (
                      <span className="ml-auto text-[10px] text-slate-400 shrink-0">{v.lat.toFixed(2)}°N {v.lng?.toFixed(2)}°E</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {selectedVillage && (
          <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2">
            <MapPin size={14} />
            <span>{t('map.showing')} <strong>{filteredProblems.length}</strong> {t('map.problem')}{filteredProblems.length !== 1 ? 's' : ''} {t('map.in')} <strong>{t('seed.' + selectedVillage.name, selectedVillage.name)}</strong></span>
            <button onClick={clearVillage} className="ml-auto text-emerald-500 hover:text-emerald-700"><X size={14} /></button>
          </div>
        )}

        {/* Map + Recent cases */}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">{t('map.problem_map')}</h2>
              <span className="text-sm text-slate-500">{filteredProblems.length} / {problems.length} {t('map.markers')}</span>
            </div>
            <div className="h-[640px] overflow-hidden rounded-2xl">
              {loading ? (
                <div className="flex h-full items-center justify-center text-slate-500">{t('map.loading_map')}</div>
              ) : (
                <ProblemMap problems={filteredProblems} center={mapCenter} zoom={mapZoom} />
              )}
            </div>
          </div>

          {/* Scrollable full problem list */}
          <div className="flex flex-col gap-3">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">
                {selectedVillage ? `${t('seed.' + selectedVillage.name, selectedVillage.name)} cases` : t('map.all_cases')}
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                {filteredProblems.length} {t('map.problem')}{filteredProblems.length !== 1 ? 's' : ''} — {t('map.live_backend_state')}
              </p>
            </div>

            <div className="overflow-y-auto max-h-[580px] pr-1 space-y-3">
              {loading ? (
                <div className="text-center py-8 text-slate-400">{t('map.loading')}</div>
              ) : filteredProblems.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-slate-400">
                  {t('map.no_problems')}
                </div>
              ) : filteredProblems.map(problem => (
                <div key={problem.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-slate-900 truncate">{t('seed.' + problem.title, problem.title)}</h3>
                      <div className="flex items-center gap-1 mt-0.5 text-xs text-slate-500">
                        <MapPin size={11} className="text-emerald-500 shrink-0" />
                        <span className="truncate">{t('seed.' + problem.village_name, problem.village_name)}</span>
                      </div>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide shrink-0 ${STATUS_STYLES[problem.status] ?? STATUS_STYLES.pending}`}>
                      {t(`common.${problem.status.toLowerCase()}`, problem.status.replace('_', ' '))}
                    </span>
                  </div>
                  {problem.description && (
                    <p className="mt-2 line-clamp-2 text-xs text-slate-500">{t('seed.' + problem.description, problem.description)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
