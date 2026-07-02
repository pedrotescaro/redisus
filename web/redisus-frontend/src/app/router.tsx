import { createBrowserRouter, Navigate } from 'react-router-dom';

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
import HomePage from '../features/home/HomePage';
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
import ReferenciasPage from './referencias/page';

const localAnalyzerMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';

export const router = createBrowserRouter(
  [
    {
      element: <App />,
      children: [
        { index: true, element: <HomePage /> },
        { path: '/referencias', element: <ReferenciasPage /> },
        { path: '/login', element: <LoginPage /> },
        { path: '/register', element: <RegisterPage /> },
        { path: '/forgot-password', element: <ForgotPasswordPage /> },
        ...(localAnalyzerMode ? [{ path: '/analyzer', element: <StandaloneAnalyzerPage /> }] : []),
        {
          element: <ProtectedRoute />,
          children: [
            { path: '/onboarding', element: <OnboardingPage /> },
            { path: '/chat', element: <ChatPage /> },
            ...(!localAnalyzerMode ? [{ path: '/analyzer', element: <AnalyzerPage /> }] : []),
            {
              element: <AppShell />,
              children: [
                { path: '/dashboard', element: <DashboardPage /> },
                { path: '/patients', element: <PatientsPage /> },
                { path: '/patients/:patientId', element: <PatientDetailsPage /> },
                { path: '/evaluations/new', element: <EvaluationPage /> },
                { path: '/agenda', element: <AgendaPage /> },
                { path: '/reports', element: <ReportsPage /> },
                { path: '/reports/compare', element: <CompareReportsPage /> },
                { path: '/profile', element: <ProfilePage /> },
                { path: '/profile/edit', element: <EditProfilePage /> },
                { path: '/settings', element: <SettingsPage /> },
                { path: '/notifications', element: <NotificationsPage /> },
                { path: '/privacy', element: <PrivacyPage /> },
                { path: '/about', element: <AboutPage /> }
              ]
            }
          ]
        },
        { path: '*', element: <Navigate to="/dashboard" replace /> }
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
