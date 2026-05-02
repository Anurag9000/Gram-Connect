import { API_BASE_URL } from '../config';
import type { Database } from '../lib/database.types';
import { signalLiveRefresh } from '../lib/liveRefresh';

type Profile = Database['public']['Tables']['profiles']['Row'];
type Volunteer = Database['public']['Tables']['volunteers']['Row'];
type Match = Database['public']['Tables']['matches']['Row'];
type Problem = Database['public']['Tables']['problems']['Row'];

export interface MediaRecord {
    id: string;
    kind: string;
    problem_id?: string | null;
    volunteer_id?: string | null;
    label?: string | null;
    filename?: string | null;
    stored_filename?: string | null;
    mime_type?: string | null;
    size_bytes?: number | null;
    sha256?: string | null;
    path?: string | null;
    url?: string | null;
    created_at: string;
}

export interface ProofRecord {
    volunteer_id: string;
    before_media_id?: string | null;
    after_media_id?: string | null;
    media_ids?: string[];
    notes?: string | null;
    submitted_at?: string | null;
    verification?: {
        accepted: boolean;
        confidence: number;
        summary: string;
        detected_change?: string | null;
        source?: string | null;
    };
}

export interface RecommendationRequest {
    proposal_text: string;
    village_name?: string;
    task_start: string;
    task_end: string;
    team_size?: number;
    num_teams?: number;
    severity?: 'LOW' | 'NORMAL' | 'HIGH';
    required_skills?: string[];
    auto_extract?: boolean;
    threshold?: number;
    weekly_quota?: number;
    overwork_penalty?: number;
    lambda_red?: number;
    lambda_size?: number;
    lambda_will?: number;
    size_buckets?: string;
    model_path?: string;
    people_csv?: string;
    schedule_csv?: string;
    village_locations?: string;
    distance_csv?: string;
    distance_scale?: number;
    distance_decay?: number;
    tau?: number;
    transcription?: string;
    visual_tags?: string[];
}

export interface TeamMember {
    person_id: string;
    name: string;
    skills: string[];
    W?: number;
    availability: string;
    home_location: string;
    distance_km?: number;
    dist_km?: number;
    score?: number;
    rank?: number;
    id?: string;
    profile?: {
        full_name?: string | null;
        phone?: string | null;
    };
}

export interface RecommendedTeam {
    rank?: number;
    team_ids: string;
    team_names: string;
    team_size: number;
    goodness: number;
    team_score: number;
    coverage: number;
    k_robustness: number;
    redundancy: number;
    set_size: number;
    willingness_avg: number;
    willingness_min: number;
    avg_distance_km?: number;
    members: TeamMember[];
}

export interface RecommendationResponse {
    severity_detected: string;
    severity_source: string;
    proposal_location: string | null;
    teams: RecommendedTeam[];
}

export interface InsightClusterExample {
    id?: string;
    title?: string;
    village_name?: string;
    status?: string;
    category?: string;
    created_at?: string;
}

export interface InsightCluster {
    cluster_id: string;
    risk_type?: string | null;
    risk_score: number;
    summary: string;
    risk_summary?: string;
    topic?: string;
    problem_count: number;
    villages: string[];
    status_counts?: Record<string, number>;
    top_topics?: [string, number][];
    time_range?: {
        earliest?: string | null;
        latest?: string | null;
    };
    geo_span_km?: number;
    examples?: InsightClusterExample[];
}

export interface InsightOverview {
    generated_at: string;
    window_days: number;
    stats: {
        problem_count: number;
        open_problem_count: number;
        completed_problem_count: number;
        volunteer_count: number;
        water_problem_count: number;
        health_problem_count: number;
        infrastructure_problem_count: number;
    };
    alerts: InsightCluster[];
    clusters: InsightCluster[];
}

export interface DuplicateCandidate {
    problem_id: string;
    title?: string;
    village_name?: string;
    category?: string;
    status?: string;
    created_at?: string;
    distance_km?: number | null;
    score: number;
    semantic_score: number;
    reason: string;
    suggested_action: string;
}

export interface InsightChatRequest {
    query: string;
    days_back?: number;
    limit?: number;
}

