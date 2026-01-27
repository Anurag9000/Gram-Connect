import { useState, useEffect } from 'react';
import { Search, CheckCircle, Clock, AlertCircle, Users, X, Cpu, UserCheck } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import ProblemMap from '../components/ProblemMap';
import LanguageToggle from '../components/LanguageToggle';
import type { Database } from '../lib/database.types';

import { api } from '../services/api';

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
}

// --- NEW TYPE for Mock AI Teams ---
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

interface CoordinatorDashboardProps {
  onNavigate: (page: string) => void;
}

export default function CoordinatorDashboard({ onNavigate }: CoordinatorDashboardProps) {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const [problems, setProblems] = useState<ProblemWithDetails[]>([]);
  const [filteredProblems, setFilteredProblems] = useState<ProblemWithDetails[]>([]);
  const [allVolunteers, setAllVolunteers] = useState<VolunteerWithProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedProblem, setSelectedProblem] = useState<ProblemWithDetails | null>(null);
  const [showAssignModal, setShowAssignModal] = useState(false);

  const [teamSize, setTeamSize] = useState(1);
  const [severityOverride] = useState<'AUTO' | 'LOW' | 'NORMAL' | 'HIGH'>('AUTO');
  const [taskStart] = useState(() => new Date().toISOString().slice(0, 16));
  const [durationHours] = useState(4);
  const [selectedVillage] = useState('');

  // Suppress unused warnings for variables kept for compatibility/future
  void setTeamSize;
  void severityOverride;
  void taskStart;
  void durationHours;
  void selectedVillage;
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSummary, setAiSummary] = useState<{ severity: string; origin: string; location?: string } | null>(null);
  const [modalTab, setModalTab] = useState<'manual' | 'ai'>('manual');
  const [individualSearch, setIndividualSearch] = useState('');
  const [individualSort, setIndividualSort] = useState<'name' | 'skills'>('name');
  const [numTeamsToShow, setNumTeamsToShow] = useState(10);
  const [aiTeams, setAiTeams] = useState<AITeam[]>([]);

  useEffect(() => {
    if (profile) {
      loadData();
    }
  }, [profile]);

  useEffect(() => {
    applyFilters();
  }, [problems, statusFilter, categoryFilter, searchTerm]);

  async function loadData() {
    setLoading(true);
    try {
      const problemsData = await api.getProblems();
      const volunteersData = await api.getVolunteers();

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
    try {
      setAiError(null);
      setAiSummary(null);
      setAiLoading(true);

      const start = new Date(taskStart);
      if (Number.isNaN(start.getTime())) {
        setAiError("Please provide a valid task start time.");
        setAiLoading(false);
        return;
      }

      const end = new Date(start.getTime() + durationHours * 60 * 60 * 1000);

      const data = await api.getRecommendations({
        proposal_text: selectedProblem.description,
        village_name: selectedVillage || selectedProblem.village_name,
        task_start: start.toISOString(),
        task_end: end.toISOString(),
        team_size: teamSize,
        num_teams: numTeamsToShow,
        severity: severityOverride === 'AUTO' ? undefined : severityOverride,
        auto_extract: true,
      });

      setAiSummary({
        severity: data.severity_detected,
        origin: data.severity_source,
        location: data.proposal_location || undefined,
      });

      const teams = (data.teams || []).map((team: any, index: number) => ({
        id: team.team_ids || `team-${index + 1}`,
        name: team.team_names || `Team ${index + 1}`,
        goodness: team.goodness,
        coverage: team.coverage || 0,
        kRobustness: team.k_robustness || 0,
        willingnessAvg: team.willingness_avg || 0,
        members: team.members || [],
        mockScore: Math.round(team.goodness * 100),
        combinedSkills: Array.from(new Set(team.members?.flatMap((m: any) => m.skills || []) || [])) as string[]
      }));

      setAiTeams(teams);
    } catch (error) {
      setAiTeams([]);
      setAiSummary(null);
      setAiError(error instanceof Error ? error.message : 'Failed to fetch recommendations');
    } finally {
      setAiLoading(false);
    }
  };

  async function handleAssignIndividual(problemId: string, volunteer: VolunteerWithProfile) {
    const volunteerName = volunteer.profile?.full_name || 'Selected Volunteer';
    const volunteerPhone = volunteer.profile?.phone || 'N/A';
    console.log(`=================================`);
    console.log(`Mock INDIVIDUAL Assignment:`);
    console.log(`  Problem ID: ${problemId}`);
    console.log(`  Assigned: ${volunteerName}`);
    console.log(`  Volunteer Phone: ${volunteerPhone}`);
    console.log(`  BACKEND ACTION: Send SMS to ${volunteerPhone}`);
    console.log(`=================================`);
    alert(`Mock: Assigned ${volunteerName}! (Check console for SMS log).`);
    setShowAssignModal(false);
  }

  async function handleAssignTeam(problemId: string, team: AITeam) {
    console.log(`=================================`);
    console.log(`Mock TEAM Assignment:`);
    console.log(`  Problem ID: ${problemId}`);
    console.log(`  Assigned Team: ${team.name}`);
    team.members.forEach(member => {
      const volunteerPhone = member.profile?.phone || 'N/A';
      console.log(`  - Member: ${member.profile?.full_name}`);
      console.log(`    BACKEND ACTION: Send SMS to ${volunteerPhone}`);
    });
    console.log(`=================================`);
    alert(`Mock: Assigned ${team.name}! (Check console for SMS logs).`);
    setShowAssignModal(false);
  }

  async function handleStatusChange(problemId: string, newStatus: string) {
    console.log(`Mock Status Change: Problem ${problemId} to ${newStatus}`);
    alert(`Mock: Status changed to ${newStatus}! (Check console).`);
  }

  if (!profile || profile.role !== 'coordinator') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <p className="text-gray-600 mb-4">You must be logged in as a Coordinator to view this page.</p>
          <button
            onClick={() => onNavigate('home')}
            className="bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  const stats = {
    total: problems.length,
    pending: problems.filter((p) => p.status === 'pending').length,
    inProgress: problems.filter((p) => p.status === 'in_progress').length,
    completed: problems.filter((p) => p.status === 'completed').length,
  };

  const displayedVolunteers = getFilteredAndSortedVolunteers();

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-green-700">{t('dashboard.coordinator_dashboard')}</h1>
          <div className="flex items-center gap-4">
            <button onClick={() => onNavigate('home')} className="text-green-700 font-semibold">{t('common.home')}</button>
            <LanguageToggle />
          </div>
        </div>

        {/* --- Interactive Map --- */}
        <div className="mb-8 h-[400px]">
          <ProblemMap problems={filteredProblems} center={[21.1458, 79.0882]} zoom={12} />
        </div>

        {/* --- RESTORED: Stats Cards --- */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">{t('dashboard.total_problems')}</p>
                <p className="text-3xl font-bold text-gray-800">{stats.total}</p>
              </div>
              <AlertCircle className="text-gray-400" size={32} />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">{t('dashboard.pending')}</p>
                <p className="text-3xl font-bold text-yellow-600">{stats.pending}</p>
              </div>
              <Clock className="text-yellow-400" size={32} />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">{t('dashboard.in_progress')}</p>
                <p className="text-3xl font-bold text-blue-600">{stats.inProgress}</p>
              </div>
              <Users className="text-blue-400" size={32} />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">{t('dashboard.completed')}</p>
                <p className="text-3xl font-bold text-green-600">{stats.completed}</p>
              </div>
              <CheckCircle className="text-green-400" size={32} />
            </div>
          </div>
        </div>
        {/* --- END RESTORED --- */}

        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          {/* --- RESTORED: Search and Filter Bar --- */}
          <div className="flex flex-col md:flex-row gap-4 items-center mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                placeholder={t('dashboard.search_placeholder')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            <div className="flex gap-3">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
              </select>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option value="all">All Categories</option>
                <option value="education">Education</option>
                <option value="health">Health</option>
                <option value="infrastructure">Infrastructure</option>
                <option value="digital">Digital Help</option>
                <option value="others">Others</option>
              </select>
            </div>
          </div>
          {/* --- END RESTORED --- */}

          {loading && problems.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600">Loading problems...</p>
            </div>
          ) : filteredProblems.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-600">No problems found that match your filters.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredProblems.map((problem) => (
                <div
                  key={problem.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex flex-col md:flex-row justify-between gap-4">
                    {/* --- RESTORED: Problem Details --- */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-800">{problem.title}</h3>
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${problem.status === 'pending'
                            ? 'bg-yellow-100 text-yellow-700'
                            : problem.status === 'in_progress'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-green-100 text-green-700'
                            }`}
                        >
                          {problem.status.replace('_', ' ').toUpperCase()}
                        </span>
                        <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-semibold capitalize">
                          {problem.category}
                        </span>
                      </div>
                      <p className="text-gray-600 mb-2">{problem.description}</p>
                      <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                        <span>Village: {problem.village_name}</span>
                        <span>Submitted by: {problem.villager?.full_name}</span>
                        <span>Date: {new Date(problem.created_at).toLocaleDateString()}</span>
                      </div>
                      {problem.matches && problem.matches.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {problem.matches.map((match: any) => (
                            <span
                              key={match.id}
                              className="inline-flex items-center bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm"
                            >
                              Assigned to: {match.volunteer?.profile?.full_name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* --- END RESTORED --- */}

                    <div className="flex flex-col gap-2">
                      {problem.status === 'pending' && (
                        <button
                          onClick={() => {
                            setSelectedProblem(problem);
                            setShowAssignModal(true);
                            setTeamSize(1);
                            setModalTab('manual');
                            setAiTeams([]);
                            setIndividualSearch('');
                          }}
                          className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-green-700 transition whitespace-nowrap"
                        >
                          {t('dashboard.assign_team')}
                        </button>
                      )}
                      {problem.status === 'in_progress' && (
                        <button
                          onClick={() => handleStatusChange(problem.id, 'completed')}
                          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition whitespace-nowrap"
                        >
                          Mark Complete
                        </button>
                      )}
                      {problem.status === 'completed' && (
                        <button
                          onClick={() => handleStatusChange(problem.id, 'in_progress')}
                          className="bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-gray-700 transition whitespace-nowrap"
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
        </div>
      </div>

      {/* --- MODAL (No changes, logic is all here) --- */}
      {showAssignModal && selectedProblem && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-green-700">Assign Team</h2>
              <button onClick={() => setShowAssignModal(false)}>
                <X size={24} className="text-gray-500 hover:text-gray-800" />
              </button>
            </div>
            <p className="text-gray-600 mb-4">Problem: {selectedProblem.title}</p>

            <div className="flex border-b border-gray-200 mb-4">
              <button
                onClick={() => setModalTab('manual')}
                className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium ${modalTab === 'manual'
                  ? 'border-b-2 border-green-600 text-green-600'
                  : 'text-gray-500 hover:text-gray-700'
                  }`}
              >
                <UserCheck size={18} />
                <span>Manual Assignment</span>
              </button>
              <button
                onClick={() => setModalTab('ai')}
                className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium ${modalTab === 'ai'
                  ? 'border-b-2 border-green-600 text-green-600'
                  : 'text-gray-500 hover:text-gray-700'
                  }`}
              >
                <Cpu size={18} />
                <span>AI Team Recommender</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2">
              {modalTab === 'manual' && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-3">Available Individuals</h3>
                  <div className="flex flex-col sm:flex-row gap-2 mb-4">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                      <input
                        type="text"
                        placeholder="Search by name or skill..."
                        value={individualSearch}
                        onChange={(e) => setIndividualSearch(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                      />
                    </div>
                    <select
                      value={individualSort}
                      onChange={(e) => setIndividualSort(e.target.value as 'name' | 'skills')}
                      className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    >
                      <option value="name">Sort by Name (A-Z)</option>
                      <option value="skills">Sort by Most Skills</option>
                    </select>
                  </div>

                  {displayedVolunteers.length === 0 ? (
                    <p className="text-gray-600 text-center py-8">No available volunteers found.</p>
                  ) : (
                    <div className="space-y-3">
                      {displayedVolunteers.map((volunteer) => (
                        <div key={volunteer.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition">
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <h3 className="font-semibold text-gray-800">{volunteer.profile?.full_name}</h3>
                              <p className="text-sm text-gray-600 mb-2">{volunteer.profile?.email} | {volunteer.availability_status}</p>
                              <div className="flex flex-wrap gap-2">
                                {volunteer.skills.map((skill) => (
                                  <span key={skill} className="inline-block bg-green-100 text-green-700 px-2 py-1 rounded text-xs">
                                    {skill}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <button
                              onClick={() => handleAssignIndividual(selectedProblem.id, volunteer)}
                              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-green-700 transition"
                            >
                              Assign
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {modalTab === 'ai' && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-3">Find Best Teams</h3>
                  <div className="flex flex-col sm:flex-row gap-4 p-4 bg-gray-50 rounded-lg mb-4">
                    <div className="flex-1">
                      <label htmlFor="teamSize" className="block text-sm font-medium text-gray-700 mb-2">
                        Volunteers per team
                      </label>
                      <input
                        type="number"
                        id="teamSize"
                        value={teamSize}
                        onChange={(e) => setTeamSize(Math.max(1, parseInt(e.target.value) || 1))}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                        min="1"
                      />
                    </div>
                    <div className="flex-1">
                      <label htmlFor="numTeams" className="block text-sm font-medium text-gray-700 mb-2">
                        Top teams to show
                      </label>
                      <input
                        type="number"
                        id="numTeams"
                        value={numTeamsToShow}
                        onChange={(e) => setNumTeamsToShow(Math.max(1, parseInt(e.target.value) || 1))}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                        min="1"
                      />
                    </div>
                    <div className="flex-shrink-0 sm:self-end">
                      <button
                        onClick={runAiAlgo}
                        disabled={loading}
                        className="w-full bg-blue-600 text-white px-5 py-2 rounded-lg font-semibold hover:bg-blue-700 transition"
                      >
                        {aiLoading ? 'Finding...' : 'Find Teams'}
                      </button>
                    </div>
                  </div>

                  {aiError && (
                    <p className="text-sm text-red-600 mb-3">{aiError}</p>
                  )}
                  {aiSummary && (
                    <div className="bg-blue-100 text-blue-800 px-3 py-2 rounded mb-3 text-sm">
                      <p><strong>Severity:</strong> {aiSummary.severity} ({aiSummary.origin})</p>
                      {aiSummary.location && (<p><strong>Location:</strong> {aiSummary.location}</p>)}
                    </div>
                  )}

                  {aiLoading && aiTeams.length === 0 ? (
                    <p className="text-gray-600 text-center py-8">Running AI algorithm...</p>
                  ) : aiTeams.length === 0 ? (
                    <p className="text-gray-600 text-center py-8">Click "Find Teams" to see AI recommendations.</p>
                  ) : (
                    <div className="space-y-3">
                      {aiTeams.map((team) => (
                        <div key={team.id} className="border border-blue-200 rounded-lg p-4 bg-blue-50">
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <h3 className="font-semibold text-blue-800">{team.name} (Mock Score: {team.mockScore}%)</h3>
                              <p className="text-sm text-blue-700 mb-2">
                                Members: {team.members.map(m => m.profile?.full_name).join(', ')}
                              </p>
                              <div className="flex flex-wrap gap-2">
                                <span className="text-xs font-semibold text-gray-700">Combined Skills:</span>
                                {team.combinedSkills.map((skill) => (
                                  <span key={skill} className="inline-block bg-green-100 text-green-700 px-2 py-1 rounded text-xs">
                                    {skill}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <button
                              onClick={() => handleAssignTeam(selectedProblem.id, team)}
                              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition"
                            >
                              Assign Team
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



