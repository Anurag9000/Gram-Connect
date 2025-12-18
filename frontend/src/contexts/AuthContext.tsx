import { createContext, useContext, useState, ReactNode } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import type { Database } from '../lib/database.types';

type Profile = Database['public']['Tables']['profiles']['Row'];

// --- DUMMY DATA ---
// We create mock users and profiles here to return when signIn is successful

const MOCK_VOLUNTEER_USER: User = {
  id: 'mock-volunteer-uuid',
  app_metadata: {},
  user_metadata: {},
  aud: 'authenticated',
  created_at: new Date().toISOString(),
};
const MOCK_VOLUNTEER_PROFILE: Profile = {
  id: 'mock-volunteer-uuid',
  email: 'volunteer@test.com',
  full_name: 'Test Volunteer',
  phone: '1234567890',
  role: 'volunteer',
  created_at: new Date().toISOString(),
};

const MOCK_COORDINATOR_USER: User = {
  id: 'mock-coordinator-uuid',
  app_metadata: {},
  user_metadata: {},
  aud: 'authenticated',
  created_at: new Date().toISOString(),
};
const MOCK_COORDINATOR_PROFILE: Profile = {
  id: 'mock-coordinator-uuid',
  email: 'coordinator@test.com',
  full_name: 'Test Coordinator',
  phone: '0987654321',
  role: 'coordinator',
  created_at: new Date().toISOString(),
};
// --- END DUMMY DATA ---

interface AuthContextType {
  user: User | null;
  profile: Profile | null;
  session: Session | null;
  loading: boolean;
  signUp: (
    email: string,
    password: string,
    fullName: string,
    phone: string,
    role: 'villager' | 'volunteer' | 'coordinator'
  ) => Promise<{ error: Error | null }>;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false); // Default to false, no auto-login

  // This app no longer auto-logs in.
  // The default state (user: null) is the "Villager" state.

  async function signUp(
    email: string,
    password: string,
    fullName: string,
    phone: string,
    role: 'villager' | 'volunteer' | 'coordinator'
  ) {
    // This is mocked, it will just log to console and return
    console.log('Mock SignUp Attempt:', { email, password, fullName, phone, role });
    return { error: new Error('Sign up is disabled in mock mode') };
  }

  async function signIn(email: string, password: string) {
    setLoading(true);
    try {
      // --- DUMMY LOGIN LOGIC ---
      if (email === 'volunteer@test.com' && password === 'password') {
        setUser(MOCK_VOLUNTEER_USER);
        setProfile(MOCK_VOLUNTEER_PROFILE);
        setSession({} as Session); // Mock session
        return { error: null };
      }

      if (email === 'coordinator@test.com' && password === 'password') {
        setUser(MOCK_COORDINATOR_USER);
        setProfile(MOCK_COORDINATOR_PROFILE);
        setSession({} as Session); // Mock session
        return { error: null };
      }
      // --- END DUMMY LOGIN LOGIC ---

      throw new Error('Invalid email or password');
    } catch (error) {
      return { error: error as Error };
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    // Resets the state to the default "Villager" (logged out) state
    setUser(null);
    setProfile(null);
    setSession(null);
  }

  const value = {
    user,
    profile,
    session,
    loading,
    signUp,
    signIn,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}