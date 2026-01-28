import { useState } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Navigation from './components/Navigation';
import Home from './pages/Home';
import SubmitProblem from './pages/SubmitProblem';
import VolunteerProfile from './pages/VolunteerProfile';
import CoordinatorDashboard from './pages/CoordinatorDashboard';
import VolunteerLogin from './pages/VolunteerLogin';
import CoordinatorLogin from './pages/CoordinatorLogin';
import VolunteerDashboard from './pages/VolunteerDashboard';

function AppContent() {
  const { loading } = useAuth();
  const [currentPage, setCurrentPage] = useState('home');

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
    <div className="min-h-screen bg-gray-50">
      <Navigation currentPage={currentPage} onNavigate={setCurrentPage} />

      {currentPage === 'home' && <Home onNavigate={setCurrentPage} />}
      {currentPage === 'submit' && <SubmitProblem onNavigate={setCurrentPage} />}
      {currentPage === 'profile' && <VolunteerProfile onNavigate={setCurrentPage} />}
      {currentPage === 'dashboard' && <CoordinatorDashboard onNavigate={setCurrentPage} />}
      {currentPage === 'volunteer-login' && <VolunteerLogin onNavigate={setCurrentPage} />}
      {currentPage === 'coordinator-login' && <CoordinatorLogin onNavigate={setCurrentPage} />}
      {currentPage === 'volunteer-dashboard' && <VolunteerDashboard onNavigate={setCurrentPage} />}
    </div>
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