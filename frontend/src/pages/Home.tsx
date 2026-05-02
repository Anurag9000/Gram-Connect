import { ArrowRight, Zap, MessageSquare, Map, Users, Briefcase, ClipboardList, LayoutDashboard, Settings2 } from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

export default function Home() {
  const { profile } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (profile) {
    const dashboardCard = (title: string, description: string, buttonLabel: string, onClick: () => void, accentClass: string, icon: JSX.Element) => (
      <div
        className="rounded-2xl border border-gray-100 bg-white p-8 shadow-sm transition hover:shadow-md"
        onClick={onClick}
      >
        <div className={`mb-6 flex h-12 w-12 items-center justify-center rounded-xl ${accentClass}`}>
          {icon}
        </div>
        <h2 className="mb-4 text-2xl font-bold text-gray-900">{title}</h2>
        <p className="mb-6 text-gray-600">{description}</p>
        <div className={`flex items-center font-semibold ${accentClass.replace('bg-', 'text-').replace('100', '600')}`}>
          {buttonLabel} <ArrowRight className="ml-2" size={20} />
        </div>
      </div>
    );

    const loggedInView = () => {
      switch (profile.role) {
        case 'coordinator':
          return (
            <>
              {dashboardCard(
                t('home.dashboard_title'),
                t('home.dashboard_desc'),
                t('common.go_to_dashboard'),
                () => navigate('/dashboard'),
                'bg-green-100',
                <Zap className="text-green-600" size={24} />
              )}
              {dashboardCard(
                t('home.submit_title'),
                t('home.submit_desc'),
                t('common.submit_problem'),
                () => navigate('/submit'),
                'bg-blue-100',
                <MessageSquare className="text-blue-600" size={24} />
              )}
              {dashboardCard(
                t('home.live_map_view'),
                t('home.live_map_desc'),
                t('common.open_map'),
                () => navigate('/map'),
                'bg-purple-100',
                <Map className="text-purple-600" size={24} />
              )}
              {dashboardCard(
                'Platform studio',
                'Manage asset lifecycle, procurement, trust checks, and platform exports.',
                'Open studio',
                () => navigate('/platform-studio'),
                'bg-slate-100',
                <Settings2 className="text-slate-700" size={24} />
              )}
            </>
          );
        case 'volunteer':
          return (
            <>
              {dashboardCard(
                t('home.volunteer_portal'),
                t('home.volunteer_desc'),
                t('common.go_to_tasks'),
                () => navigate('/volunteer-dashboard'),
                'bg-green-100',
                <Users className="text-green-600" size={24} />
              )}
              {dashboardCard(
                'Repair assistant',
                'Open the photo-based Jugaad assistant for temporary field fixes.',
                'Open repair assistant',
                () => navigate('/volunteer-dashboard'),
                'bg-amber-100',
                <MessageSquare className="text-amber-600" size={24} />
              )}
            </>
          );
        case 'supervisor':
          return (
            <>
              {dashboardCard(
                'Supervisor dashboard',
                'Review escalations, seasonal risk, maintenance reminders, and campaign activity.',
                'Open supervisor view',
                () => navigate('/supervisor-dashboard'),
                'bg-amber-100',
                <LayoutDashboard className="text-amber-600" size={24} />
              )}
              {dashboardCard(
                'Public status board',
                'Check what residents can currently see before program reviews.',
                'Open status board',
                () => navigate('/status'),
                'bg-sky-100',
                <ClipboardList className="text-sky-600" size={24} />
              )}
              {dashboardCard(
                'Platform studio',
                'Manage assets, procurement, confirmations, community signals, and exports.',
                'Open studio',
                () => navigate('/platform-studio'),
                'bg-slate-100',
                <Settings2 className="text-slate-700" size={24} />
              )}
            </>
          );
        case 'partner':
          return (
            <>
              {dashboardCard(
                'Partner dashboard',
                'Track the weekly briefing, public accountability, and early warning signals.',
                'Open partner view',
                () => navigate('/partner-dashboard'),
                'bg-emerald-100',
                <Briefcase className="text-emerald-600" size={24} />
              )}
              {dashboardCard(
                'Public status board',
                'Review the resident-facing problem snapshot and completion mix.',
                'Open status board',
                () => navigate('/status'),
                'bg-sky-100',
                <ClipboardList className="text-sky-600" size={24} />
              )}
              {dashboardCard(
                'Platform studio',
                'Manage operational records, confirmations, analytics, and admin exports.',
                'Open studio',
                () => navigate('/platform-studio'),
                'bg-slate-100',
                <Settings2 className="text-slate-700" size={24} />
              )}
            </>
          );
        default:
          return (
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition cursor-pointer" onClick={() => navigate('/volunteer-dashboard')}>
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6">
                <Users className="text-green-600" size={24} />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-4">{t('home.volunteer_portal')}</h2>
              <p className="text-gray-600 mb-6">{t('home.volunteer_desc')}</p>
              <div className="flex items-center text-green-600 font-semibold">
                {t('common.go_to_tasks')} <ArrowRight className="ml-2" size={20} />
              </div>
            </div>
          );
      }
    };

    return (
      <div className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900">
              {t('home.welcome_back')} <span className="text-green-600">{t('seed.' + profile.full_name, profile.full_name)}</span>
            </h1>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {loggedInView()}
          </div>
        </div>
      </div>
    );
  }

  // Hero section for non-logged in users
  return (
    <div className="min-h-screen bg-white pt-16">


      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center space-x-2 bg-green-50 text-green-700 px-4 py-2 rounded-full mb-8 animate-fade-in">
            <Zap size={16} />
            <span className="text-sm font-bold uppercase tracking-wider">{t('home.ai_powered_label')}</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold text-gray-900 mb-8 tracking-tight">
            {t('home.hero_heading')} <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-emerald-600">
              {t('home.hero_heading_highlight', 'Intelligent Action')}
            </span>
          </h1>
          <p className="text-xl text-gray-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            {t('home.hero_body')}
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <button
              onClick={() => navigate('/volunteer-login')}
              className="bg-gray-900 text-white px-8 py-4 rounded-full font-bold text-lg hover:bg-gray-800 transition flex items-center group"
            >
              {t('home.start_volunteering')}
              <ArrowRight className="ml-2 group-hover:translate-x-1 transition" size={20} />
            </button>
            <button
              onClick={() => navigate('/villager-onboarding')}
              className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-green-600 hover:text-green-600 transition"
            >
              {t('home.report_problem')}
            </button>
            <button
              onClick={() => navigate('/map')}
              className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-green-600 hover:text-green-600 transition"
            >
              {t('home.explore_projects')}
            </button>
            <button
              onClick={() => navigate('/supervisor-login')}
              className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-amber-600 hover:text-amber-600 transition"
            >
              Supervisor access
            </button>
            <button
              onClick={() => navigate('/partner-login')}
              className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-emerald-600 hover:text-emerald-600 transition"
            >
              Partner access
            </button>
            <button
              onClick={() => navigate('/status')}
              className="bg-white text-gray-900 border-2 border-gray-200 px-8 py-4 rounded-full font-bold text-lg hover:border-green-600 hover:text-green-600 transition"
            >
              Public status board
            </button>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">{t('home.features_heading')}</h2>
            <p className="text-gray-600">{t('home.features_subheading')}</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6">
                <MessageSquare className="text-green-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">{t('home.feature_multimodal_title')}</h3>
              <p className="text-gray-600 leading-relaxed">{t('home.feature_multimodal_desc')}</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-6">
                <Zap className="text-blue-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">{t('home.feature_matching_title')}</h3>
              <p className="text-gray-600 leading-relaxed">{t('home.feature_matching_desc')}</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition border border-gray-100">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mb-6">
                <Map className="text-purple-600" size={24} />
              </div>
              <h3 className="text-xl font-bold mb-4">{t('home.feature_map_title')}</h3>
              <p className="text-gray-600 leading-relaxed">{t('home.feature_map_desc')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 bg-green-600">
        <div className="max-w-7xl mx-auto px-4 grid md:grid-cols-3 gap-12 text-center text-white">
          <div>
            <div className="text-5xl font-extrabold mb-2">50+</div>
            <div className="text-green-100 font-medium">{t('home.stat_villages')}</div>
          </div>
          <div>
            <div className="text-5xl font-extrabold mb-2">1.2k</div>
            <div className="text-green-100 font-medium">{t('home.stat_hours')}</div>
          </div>
          <div>
            <div className="text-5xl font-extrabold mb-2">98%</div>
            <div className="text-green-100 font-medium">{t('home.stat_resolution')}</div>
          </div>
        </div>
      </section>
    </div>
  );
}
