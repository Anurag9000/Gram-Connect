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
    coverage: number;
    k_robustness: number;
    redundancy: number;
    set_size: number;
    willingness_avg: number;
    willingness_min: number;
    members: TeamMember[];
}

export interface RecommendationResponse {
    severity_detected: string;
    severity_source: string;
    proposal_location: string | null;
    teams: RecommendedTeam[];
}

export interface ProblemSubmission {
    title: string;
    description: string;
    category: string;
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
    role?: 'villager' | 'volunteer' | 'coordinator';
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

    async submitProblem(problem: ProblemSubmission): Promise<{ status: string; id: string }> {
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

    async getStateVersion(): Promise<number> {
        const response = await fetch(`${API_BASE_URL}/state-version`, {
            cache: 'no-store',
        });
        if (!response.ok) {
            throw new Error('Failed to fetch state version');
        }
        const data = await response.json();
        return Number(data.version || 0);
    }
};
