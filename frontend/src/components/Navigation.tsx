import { Home, FileText, UserPlus, LayoutDashboard, LogOut, LogIn } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

// Declare the google global object for TypeScript
declare global {
  interface Window {
    google: any;
    googleTranslateElementInit: () => void;
  }
}

export default function Navigation() {
  const { profile, signOut } = useAuth();
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

  // (The Google Translate useEffect remains unchanged)
  useEffect(() => {
    if (!document.getElementById('google-translate-script')) {
      const script = document.createElement('script');
      script.type = 'text/javascript';
      script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
      script.async = true;
      script.id = 'google-translate-script';
      document.body.appendChild(script);

      window.googleTranslateElementInit = () => {
        if (window.google && window.google.translate) {
          new window.google.translate.TranslateElement(
            {
              pageLanguage: 'en',
              layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE,
              includedLanguages: 'en,hi,bn,ta,te,mr,pa,gu,kn'
            },
            'google_translate_element'
          );
        }
      };
    } else {
      if (window.google && window.google.translate && window.googleTranslateElementInit) {
        window.googleTranslateElementInit();
      }
    }

    const intervalId = setInterval(() => {
      const banner = document.querySelector('.goog-te-banner-frame') as HTMLElement;
      const body = document.body;

      if (banner) {
        banner.style.display = 'none';
        banner.style.visibility = 'hidden';
      }
      if (body.style.top !== '0px') {
        body.style.top = '0px';
      }
    }, 100);

    return () => {
      clearInterval(intervalId);
    };
  }, []);

  return (
    <nav className="bg-green-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-2 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
              <span className="text-green-600 font-bold text-xl">S</span>
            </div>
            <h1 className="text-xl font-bold">SocialCode</h1>
          </div>

          <div className="flex space-x-1 md:space-x-2 items-center">
            <button
              onClick={() => navigate('/')}
              className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/') ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
            >
              <Home size={20} />
              <span className="hidden sm:inline">Home</span>
            </button>

            {profile?.role === 'coordinator' && (
              <button
                onClick={() => navigate('/submit')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/submit') ? 'bg-green-700' : 'hover:bg-green-700'
                  }`}
              >
                <FileText size={20} />
                <span className="hidden sm:inline">New Problem</span>
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
                  <span className="hidden sm:inline">My Tasks</span>
                </button>
                <button
                  onClick={() => navigate('/profile')}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${isActive('/profile') ? 'bg-green-700' : 'hover:bg-green-700'
                    }`}
                >
                  <UserPlus size={20} />
                  <span className="hidden sm:inline">Profile</span>
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
                <span className="hidden sm:inline">Dashboard</span>
              </button>
            )}

            {profile ? (
              <button
                onClick={handleSignOut}
                className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-red-600 hover:bg-red-700 transition"
              >
                <LogOut size={20} />
                <span className="hidden sm:inline">Logout</span>
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => navigate('/volunteer-login')}
                  className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition border border-white/20"
                >
                  <LogIn size={20} />
                  <span className="hidden sm:inline">Volunteer</span>
                </button>
                <button
                  onClick={() => navigate('/coordinator-login')}
                  className="flex items-center space-x-1 px-3 py-2 rounded-lg bg-green-700 hover:bg-green-800 transition shadow-sm"
                >
                  <LogIn size={20} />
                  <span className="hidden sm:inline">Coordinator</span>
                </button>
              </div>
            )}

            <div id="google_translate_element" className="ml-2"></div>
          </div>
        </div>
      </div>
    </nav>
  );
}