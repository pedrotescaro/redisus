import { createBrowserRouter } from 'react-router-dom';

import { AppShell } from '../components/layout/AppShell';
import { ProtectedRoute } from '../components/layout/ProtectedRoute';
import { AgendaPage } from '../features/agenda/AgendaPage';
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage';
import { LoginPage } from '../features/auth/LoginPage';
import { OnboardingPage } from '../features/auth/OnboardingPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { AnalyzerPage, StandaloneAnalyzerPage } from '../features/analyzer/AnalyzerPage';
import { ChatPage } from '../features/chat/ChatPage';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { EvaluationPage } from '../features/evaluations/EvaluationPage';
import { PatientDetailsPage } from '../features/patients/PatientDetailsPage';
import { PatientsPage } from '../features/patients/PatientsPage';
import { EditProfilePage } from '../features/profile/EditProfilePage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { CompareReportsPage } from '../features/reports/CompareReportsPage';
import { ReportsPage } from '../features/reports/ReportsPage';
import { AboutPage } from '../features/settings/AboutPage';
import { NotificationsPage } from '../features/settings/NotificationsPage';
import { PrivacyPage } from '../features/settings/PrivacyPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import { App } from './App';

const localAnalyzerMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';

export const router = createBrowserRouter(
  [
    {
      element: <App />,
      children: [
        { path: '/login', element: <LoginPage /> },
        { path: '/register', element: <RegisterPage /> },
        { path: '/forgot-password', element: <ForgotPasswordPage /> },
        ...(localAnalyzerMode ? [{ path: '/analyzer', element: <StandaloneAnalyzerPage /> }] : []),
        {
          element: <ProtectedRoute />,
          children: [
            { path: '/onboarding', element: <OnboardingPage /> },
            {
              element: <AppShell />,
              children: [
                { index: true, element: <DashboardPage /> },
                { path: '/patients', element: <PatientsPage /> },
                { path: '/patients/:patientId', element: <PatientDetailsPage /> },
                { path: '/evaluations/new', element: <EvaluationPage /> },
                { path: '/agenda', element: <AgendaPage /> },
                { path: '/reports', element: <ReportsPage /> },
                { path: '/reports/compare', element: <CompareReportsPage /> },
                ...(!localAnalyzerMode ? [{ path: '/analyzer', element: <AnalyzerPage /> }] : []),
                { path: '/profile', element: <ProfilePage /> },
                { path: '/profile/edit', element: <EditProfilePage /> },
                { path: '/settings', element: <SettingsPage /> },
                { path: '/notifications', element: <NotificationsPage /> },
                { path: '/privacy', element: <PrivacyPage /> },
                { path: '/about', element: <AboutPage /> },
                { path: '/chat', element: <ChatPage /> }
              ]
            }
          ]
        }
      ]
    }
  ],
  {
    future: {
      v7_startTransition: true,
      v7_relativeSplatPath: true
    } as never
  }
);
