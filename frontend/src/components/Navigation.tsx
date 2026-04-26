import { Home, FileText, UserPlus, LayoutDashboard, LogOut, LogIn, MapPinned } from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import { useNavigate, useLocation } from 'react-router-dom';
import LanguageToggle from './LanguageToggle';
import { useTranslation } from 'react-i18next';

export default function Navigation() {
  const { profile, signOut } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentPage = location.pathname;

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  const isActive = (path: string) => {
    if (path === '/' && currentPage === '/') return true;
    if (path !== '/' && currentPage.startsWith(path)) return true;
    return false;
  };

  return (
    <nav className="bg-green-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-2 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
              <span className="text-green-600 font-bold text-xl">G</span>
            </div>
            <h1 className="text-xl font-bold">{t('nav.brand')}</h1>
          </div>

          <div className="flex space-x-1 md:space-x-2 items-center">
            <button
              onClick={() => navigate('/')}
              className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/') ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
            >
              <Home size={20} />
              <span className="hidden sm:inline">{t('nav.home')}</span>
            </button>

            {profile?.role === 'coordinator' && (
              <button
                onClick={() => navigate('/submit')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/submit') ? 'bg-green-700' : 'hover:bg-green-700'
                  }`}
              >
                <FileText size={20} />
                <span className="hidden sm:inline">{t('nav.new_problem')}</span>
              </button>
            )}

            {(!profile || profile.role === 'villager') && (
              <button
                onClick={() => navigate('/villager-onboarding')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/villager-onboarding') ? 'bg-green-700' : 'hover:bg-green-700'
                  }`}
              >
                <UserPlus size={20} />
                <span className="hidden sm:inline">{t('nav.report_issue')}</span>
              </button>
            )}

            {profile?.role === 'volunteer' && (
              <>
                <button
                  onClick={() => navigate('/volunteer-dashboard')}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/volunteer-dashboard') ? 'bg-green-700' : 'hover:bg-green-700'
                    }`}
                >
                  <LayoutDashboard size={20} />
                  <span className="hidden sm:inline">{t('nav.my_tasks')}</span>
                </button>
                <button
                  onClick={() => navigate('/profile')}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/profile') ? 'bg-green-700' : 'hover:bg-green-700'
                    }`}
                  >
                  <UserPlus size={20} />
                  <span className="hidden sm:inline">{t('nav.profile')}</span>
                </button>
              </>
            )}

            {profile?.role === 'coordinator' && (
              <button
                onClick={() => navigate('/dashboard')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/dashboard') ? 'bg-green-700' : 'hover:bg-green-700'
                  }`}
              >
                <LayoutDashboard size={20} />
                <span className="hidden sm:inline">{t('nav.dashboard')}</span>
              </button>
            )}

            <button
              onClick={() => navigate('/map')}
              className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/map') ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
            >
              <MapPinned size={20} />
              <span className="hidden sm:inline">{t('nav.map')}</span>
            </button>

            {profile ? (
              <button
                onClick={handleSignOut}
                className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-red-600 hover:bg-red-700 transition"
              >
                <LogOut size={20} />
                <span className="hidden sm:inline">{t('nav.logout')}</span>
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => navigate('/volunteer-login')}
                  className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition border border-white/20"
                >
                  <LogIn size={20} />
                  <span className="hidden sm:inline">{t('nav.volunteer')}</span>
                </button>
                <button
                  onClick={() => navigate('/coordinator-login')}
                  className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-green-700 hover:bg-green-800 transition shadow-sm"
                >
                  <LogIn size={20} />
                  <span className="hidden sm:inline">{t('nav.coordinator')}</span>
                </button>
              </div>
            )}

            <div className="ml-2">
              <LanguageToggle />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
