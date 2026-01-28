import { ArrowRight, Zap, Globe, MessageSquare, Map, Users } from 'lucide-react';
import LanguageToggle from '../components/LanguageToggle';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

export default function Home() {
  const { profile } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Show this view if a user (Volunteer or Coordinator) is logged in
  if (profile) {
    return (
      <div className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900">
              Welcome back, <span className="text-green-600">{profile.full_name}</span>
            </h1>
            <LanguageToggle />
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {profile.role === 'coordinator' ? (
              <>
                <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition cursor-pointer" onClick={() => navigate('/dashboard')}>
                  <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6">
                    <Zap className="text-green-600" size={24} />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">{t('home.dashboard_title')}</h2>
                  <p className="text-gray-600 mb-6">{t('home.dashboard_desc')}</p>
                  <div className="flex items-center text-green-600 font-semibold">
                    {t('common.go_to_dashboard')} <ArrowRight className="ml-2" size={20} />
                  </div>
                </div>

                <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition cursor-pointer" onClick={() => navigate('/submit')}>
                  <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-6">
                    <MessageSquare className="text-blue-600" size={24} />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">{t('home.submit_title')}</h2>
                  <p className="text-gray-600 mb-6">{t('home.submit_desc')}</p>
                  <div className="flex items-center text-blue-600 font-semibold">
                    {t('common.submit_problem')} <ArrowRight className="ml-2" size={20} />
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition cursor-pointer" onClick={() => navigate('/volunteer-dashboard')}>
                <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6">
                  <Users className="text-green-600" size={24} />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Volunteer Portal</h2>
                <p className="text-gray-600 mb-6">View your assignments, track your impact, and submit "Before & After" proof for completed tasks.</p>
                <div className="flex items-center text-green-600 font-semibold">
                  Go to Tasks <ArrowRight className="ml-2" size={20} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Hero section for non-logged in users
  return (
    <div className="min-h-screen bg-white pt-16">
      {/* Navigation */}
      <nav className="fixed w-full bg-white/80 backdrop-blur-md z-50 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-2">
              <Globe className="text-green-600" size={32} />
              <span className="text-2xl font-bold text-gray-900 tracking-tight">SocialCode</span>
            </div>
            <div className="hidden md:flex items-center space-x-8">
              <a href="#features" className="text-gray-600 hover:text-green-600 transition">Features</a>
              <a href="#how-it-works" className="text-gray-600 hover:text-green-600 transition">How it Works</a>
              <LanguageToggle />
              <button
                onClick={() => navigate('/volunteer-login')}
                className="bg-green-600 text-white px-6 py-2 rounded-full font-semibold hover:bg-green-700 transition shadow-lg shadow-green-200"
              >
                Sign In
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center space-x-2 bg-green-50 text-green-700 px-4 py-2 rounded-full mb-8 animate-fade-in">
            <Zap size={16} />
            <span className="text-sm font-bold uppercase tracking-wider">AI-Powered Social Impact</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold text-gray-900 mb-8 tracking-tight">
            Bridging Villages with <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-emerald-600">
              Intelligent Action
            </span>
          </h1>
          <p className="text-xl text-gray-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            SocialCode uses multimodal AI to match student volunteers with critical village needs,
            ensuring expertise goes exactly where it's needed most.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <button
              onClick={() => navigate('/volunteer-login')}
              className="bg-gray-900 text-white px-8 py-4 rounded-full font-bold text-lg hover:bg-gray-800 transition flex items-center group"
            >
              Start Volunteering
              <ArrowRight className="ml-2 group-hover:translate-x-1 transition" size={20} />
            </button>
            <button className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-green-600 hover:text-green-600 transition">
              Explore Projects
            </button>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Empowering Communities</h2>
            <p className="text-gray-600">Next-generation tools for grassroots development.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6">
                <MessageSquare className="text-green-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">Multimodal AI</h3>
              <p className="text-gray-600 leading-relaxed">Villagers can report problems using audio, photos, or text in their local language.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-6">
                <Zap className="text-blue-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">Smart Matching</h3>
              <p className="text-gray-600 leading-relaxed">Our M3 Recommender finds the perfect team based on skills, logistics, and fairness.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mb-6">
                <Map className="text-purple-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">Geo-Spatial Map</h3>
              <p className="text-gray-600 leading-relaxed">Coordinators visualize problems and volunteer deployments on an interactive map.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 bg-green-600">
        <div className="max-w-7xl mx-auto px-4 grid md:grid-cols-3 gap-12 text-center text-white">
          <div>
            <div className="text-5xl font-extrabold mb-2">50+</div>
            <div className="text-green-100 font-medium">Villages Empowered</div>
          </div>
          <div>
            <div className="text-5xl font-extrabold mb-2">1.2k</div>
            <div className="text-green-100 font-medium">Volunteer Hours</div>
          </div>
          <div>
            <div className="text-5xl font-extrabold mb-2">98%</div>
            <div className="text-green-100 font-medium">Resolution Rate</div>
          </div>
        </div>
      </section>
    </div>
  );
}