export interface InsightChatResponse {
    query: string;
    intent: string;
    reason: string;
    answer: string;
    parameters: Record<string, unknown>;
    overview: InsightOverview;
    payload: Record<string, unknown>;
    suggested_questions: string[];
}

export interface WeeklyBriefing {
    generated_at: string;
    window_days: number;
    summary: string;
    highlights: string[];
    stats: InsightOverview['stats'];
    risk_alerts: InsightCluster[];
    open_cases: Array<{
        problem_id: string;
        title?: string;
        village_name?: string;
        category?: string;
        status?: string;
        severity?: string;
        created_at?: string;
        age_days: number;
        topic?: string;
    }>;
    volunteer_load: Array<{
        volunteer_id: string;
        name: string;
        home_location?: string;
        assignment_count: number;
        skills: string[];
    }>;
    root_cause_graph: {
        generated_at: string;
        window_days: number;
        nodes: Array<{
            id: string;
            label: string;
            kind: string;
            weight: number;
        }>;
        edges: Array<{
            source: string;
            target: string;
            weight: number;
        }>;
        summary: string;
        top_topics: [string, number][];
        top_villages: [string, number][];
        top_assets: [string, number][];
        top_months: [string, number][];
    };
    duplicate_patterns: [string, number][];
}

export interface ProblemTimelineItem {
    type: string;
    timestamp?: string;
    title: string;
    summary: string;
    details?: string;
    source?: string;
    data?: Record<string, unknown>;
}

export interface ProblemTimelineResponse {
    problem_id: string;
    problem: ProblemRecord;
    timeline: ProblemTimelineItem[];
    summary: {
        event_count: number;
        media_count: number;
        assignment_count: number;
        duplicate_count: number;
        completed: boolean;
    };
}

export interface ProblemSubmission {
    title: string;
    description: string;
    category: string;
    severity?: 'LOW' | 'NORMAL' | 'HIGH';
    village_name: string;
    village_address?: string;
    coordinator_id?: string;
    villager_id?: string;
    reporter_name?: string;
    reporter_phone?: string;
    visual_tags?: string[];
    has_audio?: boolean;
    transcript?: string;
    transcript_language?: string;
    media_ids?: string[];
}

export interface ProfileSubmission {
    id?: string;
    email?: string;
    full_name: string;
    phone?: string;
    role?: 'villager' | 'volunteer' | 'coordinator' | 'supervisor' | 'partner';
    village_name?: string;
}

export interface VolunteerRecord extends Volunteer {
    profile?: Profile;
    profiles?: Profile;
}

export interface MatchRecord extends Match {
    volunteer?: VolunteerRecord;
    volunteers?: VolunteerRecord;
}

export interface ProblemRecord extends Problem {
    profiles?: Profile;
    matches?: MatchRecord[];
    visual_tags?: string[];
    village_address?: string;
    media_ids?: string[];
    media_assets?: MediaRecord[];
    proof?: ProofRecord;
    transcript?: string | null;
}

export interface VolunteerTask {
    id: string;
    title: string;
    village: string;
    location: string;
    status: string;
    description: string;
    category: string;
    severity: 'LOW' | 'NORMAL' | 'HIGH';
    severity_source: string;
    assigned_at: string;
    media_assets?: MediaRecord[];
    proof?: ProofRecord;
    proof_assets?: MediaRecord[];
}

export interface UpdateVolunteerRequest {
    id?: string;
    user_id: string;
    skills: string[];
    availability_status: string;
}

export interface UpdateVolunteerResponse {
    status: string;
    data: VolunteerRecord;
}

export interface AssignTaskResponse {
    status: string;
    match: MatchRecord;
}

export interface ProblemStatusResponse {
    status: string;
    problem: ProblemRecord;
}

export interface ImageAnalysisResponse {
    top_label: string;
    confidence: number;
    all_probs?: Record<string, number | string>;
    tags?: string[];
}

export interface TranscriptionResponse {
    text: string;
    language?: string | null;
    language_code?: string | null;
    language_name?: string | null;
    source?: string | null;
}

export interface JugaadRepairRequest {
    problem_id: string;
    broken_media_id: string;
    materials_media_id: string;
    volunteer_id?: string;
    notes?: string;
}

