import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { LoadingState } from '../ui/LoadingState';

export function ProtectedRoute() {
  const { user, profile, loading } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingState label="Validando sessao..." />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (profile?.onboardingCompleted === false && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
