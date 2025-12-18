import { Users, Heart, Briefcase } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface HomeProps {
  onNavigate: (page: string) => void;
}

export default function Home({ onNavigate }: HomeProps) {
  const { profile } = useAuth();

  // Show this view if a user (Volunteer or Coordinator) is logged in
  if (profile) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-50 to-white">
        <div className="max-w-4xl mx-auto px-4 py-16">
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold text-green-800 mb-4">
              Welcome to Gram-Connect
            </h1>
            <p className="text-xl text-gray-700">
              Connecting villages with solutions
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <h2 className="text-2xl font-semibold text-green-700 mb-4">
              Hello, {profile.full_name}!
            </h2>
            <p className="text-gray-600 mb-6">
              You are logged in as a <span className="font-semibold capitalize">{profile.role}</span>
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {profile.role === 'volunteer' && (
                <button
                  onClick={() => onNavigate('profile')}
                  className="bg-green-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-green-700 transition"
                >
                  View My Profile
                </button>
              )}
              {profile.role === 'coordinator' && (
                <>
                  <button
                    onClick={() => onNavigate('dashboard')}
                    className="bg-green-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-green-700 transition"
                  >
                    Open Dashboard
                  </button>
                  <button
                    onClick={() => onNavigate('submit')}
                    className="bg-blue-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-blue-700 transition"
                  >
                    Submit New Problem
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --- NEW LOGGED-OUT VIEW ---
  // Show this view if no user is logged in
  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-white">
      <div className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-6xl font-bold text-green-800 mb-4">
            Welcome to Gram-Connect
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            A platform that bridges the gap between rural needs and volunteer expertise
          </p>
        </div>

        {/* --- NEW LOGIN CARDS --- */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Volunteer Login Card */}
          <div
            onClick={() => onNavigate('volunteer-login')}
            className="bg-white rounded-xl shadow-lg p-8 text-center cursor-pointer transform hover:scale-105 transition"
          >
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Heart className="text-green-600" size={40} />
            </div>
            <h2 className="text-2xl font-bold text-green-700 mb-3">Volunteer (Student)</h2>
            <p className="text-gray-600 mb-6">
              Use your skills to make a difference.
            </p>
            <button className="bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition w-full">
              Login Here
            </button>
          </div>

          {/* Coordinator Login Card */}
          <div
            onClick={() => onNavigate('coordinator-login')}
            className="bg-white rounded-xl shadow-lg p-8 text-center cursor-pointer transform hover:scale-105 transition"
          >
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Briefcase className="text-green-600" size={40} />
            </div>
            <h2 className="text-2xl font-bold text-green-700 mb-3">Coordinator</h2>
            <p className="text-gray-600 mb-6">
              Manage problems and assign teams.
            </p>
            <button className="bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition w-full">
              Login Here
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}