export interface JugaadRepairResponse {
    problem_id: string;
    summary: string;
    problem_read: string;
    observed_broken_part: string;
    observed_materials: string;
    temporary_fix: string;
    step_by_step: string[];
    safety_notes: string[];
    materials_to_use: string[];
    materials_to_avoid: string[];
    when_to_stop: string[];
    needs_official_part: boolean;
    confidence: number;
    source: string;
    broken_analysis?: ImageAnalysisResponse | null;
    materials_analysis?: ImageAnalysisResponse | null;
}

export interface ProblemGuidanceRequest {
    title: string;
    description: string;
    category?: string;
    village_name?: string;
    transcript?: string;
    severity?: 'LOW' | 'NORMAL' | 'HIGH';
    visual_tags?: string[];
}

export interface ProblemGuidanceResponse {
    topic: string;
    department: string;
    urgency: string;
    response_path: string;
    summary: string;
    what_you_can_do_now: string[];
    materials_to_find: string[];
    safety_notes: string[];
    when_to_stop: string[];
    best_duration: string;
    confidence: number;
    source: string;
    visual_tags: string[];
    duplicate_candidates: DuplicateCandidate[];
    similar_problem_count: number;
    root_cause_hint?: string | null;
}

export interface ProblemSubmissionResponse {
    status: string;
    id: string;
    duplicate_of?: string | null;
    duplicate_report?: Record<string, unknown> | null;
    duplicate_candidates?: DuplicateCandidate[];
}

export interface PublicStatusBoardItem {
    id: string;
    title: string;
    category?: string | null;
    village_name?: string | null;
    village_address?: string | null;
    status: string;
    severity?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
    assigned_count: number;
    duplicate_count: number;
    media_count: number;
}

export interface PublicStatusBoardResponse {
    generated_at: string;
    window_days: number;
    village_name?: string | null;
    status_filter?: string | null;
    open_count: number;
    in_progress_count: number;
    completed_count: number;
    total_count: number;
    items: PublicStatusBoardItem[];
}

export interface PlaybookRecord {
    id: string;
    topic: string;
    village_name?: string | null;
    title: string;
    summary: string;
    materials: string[];
    safety_notes: string[];
    steps: string[];
    source_problem_id?: string | null;
    source_problem_title?: string | null;
    created_at: string;
}

export interface InventoryRecord {
    id: string;
    owner_type: string;
    owner_id: string;
    item_name: string;
    quantity: number;
    notes?: string | null;
    updated_at: string;
}

export interface EscalationRecord {
    problem_id: string;
    title?: string;
    village_name?: string;
    severity?: string;
    status?: string;
    age_hours: number;
    escalation_level: string;
    next_action: string;
}

export interface ReputationRecord {
    volunteer_id: string;
    name: string;
    home_location: string;
    skills: string[];
    completed_count: number;
    open_assignments: number;
    duplicate_reports_seen: number;
    avg_resolution_hours?: number | null;
    reliability_score: number;
}

export interface RouteOptimizationRecord {
    route_id: string;
    village_name: string;
    problem_ids: string[];
    titles: string[];
    problem_count: number;
    severity_counts: Record<string, number>;
    recommended_volunteers: Array<{
        volunteer_id: string;
        name?: string | null;
        skills: string[];
    }>;
    route_hint: string;
}

export interface SeasonalRiskRecord {
    risk_id: string;
    topic: string;
    season: string;
    peak_month: string;
    current_month_count: number;
    peak_month_count: number;
    supporting_village: string;
    supporting_village_count: number;
    confidence: number;
    summary: string;
    recommended_action: string;
}

export interface SeasonalRiskForecast {
    generated_at: string;
    window_days: number;
    summary: string;
    risks: SeasonalRiskRecord[];
    top_topics: Array<[string, number]>;
    top_months: Array<[string, number]>;
}

export interface MaintenancePlanRecord {
    plan_id: string;
    village_name: string;
    asset_type: string;
    inspection_frequency_days: number;
    next_due_in_days: number;
    priority: 'high' | 'normal';
    related_problem_count: number;
    open_problem_count: number;
    recommended_action: string;
    examples: Array<{
        problem_id?: string;
        title?: string;
        status?: string;
    }>;
    assigned_volunteers: Array<{
        volunteer_id: string;
        name: string;
        skills: string[];
    }>;
}

