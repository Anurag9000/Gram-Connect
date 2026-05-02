export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          email: string | null;
          full_name: string;
          phone: string | null;
          role: 'villager' | 'volunteer' | 'coordinator' | 'supervisor' | 'partner';
          village_name?: string | null;
          created_at: string;
          updated_at?: string;
        };
      };
      volunteers: {
        Row: {
          id: string;
          user_id: string;
          skills: string[];
          availability_status: 'available' | 'busy' | 'inactive' | string;
          created_at: string;
          updated_at?: string;
          availability?: string;
          home_location?: string;
        };
      };
      problems: {
        Row: {
          id: string;
          villager_id: string;
          title: string;
          description: string;
          category: 'water-sanitation' | 'infrastructure' | 'health-nutrition' | 'agriculture-environment' | 'education-digital' | 'livelihood-governance' | 'others' | string;
          severity: 'LOW' | 'NORMAL' | 'HIGH';
          severity_source?: string;
          village_name: string;
          village_address?: string | null;
          status: 'pending' | 'in_progress' | 'completed' | string;
          created_at: string;
          updated_at: string;
          lat?: number;
          lng?: number;
          visual_tags?: string[];
          has_audio?: boolean;
          media_ids?: string[];
          transcript?: string | null;
          proof?: {
            volunteer_id: string;
            before_media_id?: string | null;
            after_media_id?: string | null;
            media_ids?: string[];
            notes?: string | null;
            submitted_at?: string | null;
          } | null;
        };
      };
      matches: {
        Row: {
          id: string;
          problem_id: string;
          volunteer_id: string;
          assigned_at: string;
          completed_at: string | null;
          notes: string | null;
          proof_media_ids?: string[] | null;
        };
      };
      media_assets: {
        Row: {
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
        };
      };
    };
  };
}
