import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/toaster';

// contexts
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProfileProvider } from './context/ProfileContext';

// utils
import { setStreamSessionExpiredHandler } from './lib/api/streamUtils';

// components
import TopBar from './components/TopBar';
import { LoginForm } from './components/features/auth';

// pages
import MainPage from './pages/MainPage';
import Profile from './pages/Profile';
import TokenLogin from './pages/TokenLogin';

// Inner component that uses auth context
function AppContent() {
  const { handleSessionExpired, isAuthenticated } = useAuth();

  // Set up session expiry handler
  useEffect(() => {
    setStreamSessionExpiredHandler(handleSessionExpired);
    return () => setStreamSessionExpiredHandler(() => { });
  }, [handleSessionExpired]);

  // Main app content when authenticated
  const AuthenticatedApp = () => {
    return (
      <div className="h-screen flex flex-col dark:bg-gray-900 bg-gray-50">
        <TopBar />
        <main className="flex-1 overflow-hidden pt-16">
          <Routes>
            <Route path="/" element={<MainPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/settings" element={<Navigate to="/profile" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    );
  };

  if (!isAuthenticated) {
    return (
      <ThemeProvider>
        <Routes>
          <Route path="/auth/token-login" element={<TokenLogin />} />
          <Route path="*" element={
            <div className="min-h-screen flex items-center justify-center dark:bg-gray-900 bg-gray-50">
              <LoginForm />
            </div>
          } />
        </Routes>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <ProfileProvider>
        <AuthenticatedApp />
      </ProfileProvider>
      <Toaster />
    </ThemeProvider>
  );
}

// Main App component that provides contexts
function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true
      }}
    >
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