export interface MaintenancePlanResponse {
    generated_at: string;
    window_days: number;
    summary: string;
    items: MaintenancePlanRecord[];
    top_assets: Array<[string, number]>;
}

export interface HeatmapCell {
    cell_id: string;
    village_name: string;
    lat: number;
    lng: number;
    weight: number;
    problem_count: number;
    open_count: number;
    top_topic: string;
    severity_counts: Record<string, number>;
}

export interface HeatmapResponse {
    generated_at: string;
    window_days: number;
    summary: string;
    cells: HeatmapCell[];
}

export interface CampaignModeRecord {
    campaign_id: string;
    topic: string;
    title: string;
    goal: string;
    target_villages: string[];
    problem_count: number;
    recommended_volunteers: Array<{
        volunteer_id: string;
        name: string;
        skills: string[];
        home_location: string;
    }>;
    talking_points: string[];
    field_tasks: string[];
}

export interface CampaignModeResponse {
    generated_at: string;
    window_days: number;
    summary: string;
    campaigns: CampaignModeRecord[];
    top_topics: Array<[string, number]>;
}

export interface EvidenceComparisonResponse {
    generated_at: string;
    problem_id: string;
    title: string;
    status: string;
    before_media_id?: string | null;
    after_media_id?: string | null;
    before_url?: string | null;
    after_url?: string | null;
    accepted: boolean;
    confidence: number;
    summary: string;
    detected_change: string;
    source: string;
}

