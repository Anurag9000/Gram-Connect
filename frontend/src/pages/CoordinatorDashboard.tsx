import { useState, useEffect, useCallback } from 'react';
import {
  Activity, Clock, AlertTriangle, CheckCircle, Search,
  BarChart3, LayoutGrid, List, MapPin, ChevronRight, X, UserCheck, Cpu, Trash2
} from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import { useTranslation } from 'react-i18next';
import { api, type MediaRecord, type ProblemRecord, type ProofRecord, type TeamMember, type VolunteerRecord } from '../services/api';
import { Navigate, useNavigate } from 'react-router-dom';
import type { Database } from '../lib/database.types';
import GramSahayakaPanel from '../components/GramSahayakaPanel';
import ProblemMap from '../components/ProblemMap';
import { subscribeLiveRefresh } from '../lib/liveRefresh';

type Problem = Database['public']['Tables']['problems']['Row'];
type Profile = Database['public']['Tables']['profiles']['Row'];
type Volunteer = Database['public']['Tables']['volunteers']['Row'];
type Match = Database['public']['Tables']['matches']['Row'];

interface VolunteerWithProfile extends Volunteer {
  profile?: Profile;
  willingness_eff?: number;
}

interface ProblemWithDetails extends Problem {
  villager?: Profile;
  matches?: (Match & { volunteer?: VolunteerWithProfile })[];
  visual_tags?: string[];
  village_address?: string;
  media_assets?: MediaRecord[];
  proof?: ProofRecord;
}

interface AITeam {
  id: string;
  name: string;
  members: (TeamMember & {
    domain_score?: number;
    willingness_score?: number;
    match_score?: number;
    nexus_score?: number;
    distance_km?: number;
    availability_level?: number;
  })[];
  teamScore: number;
  coverage: number;
  kRobustness: number;
  willingnessAvg: number;
  avgDistanceKm: number;
  combinedSkills: string[];
}

function normalizePositiveInt(value: string, fallback: number, min: number, max: number) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

