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

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

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
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/submit" element={<SubmitProblem />} />
          <Route path="/profile" element={<VolunteerProfile />} />
          <Route path="/dashboard" element={<CoordinatorDashboard />} />
          <Route path="/volunteer-login" element={<VolunteerLogin />} />
          <Route path="/coordinator-login" element={<CoordinatorLogin />} />
          <Route path="/volunteer-dashboard" element={<VolunteerDashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
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