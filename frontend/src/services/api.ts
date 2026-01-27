import { API_BASE_URL } from '../config';

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
    W: number;
    availability: string;
    home_location: string;
    dist_km: number;
    score: number;
    rank: number;
}

export interface RecommendationResponse {
    severity_detected: string;
    severity_source: string;
    proposal_location: string | null;
    teams: {
        team_members: TeamMember[];
        goodness: number;
        team_size: number;
        metrics: Record<string, number>;
    }[];
}

export interface ProblemSubmission {
    title: string;
    description: string;
    category: string;
    village_name: string;
    village_address?: string;
    coordinator_id: string;
    visual_tags?: string[];
    has_audio?: boolean;
}

export const api = {
    async transcribe(blob: Blob): Promise<string> {
        const formData = new FormData();
        formData.append('file', blob, 'recording.wav');

        const response = await fetch(`${API_BASE_URL}/transcribe`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Transcription failed');
        }

        const data = await response.json();
        return data.text;
    },

    async analyzeImage(file: File, labels?: string[]): Promise<any> {
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

        return await response.json();
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

    async getProblems(): Promise<any[]> {
        const response = await fetch(`${API_BASE_URL}/problems`);
        if (!response.ok) {
            throw new Error('Failed to fetch problems');
        }
        return await response.json();
    },

    async getVolunteers(): Promise<any[]> {
        const response = await fetch(`${API_BASE_URL}/volunteers`);
        if (!response.ok) {
            throw new Error('Failed to fetch volunteers');
        }
        return await response.json();
    },

    async getVolunteerTasks(volunteerId: string): Promise<any[]> {
        const response = await fetch(`${API_BASE_URL}/volunteer-tasks?volunteer_id=${volunteerId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch volunteer tasks');
        }
        return await response.json();
    },

    async getVolunteer(volunteerId: string): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/volunteer/${volunteerId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch volunteer profile');
        }
        return await response.json();
    },

    async updateVolunteer(volunteer: any): Promise<any> {
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

        return await response.json();
    }
};