export default function CoordinatorDashboard() {
  const { profile } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const seedText = (value: string | null | undefined, fallback = 'Unknown') => t('seed.' + (value ?? fallback), value ?? fallback);

  const [problems, setProblems] = useState<ProblemWithDetails[]>([]);
  const [filteredProblems, setFilteredProblems] = useState<ProblemWithDetails[]>([]);
  const [allVolunteers, setAllVolunteers] = useState<VolunteerWithProfile[]>([]);
  const [loading, setLoading] = useState(true);

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const [selectedProblem, setSelectedProblem] = useState<ProblemWithDetails | null>(null);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [modalTab, setModalTab] = useState<'manual' | 'ai'>('manual');

  // AI Team Generation State
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSummary, setAiSummary] = useState<{ severity: string; origin: string; location?: string } | null>(null);
  const [aiTeams, setAiTeams] = useState<AITeam[]>([]);
  const [teamSize, setTeamSize] = useState(2);
  const [numTeamsToShow, setNumTeamsToShow] = useState(3);

  // Manual Assignment State
  const [individualSearch, setIndividualSearch] = useState('');
  const [individualSort] = useState<'name' | 'skills'>('name');
  const [selectedManualIds, setSelectedManualIds] = useState<Set<string>>(new Set());
  const [expandedVolunteerId, setExpandedVolunteerId] = useState<string | null>(null);
  const [confirmingManual, setConfirmingManual] = useState(false);

  // Stats
  const [stats, setStats] = useState({ pending: 0, inProgress: 0, resolved: 0 });

  const loadDashboardData = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const [problemsData, volunteersData] = await Promise.all([
        api.getProblems(),
        api.getVolunteers()
      ]);

      const problemsWithMatches: ProblemWithDetails[] = problemsData.map((problem: ProblemRecord) => ({
        ...problem,
        villager: problem.profiles,
        matches: problem.matches?.map((m: any) => ({
          ...m,
          volunteer: {
            ...m.volunteers,
            profile: m.volunteers?.profiles ?? m.volunteers?.profile
          },
        })) || [],
      }));

      setProblems(problemsWithMatches);
      setAllVolunteers(volunteersData.map((volunteer: VolunteerRecord) => ({
        ...volunteer,
        profile: volunteer.profiles ?? volunteer.profile,
      })));

      // Calculate stats
      const s = { pending: 0, inProgress: 0, resolved: 0 };
      problemsData.forEach((p) => {
        if (p.status === 'pending') s.pending++;
        else if (p.status === 'in_progress') s.inProgress++;
        else if (p.status === 'completed') s.resolved++;
      });
      setStats(s);

    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
    }
  }, [profile]);

  const applyFilters = useCallback(() => {
    let filtered = [...problems];
    if (statusFilter !== 'all') {
      filtered = filtered.filter((p) => p.status === statusFilter);
    }
    if (categoryFilter !== 'all') {
      filtered = filtered.filter((p) => p.category === categoryFilter);
    }
    if (searchTerm) {
      filtered = filtered.filter(
        (p) =>
          p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
          p.village_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          p.description.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    setFilteredProblems(filtered);
  }, [categoryFilter, problems, searchTerm, statusFilter]);

  useEffect(() => {
    if (profile) {
      loadDashboardData();
    }
  }, [loadDashboardData, profile]);

  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  const getFilteredAndSortedVolunteers = () => {
    let individuals = [...allVolunteers];
    if (individualSearch) {
      individuals = individuals.filter(v =>
        (v.profile?.full_name ?? '').toLowerCase().includes(individualSearch.toLowerCase()) ||
        v.skills.join(' ').toLowerCase().includes(individualSearch.toLowerCase())
      );
    }
    if (individualSort === 'name') {
      individuals.sort((a, b) => (a.profile?.full_name ?? '').localeCompare(b.profile?.full_name ?? ''));
    } else if (individualSort === 'skills') {
      individuals.sort((a, b) => b.skills.length - a.skills.length);
    }
    return individuals;
  };

  const runAiAlgo = useCallback(async () => {
    if (!selectedProblem) return;
    setAiError(null);
    setAiSummary(null);
    setAiLoading(true);

    try {
      const start = new Date();
      const end = new Date(start.getTime() + 4 * 60 * 60 * 1000);

      const data = await api.getRecommendations({
        proposal_text: selectedProblem.description,
        village_name: selectedProblem.village_name,
        task_start: start.toISOString(),
        task_end: end.toISOString(),
        team_size: teamSize,
        num_teams: numTeamsToShow,
        auto_extract: true,
      });

      setAiSummary({
        severity: data.severity_detected || 'NORMAL',
        origin: data.severity_source || 'AI',
        location: data.proposal_location || undefined,
      });

      const teams = (data.teams || []).map((team: any, index: number) => ({
        id: team.team_ids || `team-${index + 1}`,
        name: team.team_names || `Team ${index + 1}`,
        members: team.members || [],
        teamScore: team.team_score ?? team.goodness ?? 0,
        coverage: team.coverage || 0,
        kRobustness: team.k_robustness || 0,
        willingnessAvg: team.willingness_avg || 0,
        avgDistanceKm: team.avg_distance_km ?? 0,
        combinedSkills: Array.from(new Set(team.members?.flatMap((m: any) => m.skills || []) || [])) as string[]
      }));

      setAiTeams(teams);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to generate recommendations.");
      setAiTeams([]);
    } finally {
      setAiLoading(false);
    }
  }, [numTeamsToShow, selectedProblem, teamSize]);

  useEffect(() => {
    if (!profile) return;
    const unsubscribe = subscribeLiveRefresh(() => {
      loadDashboardData();
      if (showAssignModal && selectedProblem && modalTab === 'ai') {
        runAiAlgo();
        return;
      }
      setAiTeams([]);
      setAiSummary(null);
      setAiError(null);
    });

    const handleFocus = () => loadDashboardData();
    window.addEventListener('focus', handleFocus);
    return () => { unsubscribe(); window.removeEventListener('focus', handleFocus); };
  }, [loadDashboardData, modalTab, profile, runAiAlgo, selectedProblem, showAssignModal]);

  useEffect(() => {
    if (!selectedProblem) return;
    const latestProblem = problems.find((problem) => problem.id === selectedProblem.id);
    if (!latestProblem) {
      setSelectedProblem(null);
      setShowAssignModal(false);
      setAiTeams([]);
      setAiSummary(null);
      setAiError(null);
      return;
    }
    if (latestProblem !== selectedProblem) {
      setSelectedProblem(latestProblem);
    }
  }, [problems, selectedProblem]);

  const confirmManualTeam = async (problemId: string) => {
    if (selectedManualIds.size === 0) return;
    setConfirmingManual(true);
    try {
      await Promise.all(
        Array.from(selectedManualIds).map(id => api.assignTask(problemId, id))
      );
      setShowAssignModal(false);
      setSelectedManualIds(new Set());
      setExpandedVolunteerId(null);
      loadDashboardData();
    } catch {
      alert('Failed to assign one or more volunteers.');
    } finally {
      setConfirmingManual(false);
    }
  };

  const handleAssignTeam = async (problemId: string, team: AITeam) => {
    try {
      const memberIds = Array.from(
        new Set(team.members.map((member) => member.person_id || member.id).filter(Boolean))
      ) as string[];
      if (memberIds.length === 0) throw new Error("No valid team members to assign.");
      await Promise.all(memberIds.map((memberId) => api.assignTask(problemId, memberId)));
      setShowAssignModal(false);
      loadDashboardData();
    } catch {
      alert("Failed to assign team.");
    }
  };

  const handleStatusChange = async (problemId: string, newStatus: string) => {
    try {
      await api.updateProblemStatus(problemId, newStatus);
      loadDashboardData();
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  };

  const handleDeleteProblem = async (problemId: string) => {
    if (!window.confirm("Are you sure you want to delete this problem? This action cannot be undone.")) return;
    try {
      await api.deleteProblem(problemId);
      loadDashboardData();
    } catch (err) {
      console.error("Failed to delete problem", err);
      alert("Failed to delete problem.");
    }
  };

  const handleUnassignVolunteer = async (problemId: string, matchId: string) => {
    try {
      await api.unassignVolunteer(problemId, matchId);
      loadDashboardData();
    } catch (err) {
      console.error("Failed to unassign volunteer", err);
      alert("Failed to unassign volunteer.");
    }
  };

  if (!profile || profile.role !== 'coordinator') {
    return <Navigate to="/coordinator-login" replace />;
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 border-4 border-green-200 border-t-green-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-500 font-medium">{t('dashboard.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation Bar */}
      <header className="bg-white shadow-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center gap-2">
              <Activity className="text-green-600" />
              <h1 className="text-xl font-bold text-gray-900">{t('dashboard.coordinator_dashboard')}</h1>
            </div>
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/')} className="text-gray-500 hover:text-green-600 font-medium transition">
                {t('dashboard.home_btn')}
              </button>
              <div className="h-6 w-px bg-gray-200"></div>
              <div className="flex items-center gap-2 ml-2">
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-700 font-bold text-sm">
                  {profile?.full_name?.charAt(0) || "C"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <GramSahayakaPanel />
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col">
            <span className="text-gray-500 text-sm font-medium mb-1">{t('dashboard.total_issues')}</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-gray-900">{problems.length}</span>
              <BarChart3 className="text-gray-300 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-red-500">
            <span className="text-gray-500 text-sm font-medium mb-1">{t('dashboard.needs_attention')}</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-red-600">{stats.pending}</span>
              <AlertTriangle className="text-red-200 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-yellow-500">
            <span className="text-gray-500 text-sm font-medium mb-1">{t('dashboard.in_progress')}</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-yellow-600">{stats.inProgress}</span>
              <Clock className="text-yellow-200 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-green-500">
            <span className="text-gray-500 text-sm font-medium mb-1">{t('dashboard.resolved')}</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-green-600">{stats.resolved}</span>
              <CheckCircle className="text-green-200 mb-1" size={20} />
            </div>
          </div>
        </div>

        <div className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
          <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-900">{t('dashboard.live_map')}</h2>
                <p className="text-sm text-gray-500">{t('dashboard.live_map_desc')}</p>
              </div>
              <button
                onClick={() => navigate('/map')}
                className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-semibold text-green-700 hover:bg-green-100"
              >
                {t('dashboard.open_full_view')}
              </button>
            </div>
            <div className="h-[420px] overflow-hidden rounded-xl">
              <ProblemMap problems={filteredProblems.length > 0 ? filteredProblems : problems} zoom={6} />
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-3">{t('dashboard.map_notes_title')}</h3>
            <div className="space-y-3 text-sm text-gray-600">
              <p>• {t('dashboard.map_note_1')}</p>
              <p>• {t('dashboard.map_note_2')}</p>
              <p>• {t('dashboard.map_note_3')}</p>
            </div>
          </div>
        </div>

        {/* Filters and Actions */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
          <div className="flex items-center bg-white rounded-lg shadow-sm border border-gray-200 p-1 w-full md:w-auto">
            <Search className="text-gray-400 ml-2" size={20} />
            <input
              type="text"
              placeholder={t('dashboard.search_placeholder')}
              data-testid="problem-search-input"
              className="px-3 py-2 outline-none w-full md:w-64"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="flex gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
            {(['all', 'pending', 'in_progress', 'completed'] as const).map(status => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${statusFilter === status ? 'bg-gray-800 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}
              >
                {t('common.' + status, status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' '))}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 border-l pl-4 border-gray-300">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg ${viewMode === 'grid' ? 'bg-green-100 text-green-700' : 'text-gray-400 hover:bg-gray-100'}`}
            >
              <LayoutGrid size={20} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg ${viewMode === 'list' ? 'bg-green-100 text-green-700' : 'text-gray-400 hover:bg-gray-100'}`}
            >
              <List size={20} />
            </button>
          </div>
        </div>

        {/* Problems Grid/List */}
        {filteredProblems.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-dashed border-gray-300">
            <p className="text-gray-500">{t('dashboard.no_problems_found')}</p>
          </div>
        ) : (
          <div className={viewMode === 'grid' ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filteredProblems.map((problem) => (
              <div key={problem.id} data-testid={`problem-card-${problem.id}`} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow flex flex-col">
                <div className="p-6 flex-1 flex flex-col">
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-2">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase ${
                        problem.status === 'pending' ? 'bg-red-100 text-red-700' :
                        problem.status === 'in_progress' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {t('common.' + problem.status.toLowerCase(), problem.status.replace('_', ' '))}
                      </span>
                      {problem.severity && (
                        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wide ${
                          problem.severity === 'HIGH'   ? 'bg-red-600 text-white' :
                          problem.severity === 'NORMAL' ? 'bg-amber-100 text-amber-700' :
                                                          'bg-gray-100 text-gray-500'
                        }`}>
                          {t('common.' + (problem.severity || 'normal').toLowerCase(), problem.severity || 'NORMAL')}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">{new Date(problem.created_at).toLocaleDateString()}</span>
                  </div>

                  <h3 className="text-lg font-bold text-gray-900 mb-2">{seedText(problem.title, problem.title)}</h3>

                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
                    <MapPin size={16} />
                    <span className="truncate">{seedText(problem.village_name, problem.village_name)}, {seedText(problem.village_address, problem.village_address)}</span>
                  </div>

                  <p className="text-gray-600 text-sm mb-4 line-clamp-3">{seedText(problem.description, problem.description)}</p>

                  <div className="flex flex-wrap gap-2 mb-4 mt-auto">
                    {problem.visual_tags?.slice(0, 3).map((tag: string) => (
                      <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded border border-gray-200">#{seedText(tag, tag)}</span>
                    ))}
                  </div>

                  {problem.matches && problem.matches.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-bold text-gray-500 mb-2 uppercase">{t('dashboard.assigned_volunteers')}</p>
                      <div className="space-y-2">
                        {problem.matches.map(m => (
                          <div key={m.id} className="flex justify-between items-center text-sm bg-gray-50 p-2 rounded border border-gray-100">
                            <span className="font-medium text-gray-700">{seedText(m.volunteer?.profile?.full_name || "Unknown", m.volunteer?.profile?.full_name || "Unknown")}</span>
                            <button onClick={() => handleUnassignVolunteer(problem.id, m.id)} className="text-red-500 hover:text-red-700 text-xs font-semibold">{t('dashboard.unassign')}</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Action Footer */}
                  <div className="pt-4 border-t border-gray-100 flex items-center justify-between mt-auto">
                    <div className="flex flex-wrap gap-2">
                        {problem.status !== 'completed' && (
                        <button
                            onClick={() => {
                            setSelectedProblem(problem);
                            setShowAssignModal(true);
                            setModalTab('ai'); // Default to AI
                            setAiTeams([]);
                            }}
                            className="text-sm font-semibold text-green-600 hover:text-green-800 flex items-center gap-1 bg-green-50 px-3 py-1 rounded-md transition"
                        >
                            {t('dashboard.assign_team', 'Assign Team')} <ChevronRight size={16} />
                        </button>
                        )}
                        {problem.status === 'in_progress' && (
                        <button
                            onClick={() => handleStatusChange(problem.id, 'completed')}
                            className="text-sm bg-blue-50 text-blue-700 px-3 py-1 rounded-md hover:bg-blue-100 font-medium transition"
                        >
                            {t('dashboard.force_resolve')}
                        </button>
                        )}
                        {problem.status === 'completed' && (
                        <button
                            onClick={() => handleStatusChange(problem.id, 'in_progress')}
                            className="text-sm bg-yellow-50 text-yellow-700 px-3 py-1 rounded-md hover:bg-yellow-100 font-medium transition"
                        >
                            {t('dashboard.reopen_task')}
                        </button>
                        )}
                    </div>
                    <button
                      onClick={() => handleDeleteProblem(problem.id)}
                      className="text-red-400 hover:text-red-600 hover:bg-red-50 p-2 rounded-lg transition"
                      title="Nuke/Delete Task"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Assignment Modal */}
      {showAssignModal && selectedProblem && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="p-6 border-b flex justify-between items-center bg-gray-50">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">{t('dashboard.assign_modal_title')}</h2>
                <p className="text-gray-500 text-sm mt-1">{t('dashboard.assign_modal_for')} <span className="font-semibold text-gray-900">{seedText(selectedProblem.title, selectedProblem.title)}</span></p>
              </div>
              <button onClick={() => { setShowAssignModal(false); setSelectedManualIds(new Set()); setExpandedVolunteerId(null); }} className="text-gray-400 hover:text-gray-600 p-2 hover:bg-gray-100 rounded-full transition">
                <X size={24} />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setModalTab('manual')}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${modalTab === 'manual' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              >
                <div className="flex items-center justify-center gap-2"><UserCheck size={18} /> {t('dashboard.tab_manual')}</div>
              </button>
              <button
                onClick={() => setModalTab('ai')}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${modalTab === 'ai' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              >
                <div className="flex items-center justify-center gap-2"><Cpu size={18} /> {t('dashboard.tab_ai')}</div>
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50">

              {/* Manual Assignment */}
              {modalTab === 'manual' && (
                <div className="flex flex-col gap-3">
                  {/* Search */}
                  <div className="flex items-center bg-white border border-gray-300 rounded-lg px-3 py-2">
                    <Search size={18} className="text-gray-400 mr-2 shrink-0" />
                    <input
                      type="text"
                      placeholder={t('dashboard.search_volunteer_placeholder')}
                      className="flex-1 outline-none text-sm"
                      value={individualSearch}
                      onChange={(e) => setIndividualSearch(e.target.value)}
                    />
                    {selectedManualIds.size > 0 && (
                      <button onClick={() => setSelectedManualIds(new Set())} className="ml-2 text-xs text-red-500 hover:text-red-700 font-semibold shrink-0">
                        {t('dashboard.clear', 'Clear')} ({selectedManualIds.size})
                      </button>
                    )}
                  </div>

                  {/* Volunteer list */}
                  <div className="space-y-2">
                    {getFilteredAndSortedVolunteers().map(volunteer => {
                      const vid = volunteer.id || volunteer.user_id;
                      const checked = selectedManualIds.has(vid);
                      const expanded = expandedVolunteerId === vid;
                      const avail = (volunteer.availability_status || 'unknown');
                      const availColor = avail === 'available' ? 'text-emerald-600 bg-emerald-50' : avail === 'busy' ? 'text-amber-600 bg-amber-50' : 'text-gray-500 bg-gray-100';
                      return (
                        <div key={vid} className={`rounded-xl border transition-all ${checked ? 'border-green-400 bg-green-50/40 shadow-sm' : 'border-gray-200 bg-white'}`}>
                          {/* Row */}
                          <div className="flex items-center gap-3 p-3">
                            {/* Checkbox */}
                            <input
                              type="checkbox"
                              id={`vol-check-${vid}`}
                              checked={checked}
                              onChange={() => {
                                const next = new Set(selectedManualIds);
                                if (checked) next.delete(vid); else next.add(vid);
                                setSelectedManualIds(next);
                              }}
                              className="w-4 h-4 accent-green-600 shrink-0 cursor-pointer"
                            />
                            {/* Avatar */}
                            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-green-200 to-emerald-400 flex items-center justify-center text-white font-bold text-sm shrink-0">
                              {(volunteer.profile?.full_name || 'V').charAt(0).toUpperCase()}
                            </div>
                            {/* Name + skills summary */}
                            <div className="flex-1 min-w-0">
                              <button
                                className="font-semibold text-sm text-gray-900 hover:text-green-700 text-left truncate w-full"
                                onClick={() => setExpandedVolunteerId(expanded ? null : vid)}
                              >
                                {seedText(volunteer.profile?.full_name || vid, volunteer.profile?.full_name || vid)}
                              </button>
                              <p className="text-xs text-gray-500 truncate">{volunteer.skills.slice(0, 3).map(s => seedText(s, s)).join(' · ')}{volunteer.skills.length > 3 ? ` +${volunteer.skills.length - 3}` : ''}</p>
                            </div>
                            {/* Availability badge */}
                            <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full shrink-0 ${availColor}`}>
                              {seedText(avail.toLowerCase(), avail)}
                            </span>
                            {/* Expand toggle */}
                            <button
                              onClick={() => setExpandedVolunteerId(expanded ? null : vid)}
                              className="text-gray-400 hover:text-gray-700 transition shrink-0 text-xs font-medium"
                            >
                              {expanded ? '▲ ' + t('dashboard.hide', 'Hide') : '▼ ' + t('dashboard.view', 'View')}
                            </button>
                          </div>

                          {/* Expandable detail panel */}
                          {expanded && (
                            <div className="border-t border-gray-100 p-4 bg-gray-50 rounded-b-xl">
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
                                <div className="bg-white p-2.5 rounded-lg border border-gray-100 shadow-sm">
                                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">{t('dashboard.home_location', 'Home Location')}</div>
                                  <div className="text-sm font-semibold text-gray-800">{seedText(volunteer.home_location, volunteer.home_location) || '—'}</div>
                                </div>
                                <div className="bg-white p-2.5 rounded-lg border border-gray-100 shadow-sm">
                                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">{t('dashboard.availability', 'Availability')}</div>
                                  <div className="text-sm font-semibold text-gray-800">{seedText(volunteer.availability || volunteer.availability_status, volunteer.availability || volunteer.availability_status) || '—'}</div>
                                </div>
                                <div className="bg-white p-2.5 rounded-lg border border-gray-100 shadow-sm">
                                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">{t('dashboard.willingness_eff', 'Willingness (eff)')}</div>
                                  <div className="text-sm font-semibold text-gray-800">{volunteer.willingness_eff != null ? `${(Number(volunteer.willingness_eff) * 100).toFixed(0)}%` : '—'}</div>
                                </div>
                              </div>
                              <div className="bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">{t('dashboard.full_skill_set', 'Full Skill Set')}</div>
                                <div className="flex flex-wrap gap-1.5">
                                  {volunteer.skills.map(s => (
                                    <span key={s} className="text-xs bg-emerald-50 text-emerald-800 border border-emerald-100 px-2 py-0.5 rounded-full">{seedText(s, s)}</span>
                                  ))}
                                </div>
                              </div>
                              {volunteer.profile?.email && (
                                <p className="mt-2 text-xs text-gray-400">📧 {volunteer.profile.email}</p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Sticky confirm bar */}
                  {selectedManualIds.size > 0 && (
                    <div className="sticky bottom-0 left-0 right-0 bg-white border-t-2 border-green-400 shadow-lg rounded-b-xl p-4 flex items-center justify-between gap-4 z-10">
                      <div className="text-sm font-semibold text-gray-800">
                        <span className="text-green-700 text-lg font-bold">{selectedManualIds.size}</span> {t('dashboard.volunteers_selected', 'volunteers selected')}
                        <div className="text-xs text-gray-500 font-normal mt-0.5">
                          {allVolunteers.filter(v => selectedManualIds.has(v.id || v.user_id)).map(v => v.profile?.full_name || v.id).join(', ')}
                        </div>
                      </div>
                      <button
                        onClick={() => confirmManualTeam(selectedProblem.id)}
                        disabled={confirmingManual}
                        className="bg-green-600 text-white font-bold px-6 py-2.5 rounded-lg hover:bg-green-700 disabled:opacity-50 transition shadow-md shrink-0"
                      >
                        {confirmingManual ? t('dashboard.assigning') : `${t('dashboard.confirm_team')} (${selectedManualIds.size})`}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* AI Assignment */}
              {modalTab === 'ai' && (
                <div>
                  <div className="bg-white p-4 rounded-lg border-gray-200 border mb-6 shadow-sm">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1">{t('dashboard.team_size_label')}</label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={teamSize}
                          onChange={(e) => setTeamSize(normalizePositiveInt(e.target.value, 2, 1, 10))}
                          className="w-full border border-gray-300 rounded p-2 focus:ring-2 focus:ring-green-100 focus:border-green-500 outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1">{t('dashboard.solutions_label')}</label>
                        <input
                          type="number"
                          min="1"
                          max="20"
                          value={numTeamsToShow}
                          onChange={(e) => setNumTeamsToShow(normalizePositiveInt(e.target.value, 3, 1, 20))}
                          className="w-full border border-gray-300 rounded p-2 focus:ring-2 focus:ring-green-100 focus:border-green-500 outline-none"
                        />
                      </div>
                    </div>
                    <button
                      onClick={runAiAlgo}
                      disabled={aiLoading}
                      data-testid="generate-optimal-teams"
                      className="w-full bg-blue-600 text-white py-3 rounded-lg font-bold hover:bg-blue-700 disabled:bg-gray-300 flex justify-center gap-2 items-center transition shadow-md"
                    >
                      {aiLoading ? <span className="animate-spin">⌛</span> : <Cpu size={20} />}
                      {aiLoading ? t('dashboard.ai_analyzing') : t('dashboard.find_teams')}
                    </button>
                  </div>

                  {aiError && (
                    <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6 text-sm border border-red-200 flex items-start gap-2">
                      <AlertTriangle size={18} className="shrink-0 mt-0.5" />
                      <div>
                        <div className="font-bold mb-1">{t('dashboard.ai_failed')}</div>
                        <div>{aiError}</div>
                      </div>
                    </div>
                  )}

                  {aiSummary && (
                    <div className="flex gap-3 mb-6 text-sm font-medium">
                      <span className="bg-orange-100 text-orange-800 px-3 py-1.5 rounded-lg border border-orange-200 flex items-center gap-1">
                        <AlertTriangle size={14} /> {t('dashboard.severity_label')} {aiSummary.severity}
                      </span>
                      <span className="bg-blue-100 text-blue-800 px-3 py-1.5 rounded-lg border border-blue-200 flex items-center gap-1">
                        <Activity size={14} /> {t('dashboard.origin_label')} {aiSummary.origin}
                      </span>
                      {aiSummary.location && (
                        <span className="bg-gray-100 text-gray-800 px-3 py-1.5 rounded-lg border border-gray-200 flex items-center gap-1">
                            <MapPin size={14} /> {t('dashboard.loc_label')} {aiSummary.location}
                        </span>
                      )}
                    </div>
                  )}

                  <div className="space-y-6">
                    {aiTeams.map((team, idx) => (
                      <div key={idx} className="bg-white border border-blue-200 rounded-xl p-5 shadow-md hover:border-blue-400 transition-colors">
                        <div className="flex justify-between items-start mb-4 border-b border-gray-100 pb-4">
                          <div>
                            <h4 className="font-bold text-gray-900 text-lg flex items-center gap-2">
                              <span className="bg-blue-600 text-white w-7 h-7 rounded-full flex items-center justify-center text-sm">{idx + 1}</span>
                              {seedText(team.name, team.name)}
                            </h4>
                            <div className="text-xs text-gray-600 mt-2 flex flex-wrap gap-4 font-medium">
                              <span title="Team ranking score: skill_coverage x geometric_mean(member scores) - distance_penalty" className="bg-gray-100 px-2 py-1 rounded">{t('dashboard.team_score', 'Team Score:')} {(team.teamScore * 100).toFixed(1)}%</span>
                              <span title="How well the AI team stays stable across alternate teamings" className="bg-violet-50 text-violet-700 px-2 py-1 rounded">{t('dashboard.robustness', 'Robustness:')} {team.kRobustness.toFixed(2)}</span>
                              <span title="Fraction of the task's required skills collectively covered by this team" className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded">{t('dashboard.skill_coverage', 'Skill Coverage:')} {(team.coverage * 100).toFixed(1)}%</span>
                              <span title="Average volunteer travel distance" className="bg-amber-50 text-amber-700 px-2 py-1 rounded">{t('dashboard.avg_dist', 'Avg Dist:')} {team.avgDistanceKm.toFixed(1)} km</span>
                              <span title="Average willingness to participate" className="bg-blue-50 text-blue-700 px-2 py-1 rounded">{t('dashboard.avg_will', 'Avg Will:')} {(team.willingnessAvg * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                          <button
                            onClick={() => handleAssignTeam(selectedProblem.id, team)}
                            data-testid={`assign-ai-team-${idx + 1}`}
                            className="bg-blue-600 text-white font-bold text-sm hover:bg-blue-700 px-5 py-2.5 rounded-lg shadow-sm transition"
                          >
                            {t('dashboard.assign_team_btn')}
                          </button>
                        </div>

                        <div className="space-y-3">
                          {team.members.map((member) => (
                            <div key={member.person_id || member.id} className="flex flex-col gap-2 bg-gray-50 p-4 rounded-lg border border-gray-100">
                              <div className="flex justify-between items-center text-sm">
                                <span className="font-bold text-gray-900 text-base">{seedText(member.profile?.full_name || member.name || "Unknown", member.profile?.full_name || member.name || "Unknown")}</span>
                                <span className="bg-indigo-100 text-indigo-800 text-xs font-bold px-2.5 py-1 rounded-full border border-indigo-200" title={t('dashboard.nexus_formula_tooltip', 'Nexus Score = DOMAIN^2 * WILL * AVAIL^0.5 * PROX * FRESH^0.5')}>
                                  Nexus: {((member.match_score ?? member.nexus_score ?? 0) * 100).toFixed(1)}%
                                </span>
                              </div>

                              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-700 mt-1">
                                <div className="bg-white p-2 rounded shadow-sm border border-gray-100">
                                  <span className="font-bold block text-gray-400 text-[10px] uppercase tracking-wider mb-0.5">{t('dashboard.domain_exp', 'Domain Exp.')}</span>
                                  <span className="font-medium">{(member.domain_score || 0).toFixed(3)}</span>
                                </div>
                                <div className="bg-white p-2 rounded shadow-sm border border-gray-100">
                                  <span className="font-bold block text-gray-400 text-[10px] uppercase tracking-wider mb-0.5">{t('dashboard.willingness', 'Willingness')}</span>
                                  <span className="font-medium">{(member.willingness_score || 0).toFixed(3)}</span>
                                </div>
                                <div className="bg-white p-2 rounded shadow-sm border border-gray-100">
                                  <span className="font-bold block text-gray-400 text-[10px] uppercase tracking-wider mb-0.5">{t('dashboard.distance', 'Distance')}</span>
                                  <span className="font-medium">
                                    {member.distance_km != null ? `${member.distance_km.toFixed(1)} km` : 'Unknown'}
                                    {member.home_location ? <span className="text-gray-400 ml-1">· {seedText(member.home_location, member.home_location)}</span> : null}
                                  </span>
                                </div>
                                <div className="bg-white p-2 rounded shadow-sm border border-gray-100">
                                  <span className="font-bold block text-gray-400 text-[10px] uppercase tracking-wider mb-0.5">{t('dashboard.avail_level', 'Avail Level')}</span>
                                  <span className="font-medium">{member.availability_level || 1}/3</span>
                                </div>
                              </div>
                              <div className="text-xs text-gray-600 mt-1 bg-white p-2 rounded border border-gray-100">
                                <span className="font-bold text-gray-500 mr-1">{t('dashboard.skills', 'Skills:')}</span> {member.skills?.map((s: string) => seedText(s, s)).join(', ')}
                              </div>
                            </div>
                          ))}
                        </div>

                        <div className="mt-4 text-sm text-blue-800 bg-blue-50 p-4 rounded-lg border border-blue-100 leading-relaxed">
                          <strong className="text-blue-900 block mb-2">{t('dashboard.why_this_team')}</strong>
                          <span className="block mb-1">{t('dashboard.ranked')} #{idx + 1} — <strong>{(team.coverage * 100).toFixed(0)}% {t('dashboard.skill_coverage_label', 'skill coverage')}</strong> — <strong>{(team.willingnessAvg * 100).toFixed(0)}% {t('dashboard.avg_will_label', 'avg willingness')}</strong> — <strong>{team.avgDistanceKm.toFixed(1)} {t('dashboard.km_avg_dist', 'km avg distance')}</strong>{team.avgDistanceKm === 0 ? ` (${t('dashboard.all_local', 'all local to problem village')})` : ''}</span>
                          <span className="block text-blue-700 text-xs mt-1">{t('dashboard.nexus_explanation', 'Individual score = DOMAIN² * WILL * AVAIL⁰⋅⁵ * PROX * FRESH⁰⋅⁵. Multiplicative: any factor at zero eliminates the candidate regardless of other strengths. Teams ranked by skill coverage first, then by geometric mean of member scores.')}</span>
                          {team.coverage < 0.3 && <span className="block text-amber-700 font-semibold mt-1">{t('dashboard.low_coverage_note')}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
