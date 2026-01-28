import { useState, useEffect } from 'react';
import { CheckCircle, X, Plus } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import type { Database } from '../lib/database.types';
import { useNavigate } from 'react-router-dom';

type Volunteer = Database['public']['Tables']['volunteers']['Row'];

const commonSkills = [
  'Computer Repair',
  'Teaching',
  'Plumbing',
  'Electrical Work',
  'Construction',
  'Digital Literacy',
  'Agriculture',
  'Healthcare',
  'Tutoring',
  'Web Development',
  'Marketing',
  'Accounting',
];

import { api } from '../services/api';

export default function VolunteerProfile() {
  const { profile } = useAuth();
  const navigate = useNavigate();
  const [volunteer, setVolunteer] = useState<Volunteer | null>(null);
  const [skills, setSkills] = useState<string[]>([]);
  const [customSkill, setCustomSkill] = useState('');
  const [availabilityStatus, setAvailabilityStatus] = useState<'available' | 'busy' | 'inactive'>('available');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (profile) {
      loadVolunteerData();
    }
  }, [profile]);

  async function loadVolunteerData() {
    if (!profile) return;
    setLoading(true);
    try {
      const data = await api.getVolunteer(profile.id);
      if (data) {
        setVolunteer(data);
        setSkills(data.skills || []);
        setAvailabilityStatus(data.availability_status);
      } else {
        setIsEditing(true);
      }
    } catch (err) {
      console.error("Failed to load volunteer data:", err);
      setIsEditing(true);
    } finally {
      setLoading(false);
    }
  }

  const toggleSkill = (skill: string) => {
    if (skills.includes(skill)) {
      setSkills(skills.filter((s) => s !== skill));
    } else {
      setSkills([...skills, skill]);
    }
  };

  const addCustomSkill = () => {
    if (customSkill.trim() && !skills.includes(customSkill.trim())) {
      setSkills([...skills, customSkill.trim()]);
      setCustomSkill('');
    }
  };

  const removeSkill = (skill: string) => {
    setSkills(skills.filter((s) => s !== skill));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (!profile) {
        throw new Error('You must be logged in');
      }
      if (skills.length === 0) {
        throw new Error('Please select at least one skill');
      }

      const volunteerData = {
        id: volunteer?.id,
        user_id: profile.id,
        skills,
        availability_status: availabilityStatus,
      };

      const response = await api.updateVolunteer(volunteerData);

      setVolunteer(response.data);
      setSuccess(true);
      setIsEditing(false);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setLoading(false);
    }
  };

  if (!profile || profile.role !== 'volunteer') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <p className="text-gray-600 mb-4">You must be logged in as a Volunteer to view this page.</p>
          <button
            onClick={() => navigate('/')}
            className="bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-8">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h1 className="text-3xl font-bold text-green-700 mb-2">Volunteer Profile</h1>
              <p className="text-gray-600">{profile.full_name}</p>
            </div>
            {volunteer && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="bg-green-600 text-white px-4 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
              >
                Edit Profile
              </button>
            )}
          </div>

          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-6 flex items-center">
              <CheckCircle size={20} className="mr-2" />
              Profile saved successfully!
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          {!volunteer || isEditing ? (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Availability Status
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: 'available', label: 'Available', color: 'green' },
                    { value: 'busy', label: 'Busy', color: 'yellow' },
                    { value: 'inactive', label: 'Inactive', color: 'gray' },
                  ].map((status) => (
                    <button
                      key={status.value}
                      type="button"
                      onClick={() => setAvailabilityStatus(status.value as typeof availabilityStatus)}
                      className={`p-3 rounded-lg border-2 transition ${availabilityStatus === status.value
                        ? `border-${status.color}-600 bg-${status.color}-50`
                        : 'border-gray-200 hover:border-green-300'
                        }`}
                    >
                      <p className="text-sm font-medium text-gray-700">{status.label}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Select Your Skills
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                  {commonSkills.map((skill) => (
                    <button
                      key={skill}
                      type="button"
                      onClick={() => toggleSkill(skill)}
                      className={`p-3 rounded-lg border-2 transition text-sm ${skills.includes(skill)
                        ? 'border-green-600 bg-green-50 text-green-700'
                        : 'border-gray-200 hover:border-green-300 text-gray-700'
                        }`}
                    >
                      {skill}
                    </button>
                  ))}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customSkill}
                    onChange={(e) => setCustomSkill(e.target.value)}
                    placeholder="Add custom skill..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addCustomSkill();
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={addCustomSkill}
                    className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition"
                  >
                    <Plus size={20} />
                  </button>
                </div>
              </div>

              {skills.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Your Selected Skills
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm"
                      >
                        {skill}
                        <button
                          type="button"
                          onClick={() => removeSkill(skill)}
                          className="ml-2 hover:text-green-900"
                        >
                          <X size={16} />
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={loading || skills.length === 0}
                  className="flex-1 bg-green-600 text-white py-3 rounded-lg font-semibold text-lg hover:bg-green-700 transition disabled:bg-gray-400"
                >
                  {loading ? 'Saving...' : volunteer ? 'Update Profile' : 'Create Profile'}
                </button>
                {volunteer && (
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="px-6 border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Availability Status</h3>
                <span
                  className={`inline-block px-4 py-2 rounded-full text-sm font-semibold ${volunteer.availability_status === 'available'
                    ? 'bg-green-100 text-green-700'
                    : volunteer.availability_status === 'busy'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-gray-100 text-gray-700'
                    }`}
                >
                  {volunteer.availability_status.charAt(0).toUpperCase() + volunteer.availability_status.slice(1)}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Your Skills</h3>
                <div className="flex flex-wrap gap-2">
                  {volunteer.skills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-block bg-green-100 text-green-700 px-4 py-2 rounded-full text-sm font-medium"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}