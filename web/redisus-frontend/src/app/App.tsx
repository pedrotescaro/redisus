import { Outlet, useLocation } from 'react-router-dom';

import { FirebaseConfigError } from '../components/layout/FirebaseConfigError';
import { isFirebaseConfigured } from '../lib/firebase';

export function App() {
  const location = useLocation();
  const localAnalyzerMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';
  const standaloneAnalyzer = localAnalyzerMode && location.pathname === '/analyzer';
  const publicRoute = ['/', '/referencias', '/login', '/register', '/forgot-password'].includes(location.pathname);

  if (!isFirebaseConfigured && !standaloneAnalyzer && !publicRoute) return <FirebaseConfigError />;
  return <Outlet />;
}
