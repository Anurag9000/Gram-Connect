import { useState, useEffect } from 'react';
import {
  Activity, Clock, AlertTriangle, CheckCircle, Search,
  BarChart3, LayoutGrid, List, MapPin, ChevronRight, X, UserCheck, Cpu
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import LanguageToggle from '../components/LanguageToggle';
import { api } from '../services/api';
import { useNavigate } from 'react-router-dom';
import type { Database } from '../lib/database.types';

type Problem = Database['public']['Tables']['problems']['Row'];
type Profile = Database['public']['Tables']['profiles']['Row'];
type Volunteer = Database['public']['Tables']['volunteers']['Row'];
type Match = Database['public']['Tables']['matches']['Row'];

interface VolunteerWithProfile extends Volunteer {
  profile?: Profile;
}

interface ProblemWithDetails extends Problem {
  villager?: Profile;
  matches?: (Match & { volunteer?: VolunteerWithProfile })[];
  visual_tags?: string[];
  village_address?: string;
}

interface AITeam {
  id: string;
  name: string;
  members: any[];
  goodness: number;
  coverage: number;
  kRobustness: number;
  willingnessAvg: number;
  mockScore?: number;
  combinedSkills: string[];
}

export default function CoordinatorDashboard() {
  const { profile } = useAuth();
  const navigate = useNavigate();
  // const { t } = useTranslation(); // Unused

  const [problems, setProblems] = useState<ProblemWithDetails[]>([]);
  const [filteredProblems, setFilteredProblems] = useState<ProblemWithDetails[]>([]);
  const [allVolunteers, setAllVolunteers] = useState<VolunteerWithProfile[]>([]);
  const [loading, setLoading] = useState(true);

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter] = useState<string>('all'); // Removed setter
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
  const [individualSort] = useState<'name' | 'skills'>('name'); // Removed setter

  // Stats
  const [stats, setStats] = useState({ pending: 0, inProgress: 0, resolved: 0 });

  useEffect(() => {
    if (profile) {
      loadDashboardData();
    }
  }, [profile]);

  useEffect(() => {
    applyFilters();
  }, [problems, statusFilter, categoryFilter, searchTerm]);

  async function loadDashboardData() {
    if (!profile) return;
    setLoading(true);
    try {
      const [problemsData, volunteersData] = await Promise.all([
        api.getProblems(),
        api.getVolunteers()
      ]);

      const problemsWithMatches = problemsData.map((problem: any) => ({
        ...problem,
        villager: problem.profiles,
        matches: problem.matches?.map((m: any) => ({
          ...m,
          volunteer: m.volunteers,
        })) || [],
      }));

      setProblems(problemsWithMatches);
      setAllVolunteers(volunteersData);

      // Calculate stats
      const s = { pending: 0, inProgress: 0, resolved: 0 };
      problemsData.forEach((p: any) => {
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
  }

  function applyFilters() {
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
  }

  const getFilteredAndSortedVolunteers = () => {
    let individuals = [...allVolunteers];
    if (individualSearch) {
      individuals = individuals.filter(v =>
        v.profile?.full_name.toLowerCase().includes(individualSearch.toLowerCase()) ||
        v.skills.join(' ').toLowerCase().includes(individualSearch.toLowerCase())
      );
    }
    if (individualSort === 'name') {
      individuals.sort((a, b) => a.profile?.full_name.localeCompare(b.profile?.full_name || '') || 0);
    } else if (individualSort === 'skills') {
      individuals.sort((a, b) => b.skills.length - a.skills.length);
    }
    return individuals;
  };

  const runAiAlgo = async () => {
    if (!selectedProblem) return;
    setAiError(null);
    setAiSummary(null);
    setAiLoading(true);

    try {
      const start = new Date(); // Start now
      const end = new Date(start.getTime() + 4 * 60 * 60 * 1000); // 4 hours duration

      const data = await api.getRecommendations({
        proposal_text: selectedProblem.description,
        village_name: selectedProblem.village_name,
        task_start: start.toISOString(),
        task_end: end.toISOString(),
        team_size: teamSize,
        num_teams: numTeamsToShow,
        auto_extract: true,
      });

      // if (data.error) throw new Error(data.error); // Removed as api throws on error

      setAiSummary({
        severity: data.severity_detected || 'NORMAL',
        origin: data.severity_source || 'AI',
        location: data.proposal_location || undefined, // Handle null -> undefined
      });

      const teams = (data.teams || []).map((team: any, index: number) => ({
        id: team.team_ids || `team-${index + 1}`,
        name: team.team_names || `Team ${index + 1}`,
        members: team.members || [],
        goodness: team.goodness || 0,
        coverage: team.coverage || 0,
        kRobustness: team.metrics?.k_robustness || 0,
        willingnessAvg: team.metrics?.willingness_avg || 0,
        mockScore: Math.round((team.goodness || 0) * 100),
        combinedSkills: Array.from(new Set(team.members?.flatMap((m: any) => m.skills || []) || [])) as string[]
      }));

      setAiTeams(teams);
    } catch (err: any) {
      setAiError(err.message || "Failed to generate recommendations.");
      setAiTeams([]);
    } finally {
      setAiLoading(false);
    }
  };

  const handleAssignIndividual = async (problemId: string, volunteer: VolunteerWithProfile) => {
    try {
      await api.assignTask(problemId, volunteer.id);
      alert(`Assigned to ${volunteer.profile?.full_name}!`);
      setShowAssignModal(false);
      loadDashboardData();
    } catch (err) {
      alert("Failed to assign task.");
    }
  };

  const handleAssignTeam = async (problemId: string, team: AITeam) => {
    try {
      // Assign the lead (first member for now, or use specific lead logic)
      // In a real scenario, we might assign all members to the task.
      const lead = team.members[0];
      if (lead) {
        await api.assignTask(problemId, lead.id);
        alert(`Team ${team.name} assigned! Lead: ${lead.profile?.full_name}`);
        setShowAssignModal(false);
        loadDashboardData();
      }
    } catch (err) {
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

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 border-4 border-green-200 border-t-green-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-500 font-medium">Loading Dashboard...</p>
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
              <h1 className="text-xl font-bold text-gray-900">Coordination Center</h1>
            </div>
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/')} className="text-gray-500 hover:text-green-600 font-medium transition">
                Home
              </button>
              <div className="h-6 w-px bg-gray-200"></div>
              <LanguageToggle />
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
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col">
            <span className="text-gray-500 text-sm font-medium mb-1">Total Issues</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-gray-900">{problems.length}</span>
              <BarChart3 className="text-gray-300 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-red-500">
            <span className="text-gray-500 text-sm font-medium mb-1">Needs Attention (Open)</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-red-600">{stats.pending}</span>
              <AlertTriangle className="text-red-200 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-yellow-500">
            <span className="text-gray-500 text-sm font-medium mb-1">In Progress</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-yellow-600">{stats.inProgress}</span>
              <Clock className="text-yellow-200 mb-1" size={20} />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col border-l-4 border-l-green-500">
            <span className="text-gray-500 text-sm font-medium mb-1">Resolved</span>
            <div className="flex items-end justify-between">
              <span className="text-3xl font-bold text-green-600">{stats.resolved}</span>
              <CheckCircle className="text-green-200 mb-1" size={20} />
            </div>
          </div>
        </div>

        {/* Filters and Actions */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
          <div className="flex items-center bg-white rounded-lg shadow-sm border border-gray-200 p-1 w-full md:w-auto">
            <Search className="text-gray-400 ml-2" size={20} />
            <input
              type="text"
              placeholder="Search problems..."
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
                {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
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
            <p className="text-gray-500">No problems found matching your filters.</p>
          </div>
        ) : (
          <div className={viewMode === 'grid' ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filteredProblems.map((problem) => (
              <div key={problem.id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow group">
                <div className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase ${problem.status === 'pending' ? 'bg-red-100 text-red-700' :
                      problem.status === 'in_progress' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                      {problem.status.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-gray-400">{new Date(problem.created_at).toLocaleDateString()}</span>
                  </div>

                  <h3 className="text-lg font-bold text-gray-900 mb-2 line-clamp-2 min-h-[3.5rem]">{problem.title}</h3>

                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
                    <MapPin size={16} />
                    <span className="truncate">{problem.village_name}, {problem.village_address}</span>
                  </div>

                  <p className="text-gray-600 text-sm mb-4 line-clamp-3 h-16">{problem.description}</p>

                  <div className="flex flex-wrap gap-2 mb-4">
                    {problem.visual_tags?.slice(0, 3).map((tag: string) => (
                      <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded border border-gray-200">#{tag}</span>
                    ))}
                  </div>

                  {/* Action Footer */}
                  <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                    {problem.status !== 'completed' && (
                      <button
                        onClick={() => {
                          setSelectedProblem(problem);
                          setShowAssignModal(true);
                          setModalTab('ai'); // Default to AI
                          setAiTeams([]);
                        }}
                        className="text-sm font-semibold text-green-600 hover:text-green-800 flex items-center gap-1"
                      >
                        Assign Team <ChevronRight size={16} />
                      </button>
                    )}
                    {problem.status === 'in_progress' && (
                      <button
                        onClick={() => handleStatusChange(problem.id, 'completed')}
                        className="text-sm bg-green-50 text-green-700 px-3 py-1 rounded-md hover:bg-green-100 font-medium"
                      >
                        Mark Resolved
                      </button>
                    )}
                    {problem.status === 'completed' && (
                      <button
                        onClick={() => handleStatusChange(problem.id, 'in_progress')}
                        className="text-sm bg-gray-50 text-gray-700 px-3 py-1 rounded-md hover:bg-gray-100 font-medium"
                      >
                        Reopen
                      </button>
                    )}
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
                <h2 className="text-2xl font-bold text-gray-800">Assign Resolution Team</h2>
                <p className="text-gray-500 text-sm mt-1">For issue: <span className="font-semibold text-gray-900">{selectedProblem.title}</span></p>
              </div>
              <button onClick={() => setShowAssignModal(false)} className="text-gray-400 hover:text-gray-600 p-2 hover:bg-gray-100 rounded-full transition">
                <X size={24} />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setModalTab('manual')}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${modalTab === 'manual' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              >
                <div className="flex items-center justify-center gap-2"><UserCheck size={18} /> Manual Assignment</div>
              </button>
              <button
                onClick={() => setModalTab('ai')}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${modalTab === 'ai' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              >
                <div className="flex items-center justify-center gap-2"><Cpu size={18} /> AI Team Builder</div>
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50/50">

              {/* Manual Assignment */}
              {modalTab === 'manual' && (
                <div>
                  <div className="flex gap-4 mb-4">
                    <div className="flex-1 flex items-center bg-white border border-gray-300 rounded-lg px-3 py-2">
                      <Search size={18} className="text-gray-400 mr-2" />
                      <input
                        type="text"
                        placeholder="Search volunteer or skill..."
                        className="flex-1 outline-none"
                        value={individualSearch}
                        onChange={(e) => setIndividualSearch(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="space-y-3">
                    {getFilteredAndSortedVolunteers().map(volunteer => (
                      <div key={volunteer.id} className="bg-white p-4 rounded-lg border border-gray-200 flex justify-between items-center">
                        <div>
                          <h4 className="font-bold text-gray-800">{volunteer.profile?.full_name}</h4>
                          <p className="text-xs text-gray-500">{volunteer.skills.join(', ')}</p>
                        </div>
                        <button
                          onClick={() => handleAssignIndividual(selectedProblem.id, volunteer)}
                          className="bg-green-100 text-green-700 px-3 py-1 rounded text-sm font-semibold hover:bg-green-200"
                        >
                          Assign
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Assignment */}
              {modalTab === 'ai' && (
                <div>
                  <div className="bg-white p-4 rounded-lg border-gray-200 border mb-6">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1">TEAM SIZE</label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={teamSize}
                          onChange={(e) => setTeamSize(parseInt(e.target.value))}
                          className="w-full border border-gray-300 rounded p-2"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1">SOLUTIONS TO GENERATE</label>
                        <input
                          type="number"
                          min="1"
                          max="20"
                          value={numTeamsToShow}
                          onChange={(e) => setNumTeamsToShow(parseInt(e.target.value))}
                          className="w-full border border-gray-300 rounded p-2"
                        />
                      </div>
                    </div>
                    <button
                      onClick={runAiAlgo}
                      disabled={aiLoading}
                      className="w-full bg-blue-600 text-white py-2 rounded-lg font-bold hover:bg-blue-700 disabled:bg-gray-300 flex justify-center gap-2 items-center"
                    >
                      {aiLoading ? <span className="animate-spin">⌛</span> : <Cpu size={18} />}
                      {aiLoading ? 'Analyzing Context & Skills...' : 'Generate Optimal Teams'}
                    </button>
                  </div>

                  {aiError && (
                    <div className="bg-red-50 text-red-700 p-3 rounded mb-4 text-sm border border-red-200">
                      {aiError}
                    </div>
                  )}

                  {aiSummary && (
                    <div className="flex gap-2 mb-4 text-xs font-semibold">
                      <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded border border-orange-200">Severity: {aiSummary.severity}</span>
                      <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded border border-blue-200">Origin: {aiSummary.origin}</span>
                      {aiSummary.location && <span className="bg-gray-100 text-gray-800 px-2 py-1 rounded border border-gray-200">Loc: {aiSummary.location}</span>}
                    </div>
                  )}

                  <div className="space-y-4">
                    {aiTeams.map((team, idx) => (
                      <div key={idx} className="bg-white border border-blue-100 rounded-xl p-4 shadow-sm hover:border-blue-300 transition">
                        <div className="flex justify-between items-start mb-3">
                          <div>
                            <h4 className="font-bold text-gray-800 flex items-center gap-2">
                              <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-xs">{idx + 1}</span>
                              {team.name}
                            </h4>
                            <div className="text-[10px] text-gray-400 mt-1 flex gap-2">
                              <span>Match: {team.mockScore}%</span>
                              <span>•</span>
                              <span>Robustness: {team.kRobustness.toFixed(2)}</span>
                            </div>
                          </div>
                          <button
                            onClick={() => handleAssignTeam(selectedProblem.id, team)}
                            className="text-blue-600 font-semibold text-sm hover:bg-blue-50 px-3 py-1 rounded"
                          >
                            Assign Info
                          </button>
                        </div>
                        <div className="space-y-2">
                          {team.members.map((member: any) => (
                            <div key={member.id} className="flex justify-between items-center text-sm bg-gray-50 p-2 rounded">
                              <span className="font-medium text-gray-700">{member.profile?.full_name || member.name || "Unknown"}</span>
                              <span className="text-xs text-gray-500">{member.skills?.slice(0, 2).join(', ')}</span>
                            </div>
                          ))}
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
