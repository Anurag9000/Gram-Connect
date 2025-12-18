import { Home, FileText, UserPlus, LayoutDashboard, LogOut, LogIn } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useEffect } from 'react';

// Declare the google global object for TypeScript
declare global {
  interface Window {
    google: any;
    googleTranslateElementInit: () => void;
  }
}

interface NavigationProps {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export default function Navigation({ currentPage, onNavigate }: NavigationProps) {
  const { profile, signOut } = useAuth();

  const handleSignOut = async () => {
    await signOut();
    onNavigate('home');
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
        new window.google.translate.TranslateElement(
          { 
            pageLanguage: 'en', 
            layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE,
            includedLanguages: 'en,hi,bn,ta,te,mr,pa,gu,kn'
          },
          'google_translate_element'
        );
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
        if (body.style.top !== '0px') {
          body.style.top = '0px';
          body.style.position = 'relative'; 
        }
      } else {
         if (body.style.top !== '' && body.style.top !== '0px') {
            body.style.top = '0px';
            body.style.position = 'relative';
         }
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
          <div className="flex items-center space-x-2">
            <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
              <span className="text-green-600 font-bold text-xl">G</span>
            </div>
            <h1 className="text-xl font-bold">Gram-Connect</h1>
          </div>

          <div className="flex space-x-1 md:space-x-2 items-center">
            <button
              onClick={() => onNavigate('home')}
              className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${
                currentPage === 'home' ? 'bg-green-700' : 'hover:bg-green-700'
              }`}
            >
              <Home size={20} />
              <span className="hidden sm:inline">Home</span>
            </button>

            {profile?.role === 'coordinator' && (
              <button
                onClick={() => onNavigate('submit')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${
                  currentPage === 'submit' ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
              >
                <FileText size={20} />
                <span className="hidden sm:inline">New Problem</span>
              </button>
            )}

            {profile?.role === 'volunteer' && (
              <button
                onClick={() => onNavigate('profile')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${
                  currentPage === 'profile' ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
              >
                <UserPlus size={20} />
                <span className="hidden sm:inline">Profile</span>
              </button>
            )}

            {profile?.role === 'coordinator' && (
              <button
                onClick={() => onNavigate('dashboard')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${
                  currentPage === 'dashboard' ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
              >
                <LayoutDashboard size={20} />
                <span className="hidden sm:inline">Dashboard</span>
              </button>
            )}

            {profile ? (
              <button
                onClick={handleSignOut}
                className="flex items-center space-x-1 px-3 py-2 rounded-lg hover:bg-green-700 transition"
              >
                <LogOut size={20} />
                <span className="hidden sm:inline">Logout</span>
              </button>
            ) : (
              // --- UPDATED: This button now navigates to 'home' ---
              <button
                onClick={() => onNavigate('home')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-lg transition ${
                  // It's "active" if we are on the home page (where the panels are)
                  currentPage === 'home' ? 'bg-green-700' : 'hover:bg-green-700'
                }`}
              >
                <LogIn size={20} />
                <span className="hidden sm:inline">Login</span>
              </button>
            )}

            <div id="google_translate_element" className="ml-2"></div>

          </div>
        </div>
      </div>
    </nav>
  );
}