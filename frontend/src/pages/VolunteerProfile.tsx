import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, X, Plus } from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import type { Database } from '../lib/database.types';
import { Navigate } from 'react-router-dom';
import { subscribeLiveRefresh } from '../lib/liveRefresh';

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

const availabilityStyles = {
  available: 'border-green-600 bg-green-50',
  busy: 'border-yellow-600 bg-yellow-50',
  inactive: 'border-gray-500 bg-gray-50',
} as const;

export default function VolunteerProfile() {
  const { profile } = useAuth();
  const [volunteer, setVolunteer] = useState<Volunteer | null>(null);
  const [skills, setSkills] = useState<string[]>([]);
  const [customSkill, setCustomSkill] = useState('');
  const [availabilityStatus, setAvailabilityStatus] = useState<'available' | 'busy' | 'inactive'>('available');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [lastPersistedSignature, setLastPersistedSignature] = useState('');

  const buildSignature = useCallback((nextSkills: string[], nextAvailability: 'available' | 'busy' | 'inactive') => (
    JSON.stringify({
      availabilityStatus: nextAvailability,
      skills: [...nextSkills].sort(),
    })
  ), []);

  const loadVolunteerData = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const data = await api.getVolunteer(profile.id);
      if (data) {
        setVolunteer(data);
        setSkills(data.skills || []);
        const nextAvailability = (
          data.availability_status === 'busy' || data.availability_status === 'inactive'
            ? data.availability_status
            : 'available'
        );
        setAvailabilityStatus(nextAvailability);
        setLastPersistedSignature(buildSignature(data.skills || [], nextAvailability));
      } else {
        setIsEditing(true);
      }
    } catch (err) {
      console.error("Failed to load volunteer data:", err);
      setIsEditing(true);
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => {
    if (profile) {
      loadVolunteerData();
    }
  }, [loadVolunteerData, profile]);

  useEffect(() => {
    if (!profile) {
      return;
    }

    const unsubscribe = subscribeLiveRefresh(() => {
      loadVolunteerData();
    });

    return () => {
      unsubscribe();
    };
  }, [loadVolunteerData, profile]);

  const persistVolunteerState = useCallback(async (
    nextSkills: string[],
    nextAvailability: 'available' | 'busy' | 'inactive',
  ) => {
    if (!profile) {
      return;
    }
    if (nextSkills.length === 0) {
      setError('Please select at least one skill');
      return;
    }

    const signature = buildSignature(nextSkills, nextAvailability);
    if (signature === lastPersistedSignature) {
      return;
    }

    setError('');
    setSuccess(false);
    setSaving(true);
    try {
      const response = await api.updateVolunteer({
        id: volunteer?.id,
        user_id: profile.id,
        skills: nextSkills,
        availability_status: nextAvailability,
      });

      setVolunteer(response.data);
      setLastPersistedSignature(signature);
      setSuccess(true);
      setIsEditing(false);
      window.setTimeout(() => setSuccess(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  }, [buildSignature, lastPersistedSignature, profile, volunteer?.id]);

  const toggleSkill = (skill: string) => {
    setSkills((currentSkills) => (
      currentSkills.includes(skill)
        ? currentSkills.filter((existingSkill) => existingSkill !== skill)
        : [...currentSkills, skill]
    ));
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
    setLoading(true);
    await persistVolunteerState(skills, availabilityStatus);
    setLoading(false);
  };

  if (!profile || profile.role !== 'volunteer') {
    return <Navigate to="/volunteer-login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative bg-white rounded-xl shadow-lg p-8 overflow-hidden">
          {saving && (
            <div className="absolute inset-0 z-20 bg-white/85 backdrop-blur-sm flex items-center justify-center">
              <div className="w-full max-w-sm rounded-3xl border border-emerald-100 bg-white/90 px-6 py-7 shadow-2xl">
                <div className="flex items-center justify-center">
                  <div className="relative h-20 w-20">
                    <div className="absolute inset-0 rounded-full border-4 border-emerald-100" />
                    <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-emerald-500 border-r-lime-400 animate-spin" />
                    <div className="absolute inset-3 rounded-full bg-gradient-to-br from-emerald-50 via-white to-lime-50 shadow-inner" />
                    <div className="absolute inset-[22px] rounded-full bg-emerald-500/10 animate-pulse" />
                  </div>
                </div>
                <div className="mt-5 text-center">
                  <p className="text-lg font-bold text-slate-900">Saving and reassigning</p>
                  <p className="mt-2 text-sm text-slate-600">
                    Gram Connect is recomputing your open assignments from the latest profile state.
                  </p>
                </div>
              </div>
            </div>
          )}
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
              Profile saved and assignments recomputed.
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          {!volunteer || isEditing ? (
            <form onSubmit={handleSubmit} className="space-y-6">
              <fieldset disabled={saving} className="space-y-6 disabled:opacity-100">
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
                          ? availabilityStyles[status.value as keyof typeof availabilityStyles]
                          : 'border-gray-200 hover:border-green-300'
                          } disabled:cursor-not-allowed`}
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
                          } disabled:cursor-not-allowed`}
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
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 disabled:bg-gray-50"
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
                      className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition disabled:bg-gray-400"
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
                            className="ml-2 hover:text-green-900 disabled:cursor-not-allowed"
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
                    disabled={loading || saving || skills.length === 0}
                    className="relative flex-1 overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-600 via-green-600 to-lime-500 px-6 py-3 font-semibold text-lg text-white shadow-lg shadow-emerald-200 transition hover:shadow-xl hover:shadow-emerald-200 disabled:cursor-not-allowed disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-500"
                  >
                    <span className={`flex items-center justify-center gap-3 transition ${saving ? 'opacity-0' : 'opacity-100'}`}>
                      <span>{volunteer ? 'Save & Reassign' : 'Create Profile'}</span>
                    </span>
                    {saving && (
                      <span className="absolute inset-0 flex items-center justify-center gap-3">
                        <span className="relative flex h-7 w-7 items-center justify-center">
                          <span className="absolute inset-0 rounded-full border-2 border-white/20" />
                          <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-white border-r-lime-100 animate-spin" />
                          <span className="absolute inset-[7px] rounded-full bg-white/30 animate-pulse" />
                        </span>
                        <span>Save &amp; Reassign</span>
                      </span>
                    )}
                  </button>
                  {volunteer && (
                    <button
                      type="button"
                      onClick={() => setIsEditing(false)}
                      disabled={saving}
                      className="px-6 border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition disabled:bg-gray-100 disabled:text-gray-400"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </fieldset>
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
                  {volunteer.skills.map((skill: string) => (
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
