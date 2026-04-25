import { useState, type FormEvent } from 'react';
import { ArrowRight, MapPin, UserRound, Phone, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { saveStoredProfile, loadStoredProfile } from '../lib/profileStorage';

export default function VillagerOnboarding() {
  const navigate = useNavigate();
  const storedProfile = loadStoredProfile();
  const [fullName, setFullName] = useState(storedProfile?.full_name ?? '');
  const [phone, setPhone] = useState(storedProfile?.phone ?? '');
  const [email, setEmail] = useState(storedProfile?.email ?? '');
  const [villageName, setVillageName] = useState(storedProfile?.village_name ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    try {
      const response = await api.upsertProfile({
        id: storedProfile?.id,
        full_name: fullName,
        phone,
        email,
        role: 'villager',
        village_name: villageName,
      });

      saveStoredProfile(response.profile);
      navigate('/submit');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save villager profile');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 via-white to-green-50 px-4 py-12">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="mb-6 text-green-700 font-semibold hover:text-green-800"
        >
          ← Back to Home
        </button>

        <div className="bg-white rounded-3xl shadow-xl border border-green-100 overflow-hidden">
          <div className="bg-gradient-to-r from-green-700 to-emerald-600 px-8 py-10 text-white">
            <div className="inline-flex items-center gap-2 bg-white/15 px-3 py-1 rounded-full text-sm font-semibold mb-4">
              <UserRound size={16} />
              Villager Onboarding
            </div>
            <h1 className="text-4xl font-bold mb-3">Set up your reporting profile</h1>
            <p className="text-green-50 max-w-2xl">
              Save your contact details once, then report problems with photos, audio, or text and keep every case tied to a persistent village identity.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-6">
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
                {error}
              </div>
            )}

            <div className="grid md:grid-cols-2 gap-4">
              <label className="space-y-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <UserRound size={16} className="text-green-600" />
                  Full Name
                </span>
                <input
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none"
                  placeholder="Enter your name"
                />
              </label>

              <label className="space-y-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <Phone size={16} className="text-green-600" />
                  Phone Number
                </span>
                <input
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="w-full rounded-xl border border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none"
                  placeholder="Optional"
                />
              </label>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <label className="space-y-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <Mail size={16} className="text-green-600" />
                  Email Address
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-xl border border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none"
                  placeholder="Optional"
                />
              </label>

              <label className="space-y-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <MapPin size={16} className="text-green-600" />
                  Village Name
                </span>
                <input
                  value={villageName}
                  onChange={(event) => setVillageName(event.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none"
                  placeholder="Where are you reporting from?"
                />
              </label>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-600 px-5 py-3 font-semibold text-white hover:bg-green-700 disabled:opacity-60"
              >
                {saving ? 'Saving profile...' : 'Save and continue'}
                <ArrowRight size={18} />
              </button>
              <button
                type="button"
                onClick={() => navigate('/submit')}
                className="rounded-xl border border-green-200 bg-green-50 px-5 py-3 font-semibold text-green-700 hover:bg-green-100"
              >
                Skip for now
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
