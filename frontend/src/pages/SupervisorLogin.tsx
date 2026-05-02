import { useState } from 'react';
import { useAuth } from '../contexts/auth-shared';
import { Briefcase } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function SupervisorLogin() {
  const { signIn } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState('supervisor@test.com');
  const [password, setPassword] = useState('password');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (email !== 'supervisor@test.com') {
        throw new Error(`Invalid email for supervisor. Use 'supervisor@test.com'`);
      }
      const { error } = await signIn(email, password);
      if (error) throw error;
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-amber-50 to-white px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
        <button onClick={() => navigate('/')} className="mb-4 flex items-center text-amber-600 hover:text-amber-700">
          {t('auth.back_to_home')}
        </button>
        <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-amber-100">
          <Briefcase className="text-amber-600" size={40} />
        </div>
        <h2 className="mb-6 text-center text-3xl font-bold text-amber-700">{t('auth.coordinator_login')}</h2>
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t('auth.email')}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="supervisor@test.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t('auth.password')}</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="password"
            />
          </div>
          <button type="submit" disabled={loading} className="w-full rounded-lg bg-amber-600 py-3 font-semibold text-white transition hover:bg-amber-700 disabled:bg-gray-400">
            {loading ? t('common.loading') : 'Sign in as supervisor'}
          </button>
        </form>
      </div>
    </div>
  );
}
