import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './contexts/auth-shared';
import Navigation from './components/Navigation';
import AppErrorBoundary from './components/AppErrorBoundary';

const Home = lazy(() => import('./pages/Home'));
const SubmitProblem = lazy(() => import('./pages/SubmitProblem'));
const VillagerOnboarding = lazy(() => import('./pages/VillagerOnboarding'));
const MapView = lazy(() => import('./pages/MapView'));
const VolunteerProfile = lazy(() => import('./pages/VolunteerProfile'));
const CoordinatorDashboard = lazy(() => import('./pages/CoordinatorDashboard'));
const VolunteerLogin = lazy(() => import('./pages/VolunteerLogin'));
const CoordinatorLogin = lazy(() => import('./pages/CoordinatorLogin'));
const VolunteerDashboard = lazy(() => import('./pages/VolunteerDashboard'));

function AppContent() {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-green-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <AppErrorBoundary>
        <div className="min-h-screen bg-gray-50">
          <Navigation />
          <Suspense
            fallback={
              <div className="min-h-[70vh] flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <div className="mx-auto mb-4 h-14 w-14 animate-spin rounded-full border-4 border-green-200 border-t-green-600" />
                  <p className="text-sm font-medium text-gray-600">Loading Gram Connect...</p>
                </div>
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/villager-onboarding" element={<VillagerOnboarding />} />
              <Route path="/submit" element={<SubmitProblem />} />
              <Route path="/map" element={<MapView />} />
              <Route path="/profile" element={<VolunteerProfile />} />
              <Route path="/dashboard" element={<CoordinatorDashboard />} />
              <Route path="/volunteer-login" element={<VolunteerLogin />} />
              <Route path="/coordinator-login" element={<CoordinatorLogin />} />
              <Route path="/volunteer-dashboard" element={<VolunteerDashboard />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </div>
      </AppErrorBoundary>
    </Router>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