export const api = {
    async transcribe(blob: Blob): Promise<TranscriptionResponse> {
        const formData = new FormData();
        formData.append('file', blob, 'recording.wav');

        const response = await fetch(`${API_BASE_URL}/transcribe`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Transcription failed');
        }

        return await response.json();
    },

    async analyzeImage(file: File, labels?: string[]): Promise<ImageAnalysisResponse> {
        const formData = new FormData();
        formData.append('file', file);
        if (labels) {
            formData.append('labels', labels.join(','));
        }

        const response = await fetch(`${API_BASE_URL}/analyze-image`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Image analysis failed');
        }

        return await response.json();
    },

    async requestJugaadRepair(request: JugaadRepairRequest): Promise<JugaadRepairResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/jugaad/assist`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Failed to generate Jugaad guidance');
        }

        return await response.json();
    },

    async requestProblemGuidance(request: ProblemGuidanceRequest): Promise<ProblemGuidanceResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/problems/instant-guidance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Failed to fetch instant guidance');
        }

        return await response.json();
    },

    async submitProblem(problem: ProblemSubmission): Promise<ProblemSubmissionResponse> {
        const response = await fetch(`${API_BASE_URL}/submit-problem`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(problem),
        });

        if (!response.ok) {
            throw new Error('Problem submission failed');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async getProblemTimeline(problemId: string): Promise<ProblemTimelineResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/problems/${problemId}/timeline`, {
            cache: 'no-store',
        });

        if (!response.ok) {
            throw new Error('Failed to fetch problem timeline');
        }

        return await response.json();
    },

    async getWeeklyBriefing(daysBack = 7): Promise<WeeklyBriefing> {
        const response = await fetch(`${API_BASE_URL}/api/v1/insights/briefing?days_back=${daysBack}`, {
            cache: 'no-store',
        });

        if (!response.ok) {
            throw new Error('Failed to fetch weekly briefing');
        }

        return await response.json();
    },

    async getPublicStatusBoard(params: { village_name?: string; status?: string; days_back?: number } = {}): Promise<PublicStatusBoardResponse> {
        const query = new URLSearchParams();
        if (params.village_name) {
            query.set('village_name', params.village_name);
        }
        if (params.status) {
            query.set('status', params.status);
        }
        query.set('days_back', String(params.days_back ?? 60));
        const response = await fetch(`${API_BASE_URL}/api/v1/public/status-board?${query.toString()}`, {
            cache: 'no-store',
        });

        if (!response.ok) {
            throw new Error('Failed to fetch public status board');
        }

        return await response.json();
    },

    async getPlaybooks(params: { topic?: string; village_name?: string; limit?: number } = {}): Promise<PlaybookRecord[]> {
        const query = new URLSearchParams();
        if (params.topic) query.set('topic', params.topic);
        if (params.village_name) query.set('village_name', params.village_name);
        query.set('limit', String(params.limit ?? 25));
        const response = await fetch(`${API_BASE_URL}/api/v1/playbooks?${query.toString()}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch playbooks');
        }
        return await response.json();
    },

    async getInventory(params: { owner_type?: string; owner_id?: string } = {}): Promise<InventoryRecord[]> {
        const query = new URLSearchParams();
        if (params.owner_type) query.set('owner_type', params.owner_type);
        if (params.owner_id) query.set('owner_id', params.owner_id);
        const response = await fetch(`${API_BASE_URL}/api/v1/inventory${query.toString() ? `?${query.toString()}` : ''}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch inventory');
        }
        return await response.json();
    },

    async upsertInventory(item: { owner_type: string; owner_id: string; item_name: string; quantity: number; notes?: string }): Promise<InventoryRecord> {
        const response = await fetch(`${API_BASE_URL}/api/v1/inventory`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(item),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Failed to update inventory');
        }
        return await response.json();
    },

    async getEscalations(daysBack = 7): Promise<{ generated_at: string; window_days: number; overdue_count: number; items: EscalationRecord[] }> {
        const response = await fetch(`${API_BASE_URL}/api/v1/escalations?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch escalations');
        }
        return await response.json();
    },

    async getReputation(daysBack = 90): Promise<{ generated_at: string; window_days: number; volunteers: ReputationRecord[] }> {
        const response = await fetch(`${API_BASE_URL}/api/v1/reputation?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch reputation');
        }
        return await response.json();
    },

    async getRouteOptimization(daysBack = 14): Promise<{ generated_at: string; window_days: number; routes: RouteOptimizationRecord[] }> {
        const response = await fetch(`${API_BASE_URL}/api/v1/routes/optimizer?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch route optimization');
        }
        return await response.json();
    },

    async getSeasonalRiskForecast(daysBack = 365): Promise<SeasonalRiskForecast> {
        const response = await fetch(`${API_BASE_URL}/api/v1/insights/seasonal-risk?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch seasonal risk forecast');
        }
        return await response.json();
    },

    async getMaintenancePlan(daysBack = 180): Promise<MaintenancePlanResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/maintenance/plan?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch maintenance plan');
        }
        return await response.json();
    },

    async getHotspotHeatmap(daysBack = 90): Promise<HeatmapResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/hotspots/heatmap?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch hotspot heatmap');
        }
        return await response.json();
    },

    async getCampaignMode(daysBack = 30, topic?: string): Promise<CampaignModeResponse> {
        const query = new URLSearchParams();
        query.set('days_back', String(daysBack));
        if (topic) {
            query.set('topic', topic);
        }
        const response = await fetch(`${API_BASE_URL}/api/v1/campaigns/plan?${query.toString()}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch campaign plan');
        }
        return await response.json();
    },

    async getEvidenceComparison(problemId: string): Promise<EvidenceComparisonResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/problems/${problemId}/evidence-comparison`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch evidence comparison');
        }
        return await response.json();
    },

    async upsertProfile(profile: ProfileSubmission): Promise<{ status: string; profile: Profile }> {
        const response = await fetch(`${API_BASE_URL}/profile`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(profile),
        });

        if (!response.ok) {
            throw new Error('Failed to save profile');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async uploadMedia(
        file: Blob | File,
        options: {
            kind: string;
            problemId?: string;
            volunteerId?: string;
            label?: string;
            filename?: string;
        },
    ): Promise<{ status: string; media: MediaRecord }> {
        const formData = new FormData();
        formData.append('file', file, options.filename || (file instanceof File ? file.name : 'upload.bin'));
        formData.append('kind', options.kind);
        if (options.problemId) {
            formData.append('problem_id', options.problemId);
        }
        if (options.volunteerId) {
            formData.append('volunteer_id', options.volunteerId);
        }
        if (options.label) {
            formData.append('label', options.label);
        }

        const response = await fetch(`${API_BASE_URL}/media`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Media upload failed');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async submitProof(problemId: string, payload: {
        volunteer_id: string;
        before_media_id?: string;
        after_media_id?: string;
        notes?: string;
    }): Promise<{ status: string; problem: ProblemRecord; proof: ProofRecord }> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}/proof`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            let detail = 'Failed to submit proof';
            try {
                const errorData = await response.json();
                detail = errorData.detail || detail;
            } catch {
                // Ignore non-JSON error bodies.
            }
            throw new Error(detail);
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async getRecommendations(request: RecommendationRequest): Promise<RecommendationResponse> {
        const response = await fetch(`${API_BASE_URL}/recommend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Recommendation failed');
        }

        return await response.json();
    },

    async askInsights(request: InsightChatRequest): Promise<InsightChatResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/insights/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Insights query failed');
        }

        return await response.json();
    },

    async getInsightOverview(daysBack = 30): Promise<InsightOverview> {
        const response = await fetch(`${API_BASE_URL}/api/v1/insights/overview?days_back=${daysBack}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch insight overview');
        }
        return await response.json();
    },

    async getProblems(): Promise<ProblemRecord[]> {
        const response = await fetch(`${API_BASE_URL}/problems`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch problems');
        }
        return await response.json();
    },

    async getVolunteers(): Promise<VolunteerRecord[]> {
        const response = await fetch(`${API_BASE_URL}/volunteers`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch volunteers');
        }
        return await response.json();
    },

    async getVolunteerTasks(volunteerId: string): Promise<VolunteerTask[]> {
        const response = await fetch(`${API_BASE_URL}/volunteer-tasks?volunteer_id=${volunteerId}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch volunteer tasks');
        }
        return await response.json();
    },

    async getVolunteer(volunteerId: string): Promise<VolunteerRecord> {
        const response = await fetch(`${API_BASE_URL}/volunteer/${volunteerId}`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch volunteer profile');
        }
        return await response.json();
    },

    async updateVolunteer(volunteer: UpdateVolunteerRequest): Promise<UpdateVolunteerResponse> {
        const response = await fetch(`${API_BASE_URL}/volunteer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(volunteer),
        });

        if (!response.ok) {
            throw new Error('Failed to update volunteer profile');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async assignTask(problemId: string, volunteerId: string): Promise<AssignTaskResponse> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}/assign`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ volunteer_id: volunteerId }),
        });

        if (!response.ok) {
            throw new Error('Failed to assign task');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async updateProblemStatus(problemId: string, status: string): Promise<ProblemStatusResponse> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status }),
        });

        if (!response.ok) {
            throw new Error('Failed to update problem status');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async submitFollowUpFeedback(problemId: string, payload: {
        source?: 'public-board' | 'whatsapp' | 'sms' | 'manual' | 'phone';
        response: 'resolved' | 'still_broken' | 'needs_more_help';
        note?: string;
        reporter_name?: string;
        reporter_phone?: string;
    }): Promise<{ status: string; feedback: Record<string, unknown>; problem: ProblemRecord }> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}/follow-up-feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || 'Failed to submit follow-up feedback');
        }

        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async getStateVersion(): Promise<number> {
        const response = await fetch(`${API_BASE_URL}/state-version`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch state version');
        }
        const data = await response.json();
        return Number(data.version || 0);
    },

    async deleteProblem(problemId: string): Promise<{ status: string; deleted_id: string }> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error('Failed to delete problem');
        }
        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async editProblem(problemId: string, payload: Partial<ProblemSubmission>): Promise<ProblemStatusResponse> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            throw new Error('Failed to edit problem');
        }
        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async unassignVolunteer(problemId: string, matchId: string): Promise<ProblemStatusResponse> {
        const response = await fetch(`${API_BASE_URL}/problems/${problemId}/matches/${matchId}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error('Failed to unassign volunteer');
        }
        const data = await response.json();
        signalLiveRefresh();
        return data;
    },

    async getVillages(): Promise<{ name: string; district: string; state: string; lat?: number; lng?: number }[]> {
        const response = await fetch(`${API_BASE_URL}/villages`, { cache: 'no-store' });
        if (!response.ok) return [];
        return await response.json();
    },
};
